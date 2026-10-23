"""Outgoing communication: WhatsApp (Meta Cloud API), SMS (any HTTP gateway), e-mail (SMTP) and in-app notifications.

Everything goes through the `outbox` table: a call to `notify_members` writes one row per member per channel, and the
worker thread (or a test calling `process_outbox`) delivers them. A channel that is not configured marks its rows
`demo` instead of failing, so the whole app is usable - and visibly so - before any gateway account exists.

Environment:
  WhatsApp   CLUB_WA_TOKEN, CLUB_WA_PHONE_ID, optional CLUB_WA_TEMPLATE (an approved template with one {{1}} body
             parameter; without it a plain text message is sent, which WhatsApp delivers only inside a 24-hour
             customer-service window)
  SMS        CLUB_SMS_URL  - URL with {to} and {text} placeholders (GET), or
             CLUB_SMS_URL + CLUB_SMS_BODY (JSON template with {to}/{text}, POSTed) + CLUB_SMS_HEADERS (JSON)
             CLUB_SMS_SENDER, CLUB_SMS_DLT_TEMPLATE are substituted too ({sender}, {dlt}). Works with MSG91,
             Fast2SMS, Textlocal, Twilio-style and most Indian DLT gateways.
  E-mail     CLUB_SMTP_HOST, CLUB_SMTP_PORT (587 / 465), CLUB_SMTP_USER, CLUB_SMTP_PASS, CLUB_SMTP_FROM
"""
import json
import logging
import os
import re
import smtplib
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from email.message import EmailMessage

from . import db, i18n, tenancy

log = logging.getLogger("club.comms")
CHANNELS = ("whatsapp", "sms", "email", "app", "push")

# Tests and local runs can plug in a fake transport: sender(channel, to, subject, body) -> provider_id
_override_sender = None


def set_sender(fn):
    global _override_sender
    _override_sender = fn


# Each club may carry its own gateway credentials under Settings; a blank setting falls back to the server's .env.
ENV_SETTING = {"CLUB_WA_TOKEN": "wa_token", "CLUB_WA_PHONE_ID": "wa_phone_id", "CLUB_WA_TEMPLATE": "wa_template", "CLUB_WA_TEMPLATE_LANG": "wa_template_lang",
               "CLUB_SMS_URL": "sms_url", "CLUB_SMS_BODY": "sms_body", "CLUB_SMS_HEADERS": "sms_headers", "CLUB_SMS_KEY": "sms_key", "CLUB_SMS_SENDER": "sms_sender", "CLUB_SMS_DLT_TEMPLATE": "sms_dlt",
               "CLUB_SMTP_HOST": "smtp_host", "CLUB_SMTP_PORT": "smtp_port", "CLUB_SMTP_USER": "smtp_user", "CLUB_SMTP_PASS": "smtp_pass", "CLUB_SMTP_FROM": "smtp_from",
               "CLUB_RZP_KEY_ID": "rzp_key_id", "CLUB_RZP_KEY_SECRET": "rzp_key_secret", "CLUB_RZP_WEBHOOK_SECRET": "rzp_webhook_secret"}
SECRET_SETTINGS = ("wa_token", "sms_key", "sms_headers", "smtp_pass", "rzp_key_secret", "rzp_webhook_secret")


def cfg(env, default=""):
    """A gateway value: the club's own setting when filled in, else the environment."""
    key = ENV_SETTING.get(env)
    if key:
        v = (db.setting(key, "") or "").strip()
        if v:
            return v
    return os.environ.get(env) or default


def own_channels():
    """Which channels this club configured for itself (rather than inheriting the server's)."""
    s = db.settings_all()
    return {"whatsapp": bool(s["wa_token"] and s["wa_phone_id"]), "sms": bool(s["sms_url"]), "email": bool(s["smtp_host"] and s["smtp_from"]),
            "gateway": bool(s["rzp_key_id"] and s["rzp_key_secret"])}


def configured():
    return {
        "whatsapp": bool(cfg("CLUB_WA_TOKEN") and cfg("CLUB_WA_PHONE_ID")),
        "sms": bool(cfg("CLUB_SMS_URL")),
        "email": bool(cfg("CLUB_SMTP_HOST") and cfg("CLUB_SMTP_FROM")),
        "app": True,
        "push": True,
    }


def normalise_phone(p, default_cc="91"):
    """Digits only, with the country code in front: '98470 12345' -> '919847012345'."""
    d = re.sub(r"\D", "", p or "")
    if not d:
        return ""
    if d.startswith("00"):
        d = d[2:]
    if len(d) == 10:
        d = default_cc + d
    if len(d) == 11 and d.startswith("0"):
        d = default_cc + d[1:]
    return d


def wa_link(phone, text=""):
    d = normalise_phone(phone)
    if not d:
        return ""
    return f"https://wa.me/{d}" + (f"?text={urllib.parse.quote(text)}" if text else "")


def club_ctx():
    s = db.settings_all()
    return {"club": s["club_name_en"], "club_ml": s["club_name_ml"], "club_short": s["club_short"],
            "link": tenancy.base_url()}


def _ctx_for(lang, ctx):
    base = club_ctx()
    if lang == "ml":
        base["club"] = base["club_ml"] or base["club"]
    base.update(ctx)
    return base


def queue(c, channel, to_addr, subject, body, *, lang="en", member_id=None, template="", ref_kind="", ref_id=None, batch_id="", created_by=None, not_before=None):
    if channel == "app":
        if not member_id:
            return None
        nid = db.insert(c, "notifications", {"member_id": member_id, "created": time.time(), "title": subject[:200], "body": body,
                                             "link": ref_link(ref_kind, ref_id), "ref_kind": ref_kind, "ref_id": ref_id})
        # the same notification goes to the member's phone / browser by Web Push, when they have allowed it
        for sub in db.q("SELECT id FROM push_subs WHERE member_id=? AND failures<5", (member_id,)):
            db.insert(c, "outbox", {"created": time.time(), "channel": "push", "to_addr": f"sub:{sub['id']}", "subject": subject[:200], "body": body[:1000], "lang": lang, "status": "pending",
                                    "member_id": member_id, "template": template, "ref_kind": ref_kind, "ref_id": ref_id, "batch_id": batch_id, "created_by": created_by, "not_before": not_before})
        return nid
    if not to_addr:
        return None
    return db.insert(c, "outbox", {"created": time.time(), "channel": channel, "to_addr": to_addr, "subject": subject, "body": body, "lang": lang,
                                   "status": "pending", "member_id": member_id, "template": template, "ref_kind": ref_kind, "ref_id": ref_id,
                                   "batch_id": batch_id, "created_by": created_by, "not_before": not_before})


def ref_link(ref_kind, ref_id):
    if not ref_kind or not ref_id:
        return ""
    return {"post": f"#/posts/{ref_id}", "meeting": f"#/meetings/{ref_id}", "action": "#/actions", "issue": "#/library/mine",
            "member": "#/me", "receipt": "#/me/payments", "subscription": "#/me/payments"}.get(ref_kind, "")


def member_channels(m, requested):
    """Which of the requested channels this member actually gets, by consent and by having an address."""
    out = []
    for ch in requested:
        if ch == "whatsapp" and m.get("notify_whatsapp") and (m.get("whatsapp") or m.get("phone")):
            out.append(("whatsapp", normalise_phone(m.get("whatsapp") or m.get("phone"))))
        elif ch == "sms" and m.get("notify_sms") and m.get("phone"):
            out.append(("sms", normalise_phone(m["phone"])))
        elif ch == "email" and m.get("notify_email") and m.get("email"):
            out.append(("email", m["email"].strip()))
        elif ch == "app":
            out.append(("app", str(m["id"])))
    return out


def notify_members(c, member_ids, template, ctx, channels=("app", "whatsapp"), *, ref_kind="", ref_id=None, batch_id="", created_by=None, per_member=None, not_before=None):
    """Queue `template` for each member on each channel they accept. per_member(m) may add member-specific context.
    Returns the number of messages queued (app notifications included)."""
    if not member_ids:
        return 0
    marks = ",".join("?" for _ in member_ids)
    members = {r["id"]: r for r in db.q(f"SELECT * FROM members WHERE id IN ({marks})", list(member_ids))}
    n = 0
    for mid in member_ids:
        m = members.get(mid)
        if not m:
            continue
        lang = m.get("lang") or db.setting("default_lang")
        mctx = {"name": i18n.pick(m, "name", lang), "member_no": m.get("member_no") or ""}
        mctx.update(ctx)
        if per_member:
            mctx.update(per_member(m) or {})
        subject, body = i18n.render(template, lang, _ctx_for(lang, mctx))
        for ch, addr in member_channels(m, channels):
            if queue(c, ch, addr, subject, body, lang=lang, member_id=mid, template=template, ref_kind=ref_kind, ref_id=ref_id, batch_id=batch_id, created_by=created_by, not_before=not_before):
                n += 1
    return n


def notify_contact(c, phone, email, template, ctx, lang, channels=("whatsapp", "sms", "email"), **kw):
    """For people who are not members yet (an applicant)."""
    subject, body = i18n.render(template, lang, _ctx_for(lang, ctx))
    n = 0
    for ch in channels:
        addr = ""
        if ch in ("whatsapp", "sms"):
            addr = normalise_phone(phone)
        elif ch == "email":
            addr = (email or "").strip()
        if addr and queue(c, ch, addr, subject, body, lang=lang, template=template, **kw):
            n += 1
    return n


def new_batch():
    return uuid.uuid4().hex[:12]


# ---------- transports ----------
def _http(url, data=None, headers=None, method=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def send_whatsapp(to, body):
    token, phone_id = cfg("CLUB_WA_TOKEN"), cfg("CLUB_WA_PHONE_ID")
    version = os.environ.get("CLUB_WA_API_VERSION", "v20.0")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    template = cfg("CLUB_WA_TEMPLATE")
    if template:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "template",
                   "template": {"name": template, "language": {"code": cfg("CLUB_WA_TEMPLATE_LANG", "en")},
                                "components": [{"type": "body", "parameters": [{"type": "text", "text": body[:1024]}]}]}}
    else:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"preview_url": True, "body": body[:4096]}}
    status, text = _http(url, json.dumps(payload).encode(), {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, "POST")
    try:
        return json.loads(text)["messages"][0]["id"]
    except Exception:
        return text[:200]


def send_sms(to, body):
    url_t = cfg("CLUB_SMS_URL")
    subs = {"to": to, "text": body, "sender": cfg("CLUB_SMS_SENDER"), "dlt": cfg("CLUB_SMS_DLT_TEMPLATE"),
            "key": cfg("CLUB_SMS_KEY")}
    headers = json.loads(cfg("CLUB_SMS_HEADERS") or "{}")
    body_t = cfg("CLUB_SMS_BODY")
    if body_t:
        data = body_t
        for k, v in subs.items():
            data = data.replace("{" + k + "}", json.dumps(v)[1:-1])
        headers.setdefault("Content-Type", "application/json")
        url = url_t
        for k, v in subs.items():
            url = url.replace("{" + k + "}", urllib.parse.quote(v))
        status, text = _http(url, data.encode(), headers, "POST")
    else:
        url = url_t
        for k, v in subs.items():
            url = url.replace("{" + k + "}", urllib.parse.quote(v))
        status, text = _http(url, None, headers, "GET")
    return text[:200]


def send_email(to, subject, body):
    host, port = cfg("CLUB_SMTP_HOST"), int(cfg("CLUB_SMTP_PORT") or 587)
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg("CLUB_SMTP_FROM"), to, subject
    msg.set_content(body)
    ctx = ssl.create_default_context()
    s = smtplib.SMTP_SSL(host, port, timeout=20, context=ctx) if port == 465 else smtplib.SMTP(host, port, timeout=20)
    try:
        if port != 465:
            s.starttls(context=ctx)
        if cfg("CLUB_SMTP_USER"):
            s.login(cfg("CLUB_SMTP_USER"), cfg("CLUB_SMTP_PASS"))
        s.send_message(msg)
    finally:
        s.quit()
    return "smtp"


def deliver(row):
    """Send one outbox row. Returns (status, provider_id_or_error)."""
    ch = row["channel"]
    if _override_sender:
        return "sent", str(_override_sender(ch, row["to_addr"], row["subject"], row["body"]) or "")
    if not configured().get(ch):
        return "demo", "channel not configured"
    try:
        if ch == "whatsapp":
            return "sent", send_whatsapp(row["to_addr"], row["body"])
        if ch == "sms":
            return "sent", send_sms(row["to_addr"], row["body"])
        if ch == "email":
            return "sent", send_email(row["to_addr"], row["subject"] or db.setting("club_short"), row["body"])
        if ch == "push":
            from . import push
            sub = db.one("SELECT * FROM push_subs WHERE id=?", (int(row["to_addr"].split(":")[1]),))
            if not sub:
                return "failed", "subscription gone"
            ok, info = push.send(sub, row["subject"], row["body"], ref_link(row["ref_kind"], row["ref_id"]))
            with db.tx() as c:
                if ok:
                    c.execute("UPDATE push_subs SET last_ok=?, failures=0 WHERE id=?", (time.time(), sub["id"]))
                elif info in ("HTTP 404", "HTTP 410"):
                    c.execute("DELETE FROM push_subs WHERE id=?", (sub["id"],))
                else:
                    c.execute("UPDATE push_subs SET failures=failures+1 WHERE id=?", (sub["id"],))
            return ("sent", info) if ok else ("failed", info)
    except urllib.error.HTTPError as e:
        return "failed", f"HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}"
    except Exception as e:  # noqa: BLE001 - the error text is what the operator needs to see
        return "failed", f"{type(e).__name__}: {e}"[:300]
    return "failed", "unknown channel"


MAX_ATTEMPTS = 3


def process_outbox(limit=50):
    rows = db.q("SELECT * FROM outbox WHERE status='pending' AND (not_before IS NULL OR not_before<=?) ORDER BY id LIMIT ?", (time.time(), limit))
    done = 0
    for r in rows:
        status, info = deliver(r)
        with db.tx() as c:
            if status == "failed" and r["attempts"] + 1 < MAX_ATTEMPTS:
                c.execute("UPDATE outbox SET attempts=attempts+1, error=? WHERE id=?", (info, r["id"]))
            else:
                c.execute("UPDATE outbox SET status=?, attempts=attempts+1, error=?, sent_at=?, provider_id=? WHERE id=?",
                          (status, info if status == "failed" else "", time.time() if status in ("sent", "demo") else None,
                           info if status == "sent" else "", r["id"]))
        done += 1
    return done


def retry_failed(c, ids=None):
    if ids:
        marks = ",".join("?" for _ in ids)
        c.execute(f"UPDATE outbox SET status='pending', attempts=0, error='' WHERE id IN ({marks}) AND status IN ('failed','demo')", list(ids))
    else:
        c.execute("UPDATE outbox SET status='pending', attempts=0, error='' WHERE status='failed'")


_worker = None


def start_worker(interval=5.0):
    global _worker
    if _worker or os.environ.get("CLUB_NO_WORKER"):
        return

    def run():
        while True:
            try:
                n = 0
                for slug in tenancy.all_slugs():
                    with tenancy.use(slug):
                        n += process_outbox()
                if n == 0:
                    time.sleep(interval)
            except Exception:  # noqa: BLE001
                log.exception("outbox worker")
                time.sleep(interval)

    _worker = threading.Thread(target=run, name="club-outbox", daemon=True)
    _worker.start()
