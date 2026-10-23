"""Membership: self-registration, approval and the membership number, member records, family members, the
members' directory and audience selection for broadcasts."""
import csv
import datetime as dt
import io
import json
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import File, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from . import auth, comms, db, i18n
from .auth import can, current_user, require

router = APIRouter(prefix="/api")
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
RELATIONS = ["spouse", "son", "daughter", "father", "mother", "brother", "sister", "grandson", "granddaughter", "grandfather", "grandmother", "other"]
STATUSES = ["applied", "active", "inactive", "suspended", "resigned", "deceased", "rejected"]
EDITABLE = ["name_en", "name_ml", "gender", "dob", "blood_group", "phone", "whatsapp", "email", "house_en", "house_ml", "address_en", "address_ml",
            "ward", "pincode", "occupation", "education", "interests", "id_proof", "photo", "notify_whatsapp", "notify_sms", "notify_email", "show_phone", "lang"]
ADMIN_ONLY = ["membership_type", "notes", "joined_on", "introduced_by"]
INTS = {"notify_whatsapp", "notify_sms", "notify_email", "show_phone"}


def clean(b, fields):
    out = {}
    for k in fields:
        if k in b:
            v = b[k]
            if k in INTS:
                v = 1 if v in (1, True, "1", "true", "on") else 0
            elif k == "phone" or k == "whatsapp":
                v = "".join(ch for ch in str(v or "") if ch.isdigit() or ch == "+")
            elif k == "lang":
                v = v if v in ("en", "ml") else "ml"
            else:
                v = (str(v) if v is not None else "").strip()
            out[k] = v
    return out


def phone_key(p):
    d = "".join(ch for ch in (p or "") if ch.isdigit())
    return d[-10:]


def _dup(phone, email, exclude=None):
    pk = phone_key(phone)
    for r in db.q("SELECT id, phone, email, status FROM members WHERE status NOT IN ('rejected')"):
        if exclude and r["id"] == exclude:
            continue
        if pk and phone_key(r["phone"]) == pk:
            return "phone already registered"
        if email and r["email"] and r["email"].lower() == email.lower():
            return "e-mail already registered"
    return ""


def issue_member_no(c):
    s = db.settings_all()
    year = dt.date.today().year
    key = f"member_no:{year}" if s["member_no_yearly"] == "1" else "member_no"
    seq = db.next_counter(c, key)
    return s["member_no_format"].format(prefix=s["member_no_prefix"], year=year, yy=str(year)[2:], seq=seq)


def _log(c, member_id, user_id, kind, text=""):
    db.insert(c, "member_log", {"member_id": member_id, "ts": time.time(), "user_id": user_id, "kind": kind, "text": text})


# ---------- public self-registration ----------
@router.post("/public/apply")
async def apply(request: Request):
    if db.setting("public_registration") != "1":
        raise HTTPException(403, "registration is closed")
    b = await request.json()
    row = clean(b, EDITABLE + ["membership_type"])
    if not row.get("name_en") or len(phone_key(row.get("phone"))) != 10:
        raise HTTPException(400, "name and a 10-digit phone are required")
    pw = b.get("password") or ""
    if len(pw) < 8:
        raise HTTPException(400, "choose a password of at least 8 characters")
    if (d := _dup(row["phone"], row.get("email"))):
        raise HTTPException(409, d)
    types = {t["key"] for t in db.setting_json("membership_types", [])}
    if row.get("membership_type") not in types:
        row["membership_type"] = "ordinary"
    now = time.time()
    row.update({"status": "applied", "applied_at": now, "created": now, "updated": now})
    lang = row.get("lang") or db.setting("default_lang")
    with db.tx() as c:
        mid = db.insert(c, "members", row)
        login = phone_key(row["phone"])
        db.insert(c, "users", {"login": login, "name": row["name_en"], "role": "member", "pw_hash": auth.hash_pw(pw), "active": 0,
                               "member_id": mid, "created": now, "lang": lang})
        for f in b.get("family") or []:
            fr = clean(f, ["name_en", "name_ml", "relation", "gender", "dob", "phone", "blood_group", "education", "occupation", "notes"])
            if fr.get("name_en"):
                fr.update({"member_id": mid, "created": now, "updated": now})
                db.insert(c, "family", fr)
        _log(c, mid, None, "applied", "self-registration")
        comms.notify_contact(c, row["phone"], row.get("email"), "application_received", {"name": row["name_en"] if lang == "en" else (row.get("name_ml") or row["name_en"])},
                             lang, ("whatsapp", "sms", "email"), ref_kind="member", ref_id=mid)
        officers = [r["member_id"] for r in db.q("SELECT member_id FROM users WHERE role IN ('admin','secretary','president') AND member_id IS NOT NULL AND active=1")]
        for o in officers:
            comms.queue(c, "app", "", "New membership application", f"{row['name_en']} ({row['phone']})", member_id=o, ref_kind="applications")
    return {"ok": True, "id": mid}


# ---------- lists ----------
def _member_rows(where="1=1", args=(), order="m.name_en"):
    return db.q(f"SELECT m.*, (SELECT COUNT(*) FROM family f WHERE f.member_id=m.id AND f.deleted=0) AS family_count, "
                f"(SELECT COUNT(*) FROM issues i WHERE i.member_id=m.id AND i.returned_on='') AS books_out, "
                f"(SELECT COALESCE(SUM(amount-paid),0) FROM subscriptions s WHERE s.member_id=m.id AND s.status='due') AS dues "
                f"FROM members m WHERE {where} ORDER BY {order}", args)


@router.get("/members")
def list_members(status: str = "", q: str = "", ward: str = "", mtype: str = "", blood: str = "", user=Depends(require("members.view"))):
    where, args = ["1=1"], []
    if status:
        where.append("m.status=?"); args.append(status)
    if ward:
        where.append("m.ward=?"); args.append(ward)
    if mtype:
        where.append("m.membership_type=?"); args.append(mtype)
    if blood:
        where.append("m.blood_group=?"); args.append(blood)
    if q:
        like = f"%{q.strip()}%"
        where.append("(m.name_en LIKE ? OR m.name_ml LIKE ? OR m.phone LIKE ? OR m.member_no LIKE ? OR m.house_en LIKE ? OR m.email LIKE ?)")
        args += [like] * 6
    rows = _member_rows(" AND ".join(where), args)
    for r in rows:
        r["wa_link"] = comms.wa_link(r.get("whatsapp") or r.get("phone"))
    return rows


@router.get("/members/applications")
def applications(user=Depends(require("members.manage"))):
    rows = _member_rows("m.status='applied'", (), "m.applied_at")
    for r in rows:
        r["family"] = db.q("SELECT * FROM family WHERE member_id=? AND deleted=0", (r["id"],))
    return rows


@router.get("/members/directory")
def directory(q: str = "", blood: str = "", user=Depends(current_user)):
    """What any signed-in member may see of the others: name, ward, house, blood group and phone if they allow it."""
    if not user.get("member_id") and not can(user, "members.view"):
        raise HTTPException(403, "members only")
    where, args = ["status='active'"], []
    if blood:
        where.append("blood_group=?"); args.append(blood)
    if q:
        like = f"%{q.strip()}%"
        where.append("(name_en LIKE ? OR name_ml LIKE ? OR house_en LIKE ? OR house_ml LIKE ? OR ward LIKE ?)"); args += [like] * 5
    rows = db.q(f"SELECT id, member_no, name_en, name_ml, house_en, house_ml, ward, blood_group, phone, whatsapp, show_phone, photo, membership_type, occupation "
                f"FROM members WHERE {' AND '.join(where)} ORDER BY name_en", args)
    for r in rows:
        if not r["show_phone"]:
            r["phone"], r["whatsapp"] = "", ""
        r["wa_link"] = comms.wa_link(r.get("whatsapp") or r.get("phone"))
    return rows


@router.get("/members/{mid}")
def get_member(mid: int, user=Depends(current_user)):
    if not (can(user, "members.view") or user.get("member_id") == mid):
        raise HTTPException(403, "no")
    m = db.one("SELECT * FROM members WHERE id=?", (mid,))
    if not m:
        raise HTTPException(404)
    m["family"] = db.q("SELECT * FROM family WHERE member_id=? AND deleted=0 ORDER BY id", (mid,))
    m["log"] = db.q("SELECT l.*, u.name AS by_name FROM member_log l LEFT JOIN users u ON u.id=l.user_id WHERE l.member_id=? ORDER BY l.id DESC LIMIT 50", (mid,))
    m["committees"] = db.q("SELECT cm.*, c.name_en AS committee_en, c.name_ml AS committee_ml FROM committee_members cm JOIN committees c ON c.id=cm.committee_id WHERE cm.member_id=? AND cm.active=1", (mid,))
    m["subscriptions"] = db.q("SELECT * FROM subscriptions WHERE member_id=? ORDER BY year DESC", (mid,))
    m["receipts"] = db.q("SELECT * FROM transactions WHERE member_id=? AND void=0 ORDER BY tx_date DESC, id DESC LIMIT 50", (mid,))
    m["issues"] = db.q("SELECT i.*, b.title_en, b.title_ml, c.accession_no FROM issues i JOIN books b ON b.id=i.book_id JOIN copies c ON c.id=i.copy_id WHERE i.member_id=? ORDER BY i.id DESC LIMIT 50", (mid,))
    m["registrations"] = db.q("SELECT r.*, p.title_en, p.title_ml, p.starts_at FROM registrations r JOIN posts p ON p.id=r.post_id WHERE r.member_id=? ORDER BY r.id DESC LIMIT 50", (mid,))
    m["user"] = db.one("SELECT id, login, role, active, last_login FROM users WHERE member_id=?", (mid,))
    m["wa_link"] = comms.wa_link(m.get("whatsapp") or m.get("phone"))
    return m


@router.post("/members")
async def create_member(request: Request, user=Depends(require("members.manage"))):
    """Office entry of a member (e.g. migrating the old register). Approved straight away; number issued unless given."""
    b = await request.json()
    row = clean(b, EDITABLE + ADMIN_ONLY)
    if not row.get("name_en"):
        raise HTTPException(400, "name is required")
    if row.get("phone") and (d := _dup(row["phone"], row.get("email"))):
        raise HTTPException(409, d)
    now = time.time()
    row.update({"status": "active", "applied_at": now, "approved_at": now, "approved_by": user["id"], "created": now, "updated": now})
    row.setdefault("joined_on", dt.date.today().isoformat())
    with db.tx() as c:
        row["member_no"] = (b.get("member_no") or "").strip() or issue_member_no(c)
        if db.one("SELECT 1 FROM members WHERE member_no=?", (row["member_no"],)):
            raise HTTPException(409, "membership number already in use")
        mid = db.insert(c, "members", row)
        pk = phone_key(row.get("phone"))
        if pk and b.get("password") and not db.one("SELECT 1 FROM users WHERE login=?", (pk,)):
            db.insert(c, "users", {"login": pk, "name": row["name_en"], "role": "member", "pw_hash": auth.hash_pw(b["password"]), "active": 1,
                                   "member_id": mid, "created": now, "lang": row.get("lang") or "ml"})
        _log(c, mid, user["id"], "created", f"office entry, no {row['member_no']}")
        db.audit(c, user["id"], "member.create", "member", mid, row["member_no"])
    return {"ok": True, "id": mid, "member_no": row["member_no"]}


@router.put("/members/{mid}")
async def update_member(mid: int, request: Request, user=Depends(current_user)):
    own = user.get("member_id") == mid
    if not (can(user, "members.manage") or own):
        raise HTTPException(403, "no")
    b = await request.json()
    row = clean(b, EDITABLE + (ADMIN_ONLY if can(user, "members.manage") else []))
    if "phone" in row and (d := _dup(row["phone"], row.get("email"), exclude=mid)):
        raise HTTPException(409, d)
    if not row:
        return {"ok": True}
    row["updated"] = time.time()
    with db.tx() as c:
        db.update(c, "members", mid, row)
        if "lang" in row:
            c.execute("UPDATE users SET lang=? WHERE member_id=?", (row["lang"], mid))
        _log(c, mid, user["id"], "updated", ", ".join(k for k in row if k != "updated"))
    return {"ok": True}


@router.post("/members/{mid}/decide")
async def decide(mid: int, request: Request, user=Depends(require("members.manage"))):
    """Approve (issues the membership number, activates sign-in, tells the member) or reject an application."""
    b = await request.json()
    m = db.one("SELECT * FROM members WHERE id=?", (mid,))
    if not m or m["status"] != "applied":
        raise HTTPException(400, "not a pending application")
    decision, note = b.get("decision"), (b.get("note") or "").strip()
    now = time.time()
    with db.tx() as c:
        if decision == "approve":
            no = (b.get("member_no") or "").strip() or issue_member_no(c)
            if db.one("SELECT 1 FROM members WHERE member_no=?", (no,)):
                raise HTTPException(409, "membership number already in use")
            row = {"status": "active", "member_no": no, "approved_at": now, "approved_by": user["id"], "decision_note": note, "updated": now,
                   "joined_on": b.get("joined_on") or dt.date.today().isoformat()}
            if b.get("membership_type"):
                row["membership_type"] = b["membership_type"]
            db.update(c, "members", mid, row)
            c.execute("UPDATE users SET active=1 WHERE member_id=?", (mid,))
            _log(c, mid, user["id"], "approved", f"membership no {no}")
            comms.notify_members(c, [mid], "application_approved", {}, ("whatsapp", "sms", "email", "app"), ref_kind="member", ref_id=mid, created_by=user["id"])
            # admission fee + current year's subscription become due
            from . import finance
            finance.create_dues_for(c, mid, m["membership_type"] if not b.get("membership_type") else b["membership_type"])
            db.audit(c, user["id"], "member.approve", "member", mid, no)
            return {"ok": True, "member_no": no}
        if decision == "reject":
            db.update(c, "members", mid, {"status": "rejected", "decision_note": note, "updated": now, "approved_by": user["id"], "approved_at": now})
            c.execute("UPDATE users SET active=0 WHERE member_id=?", (mid,))
            _log(c, mid, user["id"], "rejected", note)
            comms.notify_members(c, [mid], "application_rejected", {"note": note}, ("whatsapp", "sms", "email"), ref_kind="member", ref_id=mid, created_by=user["id"])
            db.audit(c, user["id"], "member.reject", "member", mid, note)
            return {"ok": True}
    raise HTTPException(400, "decision must be approve or reject")


@router.post("/members/{mid}/status")
async def set_status(mid: int, request: Request, user=Depends(require("members.manage"))):
    b = await request.json()
    st, note = b.get("status"), (b.get("note") or "").strip()
    if st not in STATUSES or st in ("applied", "rejected"):
        raise HTTPException(400, "status")
    with db.tx() as c:
        db.update(c, "members", mid, {"status": st, "updated": time.time()})
        c.execute("UPDATE users SET active=? WHERE member_id=? AND role='member'", (1 if st == "active" else 0, mid))
        if st != "active":
            c.execute("DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE member_id=? AND role='member')", (mid,))
        _log(c, mid, user["id"], f"status:{st}", note)
        db.audit(c, user["id"], "member.status", "member", mid, f"{st} {note}")
    return {"ok": True}


@router.post("/members/{mid}/reset-password")
async def reset_password(mid: int, request: Request, user=Depends(require("members.manage"))):
    b = await request.json()
    pw = b.get("password") or ""
    if len(pw) < 8:
        raise HTTPException(400, "at least 8 characters")
    m = db.one("SELECT * FROM members WHERE id=?", (mid,))
    with db.tx() as c:
        u = db.one("SELECT id FROM users WHERE member_id=?", (mid,))
        if u:
            c.execute("UPDATE users SET pw_hash=?, active=? WHERE id=?", (auth.hash_pw(pw), 1 if m["status"] == "active" else 0, u["id"]))
            c.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
        else:
            pk = phone_key(m["phone"]) or (m["email"] or "").lower()
            if not pk:
                raise HTTPException(400, "member has no phone or e-mail to sign in with")
            db.insert(c, "users", {"login": pk, "name": m["name_en"], "role": "member", "pw_hash": auth.hash_pw(pw), "active": 1 if m["status"] == "active" else 0,
                                   "member_id": mid, "created": time.time(), "lang": m["lang"]})
        _log(c, mid, user["id"], "password-reset")
    return {"ok": True}


# ---------- family ----------
FAMILY_FIELDS = ["name_en", "name_ml", "relation", "gender", "dob", "phone", "blood_group", "education", "occupation", "notes"]


def _family_access(user, mid):
    if not (can(user, "members.manage") or user.get("member_id") == mid):
        raise HTTPException(403, "no")


@router.get("/members/{mid}/family")
def list_family(mid: int, user=Depends(current_user)):
    if not (can(user, "members.view") or user.get("member_id") == mid):
        raise HTTPException(403, "no")
    return db.q("SELECT * FROM family WHERE member_id=? AND deleted=0 ORDER BY id", (mid,))


@router.post("/members/{mid}/family")
async def save_family(mid: int, request: Request, user=Depends(current_user)):
    _family_access(user, mid)
    b = await request.json()
    row = clean(b, FAMILY_FIELDS)
    if not row.get("name_en"):
        raise HTTPException(400, "name is required")
    if row.get("relation") and row["relation"] not in RELATIONS:
        row["relation"] = "other"
    row["updated"] = time.time()
    with db.tx() as c:
        if b.get("id"):
            if not db.one("SELECT 1 FROM family WHERE id=? AND member_id=?", (b["id"], mid)):
                raise HTTPException(404)
            if not can(user, "members.manage"):
                row["verified"] = 0
            db.update(c, "family", b["id"], row)
            fid = b["id"]
            _log(c, mid, user["id"], "family-updated", row["name_en"])
        else:
            row.update({"member_id": mid, "created": time.time(), "verified": 1 if can(user, "members.manage") else 0})
            fid = db.insert(c, "family", row)
            _log(c, mid, user["id"], "family-added", row["name_en"])
    return {"ok": True, "id": fid}


@router.delete("/members/{mid}/family/{fid}")
def delete_family(mid: int, fid: int, user=Depends(current_user)):
    _family_access(user, mid)
    with db.tx() as c:
        c.execute("UPDATE family SET deleted=1, updated=? WHERE id=? AND member_id=?", (time.time(), fid, mid))
        _log(c, mid, user["id"], "family-removed", str(fid))
    return {"ok": True}


@router.post("/members/{mid}/family/{fid}/verify")
def verify_family(mid: int, fid: int, user=Depends(require("members.manage"))):
    with db.tx() as c:
        c.execute("UPDATE family SET verified=1 WHERE id=? AND member_id=?", (fid, mid))
    return {"ok": True}


# ---------- audiences for broadcasts and notices ----------
def audience_ids(a):
    """a = {"kind": "all"|"ward"|"type"|"committee"|"post"|"blood"|"members", "value": ...}. Active members only."""
    kind, value = a.get("kind", "all"), a.get("value")
    if kind == "members":
        ids = [int(x) for x in (value or [])]
        if not ids:
            return []
        marks = ",".join("?" for _ in ids)
        return [r["id"] for r in db.q(f"SELECT id FROM members WHERE status='active' AND id IN ({marks})", ids)]
    if kind == "ward":
        return [r["id"] for r in db.q("SELECT id FROM members WHERE status='active' AND ward=?", (value,))]
    if kind == "type":
        return [r["id"] for r in db.q("SELECT id FROM members WHERE status='active' AND membership_type=?", (value,))]
    if kind == "blood":
        return [r["id"] for r in db.q("SELECT id FROM members WHERE status='active' AND blood_group=?", (value,))]
    if kind == "committee":
        return [r["member_id"] for r in db.q("SELECT cm.member_id FROM committee_members cm JOIN members m ON m.id=cm.member_id WHERE cm.committee_id=? AND cm.active=1 AND m.status='active'", (value,))]
    if kind == "post":
        return [r["member_id"] for r in db.q("SELECT DISTINCT r.member_id FROM registrations r JOIN members m ON m.id=r.member_id WHERE r.post_id=? AND r.status<>'cancelled' AND m.status='active'", (value,))]
    if kind == "dues":
        return [r["member_id"] for r in db.q("SELECT DISTINCT s.member_id FROM subscriptions s JOIN members m ON m.id=s.member_id WHERE s.status='due' AND m.status='active'")]
    return [r["id"] for r in db.q("SELECT id FROM members WHERE status='active'")]


# ---------- exports and the card ----------
@router.get("/members/export/csv")
def export_csv(user=Depends(require("members.view"))):
    rows = db.q("SELECT member_no, name_en, name_ml, gender, dob, blood_group, phone, whatsapp, email, house_en, address_en, ward, pincode, occupation, "
                "membership_type, status, joined_on FROM members WHERE status<>'rejected' ORDER BY member_no")
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    if rows:
        w.writerow(rows[0].keys())
        for r in rows:
            w.writerow(r.values())
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=members.csv"})


@router.get("/members/export/family.csv")
def export_family_csv(user=Depends(require("members.view"))):
    rows = db.q("SELECT m.member_no, m.name_en AS member, f.name_en, f.name_ml, f.relation, f.gender, f.dob, f.phone, f.blood_group, f.education, f.occupation "
                "FROM family f JOIN members m ON m.id=f.member_id WHERE f.deleted=0 AND m.status='active' ORDER BY m.member_no, f.id")
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    if rows:
        w.writerow(rows[0].keys())
        for r in rows:
            w.writerow(r.values())
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=family.csv"})


@router.get("/members/{mid}/card", response_class=HTMLResponse)
def member_card(mid: int, request: Request, lang: str = "ml"):
    user = auth.user_from_request(request)
    if not user or not (can(user, "members.view") or user.get("member_id") == mid):
        raise HTTPException(401, "sign in")
    m = db.one("SELECT * FROM members WHERE id=? AND status='active'", (mid,))
    if not m:
        raise HTTPException(404)
    s = db.settings_all()
    import html as _h
    import segno
    e = _h.escape
    qr = segno.make(f"MEMBER:{m['member_no']}|{m['name_en']}", error="m").svg_data_uri(scale=3, border=1)
    name = e(i18n.pick(m, "name", lang))
    club = e(s["club_name_ml" if lang == "ml" else "club_name_en"])
    place = e(s["club_place_ml" if lang == "ml" else "club_place_en"])
    types = {t["key"]: t for t in json.loads(s["membership_types"])}
    mtype = e(types.get(m["membership_type"], {}).get(lang) or m["membership_type"])
    photo = f"<img class='photo' src='/uploads/{e(m['photo'])}'>" if m["photo"] else "<div class='photo'></div>"
    m = {**m, "member_no": e(m["member_no"] or ""), "blood_group": e(m["blood_group"]), "joined_on": e(m["joined_on"])}
    s = {**s, "club_phone": e(s["club_phone"])}
    lbl = {"en": ("Membership No", "Blood group", "Valid member of", "Joined"), "ml": ("അംഗത്വ നമ്പർ", "രക്തഗ്രൂപ്പ്", "അംഗം", "ചേർന്ന തീയതി")}[lang if lang in ("en", "ml") else "en"]
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{m['member_no']}</title>
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;background:#eee;margin:0;display:grid;place-items:center;min-height:100vh}}
.card{{width:85.6mm;height:54mm;background:#fff;border-radius:3mm;box-shadow:0 2px 12px #0003;position:relative;overflow:hidden;font-size:9pt;color:#222}}
.band{{background:#0F4C45;color:#fff;padding:3mm 4mm;font-weight:700;font-size:9.5pt;line-height:1.2}}
.band small{{display:block;font-weight:400;opacity:.85;font-size:7.5pt}}
.photo{{position:absolute;left:4mm;top:15mm;width:20mm;height:24mm;object-fit:cover;background:#ddd;border-radius:1.5mm}}
.body{{position:absolute;left:27mm;top:15mm;right:4mm}} .n{{font-weight:700;font-size:11pt}} .k{{color:#777;font-size:7pt;margin-top:1.5mm}}
.qr{{position:absolute;right:4mm;bottom:3mm;width:16mm}} .foot{{position:absolute;left:4mm;bottom:3mm;font-size:7pt;color:#777}}
@media print{{body{{background:#fff}}.card{{box-shadow:none;border:.2mm solid #999}}}}</style></head>
<body><div class="card"><div class="band">{club}<small>{place}</small></div>{photo}
<div class="body"><div class="n">{name}</div><div>{mtype}</div>
<div class="k">{lbl[0]}</div><div><b>{m['member_no']}</b></div>
<div class="k">{lbl[1]} · {lbl[3]}</div><div>{m['blood_group'] or '-'} · {m['joined_on'] or '-'}</div></div>
<img class="qr" src="{qr}"><div class="foot">{s['club_phone']}</div></div>
<script>setTimeout(()=>window.print(),400)</script></body></html>"""


# ---------- batch cards ----------
def _card_html(m, s, lang, types):
    import html as _h
    import segno
    e = _h.escape
    qr = segno.make(f"MEMBER:{m['member_no']}|{m['name_en']}", error="m").svg_data_uri(scale=3, border=1)
    name = e(i18n.pick(m, "name", lang))
    club = e(s["club_name_ml" if lang == "ml" else "club_name_en"])
    place = e(s["club_place_ml" if lang == "ml" else "club_place_en"])
    mtype = e(types.get(m["membership_type"], {}).get(lang) or m["membership_type"])
    photo = f"<img class='photo' src='/uploads/{e(m['photo'])}'>" if m["photo"] else "<div class='photo'></div>"
    m = {**m, "member_no": e(m["member_no"] or ""), "blood_group": e(m["blood_group"]), "joined_on": e(m["joined_on"])}
    s = {**s, "club_phone": e(s["club_phone"])}
    lbl = {"en": ("Membership No", "Blood group", "Joined"), "ml": ("അംഗത്വ നമ്പർ", "രക്തഗ്രൂപ്പ്", "ചേർന്ന തീയതി")}[lang]
    return f"""<div class="card"><div class="band">{club}<small>{place}</small></div>{photo}
<div class="body"><div class="n">{name}</div><div>{mtype}</div><div class="k">{lbl[0]}</div><div><b>{m['member_no']}</b></div>
<div class="k">{lbl[1]} · {lbl[2]}</div><div>{m['blood_group'] or '-'} · {m['joined_on'] or '-'}</div></div><img class="qr" src="{qr}"><div class="foot">{s['club_phone']}</div></div>"""


CARD_CSS = """body{font-family:Inter,Manjari,sans-serif;background:#eee;margin:0;padding:8mm}.sheet{display:grid;grid-template-columns:repeat(2,85.6mm);gap:6mm;justify-content:center}
.card{width:85.6mm;height:54mm;background:#fff;border-radius:3mm;box-shadow:0 2px 12px #0003;position:relative;overflow:hidden;font-size:9pt;color:#222;page-break-inside:avoid}
.band{background:#0F4C45;color:#fff;padding:3mm 4mm;font-weight:700;font-size:9.5pt;line-height:1.2}.band small{display:block;font-weight:400;opacity:.85;font-size:7.5pt}
.photo{position:absolute;left:4mm;top:15mm;width:20mm;height:24mm;object-fit:cover;background:#ddd;border-radius:1.5mm}.body{position:absolute;left:27mm;top:15mm;right:4mm}
.n{font-weight:700;font-size:11pt}.k{color:#777;font-size:7pt;margin-top:1.5mm}.qr{position:absolute;right:4mm;bottom:3mm;width:16mm}.foot{position:absolute;left:4mm;bottom:3mm;font-size:7pt;color:#777}
@media print{body{background:#fff;padding:0}.card{box-shadow:none;border:.2mm solid #999}}"""


@router.get("/members/print/cards", response_class=HTMLResponse)
def member_cards(ids: str = "", ward: str = "", mtype: str = "", lang: str = "ml", user=Depends(require("members.view"))):
    """Many cards on A4 for batch printing: ?ids=1,2,3 or ?ward=7 or ?mtype=life (active members only)."""
    where, args = ["status='active'"], []
    if ids:
        idl = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        where.append(f"id IN ({','.join('?' for _ in idl) or '0'})"); args += idl
    if ward:
        where.append("ward=?"); args.append(ward)
    if mtype:
        where.append("membership_type=?"); args.append(mtype)
    rows = db.q(f"SELECT * FROM members WHERE {' AND '.join(where)} ORDER BY member_no", args)
    s = db.settings_all(); types = {t["key"]: t for t in json.loads(s["membership_types"])}
    lang = lang if lang in ("en", "ml") else "ml"
    cards = "".join(_card_html(m, s, lang, types) for m in rows)
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>cards</title>
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet"><style>{CARD_CSS}</style></head>
<body><div class="sheet">{cards}</div><script>setTimeout(()=>window.print(),600)</script></body></html>"""


# ---------- Excel import of an existing register ----------
IMPORT_COLS = [("member_no", "Membership No"), ("name_en", "Name (English)"), ("name_ml", "Name (Malayalam)"), ("gender", "Gender (male/female/other)"), ("dob", "Date of birth (YYYY-MM-DD)"),
               ("blood_group", "Blood group"), ("phone", "Phone"), ("whatsapp", "WhatsApp"), ("email", "E-mail"), ("house_en", "House (English)"), ("house_ml", "House (Malayalam)"),
               ("address_en", "Address"), ("ward", "Ward"), ("pincode", "PIN"), ("occupation", "Occupation"), ("education", "Education"), ("membership_type", "Membership type (key)"),
               ("joined_on", "Joined on (YYYY-MM-DD)"), ("status", "Status (active/inactive)"), ("notes", "Notes")]
FAMILY_COLS = [("member_no", "Membership No"), ("member_phone", "Member phone (if no number)"), ("name_en", "Name (English)"), ("name_ml", "Name (Malayalam)"), ("relation", "Relation"),
               ("gender", "Gender"), ("dob", "Date of birth (YYYY-MM-DD)"), ("phone", "Phone"), ("blood_group", "Blood group"), ("education", "Education"), ("occupation", "Occupation")]


@router.get("/members/import/template.xlsx")
def import_template(user=Depends(require("members.manage"))):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "Members"
    ws.append([h for _, h in IMPORT_COLS])
    ws.append(["ASC/2019/0012", "Ramesh Kumar", "രമേശ് കുമാർ", "male", "1980-05-14", "O+", "9847012345", "", "ramesh@example.org", "Kizhakkethil", "കിഴക്കേതിൽ", "", "7", "686001", "Teacher", "B.Ed", "ordinary", "2019-06-01", "active", ""])
    for c in ws[1]:
        c.font = Font(bold=True)
    ws2 = wb.create_sheet("Family"); ws2.append([h for _, h in FAMILY_COLS])
    ws2.append(["ASC/2019/0012", "", "Sita R", "സീത ആർ", "spouse", "female", "1984-01-02", "", "B+", "", ""])
    for c in ws2[1]:
        c.font = Font(bold=True)
    ws3 = wb.create_sheet("Keys"); ws3.append(["Membership type keys", "Relations", "Blood groups"])
    types = [t["key"] for t in db.setting_json("membership_types", [])]
    for i in range(max(len(types), len(RELATIONS), len(BLOOD_GROUPS))):
        ws3.append([types[i] if i < len(types) else "", RELATIONS[i] if i < len(RELATIONS) else "", BLOOD_GROUPS[i] if i < len(BLOOD_GROUPS) else ""])
    for w in (ws, ws2):
        for col in w.columns:
            w.column_dimensions[col[0].column_letter].width = 18
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=members-import.xlsx"})


def _cell(v):
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _read_sheet(ws, cols):
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [_cell(h).lower() for h in rows[0]]
    idx = {}
    for key, label in cols:
        for i, h in enumerate(header):
            if h == label.lower() or h == key or h.startswith(label.lower().split(" (")[0]):
                idx[key] = i; break
    out = []
    for n, r in enumerate(rows[1:], start=2):
        if not any(_cell(v) for v in r):
            continue
        out.append({"_row": n, **{k: _cell(r[i]) if i < len(r) else "" for k, i in idx.items()}})
    return out


@router.post("/members/import")
async def import_members(file: UploadFile = File(...), commit: int = 0, user=Depends(require("members.manage"))):
    """Preview (commit=0) or import (commit=1) the Excel register. Rows with errors are reported and never written;
    with commit=1 the valid rows are created as active members and family entries."""
    from openpyxl import load_workbook
    data = file.file.read(20 * 1024 * 1024)
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(400, "not an Excel (.xlsx) file")
    types = {t["key"] for t in db.setting_json("membership_types", [])}
    members_rows = _read_sheet(wb["Members"] if "Members" in wb.sheetnames else wb[wb.sheetnames[0]], IMPORT_COLS)
    family_rows = _read_sheet(wb["Family"], FAMILY_COLS) if "Family" in wb.sheetnames else []
    existing_no = {r["member_no"] for r in db.q("SELECT member_no FROM members WHERE member_no IS NOT NULL")}
    existing_phone = {phone_key(r["phone"]) for r in db.q("SELECT phone FROM members WHERE status<>'rejected'") if phone_key(r["phone"])}
    seen_no, seen_phone, report = set(), set(), []
    for r in members_rows:
        errs = []
        if not r.get("name_en"):
            errs.append("name missing")
        pk = phone_key(r.get("phone"))
        if r.get("phone") and len(pk) != 10:
            errs.append("phone must have 10 digits")
        if pk and (pk in existing_phone or pk in seen_phone):
            errs.append("phone already registered")
        no = r.get("member_no") or ""
        if no and (no in existing_no or no in seen_no):
            errs.append("membership number already used")
        if r.get("membership_type") and r["membership_type"] not in types:
            errs.append(f"unknown membership type '{r['membership_type']}'")
        for k in ("dob", "joined_on"):
            if r.get(k) and not re.match(r"^\d{4}-\d{2}-\d{2}$", r[k]):
                errs.append(f"{k} must be YYYY-MM-DD")
        if r.get("blood_group") and r["blood_group"].upper() not in BLOOD_GROUPS:
            errs.append("blood group")
        if r.get("status") and r["status"] not in ("active", "inactive", "suspended", "resigned", "deceased"):
            errs.append("status")
        seen_no.add(no); seen_phone.add(pk)
        report.append({"row": r["_row"], "member_no": no, "name_en": r.get("name_en", ""), "phone": r.get("phone", ""), "errors": errs})
    fam_report = []
    keys_no = {r["member_no"] for r in members_rows if r.get("member_no")} | existing_no
    keys_phone = {phone_key(r.get("phone")) for r in members_rows} | existing_phone
    for f in family_rows:
        errs = []
        if not f.get("name_en"):
            errs.append("name missing")
        if not ((f.get("member_no") and f["member_no"] in keys_no) or (phone_key(f.get("member_phone")) in keys_phone)):
            errs.append("member not found")
        fam_report.append({"row": f["_row"], "member_no": f.get("member_no", ""), "name_en": f.get("name_en", ""), "errors": errs})
    valid = [r for r, rep in zip(members_rows, report) if not rep["errors"]]
    valid_f = [f for f, rep in zip(family_rows, fam_report) if not rep["errors"]]
    out = {"members": report, "family": fam_report, "valid": len(valid), "invalid": len(report) - len(valid), "family_valid": len(valid_f), "created": 0, "family_created": 0}
    if not commit:
        return out
    now = time.time()
    with db.tx() as c:
        by_no, by_phone = {}, {}
        for r in valid:
            row = clean(r, EDITABLE + ADMIN_ONLY)
            row.pop("photo", None)
            if row.get("blood_group"):
                row["blood_group"] = row["blood_group"].upper()
            row.update({"status": r.get("status") or "active", "applied_at": now, "approved_at": now, "approved_by": user["id"], "created": now, "updated": now, "lang": db.setting("default_lang")})
            row.setdefault("membership_type", "ordinary")
            if not row.get("membership_type"):
                row["membership_type"] = "ordinary"
            row["member_no"] = r.get("member_no") or issue_member_no(c)
            mid = db.insert(c, "members", row)
            by_no[row["member_no"]] = mid
            if phone_key(row.get("phone")):
                by_phone[phone_key(row["phone"])] = mid
            _log(c, mid, user["id"], "imported", f"row {r['_row']}")
            out["created"] += 1
        for m in db.q("SELECT id, member_no, phone FROM members"):
            by_no.setdefault(m["member_no"], m["id"])
            if phone_key(m["phone"]):
                by_phone.setdefault(phone_key(m["phone"]), m["id"])
        for f in valid_f:
            mid = by_no.get(f.get("member_no")) or by_phone.get(phone_key(f.get("member_phone")))
            if not mid:
                continue
            fr = clean(f, FAMILY_FIELDS)
            if fr.get("relation") and fr["relation"] not in RELATIONS:
                fr["relation"] = "other"
            fr.update({"member_id": mid, "created": now, "updated": now, "verified": 1})
            db.insert(c, "family", fr)
            out["family_created"] += 1
        db.audit(c, user["id"], "members.import", detail=f"{out['created']} members, {out['family_created']} family")
    return out
