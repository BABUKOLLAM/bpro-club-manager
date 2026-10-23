"""SaaS edition: clubs sign up by themselves, start on a trial, and pay the operator yearly.

Pricing rule (editable on /_platform): a flat yearly price for small clubs (up to `flat_upto` active members),
otherwise `per_member` rupees per active member per year. The price is worked out from the live member count at the
time of payment, so a club that grows pays more at its next renewal and never hits a cap.

Plan state lives in the registry next to the club: {"status": trial|active|overdue|suspended, "trial_ends", "paid_until",
"payments": [...], "claims": [...], "pending_order": {...}}. The original (default) club is the operator's own and is exempt.
Grace: after the trial or the paid year ends the club is "overdue" for `grace_days`, then "suspended" (read-only until
paid; data kept). The operator's Razorpay account (CLUBPRO_RZP_*) takes the payments; UPI with a manual claim is the
fallback.
"""
import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import time
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, comms, db, i18n, tenancy
from .auth import require
from fastapi import Depends

log = logging.getLogger("saas")
router = APIRouter()
pages = APIRouter()
DAY = 86400
YEAR = 365 * DAY

DEFAULT_PRICING = {"flat_upto": 49, "flat_price": 2500, "per_member": 120, "trial_days": 30, "grace_days": 15,
                   "upi_id": "", "upi_name": "", "support": ""}
DEFAULT_PRODUCT = tenancy.DEFAULT_PRODUCT
DEFAULT_POWERED_BY = tenancy.DEFAULT_POWERED_BY

# What a club gets: shown on /pricing and /signup, in both languages.
SERVICES = [
    ("Membership register", "അംഗത്വ രജിസ്റ്റർ", "Online application with approval, membership numbers, family details, photo, QR membership e-card, Excel import of the old register.",
     "ഓൺലൈൻ അപേക്ഷയും അംഗീകാരവും, അംഗത്വ നമ്പർ, കുടുംബ വിവരങ്ങൾ, ഫോട്ടോ, QR ഇ-കാർഡ്, പഴയ രജിസ്റ്റർ Excel-ൽ നിന്ന് ഇറക്കുമതി."),
    ("Subscriptions & dues", "വരിസംഖ്യയും കുടിശ്ശികയും", "Membership types and fees, yearly dues, reminders, receipts, UPI and online payment with automatic receipts.",
     "അംഗത്വ തരങ്ങളും ഫീസും, വാർഷിക കുടിശ്ശിക, ഓർമ്മപ്പെടുത്തൽ, രസീതുകൾ, UPI / ഓൺലൈൻ പേയ്മെന്റ്."),
    ("Donations & accounts", "സംഭാവനകളും കണക്കുകളും", "Receipts and vouchers under standard heads (donations, sponsorship, grants, expenses), cash book and the annual statement.",
     "സംഭാവന, സ്പോൺസർഷിപ്പ്, ഗ്രാന്റ്, ചെലവുകൾ എന്നിങ്ങനെ രസീതുകളും വൗച്ചറുകളും, ക്യാഷ് ബുക്ക്, വാർഷിക കണക്ക്."),
    ("Events & competitions", "പരിപാടികളും മത്സരങ്ങളും", "News and events with WhatsApp / SMS / e-mail / app push, online registration, fixtures, judging, points tables and results.",
     "വാർത്തകളും പരിപാടികളും വാട്സ്ആപ്പ് / SMS / ഇ-മെയിൽ / ആപ്പ് വഴി, ഓൺലൈൻ രജിസ്ട്രേഷൻ, ഫിക്സ്ചർ, ജഡ്ജിംഗ്, പോയിന്റ് പട്ടിക, ഫലങ്ങൾ."),
    ("Camps & social activities", "ക്യാമ്പുകളും സാമൂഹിക പ്രവർത്തനങ്ങളും", "Medical camps, blood donor requests by blood group, regional programmes, volunteer registration.",
     "മെഡിക്കൽ ക്യാമ്പുകൾ, രക്തഗ്രൂപ്പ് അനുസരിച്ച് രക്തദാന അഭ്യർത്ഥന, പ്രാദേശിക പരിപാടികൾ, വോളന്റിയർ രജിസ്ട്രേഷൻ."),
    ("Committees & meetings", "കമ്മിറ്റികളും യോഗങ്ങളും", "Executive and sub-committees, notices, agenda, attendance, online minutes with resolutions, action items and plans.",
     "എക്സിക്യൂട്ടീവ്, സബ് കമ്മിറ്റികൾ, നോട്ടീസ്, അജണ്ട, ഹാജർ, തീരുമാനങ്ങളോടെ ഓൺലൈൻ മിനിറ്റ്സ്, നടപടികൾ, പദ്ധതികൾ."),
    ("Library & reading room", "ലൈബ്രറിയും വായനശാലയും", "Catalogue with accession numbers, issue / return / renew, reservations, fines, reading-room register, newspapers and periodicals.",
     "അക്സഷൻ നമ്പറോടെ കാറ്റലോഗ്, ഇഷ്യൂ / തിരികെ / പുതുക്കൽ, റിസർവേഷൻ, പിഴ, വായനശാല രജിസ്റ്റർ, പത്രങ്ങളും ആനുകാലികങ്ങളും."),
    ("Facilities & rentals", "സൗകര്യങ്ങളും വാടകയും", "Hall, ground and equipment bookings with rates and approvals, calendar, receipts for rentals.",
     "ഹാൾ, ഗ്രൗണ്ട്, ഉപകരണങ്ങൾ എന്നിവയുടെ ബുക്കിംഗ് നിരക്കും അംഗീകാരവും, കലണ്ടർ, വാടക രസീതുകൾ."),
    ("Assets & lending", "ആസ്തികളും കടം നൽകലും", "Asset register with categories, lending to members with return tracking.",
     "ആസ്തി രജിസ്റ്റർ, അംഗങ്ങൾക്ക് കടം നൽകലും തിരികെ വാങ്ങലും."),
    ("Broadcasts", "ബ്രോഡ്കാസ്റ്റ്", "Messages to all members or a chosen audience by WhatsApp, SMS, e-mail and app notification, scheduled sending, outbox with delivery status.",
     "എല്ലാ അംഗങ്ങൾക്കും അല്ലെങ്കിൽ തിരഞ്ഞെടുത്തവർക്കും വാട്സ്ആപ്പ്, SMS, ഇ-മെയിൽ, ആപ്പ് അറിയിപ്പ്; ഷെഡ്യൂൾ ചെയ്ത അയയ്ക്കൽ; ഡെലിവറി നില."),
    ("Polls & elections", "വോട്ടെടുപ്പും തിരഞ്ഞെടുപ്പും", "Member polls and office-bearer elections with one vote per member and results.",
     "അംഗങ്ങളുടെ വോട്ടെടുപ്പും ഭാരവാഹി തിരഞ്ഞെടുപ്പും, ഒരംഗത്തിന് ഒരു വോട്ട്, ഫലങ്ങൾ."),
    ("Documents & website", "രേഖകളും വെബ്സൈറ്റും", "Bye-laws, circulars and certificates with audience control; a public website with office bearers, events and photos.",
     "ബൈലോ, സർക്കുലർ, സർട്ടിഫിക്കറ്റുകൾ; ഭാരവാഹികൾ, പരിപാടികൾ, ഫോട്ടോകൾ എന്നിവയോടെ പൊതു വെബ്സൈറ്റ്."),
    ("Reports & backups", "റിപ്പോർട്ടുകളും ബാക്കപ്പും", "Dashboard, member statistics, annual report for the general body, nightly backups with Google Drive copies.",
     "ഡാഷ്ബോർഡ്, അംഗ സ്ഥിതിവിവരം, ജനറൽ ബോഡിക്കുള്ള വാർഷിക റിപ്പോർട്ട്, രാത്രി ബാക്കപ്പ്, ഗൂഗിൾ ഡ്രൈവ് പകർപ്പ്."),
    ("Your own brand", "നിങ്ങളുടെ സ്വന്തം ബ്രാൻഡ്", "Logo, colours and app name on everything including the e-card; your own domain; bilingual English / Malayalam; works as an installed phone app.",
     "ലോഗോ, നിറങ്ങൾ, ആപ്പിന്റെ പേര് എല്ലായിടത്തും; സ്വന്തം ഡൊമെയ്ൻ; ഇംഗ്ലീഷ് / മലയാളം; ഫോണിൽ ആപ്പായി ഇൻസ്റ്റാൾ ചെയ്യാം."),
]


# ---------- pricing and plan state ----------
def pricing():
    return {**DEFAULT_PRICING, **(tenancy.registry().get("pricing") or {})}


def product():
    reg = tenancy.registry()
    return {"name": reg.get("product_name") or DEFAULT_PRODUCT, "powered_by": reg.get("powered_by") or DEFAULT_POWERED_BY,
            "base_domain": os.environ.get("CLUB_BASE_DOMAIN", ""), "support": pricing().get("support", "")}


def price_for(members, p=None):
    p = p or pricing()
    members = max(0, int(members or 0))
    if members <= int(p["flat_upto"]):
        return int(p["flat_price"])
    return members * int(p["per_member"])


def active_members(slug):
    with tenancy.use(slug):
        db.init()
        return db.one("SELECT COUNT(*) n FROM members WHERE status='active'")["n"]


def _plan_raw(slug):
    t = tenancy.tenants().get(slug) or {}
    return t.setdefault("plan", {}) if t else {}


def effective_status(plan, now=None):
    """What the plan is right now, from its dates (the stored status may lag until the daily job runs)."""
    now = now or time.time()
    grace = int(pricing()["grace_days"]) * DAY
    st = plan.get("status") or "trial"
    if st == "suspended":
        return "suspended"
    end = plan.get("paid_until") if st in ("active", "overdue") and plan.get("paid_until") else plan.get("trial_ends")
    if not end:
        return st
    if now <= end:
        return "active" if plan.get("paid_until") and plan["paid_until"] >= now else "trial"
    return "overdue" if now <= end + grace else "suspended"


def plan_of(slug):
    """The plan as the club and the console see it."""
    if slug == "default":
        return {"status": "active", "exempt": True, "days_left": None, "ends": None}
    t = tenancy.tenants().get(slug)
    if not t:
        return {"status": "active", "exempt": True, "days_left": None, "ends": None}
    plan = t.get("plan") or {}
    st = effective_status(plan)
    ends = plan.get("paid_until") if plan.get("paid_until") else plan.get("trial_ends")
    grace = int(pricing()["grace_days"])
    return {"status": st, "exempt": False, "ends": ends, "days_left": int((ends - time.time()) // DAY) if ends else None,
            "grace_days": grace, "paid_until": plan.get("paid_until"), "trial_ends": plan.get("trial_ends"),
            "payments": plan.get("payments", []), "claims": [c for c in plan.get("claims", []) if c.get("status") == "pending"],
            "read_only": st == "suspended"}


def start_trial(slug, days=None):
    reg = tenancy.registry()
    t = reg["tenants"][slug]
    days = int(days if days is not None else pricing()["trial_days"])
    t["plan"] = {"status": "trial", "trial_ends": time.time() + days * DAY, "paid_until": None, "payments": [], "claims": []}
    tenancy.save_registry(reg)
    return t["plan"]


def mark_paid(slug, amount, members, ref, via, years=1):
    reg = tenancy.registry()
    t = reg["tenants"][slug]
    plan = t.setdefault("plan", {"status": "trial", "payments": [], "claims": []})
    if ref and any(p.get("ref") == ref for p in plan.get("payments", [])):
        return plan  # idempotent (webhook after verify, or a retry)
    base = max(time.time(), plan.get("paid_until") or 0)
    plan["paid_until"] = base + years * YEAR
    plan["status"] = "active"
    plan.setdefault("payments", []).append({"at": time.time(), "amount": int(amount), "members": int(members), "ref": ref, "via": via, "years": years})
    plan.pop("pending_order", None)
    t["active"] = True
    tenancy.save_registry(reg)
    return plan


def set_status(slug, status, extra_days=None):
    reg = tenancy.registry()
    t = reg["tenants"][slug]
    plan = t.setdefault("plan", {"status": "trial", "payments": [], "claims": []})
    if status == "extend":
        base = max(time.time(), plan.get("trial_ends") or 0)
        plan["trial_ends"] = base + int(extra_days or 30) * DAY
        plan["status"] = "trial"
    elif status == "suspended":
        plan["status"] = "suspended"
    elif status == "reactivate":
        # back to whatever the dates say, with a fortnight to sort payment out if everything has lapsed
        plan["status"] = "trial" if not plan.get("paid_until") else "active"
        if effective_status(plan) == "suspended":
            plan["trial_ends"] = time.time() + 14 * DAY
            plan["paid_until"] = None
            plan["status"] = "trial"
    tenancy.save_registry(reg)
    return plan


def is_read_only(slug):
    return not plan_of(slug)["exempt"] and plan_of(slug)["status"] == "suspended"


# ---------- the operator's Razorpay account ----------
_order_override = None


def set_order_creator(fn):
    global _order_override
    _order_override = fn


def operator_gateway():
    return bool(os.environ.get("CLUBPRO_RZP_KEY_ID") and os.environ.get("CLUBPRO_RZP_KEY_SECRET")) or bool(_order_override)


def _rzp(path, payload):
    key, secret = os.environ["CLUBPRO_RZP_KEY_ID"], os.environ["CLUBPRO_RZP_KEY_SECRET"]
    req = urllib.request.Request("https://api.razorpay.com/v1" + path, data=json.dumps(payload).encode(),
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode(), "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def create_order(amount_paise, receipt, notes):
    if _order_override:
        return _order_override(amount_paise, receipt, notes)
    return _rzp("/orders", {"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes})


def verify_signature(order_id, payment_id, signature):
    secret = os.environ.get("CLUBPRO_RZP_KEY_SECRET", "")
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


# ---------- club side: my plan, pay ----------
@router.get("/plan")
def my_plan(user=Depends(require("settings.manage"))):
    slug = tenancy.current.get()
    p = plan_of(slug)
    n = active_members(slug)
    pr = pricing()
    return {**p, "members": n, "price": price_for(n, pr), "pricing": {k: pr[k] for k in ("flat_upto", "flat_price", "per_member", "trial_days", "grace_days")},
            "gateway": operator_gateway(), "key_id": os.environ.get("CLUBPRO_RZP_KEY_ID", "") if operator_gateway() else "",
            "upi_id": pr["upi_id"], "upi_name": pr["upi_name"], "product": product()}


@router.post("/pay/order")
def pay_order(user=Depends(require("settings.manage"))):
    slug = tenancy.current.get()
    if slug == "default" or not tenancy.tenants().get(slug):
        raise HTTPException(400, "this club does not pay a subscription")
    if not operator_gateway():
        raise HTTPException(400, "online payment is not available; pay by UPI and send the reference")
    n = active_members(slug)
    amount = price_for(n)
    o = create_order(amount * 100, f"{slug}-{int(time.time())}", {"club": slug, "members": str(n)})
    reg = tenancy.registry()
    reg["tenants"][slug].setdefault("plan", {})["pending_order"] = {"order_id": o["id"], "amount": amount, "members": n, "at": time.time()}
    tenancy.save_registry(reg)
    s = db.settings_all()
    return {"ok": True, "order_id": o["id"], "amount": amount, "currency": "INR", "key_id": os.environ.get("CLUBPRO_RZP_KEY_ID", ""),
            "description": f"{product()['name']} · {s['club_name_en']} · {n} members · 1 year", "prefill": {"name": user["name"], "email": s["club_email"], "contact": s["club_phone"]}}


@router.post("/pay/verify")
async def pay_verify(request: Request, user=Depends(require("settings.manage"))):
    b = await request.json()
    slug = tenancy.current.get()
    po = (tenancy.tenants().get(slug) or {}).get("plan", {}).get("pending_order")
    if not po or po["order_id"] != b.get("razorpay_order_id"):
        raise HTTPException(404, "order")
    if not (_order_override or verify_signature(po["order_id"], b.get("razorpay_payment_id", ""), b.get("razorpay_signature", ""))):
        raise HTTPException(400, "payment signature does not match")
    mark_paid(slug, po["amount"], po["members"], b.get("razorpay_payment_id", ""), "razorpay")
    return {"ok": True, "plan": plan_of(slug)}


@router.post("/webhook")
async def webhook(request: Request):
    """The operator's Razorpay webhook (payment.captured / order.paid): the safety net when the browser closes early."""
    secret = os.environ.get("CLUBPRO_RZP_WEBHOOK_SECRET", "")
    body = await request.body()
    if not secret:
        raise HTTPException(404)
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Razorpay-Signature", "")):
        raise HTTPException(400, "bad signature")
    ev = json.loads(body or b"{}")
    pay = (((ev.get("payload") or {}).get("payment") or {}).get("entity") or {})
    order_id, payment_id = pay.get("order_id"), pay.get("id")
    for slug, t in tenancy.tenants().items():
        po = (t.get("plan") or {}).get("pending_order")
        if po and po.get("order_id") == order_id:
            mark_paid(slug, po["amount"], po["members"], payment_id or order_id, "razorpay-webhook")
            return {"ok": True}
    return {"ok": True, "ignored": True}


@router.post("/pay/claim")
async def pay_claim(request: Request, user=Depends(require("settings.manage"))):
    """'I have paid by UPI / bank transfer': the operator approves it on the console."""
    b = await request.json()
    slug = tenancy.current.get()
    if slug == "default" or not tenancy.tenants().get(slug):
        raise HTTPException(400, "this club does not pay a subscription")
    ref = (b.get("ref") or "").strip()[:80]
    if not ref:
        raise HTTPException(400, "the payment reference is needed")
    reg = tenancy.registry()
    plan = reg["tenants"][slug].setdefault("plan", {"status": "trial", "payments": [], "claims": []})
    n = active_members(slug)
    plan.setdefault("claims", []).append({"at": time.time(), "ref": ref, "amount": price_for(n), "members": n, "by": user["name"], "status": "pending"})
    tenancy.save_registry(reg)
    return {"ok": True}


# ---------- operator console ----------
def console_rows():
    pr = pricing()
    rows = []
    for slug, t in tenancy.tenants().items():
        p = plan_of(slug)
        try:
            n = active_members(slug)
        except Exception:  # noqa: BLE001
            n = 0
        rows.append({"slug": slug, "status": p["status"], "ends": p["ends"], "days_left": p["days_left"], "members": n, "price": price_for(n, pr),
                     "paid_until": p["paid_until"], "payments": len(p["payments"]), "claims": p["claims"], "contact": t.get("contact", {}),
                     "last_payment": p["payments"][-1] if p["payments"] else None})
    return rows


def summary():
    rows = console_rows()
    by = {"trial": 0, "active": 0, "overdue": 0, "suspended": 0}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    week = time.time() + 7 * DAY
    return {"clubs": len(rows), "by_status": by, "arr": sum(r["price"] for r in rows if r["status"] in ("trial", "active", "overdue")),
            "paid_total": sum(p["amount"] for r in rows for p in (tenancy.tenants()[r["slug"]].get("plan") or {}).get("payments", [])),
            "ending_soon": [r["slug"] for r in rows if r["ends"] and r["ends"] <= week and r["status"] in ("trial", "active")],
            "claims": sum(len(r["claims"]) for r in rows), "gateway": operator_gateway(), "pricing": pricing(), "product": product()}


def console_action(slug, action, b):
    if slug not in tenancy.tenants():
        raise ValueError("unknown club")
    if action == "mark_paid":
        n = active_members(slug)
        amount = int(b.get("amount") or price_for(n))
        return mark_paid(slug, amount, n, b.get("ref") or f"manual-{int(time.time())}", b.get("via") or "manual", int(b.get("years") or 1))
    if action == "approve_claim":
        reg = tenancy.registry()
        plan = reg["tenants"][slug].get("plan") or {}
        for c in plan.get("claims", []):
            if c.get("ref") == b.get("ref") and c.get("status") == "pending":
                c["status"] = "approved"
                tenancy.save_registry(reg)
                return mark_paid(slug, c["amount"], c["members"], c["ref"], "upi")
        raise ValueError("no such claim")
    if action == "reject_claim":
        reg = tenancy.registry()
        for c in (reg["tenants"][slug].get("plan") or {}).get("claims", []):
            if c.get("ref") == b.get("ref") and c.get("status") == "pending":
                c["status"] = "rejected"
        tenancy.save_registry(reg)
        return reg["tenants"][slug].get("plan")
    if action == "extend_trial":
        return set_status(slug, "extend", int(b.get("days") or 30))
    if action in ("suspended", "reactivate"):
        return set_status(slug, action)
    raise ValueError("unknown action")


# ---------- daily: transitions and reminders ----------
def daily(now=None):
    """Move plans along their dates and remind the club's office bearers. Runs once a day for the platform."""
    now = now or time.time()
    reg = tenancy.registry()
    out = {"changed": 0, "reminded": 0}
    for slug, t in reg.get("tenants", {}).items():
        plan = t.get("plan")
        if not plan:
            continue
        st = effective_status(plan, now)
        last = plan.get("last_reminder") or {}
        ends = plan.get("paid_until") or plan.get("trial_ends") or 0
        days_left = int((ends - now) // DAY)
        key = None
        if st in ("trial", "active") and 0 <= days_left <= 7:
            key = "saas_ending"
        elif st == "overdue":
            key = "saas_overdue"
        elif st == "suspended" and plan.get("status") != "suspended":
            key = "saas_suspended"
        if st != plan.get("status"):
            plan["status"] = st
            out["changed"] += 1
        if key and last.get("key") != key or (key and now - last.get("at", 0) > 3 * DAY):
            try:
                with tenancy.use(slug):
                    db.init()
                    _remind(slug, key, days_left, plan)
                plan["last_reminder"] = {"key": key, "at": now}
                out["reminded"] += 1
            except Exception:  # noqa: BLE001
                log.exception("plan reminder for %s", slug)
    tenancy.save_registry(reg)
    return out


def _remind(slug, key, days_left, plan):
    pr = product()
    n = db.one("SELECT COUNT(*) n FROM members WHERE status='active'")["n"]
    ctx = {"product": pr["name"], "days": max(days_left, 0), "price": price_for(n), "members": n, "link": comms.club_ctx()["link"] + "/#/plan",
           "grace": pricing()["grace_days"], "support": pr["support"]}
    officers = db.q("SELECT id, member_id, lang FROM users WHERE role IN ('admin','secretary','treasurer','president') AND active=1")
    with db.tx() as c:
        batch = comms.new_batch()
        for u in officers:
            lang = u["lang"] or db.setting("default_lang")
            subject, body = i18n.render(key, lang, ctx)
            if u["member_id"]:
                comms.queue(c, "app", "", subject, body, lang=lang, member_id=u["member_id"], template=key, ref_kind="plan", batch_id=batch)
                m = db.one("SELECT whatsapp, phone, email FROM members WHERE id=?", (u["member_id"],))
                for ch, addr in (("whatsapp", m["whatsapp"] or m["phone"]), ("email", m["email"])):
                    if addr:
                        comms.queue(c, ch, addr, subject, body, lang=lang, member_id=u["member_id"], template=key, ref_kind="plan", batch_id=batch)


# ---------- self-serve signup ----------
_signups = {}   # ticket_hash -> {"code_hash", "data", "expires", "attempts"}
_signup_lock = __import__("threading").Lock()


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:31]
    return s if tenancy.SLUG_RE.match(s or "") else ""


def _otp_channel():
    with tenancy.use("default"):
        c = comms.configured()
    for ch in ("sms", "whatsapp", "email"):
        if c.get(ch):
            return ch
    return None


def _send_now(channel, to, subject, body):
    with tenancy.use("default"):
        db.init()
        return comms.deliver({"channel": channel, "to_addr": to, "subject": subject, "body": body, "ref_kind": "", "ref_id": None})


@router.post("/signup/start")
async def signup_start(request: Request):
    b = await request.json()
    name = (b.get("club_name_en") or "").strip()[:120]
    slug = slugify(b.get("slug") or name)
    phone = re.sub(r"[^0-9+]", "", b.get("phone") or "")
    email = (b.get("email") or "").strip().lower()[:120]
    pw = b.get("password") or ""
    if not name or not slug:
        raise HTTPException(400, "club name")
    if slug in tenancy.tenants() or slug in ("default", "tenants", "admin", "api", "static", "uploads", "www", "app", "signup", "pricing"):
        raise HTTPException(400, "that web address is taken; choose another")
    if len(re.sub(r"[^0-9]", "", phone)) < 10:
        raise HTTPException(400, "phone")
    if len(pw) < 8:
        raise HTTPException(400, "password: 8+ characters")
    if not b.get("agree"):
        raise HTTPException(400, "please accept the terms")
    data = {"slug": slug, "name_en": name, "name_ml": (b.get("club_name_ml") or "").strip()[:120], "place": (b.get("place") or "").strip()[:80],
            "short": (b.get("short") or "").strip().upper()[:8], "admin_name": (b.get("admin_name") or "").strip()[:80], "phone": phone, "email": email,
            "password": pw, "lang": b.get("lang") if b.get("lang") in ("en", "ml") else "ml"}
    ch = _otp_channel()
    ticket = secrets.token_urlsafe(24)
    code = f"{secrets.randbelow(900000) + 100000}"
    with _signup_lock:
        for k in [k for k, v in _signups.items() if v["expires"] < time.time()]:
            _signups.pop(k, None)
        _signups[hashlib.sha256(ticket.encode()).hexdigest()] = {"code_hash": hashlib.sha256(code.encode()).hexdigest(), "data": data, "expires": time.time() + 600, "attempts": 0, "verified": ch is None}
    if ch:
        to = email if ch == "email" else phone
        if not to:
            raise HTTPException(400, "e-mail" if ch == "email" else "phone")
        pr = product()
        st, info = _send_now(ch, to, f"{pr['name']} code", f"{code} is your {pr['name']} sign-up code. It is valid for 10 minutes.")
        if st == "failed":
            log.warning("signup code to %s failed: %s", to, info)
            raise HTTPException(502, "could not send the code; try again in a minute")
    return {"ok": True, "ticket": ticket, "channel": ch, "slug": slug}


@router.post("/signup/verify")
async def signup_verify(request: Request):
    b = await request.json()
    th = hashlib.sha256((b.get("ticket") or "").encode()).hexdigest()
    with _signup_lock:
        rec = _signups.get(th)
        if not rec or rec["expires"] < time.time():
            raise HTTPException(400, "the code has expired; start again")
        if not rec["verified"]:
            rec["attempts"] += 1
            if rec["attempts"] > 5:
                _signups.pop(th, None)
                raise HTTPException(400, "too many attempts; start again")
            if not hmac.compare_digest(rec["code_hash"], hashlib.sha256((b.get("code") or "").strip().encode()).hexdigest()):
                raise HTTPException(400, "wrong code")
        d = rec["data"]
        _signups.pop(th, None)
    base = os.environ.get("CLUB_BASE_DOMAIN", "")
    domains = [f"{d['slug']}.{base}"] if base else []
    try:
        tenancy.create(d["slug"], d["name_en"], d["name_ml"], domains, d["email"] or d["phone"], d["password"], d["short"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    reg = tenancy.registry()
    reg["tenants"][d["slug"]]["contact"] = {"name": d["admin_name"], "phone": d["phone"], "email": d["email"]}
    reg["tenants"][d["slug"]]["source"] = "signup"
    tenancy.save_registry(reg)
    start_trial(d["slug"])
    with tenancy.use(d["slug"]):
        db.init()
        with db.tx() as c:
            db.set_setting(c, "club_place_en", d["place"])
            db.set_setting(c, "club_phone", d["phone"])
            db.set_setting(c, "club_email", d["email"])
            db.set_setting(c, "default_lang", d["lang"])
            c.execute("UPDATE users SET name=?, lang=? WHERE role='admin'", (d["admin_name"] or "Secretary", d["lang"]))
    url = f"https://{domains[0]}" if domains else ""
    return {"ok": True, "slug": d["slug"], "url": url, "login": d["email"] or d["phone"], "trial_days": pricing()["trial_days"]}


# ---------- public pages: /pricing and /signup ----------
def _page(lang, title, body, extra_head=""):
    from . import brand
    pr = product()
    with tenancy.use("default"):
        db.init()
        s = db.settings_all()
        head = brand.html_head(s)
        c = brand.colors(s)
    other = "en" if lang == "ml" else "ml"
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · {html.escape(pr['name'])}</title>{head}
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;margin:0;background:#F7F4EC;color:#1D2A28;line-height:1.55}}html[lang=ml] body{{font-family:Manjari,Inter,sans-serif}}
header{{background:{c['primary']};color:{c['primary_ink']};padding:14px 18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}header .b{{font-weight:700;font-size:1.2rem;flex:1}}
header a{{color:inherit;text-decoration:none;background:rgba(255,255,255,.15);padding:7px 12px;border-radius:9px;font-weight:600}}header a.a{{background:{c['accent']};color:{c['accent_ink']}}}
main{{max-width:980px;margin:0 auto;padding:22px 16px 60px}}h1{{font-size:1.7rem;margin:.2em 0}}h2{{font-size:1.2rem;margin:26px 0 8px;color:{c['primary']}}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}.card{{background:#fff;border:1px solid #E3DED2;border-radius:14px;padding:14px 16px}}.card b{{display:block;margin-bottom:4px}}.card p{{margin:0;color:#5B6B68;font-size:.93rem}}
.price{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}.price .card{{text-align:center}}.price .n{{font-size:2rem;font-weight:700;color:{c['primary']};font-family:Inter}}.price small{{color:#5B6B68}}
.btn{{display:inline-block;background:{c['accent']};color:{c['accent_ink']};padding:11px 18px;border-radius:10px;font-weight:700;text-decoration:none;border:0;font:inherit;cursor:pointer}}.btn.g{{background:{c['primary']};color:{c['primary_ink']}}}
label{{display:block;font-size:.85rem;color:#5B6B68;margin:10px 0 4px}}input,select{{width:100%;padding:10px;border:1px solid #E3DED2;border-radius:10px;font:inherit;box-sizing:border-box;background:#fff}}.form{{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}}.form .full{{grid-column:1/-1}}
.msg{{margin:10px 0;padding:10px 12px;border-radius:10px;background:#FBF0D9;color:#A86A00;display:none}}.msg.ok{{background:#E4F3EA;color:#2E7D4F}}.m{{color:#5B6B68;font-size:.88rem}}footer{{text-align:center;color:#8a948f;font-size:.8rem;padding:24px}}
@media(max-width:640px){{.form{{grid-template-columns:1fr}}}}</style>{extra_head}</head>
<body><header><div class="b">{html.escape(pr['name'])}</div><a href="?lang={other}">{'English' if lang == 'ml' else 'മലയാളം'}</a><a href="/pricing?lang={lang}">{'Pricing' if lang == 'en' else 'വില'}</a><a class="a" href="/signup?lang={lang}">{'Start free trial' if lang == 'en' else 'സൗജന്യ ട്രയൽ തുടങ്ങുക'}</a></header>
<main>{body}</main><footer>{html.escape(pr['powered_by'])}{(' · ' + html.escape(pr['support'])) if pr['support'] else ''}</footer></body></html>"""


def _services_html(lang):
    return "".join(f"<div class='card'><b>{html.escape(s[1] if lang == 'ml' else s[0])}</b><p>{html.escape(s[3] if lang == 'ml' else s[2])}</p></div>" for s in SERVICES)


def _pricing_html(lang):
    p = pricing()
    e = html.escape
    if lang == "ml":
        return f"""<div class="price"><div class="card"><div class="n">₹{p['flat_price']:,}</div><b>{p['flat_upto']} അംഗങ്ങൾ വരെ</b><small>പ്രതിവർഷം, ക്ലബ്ബിന് മൊത്തം</small></div>
<div class="card"><div class="n">₹{p['per_member']}</div><b>{p['flat_upto'] + 1} അംഗങ്ങൾ മുതൽ</b><small>ഒരംഗത്തിന് പ്രതിവർഷം · ഉദാ: 80 അംഗങ്ങൾ = ₹{80 * p['per_member']:,}</small></div>
<div class="card"><div class="n">{p['trial_days']} ദിവസം</div><b>സൗജന്യ ട്രയൽ</b><small>കാർഡ് വേണ്ട · എല്ലാ സൗകര്യങ്ങളും</small></div></div>
<p class="m">വില സജീവ അംഗങ്ങളുടെ എണ്ണം അനുസരിച്ച് പുതുക്കൽ സമയത്ത് കണക്കാക്കും. വാട്സ്ആപ്പ് / SMS ഗേറ്റ്‌വേ നിരക്കുകൾ അതത് കമ്പനിയുടേതാണ്.</p>"""
    return f"""<div class="price"><div class="card"><div class="n">₹{p['flat_price']:,}</div><b>Up to {p['flat_upto']} members</b><small>per year, flat for the club</small></div>
<div class="card"><div class="n">₹{p['per_member']}</div><b>{p['flat_upto'] + 1} members and above</b><small>per member per year · e.g. 80 members = ₹{80 * p['per_member']:,}</small></div>
<div class="card"><div class="n">{p['trial_days']} days</div><b>Free trial</b><small>no card needed · every feature</small></div></div>
<p class="m">The price is worked out from the number of active members at each yearly renewal. WhatsApp / SMS gateway charges are the provider's own.</p>"""


@pages.get("/pricing", response_class=HTMLResponse)
def pricing_page(lang: str = "en"):
    lang = lang if lang in ("en", "ml") else "en"
    pr = product()
    h = {"en": (f"Everything a club needs, under its own name", "What you get", "Pricing", "Start free trial"),
         "ml": ("ഒരു ക്ലബ്ബിന് വേണ്ടതെല്ലാം, സ്വന്തം പേരിൽ", "നിങ്ങൾക്ക് ലഭിക്കുന്നത്", "വില", "സൗജന്യ ട്രയൽ തുടങ്ങുക")}[lang]
    body = f"<h1>{h[0]}</h1><p class='m'>{'Membership, library, events, committees, accounts and messaging for arts & sports clubs, libraries and reading rooms, in English and Malayalam.' if lang == 'en' else 'ആർട്സ് & സ്പോർട്സ് ക്ലബ്ബുകൾ, ലൈബ്രറികൾ, വായനശാലകൾ എന്നിവയ്ക്കായി അംഗത്വം, ലൈബ്രറി, പരിപാടികൾ, കമ്മിറ്റികൾ, കണക്കുകൾ, സന്ദേശങ്ങൾ; ഇംഗ്ലീഷിലും മലയാളത്തിലും.'}</p>" \
           f"<h2>{h[2]}</h2>{_pricing_html(lang)}<h2>{h[1]}</h2><div class='grid'>{_services_html(lang)}</div><p style='margin-top:24px'><a class='btn' href='/signup?lang={lang}'>{h[3]}</a></p>"
    return _page(lang, h[2], body)


@pages.get("/signup", response_class=HTMLResponse)
def signup_page(lang: str = "en"):
    lang = lang if lang in ("en", "ml") else "en"
    pr = product()
    base = pr["base_domain"] or "your-domain"
    L = {"en": ("Start your club on", "free for", "days. No card needed.", "Club name (English)", "Club name (Malayalam)", "Place", "Short name (for membership numbers)", "Web address", "Your name", "Your mobile number", "E-mail", "Password (8+)", "I agree to the terms of service and privacy policy", "Create my club", "Enter the code we sent", "Verify and open my club", "Your club is ready", "Sign in with", "Open my club", "Language of the club"),
         "ml": ("നിങ്ങളുടെ ക്ലബ്ബ് തുടങ്ങൂ", "സൗജന്യം", "ദിവസം. കാർഡ് വേണ്ട.", "ക്ലബ്ബിന്റെ പേര് (ഇംഗ്ലീഷ്)", "ക്ലബ്ബിന്റെ പേര് (മലയാളം)", "സ്ഥലം", "ചുരുക്കപ്പേര് (അംഗത്വ നമ്പറിന്)", "വെബ് വിലാസം", "നിങ്ങളുടെ പേര്", "മൊബൈൽ നമ്പർ", "ഇ-മെയിൽ", "പാസ്‌വേഡ് (8+)", "സേവന വ്യവസ്ഥകളും സ്വകാര്യതാ നയവും അംഗീകരിക്കുന്നു", "എന്റെ ക്ലബ്ബ് ഉണ്ടാക്കുക", "ഞങ്ങൾ അയച്ച കോഡ് നൽകുക", "പരിശോധിച്ച് ക്ലബ്ബ് തുറക്കുക", "നിങ്ങളുടെ ക്ലബ്ബ് തയ്യാർ", "പ്രവേശിക്കാൻ", "എന്റെ ക്ലബ്ബ് തുറക്കുക", "ക്ലബ്ബിന്റെ ഭാഷ")}[lang]
    e = html.escape
    body = f"""<h1>{L[0]} {e(pr['name'])}</h1><p class="m">{L[1]} {pricing()['trial_days']} {L[2]}</p>
<form id="f1" class="card" onsubmit="return false"><div class="form">
<div><label>{L[3]} *</label><input name="club_name_en" required oninput="document.querySelector('[name=slug]').value=slugify(this.value)"></div><div><label>{L[4]}</label><input name="club_name_ml"></div>
<div><label>{L[5]}</label><input name="place"></div><div><label>{L[6]}</label><input name="short" maxlength="8" placeholder="KASC"></div>
<div class="full"><label>{L[7]}</label><div style="display:flex;align-items:center;gap:6px"><input name="slug" pattern="[a-z0-9][a-z0-9\\-]{{1,30}}" required style="max-width:260px"><span class="m">.{e(base)}</span></div></div>
<div><label>{L[8]} *</label><input name="admin_name" required></div><div><label>{L[19]}</label><select name="lang"><option value="ml" {'selected' if lang == 'ml' else ''}>മലയാളം</option><option value="en" {'selected' if lang == 'en' else ''}>English</option></select></div>
<div><label>{L[9]} *</label><input name="phone" required inputmode="tel" pattern="[0-9 +\\-]{{10,15}}"></div><div><label>{L[10]}</label><input name="email" type="email"></div>
<div class="full"><label>{L[11]} *</label><input name="password" type="password" minlength="8" required autocomplete="new-password"></div>
<div class="full"><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" name="agree" required style="width:auto"> {L[12]}</label></div></div>
<div class="msg" id="m1"></div><p><button class="btn" onclick="start()">{L[13]}</button></p></form>
<form id="f2" class="card" style="display:none" onsubmit="return false"><label>{L[14]}</label><input name="code" inputmode="numeric" autocomplete="one-time-code" style="max-width:200px;font-size:1.3rem;letter-spacing:.2em"><div class="msg" id="m2"></div><p><button class="btn" onclick="verify()">{L[15]}</button></p></form>
<div id="done" class="card" style="display:none"><h2 style="margin-top:0">{L[16]} 🎉</h2><p id="done-t"></p><p><a id="done-a" class="btn g" href="#">{L[17]}</a></p></div>
<h2>{'What you get' if lang == 'en' else 'നിങ്ങൾക്ക് ലഭിക്കുന്നത്'}</h2><div class="grid">{_services_html(lang)}</div>
<script>
function slugify(v){{return v.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,31)}}
let ticket='';
async function call(url,body){{const r=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json','X-Club':'1'}},body:JSON.stringify(body)}});const j=await r.json().catch(()=>({{}}));if(!r.ok)throw new Error(j.error||r.statusText);return j}}
function show(id,msg,ok){{const el=document.getElementById(id);el.textContent=msg;el.className='msg'+(ok?' ok':'');el.style.display='block'}}
async function start(){{const f=document.getElementById('f1');if(!f.reportValidity())return;const b={{}};f.querySelectorAll('[name]').forEach(el=>b[el.name]=el.type==='checkbox'?el.checked:el.value.trim());
  try{{const r=await call('/api/saas/signup/start',b);ticket=r.ticket;if(r.channel){{f.style.display='none';document.getElementById('f2').style.display='';}}else{{await verify();}}}}catch(e){{show('m1',e.message)}}}}
async function verify(){{try{{const r=await call('/api/saas/signup/verify',{{ticket,code:(document.querySelector('[name=code]').value||'').trim()}});document.getElementById('f1').style.display='none';document.getElementById('f2').style.display='none';const d=document.getElementById('done');d.style.display='';
  document.getElementById('done-t').textContent='{L[17]} '+r.login+(r.url?' · '+r.url:'');const a=document.getElementById('done-a');a.href=r.url||'/';}}catch(e){{show('m2',e.message)}}}}
</script>"""
    return _page(lang, L[13], body)
