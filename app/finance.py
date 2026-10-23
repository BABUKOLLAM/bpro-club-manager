"""Accounts: receipts and payment vouchers by head, annual subscription dues, defaulters and summaries."""
import csv
import datetime as dt
import io
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from . import comms, db, i18n
from .auth import can, current_user, require

router = APIRouter(prefix="/api/finance")
MODES = ["cash", "upi", "bank", "cheque", "other"]


def _no(c, kind, year):
    fmt = db.setting("receipt_no_format" if kind == "receipt" else "voucher_no_format")
    seq = db.next_counter(c, f"{kind}:{year}")
    return fmt.format(year=year, yy=str(year)[2:], seq=seq)


def record(c, user_id, b, notify=True):
    """Insert a transaction inside an open tx. Returns the row. Receipts against a member settle their dues."""
    kind = b.get("kind") or "receipt"
    if kind not in ("receipt", "payment"):
        raise HTTPException(400, "kind")
    head = b.get("head") or ""
    if head not in (i18n.RECEIPT_HEADS if kind == "receipt" else i18n.PAYMENT_HEADS):
        raise HTTPException(400, "head")
    amount = float(b.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(400, "amount")
    tx_date = b.get("tx_date") or dt.date.today().isoformat()
    year = int(tx_date[:4])
    mode = b.get("mode") if b.get("mode") in MODES else "cash"
    row = {"kind": kind, "no": _no(c, kind, year), "tx_date": tx_date, "head": head, "member_id": b.get("member_id") or None, "post_id": b.get("post_id") or None,
           "party": (b.get("party") or "").strip(), "amount": amount, "mode": mode, "ref": (b.get("ref") or "").strip(), "note": (b.get("note") or "").strip(),
           "year": int(b.get("year") or year), "created_by": user_id, "created": time.time()}
    row["id"] = db.insert(c, "transactions", row)
    if kind == "receipt" and row["member_id"] and head == "subscription":
        sub = db.one("SELECT * FROM subscriptions WHERE member_id=? AND year=? ", (row["member_id"], row["year"]))
        if sub:
            paid = sub["paid"] + amount
            db.update(c, "subscriptions", sub["id"], {"paid": paid, "status": "paid" if paid >= sub["amount"] else "due", "receipt_id": row["id"]})
        else:
            db.insert(c, "subscriptions", {"member_id": row["member_id"], "year": row["year"], "amount": amount, "paid": amount, "receipt_id": row["id"], "status": "paid", "created": time.time()})
    if kind == "receipt" and row["member_id"] and head == "event_fee" and row["post_id"]:
        c.execute("UPDATE registrations SET fee_paid=1, receipt_id=? WHERE post_id=? AND member_id=?", (row["id"], row["post_id"], row["member_id"]))
    if notify and kind == "receipt" and row["member_id"]:
        comms.notify_members(c, [row["member_id"]], "receipt", {"no": row["no"], "amount": f"{amount:,.0f}", "date": tx_date}, ("app", "whatsapp", "sms"),
                             ref_kind="receipt", ref_id=row["id"], created_by=user_id, per_member=lambda m: {"head": i18n.label(i18n.HEAD_LABELS, head, m["lang"])})
        c.execute("UPDATE transactions SET notified_at=? WHERE id=?", (time.time(), row["id"]))
    db.audit(c, user_id, f"{kind}.record", "transaction", row["id"], f"{head} {amount}")
    return row


def create_dues_for(c, member_id, mtype):
    """On approval: the admission fee and the current year's subscription become due."""
    types = {t["key"]: t for t in db.setting_json("membership_types", [])}
    t = types.get(mtype) or {}
    year = dt.date.today().year
    admission, annual = float(t.get("admission") or 0), float(t.get("annual") or 0)
    if annual > 0:
        c.execute("INSERT OR IGNORE INTO subscriptions(member_id, year, amount, status, due_on, created) VALUES(?,?,?,?,?,?)",
                  (member_id, year, annual, "due", f"{year}-{int(db.setting('subscription_due_month')):02d}-30", time.time()))
    if admission > 0:
        c.execute("INSERT OR IGNORE INTO subscriptions(member_id, year, amount, status, due_on, created) VALUES(?,?,?,?,?,?)",
                  (member_id, 0, admission, "due", dt.date.today().isoformat(), time.time()))   # year 0 = admission fee


@router.get("/transactions")
def transactions(kind: str = "", head: str = "", frm: str = "", to: str = "", member_id: int = 0, user=Depends(require("finance.view"))):
    where, args = ["t.void=0"], []
    if kind:
        where.append("t.kind=?"); args.append(kind)
    if head:
        where.append("t.head=?"); args.append(head)
    if frm:
        where.append("t.tx_date>=?"); args.append(frm)
    if to:
        where.append("t.tx_date<=?"); args.append(to)
    if member_id:
        where.append("t.member_id=?"); args.append(member_id)
    rows = db.q(f"SELECT t.*, m.name_en, m.name_ml, m.member_no, u.name AS by_name FROM transactions t LEFT JOIN members m ON m.id=t.member_id LEFT JOIN users u ON u.id=t.created_by "
                f"WHERE {' AND '.join(where)} ORDER BY t.tx_date DESC, t.id DESC LIMIT 1000", args)
    totals = {"receipt": sum(r["amount"] for r in rows if r["kind"] == "receipt"), "payment": sum(r["amount"] for r in rows if r["kind"] == "payment")}
    return {"rows": rows, "totals": totals}


@router.post("/transactions")
async def add_transaction(request: Request, user=Depends(require("finance.manage"))):
    b = await request.json()
    with db.tx() as c:
        row = record(c, user["id"], b, notify=b.get("notify", True))
    return {"ok": True, "id": row["id"], "no": row["no"]}


@router.post("/transactions/{tid}/void")
async def void_transaction(tid: int, request: Request, user=Depends(require("finance.manage"))):
    note = (await request.json()).get("note") or ""
    t = db.one("SELECT * FROM transactions WHERE id=? AND void=0", (tid,))
    if not t:
        raise HTTPException(404)
    with db.tx() as c:
        db.update(c, "transactions", tid, {"void": 1, "void_note": note})
        if t["kind"] == "receipt" and t["head"] == "subscription" and t["member_id"]:
            sub = db.one("SELECT * FROM subscriptions WHERE member_id=? AND year=?", (t["member_id"], t["year"]))
            if sub:
                paid = max(0, sub["paid"] - t["amount"])
                db.update(c, "subscriptions", sub["id"], {"paid": paid, "status": "paid" if paid >= sub["amount"] else "due"})
        db.audit(c, user["id"], "transaction.void", "transaction", tid, note)
    return {"ok": True}


@router.get("/summary")
def summary(year: int = 0, user=Depends(require("finance.view"))):
    year = year or dt.date.today().year
    by_head = db.q("SELECT kind, head, SUM(amount) total, COUNT(*) n FROM transactions WHERE void=0 AND tx_date LIKE ? GROUP BY kind, head ORDER BY kind, total DESC", (f"{year}%",))
    by_month = db.q("SELECT substr(tx_date,1,7) month, kind, SUM(amount) total FROM transactions WHERE void=0 AND tx_date LIKE ? GROUP BY month, kind ORDER BY month", (f"{year}%",))
    dues = db.one("SELECT COUNT(DISTINCT member_id) members, COALESCE(SUM(amount-paid),0) amount FROM subscriptions WHERE status='due'")
    rec = sum(r["total"] for r in by_head if r["kind"] == "receipt")
    pay = sum(r["total"] for r in by_head if r["kind"] == "payment")
    return {"year": year, "by_head": by_head, "by_month": by_month, "receipts": rec, "payments": pay, "balance": rec - pay, "dues": dues,
            "years": [r["y"] for r in db.q("SELECT DISTINCT substr(tx_date,1,4) y FROM transactions ORDER BY y DESC")]}


@router.get("/dues")
def dues(year: int = 0, user=Depends(require("finance.view"))):
    where, args = ["s.status='due'", []]
    if year:
        where += " AND s.year=?"; args.append(year)
    rows = db.q(f"SELECT s.*, m.name_en, m.name_ml, m.member_no, m.phone, m.ward, m.membership_type FROM subscriptions s JOIN members m ON m.id=s.member_id "
                f"WHERE {where} AND m.status='active' ORDER BY s.year, m.name_en", args)
    for r in rows:
        r["wa_link"] = comms.wa_link(r["phone"])
    return rows


@router.post("/dues/generate")
async def generate_dues(request: Request, user=Depends(require("finance.manage"))):
    """Create the annual subscription row for every active member for a year (idempotent)."""
    b = await request.json()
    year = int(b.get("year") or dt.date.today().year)
    types = {t["key"]: float(t.get("annual") or 0) for t in db.setting_json("membership_types", [])}
    due_on = f"{year}-{int(db.setting('subscription_due_month')):02d}-30"
    n = 0
    with db.tx() as c:
        for m in db.q("SELECT id, membership_type FROM members WHERE status='active'"):
            amt = types.get(m["membership_type"], 0)
            if amt <= 0:
                continue
            cur = c.execute("INSERT OR IGNORE INTO subscriptions(member_id, year, amount, status, due_on, created) VALUES(?,?,?,?,?,?)", (m["id"], year, amt, "due", due_on, time.time()))
            n += cur.rowcount
        db.audit(c, user["id"], "dues.generate", detail=f"{year}: {n}")
    return {"ok": True, "created": n}


@router.post("/dues/remind")
async def remind_dues(request: Request, user=Depends(require("finance.manage"))):
    b = await request.json()
    channels = b.get("channels") or ["app", "whatsapp", "sms"]
    rows = db.q("SELECT s.*, m.id AS mid FROM subscriptions s JOIN members m ON m.id=s.member_id WHERE s.status='due' AND s.year>0 AND m.status='active'")
    by_member = {}
    for r in rows:
        by_member.setdefault(r["mid"], []).append(r)
    n = 0
    with db.tx() as c:
        for mid, subs in by_member.items():
            n += comms.notify_members(c, [mid], "subscription_due", {"year": ", ".join(str(s["year"]) for s in subs), "amount": f"{sum(s['amount'] - s['paid'] for s in subs):,.0f}"},
                                      channels, ref_kind="subscription", ref_id=subs[0]["id"], batch_id=comms.new_batch(), created_by=user["id"])
        c.execute("UPDATE subscriptions SET reminded_at=? WHERE status='due'", (time.time(),))
    return {"ok": True, "members": len(by_member), "queued": n}


@router.get("/mine")
def my_payments(user=Depends(current_user)):
    mid = user.get("member_id")
    if not mid:
        return {"dues": [], "receipts": []}
    return {"dues": db.q("SELECT * FROM subscriptions WHERE member_id=? AND status='due' ORDER BY year", (mid,)),
            "receipts": db.q("SELECT * FROM transactions WHERE member_id=? AND kind='receipt' AND void=0 ORDER BY tx_date DESC, id DESC LIMIT 100", (mid,)),
            "claims": db.q("SELECT * FROM payment_claims WHERE member_id=? ORDER BY id DESC LIMIT 20", (mid,)), "upi": bool(db.setting("upi_id"))}


@router.get("/export.csv")
def export_csv(year: int = 0, user=Depends(require("finance.view"))):
    year = year or dt.date.today().year
    rows = db.q("SELECT t.no, t.tx_date, t.kind, t.head, m.member_no, COALESCE(m.name_en, t.party) AS party, t.amount, t.mode, t.ref, t.note FROM transactions t "
                "LEFT JOIN members m ON m.id=t.member_id WHERE t.void=0 AND t.tx_date LIKE ? ORDER BY t.tx_date, t.id", (f"{year}%",))
    buf = io.StringIO(); buf.write("﻿"); w = csv.writer(buf)
    if rows:
        w.writerow(rows[0].keys())
        for r in rows:
            w.writerow(r.values())
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=accounts-{year}.csv"})


# ---------- UPI payment claims ----------
def upi_link(amount, note, member_no=""):
    import urllib.parse
    pa, pn = db.setting("upi_id"), db.setting("upi_name") or db.setting("club_short")
    if not pa:
        return ""
    q = {"pa": pa, "pn": pn, "cu": "INR", "tn": (f"{member_no} {note}").strip()[:40]}
    if amount:
        q["am"] = f"{float(amount):.2f}"
    return "upi://pay?" + urllib.parse.urlencode(q)


@router.get("/upi")
def upi_info(amount: float = 0, note: str = "", user=Depends(current_user)):
    """The UPI deep link and a QR image for the signed-in member's dues (or any amount)."""
    m = db.one("SELECT member_no FROM members WHERE id=?", (user.get("member_id"),)) if user.get("member_id") else None
    link = upi_link(amount, note or "subscription", m["member_no"] if m else "")
    if not link:
        return {"configured": False}
    import segno
    return {"configured": True, "link": link, "qr": segno.make(link, error="m").svg_data_uri(scale=5, border=2), "upi_id": db.setting("upi_id"), "upi_name": db.setting("upi_name")}


@router.post("/claims")
async def claim_payment(request: Request, user=Depends(current_user)):
    """A member says 'I have paid by UPI'. The treasurer confirms it into a receipt."""
    if not user.get("member_id"):
        raise HTTPException(403, "members only")
    b = await request.json()
    amount = float(b.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(400, "amount")
    utr = (b.get("utr") or "").strip()
    if len(utr) < 6:
        raise HTTPException(400, "enter the UPI transaction / UTR number")
    head = b.get("head") if b.get("head") in i18n.RECEIPT_HEADS else "subscription"
    with db.tx() as c:
        if db.one("SELECT 1 FROM payment_claims WHERE utr=? AND status<>'rejected'", (utr,)):
            raise HTTPException(409, "that transaction is already recorded")
        cid = db.insert(c, "payment_claims", {"member_id": user["member_id"], "amount": amount, "utr": utr, "paid_on": b.get("paid_on") or dt.date.today().isoformat(), "head": head,
                                              "year": int(b.get("year") or dt.date.today().year), "note": (b.get("note") or "")[:300], "status": "pending", "created": time.time()})
        comms.notify_members(c, [user["member_id"]], "payment_claimed", {"amount": f"{amount:,.0f}", "utr": utr}, ("app", "whatsapp"), ref_kind="claim", ref_id=cid)
        for o in [r["member_id"] for r in db.q("SELECT member_id FROM users WHERE role IN ('admin','treasurer','secretary') AND member_id IS NOT NULL AND active=1")]:
            comms.queue(c, "app", "", "UPI payment to confirm", f"{user['name']} · Rs {amount:,.0f} · {utr}", member_id=o, ref_kind="claims")
        db.audit(c, user["id"], "claim.create", "claim", cid, f"{amount} {utr}")
    return {"ok": True, "id": cid}


@router.get("/claims")
def list_claims(status: str = "pending", user=Depends(current_user)):
    if can(user, "finance.view"):
        where, args = ("c.status=?", [status]) if status and status != "all" else ("1=1", [])
    else:
        where, args = "c.member_id=?", [user.get("member_id") or -1]
    return db.q(f"SELECT c.*, m.name_en, m.name_ml, m.member_no, m.phone FROM payment_claims c JOIN members m ON m.id=c.member_id WHERE {where} ORDER BY c.id DESC LIMIT 300", args)


@router.post("/claims/{cid}/decide")
async def decide_claim(cid: int, request: Request, user=Depends(require("finance.manage"))):
    b = await request.json()
    cl = db.one("SELECT * FROM payment_claims WHERE id=? AND status='pending'", (cid,))
    if not cl:
        raise HTTPException(404, "not a pending claim")
    decision, note = b.get("decision"), (b.get("note") or "").strip()
    with db.tx() as c:
        if decision == "confirm":
            r = record(c, user["id"], {"kind": "receipt", "head": cl["head"], "member_id": cl["member_id"], "amount": float(b.get("amount") or cl["amount"]), "mode": "upi", "ref": cl["utr"],
                                       "tx_date": cl["paid_on"] or dt.date.today().isoformat(), "year": cl["year"], "note": note or cl["note"]})
            db.update(c, "payment_claims", cid, {"status": "confirmed", "receipt_id": r["id"], "decided_by": user["id"], "decided_at": time.time(), "decision_note": note})
            return {"ok": True, "receipt": r["no"]}
        if decision == "reject":
            db.update(c, "payment_claims", cid, {"status": "rejected", "decided_by": user["id"], "decided_at": time.time(), "decision_note": note})
            comms.notify_members(c, [cl["member_id"]], "payment_rejected", {"amount": f"{cl['amount']:,.0f}", "utr": cl["utr"], "note": note}, ("app", "whatsapp"), ref_kind="claim", ref_id=cid)
            db.audit(c, user["id"], "claim.reject", "claim", cid, note)
            return {"ok": True}
    raise HTTPException(400, "decision")
