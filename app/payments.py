"""Online payment through Razorpay: the server creates an order, the browser opens Razorpay Checkout, the server
verifies the signature (and the webhook, when configured) and records the receipt. Without keys the gateway is
off and members use the UPI route.

Environment: CLUB_RZP_KEY_ID, CLUB_RZP_KEY_SECRET, optional CLUB_RZP_WEBHOOK_SECRET.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request

from . import comms, db, i18n
from .auth import can, current_user, require

router = APIRouter(prefix="/api/payments")
_create_order_override = None     # tests plug in a fake Razorpay


def set_order_creator(fn):
    global _create_order_override
    _create_order_override = fn


def configured():
    return bool(os.environ.get("CLUB_RZP_KEY_ID") and os.environ.get("CLUB_RZP_KEY_SECRET"))


def _rzp(path, payload):
    key, secret = os.environ["CLUB_RZP_KEY_ID"], os.environ["CLUB_RZP_KEY_SECRET"]
    req = urllib.request.Request("https://api.razorpay.com/v1" + path, data=json.dumps(payload).encode(),
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode(), "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def create_order(amount_paise, receipt, notes):
    if _create_order_override:
        return _create_order_override(amount_paise, receipt, notes)
    return _rzp("/orders", {"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes})


def verify_signature(order_id, payment_id, signature):
    secret = os.environ.get("CLUB_RZP_KEY_SECRET", "")
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@router.get("/config")
def config(user=Depends(current_user)):
    return {"configured": configured() or bool(_create_order_override), "key_id": os.environ.get("CLUB_RZP_KEY_ID", "") if (configured() or _create_order_override) else "",
            "club": db.setting("club_name_en"), "upi": bool(db.setting("upi_id"))}


@router.post("/order")
async def order(request: Request, user=Depends(current_user)):
    """Create a gateway order for the signed-in member: dues (head subscription/admission), an event fee or a booking."""
    if not (configured() or _create_order_override):
        raise HTTPException(400, "online payment is not set up")
    if not user.get("member_id"):
        raise HTTPException(403, "members only")
    b = await request.json()
    amount = round(float(b.get("amount") or 0), 2)
    if amount < 1:
        raise HTTPException(400, "amount")
    head = b.get("head") if b.get("head") in i18n.RECEIPT_HEADS else "subscription"
    m = db.one("SELECT member_no, name_en, phone, email FROM members WHERE id=?", (user["member_id"],))
    receipt_ref = f"m{user['member_id']}-{int(time.time())}"
    try:
        o = create_order(int(round(amount * 100)), receipt_ref, {"member_no": m["member_no"], "head": head})
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"gateway error: {e}"[:200])
    with db.tx() as c:
        gid = db.insert(c, "gateway_orders", {"provider": "razorpay", "order_id": o["id"], "member_id": user["member_id"], "amount": amount, "head": head,
                                              "year": int(b.get("year") or time.strftime("%Y")), "post_id": b.get("post_id") or None, "booking_id": b.get("booking_id") or None,
                                              "note": (b.get("note") or "")[:200], "status": "created", "created": time.time(), "raw": json.dumps(o)[:2000]})
    return {"ok": True, "id": gid, "order_id": o["id"], "amount": amount, "key_id": os.environ.get("CLUB_RZP_KEY_ID", ""), "currency": "INR",
            "prefill": {"name": m["name_en"], "contact": m["phone"], "email": m["email"]}, "description": i18n.label(i18n.HEAD_LABELS, head, "en")}


def _settle(c, go, payment_id, user_id=None, source="checkout"):
    """Record the receipt for a paid order once, however many times we hear about it."""
    if go["status"] == "paid":
        return db.one("SELECT * FROM transactions WHERE id=?", (go["receipt_id"],))
    from . import finance
    r = finance.record(c, user_id, {"kind": "receipt", "head": go["head"], "member_id": go["member_id"], "amount": go["amount"], "mode": "upi", "ref": payment_id,
                                   "year": go["year"], "post_id": go["post_id"], "note": f"online ({source}) {go['order_id']}"}, notify=False)
    db.update(c, "gateway_orders", go["id"], {"status": "paid", "payment_id": payment_id, "receipt_id": r["id"], "paid_at": time.time()})
    if go["booking_id"]:
        c.execute("UPDATE bookings SET receipt_id=?, status=CASE WHEN status='requested' THEN 'confirmed' ELSE status END, updated=? WHERE id=?", (r["id"], time.time(), go["booking_id"]))
    if go["member_id"]:
        comms.notify_members(c, [go["member_id"]], "payment_success", {"amount": f"{go['amount']:,.0f}", "payment_id": payment_id, "no": r["no"]}, ("app", "whatsapp", "sms"),
                             ref_kind="receipt", ref_id=r["id"])
    db.audit(c, user_id, "payment.online", "transaction", r["id"], f"{go['order_id']} {payment_id}")
    return r


@router.post("/verify")
async def verify(request: Request, user=Depends(current_user)):
    """Called by the browser after Checkout succeeds, with Razorpay's order_id, payment_id and signature."""
    b = await request.json()
    go = db.one("SELECT * FROM gateway_orders WHERE order_id=?", (b.get("razorpay_order_id"),))
    if not go or go["member_id"] != user.get("member_id"):
        raise HTTPException(404, "order")
    if not verify_signature(go["order_id"], b.get("razorpay_payment_id", ""), b.get("razorpay_signature", "")):
        with db.tx() as c:
            db.update(c, "gateway_orders", go["id"], {"status": "failed", "raw": "bad signature"})
        raise HTTPException(400, "payment signature does not match")
    with db.tx() as c:
        r = _settle(c, go, b["razorpay_payment_id"], user["id"])
    return {"ok": True, "receipt": r["no"], "amount": r["amount"]}


@router.post("/razorpay/webhook")
async def webhook(request: Request):
    """Razorpay's server-to-server confirmation (payment.captured / order.paid), the safety net when the browser
    closes before /verify. Needs CLUB_RZP_WEBHOOK_SECRET; idempotent."""
    secret = os.environ.get("CLUB_RZP_WEBHOOK_SECRET", "")
    body = await request.body()
    if not secret:
        raise HTTPException(404)
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Razorpay-Signature", "")):
        raise HTTPException(400, "bad signature")
    ev = json.loads(body or b"{}")
    pay = (((ev.get("payload") or {}).get("payment") or {}).get("entity") or {})
    if ev.get("event") not in ("payment.captured", "order.paid") or not pay.get("order_id"):
        return {"ok": True, "ignored": True}
    go = db.one("SELECT * FROM gateway_orders WHERE order_id=?", (pay["order_id"],))
    if not go:
        return {"ok": True, "unknown": True}
    with db.tx() as c:
        _settle(c, go, pay.get("id", ""), None, "webhook")
    return {"ok": True}


@router.get("/orders")
def orders(user=Depends(current_user)):
    if can(user, "finance.view"):
        return db.q("SELECT g.*, m.name_en, m.name_ml, m.member_no FROM gateway_orders g LEFT JOIN members m ON m.id=g.member_id ORDER BY g.id DESC LIMIT 300")
    return db.q("SELECT * FROM gateway_orders WHERE member_id=? ORDER BY id DESC LIMIT 50", (user.get("member_id") or -1,))
