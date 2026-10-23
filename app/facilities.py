"""Club assets with a lending register, and facilities (hall, ground, equipment sets) with bookings."""
import datetime as dt
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from . import comms, db, i18n
from .auth import can, current_user, require

router = APIRouter(prefix="/api")
ASSET_CATEGORIES = ["sports", "music", "furniture", "sound_light", "kitchen", "electrical", "books_misc", "other"]
BOOKING_STATUSES = ["requested", "confirmed", "cancelled", "done"]


# ---------- assets ----------
@router.get("/assets")
def list_assets(q: str = "", category: str = "", user=Depends(current_user)):
    where, args = ["a.active=1"], []
    if can(user, "library.manage") or can(user, "finance.view"):
        where = ["1=1"]
    if q:
        like = f"%{q.strip()}%"; where.append("(a.name_en LIKE ? OR a.name_ml LIKE ? OR a.code LIKE ?)"); args += [like] * 3
    if category:
        where.append("a.category=?"); args.append(category)
    rows = db.q(f"SELECT a.*, COALESCE((SELECT SUM(qty) FROM asset_loans l WHERE l.asset_id=a.id AND l.returned_on=''),0) AS out FROM assets a WHERE {' AND '.join(where)} ORDER BY a.category, a.name_en", args)
    for r in rows:
        r["available"] = r["qty"] - r["out"]
    return rows


@router.get("/assets/{aid}")
def get_asset(aid: int, user=Depends(current_user)):
    a = db.one("SELECT * FROM assets WHERE id=?", (aid,))
    if not a:
        raise HTTPException(404)
    a["loans"] = db.q("SELECT l.*, m.name_en, m.name_ml, m.member_no, m.phone AS member_phone FROM asset_loans l LEFT JOIN members m ON m.id=l.member_id WHERE l.asset_id=? ORDER BY l.returned_on='' DESC, l.id DESC LIMIT 100", (aid,))
    a["out"] = sum(l["qty"] for l in a["loans"] if not l["returned_on"])
    a["available"] = a["qty"] - a["out"]
    return a


@router.post("/assets")
async def save_asset(request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    row = {"name_en": b.get("name_en") or b.get("name_ml") or "", "name_ml": b.get("name_ml") or "", "category": b.get("category") if b.get("category") in ASSET_CATEGORIES else "other",
           "qty": max(0, int(b.get("qty") or 1)), "location": b.get("location") or "", "condition": b.get("condition") or "good", "purchased_on": b.get("purchased_on") or "",
           "cost": float(b.get("cost") or 0), "notes": b.get("notes") or "", "active": 1 if b.get("active", 1) else 0, "updated": time.time()}
    if not row["name_en"]:
        raise HTTPException(400, "name")
    with db.tx() as c:
        if b.get("id"):
            if b.get("code"):
                row["code"] = b["code"]
            db.update(c, "assets", b["id"], row); aid = b["id"]
        else:
            row["code"] = (b.get("code") or "").strip() or f"{db.setting('asset_prefix')}-{db.next_counter(c, 'asset'):04d}"
            row["created"] = time.time(); aid = db.insert(c, "assets", row)
        db.audit(c, user["id"], "asset.save", "asset", aid, row["name_en"])
    return {"ok": True, "id": aid}


@router.post("/assets/{aid}/lend")
async def lend_asset(aid: int, request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    a = get_asset(aid, user)
    qty = max(1, int(b.get("qty") or 1))
    if qty > a["available"] and not b.get("override"):
        raise HTTPException(400, f"only {a['available']} available")
    if not (b.get("member_id") or b.get("party")):
        raise HTTPException(400, "member or party")
    with db.tx() as c:
        lid = db.insert(c, "asset_loans", {"asset_id": aid, "member_id": b.get("member_id") or None, "party": b.get("party") or "", "phone": b.get("phone") or "", "qty": qty,
                                           "lent_on": b.get("lent_on") or dt.date.today().isoformat(), "due_on": b.get("due_on") or "", "note": b.get("note") or "", "lent_by": user["id"], "created": time.time()})
        db.audit(c, user["id"], "asset.lend", "asset", aid, f"{qty} loan {lid}")
    return {"ok": True, "id": lid}


@router.post("/assets/loans/{lid}/return")
async def return_asset(lid: int, request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    loan = db.one("SELECT * FROM asset_loans WHERE id=? AND returned_on=''", (lid,))
    if not loan:
        raise HTTPException(404)
    with db.tx() as c:
        db.update(c, "asset_loans", lid, {"returned_on": b.get("returned_on") or dt.date.today().isoformat(), "returned_by": user["id"], "note": (loan["note"] + " " + (b.get("note") or "")).strip()})
        if b.get("condition"):
            db.update(c, "assets", loan["asset_id"], {"condition": b["condition"], "updated": time.time()})
    return {"ok": True}


@router.post("/assets/loans/remind")
def remind_asset_loans(user=Depends(require("library.manage"))):
    today = dt.date.today().isoformat()
    rows = db.q("SELECT l.*, a.name_en, a.name_ml FROM asset_loans l JOIN assets a ON a.id=l.asset_id WHERE l.returned_on='' AND l.due_on<>'' AND l.due_on<=? AND l.member_id IS NOT NULL", (today,))
    n = 0
    with db.tx() as c:
        for l in rows:
            n += comms.notify_members(c, [l["member_id"]], "asset_due", {"qty": l["qty"], "lent": l["lent_on"], "due": l["due_on"]}, ("app", "whatsapp"), ref_kind="asset", ref_id=l["asset_id"],
                                      per_member=lambda m, l=l: {"asset": i18n.pick(l, "name", m["lang"])})
    return {"ok": True, "queued": n}


# ---------- facilities & bookings ----------
@router.get("/facilities")
def list_facilities(user=Depends(current_user)):
    return db.q("SELECT * FROM facilities WHERE active=1 OR ? ORDER BY name_en", (1 if can(user, "finance.manage") else 0,))


@router.post("/facilities")
async def save_facility(request: Request, user=Depends(require("finance.manage"))):
    b = await request.json()
    row = {"name_en": b.get("name_en") or b.get("name_ml") or "", "name_ml": b.get("name_ml") or "", "description_en": b.get("description_en") or "", "description_ml": b.get("description_ml") or "",
           "rate_day": float(b.get("rate_day") or 0), "rate_hour": float(b.get("rate_hour") or 0), "deposit": float(b.get("deposit") or 0), "capacity": int(b.get("capacity") or 0), "active": 1 if b.get("active", 1) else 0}
    if not row["name_en"]:
        raise HTTPException(400, "name")
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "facilities", b["id"], row); fid = b["id"]
        else:
            row["created"] = time.time(); fid = db.insert(c, "facilities", row)
    return {"ok": True, "id": fid}


def _overlap(facility_id, starts, ends, exclude=None):
    return db.one("SELECT id FROM bookings WHERE facility_id=? AND status IN ('requested','confirmed') AND starts_at<? AND ends_at>? AND id<>?", (facility_id, ends, starts, exclude or 0))


def _estimate(f, starts, ends):
    try:
        a, b = dt.datetime.fromisoformat(starts), dt.datetime.fromisoformat(ends)
    except ValueError:
        return 0
    hours = max(0.0, (b - a).total_seconds() / 3600)
    if f["rate_hour"] and hours <= 8:
        return round(hours * f["rate_hour"])
    days = max(1, -(-int(hours) // 24)) if hours else 1
    return round(days * f["rate_day"]) if f["rate_day"] else round(hours * f["rate_hour"])


@router.get("/bookings")
def list_bookings(month: str = "", facility_id: int = 0, mine: int = 0, user=Depends(current_user)):
    where, args = ["1=1"], []
    if month:
        where.append("b.starts_at LIKE ?"); args.append(month + "%")
    if facility_id:
        where.append("b.facility_id=?"); args.append(facility_id)
    office = can(user, "finance.view")
    if mine or not office:
        where.append("b.member_id=?"); args.append(user.get("member_id") or -1)
    rows = db.q(f"SELECT b.*, f.name_en AS facility_en, f.name_ml AS facility_ml, m.name_en, m.name_ml, m.member_no FROM bookings b JOIN facilities f ON f.id=b.facility_id "
                f"LEFT JOIN members m ON m.id=b.member_id WHERE {' AND '.join(where)} ORDER BY b.starts_at DESC LIMIT 500", args)
    if not office:
        return rows
    # the calendar needs everyone's confirmed slots, without names, so members can see what is taken
    return rows


@router.get("/bookings/calendar")
def booking_calendar(month: str = "", user=Depends(current_user)):
    month = month or dt.date.today().strftime("%Y-%m")
    rows = db.q("SELECT b.id, b.facility_id, b.starts_at, b.ends_at, b.status, b.purpose, b.member_id, f.name_en AS facility_en, f.name_ml AS facility_ml FROM bookings b JOIN facilities f ON f.id=b.facility_id "
                "WHERE b.status IN ('requested','confirmed') AND b.starts_at LIKE ? ORDER BY b.starts_at", (month + "%",))
    if not can(user, "finance.view"):
        for r in rows:
            if r["member_id"] != user.get("member_id"):
                r["purpose"] = ""
    return rows


@router.post("/bookings")
async def save_booking(request: Request, user=Depends(current_user)):
    b = await request.json()
    office = can(user, "finance.manage")
    f = db.one("SELECT * FROM facilities WHERE id=? AND active=1", (b.get("facility_id"),))
    if not f:
        raise HTTPException(404, "facility")
    starts, ends = (b.get("starts_at") or "")[:16], (b.get("ends_at") or "")[:16]
    if not starts or not ends or ends <= starts:
        raise HTTPException(400, "start must be before end")
    if _overlap(f["id"], starts, ends, b.get("id")):
        raise HTTPException(409, "that slot is already booked")
    now = time.time()
    with db.tx() as c:
        if b.get("id"):
            bk = db.one("SELECT * FROM bookings WHERE id=?", (b["id"],))
            if not bk or not (office or bk["member_id"] == user.get("member_id")):
                raise HTTPException(403, "no")
            row = {"starts_at": starts, "ends_at": ends, "purpose": b.get("purpose") or bk["purpose"], "updated": now}
            if office:
                row.update({"amount": float(b.get("amount") if b.get("amount") not in (None, "") else bk["amount"]), "deposit": float(b.get("deposit") or bk["deposit"]), "note": b.get("note") or bk["note"],
                            "party": b.get("party") or bk["party"], "phone": b.get("phone") or bk["phone"]})
            db.update(c, "bookings", b["id"], row); bid = b["id"]
        else:
            member_id = (b.get("member_id") if office else None) or user.get("member_id")
            if not member_id and not b.get("party"):
                raise HTTPException(400, "member or party")
            row = {"facility_id": f["id"], "member_id": member_id, "party": b.get("party") or "", "phone": b.get("phone") or "", "purpose": b.get("purpose") or "", "starts_at": starts, "ends_at": ends,
                   "amount": float(b.get("amount")) if office and b.get("amount") not in (None, "") else _estimate(f, starts, ends), "deposit": float(b.get("deposit") or f["deposit"]),
                   "status": "confirmed" if office and b.get("confirm") else "requested", "note": b.get("note") or "", "created_by": user["id"], "created": now, "updated": now}
            bid = db.insert(c, "bookings", row)
            if not office:
                officers = [r["member_id"] for r in db.q("SELECT member_id FROM users WHERE role IN ('admin','secretary','treasurer') AND member_id IS NOT NULL AND active=1")]
                for o in officers:
                    comms.queue(c, "app", "", f"Booking request: {f['name_en']}", f"{starts} - {ends} · {row['purpose']}", member_id=o, ref_kind="bookings")
        db.audit(c, user["id"], "booking.save", "booking", bid, f"{f['name_en']} {starts}")
    return {"ok": True, "id": bid, "amount": row.get("amount")}


@router.post("/bookings/{bid}/status")
async def booking_status(bid: int, request: Request, user=Depends(current_user)):
    b = await request.json()
    bk = db.one("SELECT b.*, f.name_en AS facility_en, f.name_ml AS facility_ml FROM bookings b JOIN facilities f ON f.id=b.facility_id WHERE b.id=?", (bid,))
    if not bk:
        raise HTTPException(404)
    st = b.get("status")
    office = can(user, "finance.manage")
    if not office and not (bk["member_id"] == user.get("member_id") and st == "cancelled"):
        raise HTTPException(403, "no")
    if st not in BOOKING_STATUSES:
        raise HTTPException(400, "status")
    now = time.time()
    with db.tx() as c:
        row = {"status": st, "updated": now}
        if b.get("note"):
            row["note"] = b["note"]
        receipt = None
        if st == "confirmed" and b.get("collect") and bk["amount"] and not bk["receipt_id"]:
            from . import finance
            receipt = finance.record(c, user["id"], {"kind": "receipt", "head": "other_income", "member_id": bk["member_id"], "party": bk["party"], "amount": bk["amount"],
                                                     "mode": b.get("mode") or "cash", "ref": b.get("ref") or "", "note": f"{bk['facility_en']} {bk['starts_at']}"}, notify=False)
            row["receipt_id"] = receipt["id"]
        db.update(c, "bookings", bid, row)
        if bk["member_id"] and st in ("confirmed", "cancelled") and bk["status"] != st:
            comms.notify_members(c, [bk["member_id"]], "booking_confirmed" if st == "confirmed" else "booking_cancelled",
                                 {"starts": bk["starts_at"].replace("T", " "), "ends": bk["ends_at"].replace("T", " "), "amount": f"{bk['amount']:,.0f}", "note": b.get("note") or ""},
                                 ("app", "whatsapp"), ref_kind="bookings", ref_id=bid, per_member=lambda m: {"facility": i18n.pick(bk, "facility", m["lang"])})
        db.audit(c, user["id"], f"booking.{st}", "booking", bid)
    return {"ok": True, "receipt": receipt}
