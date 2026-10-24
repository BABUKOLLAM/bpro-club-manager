"""Residents' association mode: what a flat owners' or residents' welfare association needs beyond a club.
Units (flats, villas, shops) are the billing entity: residents link to a unit as owner, tenant or family.
Maintenance is billed per unit per period (monthly or quarterly) on a flat, per-square-foot or per-type rule, with
a late fee after the due day; receipts under the 'maintenance' head settle the unit's bills oldest first. The
helpdesk takes complaints from residents (plumbing, lift, security...) and tracks them to closure with notes.
Everything else (committees, minutes, polls, notices, documents, bookings, accounts) is shared with club mode."""
import datetime as dt
import html
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import brand, comms, db, i18n
from .auth import can, current_user, require

router = APIRouter(prefix="/api")
OCCUPANCY = ["owner", "tenant", "family"]
UNIT_STATUS = ["occupied", "vacant", "inactive"]
TICKET_CATEGORIES = ["plumbing", "electrical", "lift", "security", "housekeeping", "parking", "water", "noise", "common_area", "other"]
TICKET_STATUS = ["open", "in_progress", "on_hold", "resolved", "closed"]
TICKET_PRIORITY = ["low", "normal", "high", "urgent"]
FEATURE_DEFAULTS = {"club": {"library": True, "units": False, "maintenance": False, "helpdesk": False},
                    "association": {"library": False, "units": True, "maintenance": True, "helpdesk": True}}


# ---------- mode and features ----------
def org_kind():
    return "association" if db.setting("org_kind") == "association" else "club"


def features():
    out = dict(FEATURE_DEFAULTS[org_kind()])
    for k, v in db.setting_json("features", {}).items():
        if k in out:
            out[k] = bool(v)
    return out


def feature(name):
    return features().get(name, False)


def unit_label(u):
    if not u:
        return ""
    return f"{u['block']}-{u['unit_no']}" if u.get("block") else u["unit_no"]


def unit_residents(unit_id):
    return db.q("SELECT id, name_en, name_ml, phone, whatsapp, occupancy, status, member_no FROM members WHERE unit_id=? AND status='active' ORDER BY CASE occupancy WHEN 'owner' THEN 0 WHEN 'tenant' THEN 1 ELSE 2 END, name_en", (unit_id,))


# ---------- units ----------
def _unit(uid):
    u = db.one("SELECT * FROM units WHERE id=?", (uid,))
    if not u:
        raise HTTPException(404)
    return u


def find_or_create_unit(c, block, unit_no, utype="", area=0):
    """Self-registration names a unit; the register grows from it when the office has not entered it yet."""
    block, unit_no = (block or "").strip(), (unit_no or "").strip()
    if not unit_no:
        return None
    u = db.one("SELECT id FROM units WHERE block=? AND unit_no=?", (block, unit_no))
    if u:
        return u["id"]
    now = time.time()
    return db.insert(c, "units", {"block": block, "unit_no": unit_no, "floor": "", "utype": utype or "", "area_sqft": float(area or 0), "parking": "", "owner_name": "", "owner_phone": "",
                                  "status": "occupied", "maint_override": 0, "notes": "", "created": now, "updated": now})


@router.get("/units")
def list_units(block: str = "", status: str = "", q: str = "", user=Depends(current_user)):
    if not (can(user, "members.view") or user.get("member_id")):
        raise HTTPException(403)
    where, args = ["1=1"], []
    if block:
        where.append("u.block=?"); args.append(block)
    if status:
        where.append("u.status=?"); args.append(status)
    if q:
        like = f"%{q.strip()}%"
        where.append("(u.unit_no LIKE ? OR u.block LIKE ? OR u.owner_name LIKE ? OR EXISTS(SELECT 1 FROM members m WHERE m.unit_id=u.id AND (m.name_en LIKE ? OR m.name_ml LIKE ?)))"); args += [like] * 5
    rows = db.q(f"SELECT u.*, (SELECT COUNT(*) FROM members m WHERE m.unit_id=u.id AND m.status='active') residents, "
                f"(SELECT COALESCE(SUM(amount+late_fee-paid),0) FROM maint_bills b WHERE b.unit_id=u.id AND b.status='due') dues, "
                f"(SELECT COUNT(*) FROM maint_bills b WHERE b.unit_id=u.id AND b.status='due') due_periods, "
                f"(SELECT GROUP_CONCAT(name_en, ', ') FROM members m WHERE m.unit_id=u.id AND m.status='active') names "
                f"FROM units u WHERE {' AND '.join(where)} ORDER BY u.block, LENGTH(u.unit_no), u.unit_no", args)
    office = can(user, "members.view")
    for r in rows:
        r["label"] = unit_label(r)
        if not office:
            for k in ("owner_phone", "notes", "maint_override", "dues", "due_periods"):
                r.pop(k, None)
    return rows


@router.get("/units/{uid}")
def get_unit(uid: int, user=Depends(require("members.view"))):
    u = _unit(uid)
    u["label"] = unit_label(u)
    u["residents"] = unit_residents(uid)
    u["bills"] = db.q("SELECT * FROM maint_bills WHERE unit_id=? ORDER BY period DESC", (uid,))
    u["receipts"] = db.q("SELECT t.*, m.name_en, m.name_ml FROM transactions t LEFT JOIN members m ON m.id=t.member_id WHERE t.unit_id=? AND t.void=0 AND t.kind='receipt' ORDER BY t.tx_date DESC, t.id DESC LIMIT 100", (uid,))
    u["tickets"] = db.q("SELECT id, no, category, title, status, priority, created FROM tickets WHERE unit_id=? ORDER BY id DESC LIMIT 20", (uid,))
    u["dues"] = sum(b["amount"] + b["late_fee"] - b["paid"] for b in u["bills"] if b["status"] == "due")
    return u


@router.post("/units")
async def save_unit(request: Request, user=Depends(require("members.manage"))):
    b = await request.json()
    row = {"block": (b.get("block") or "").strip(), "unit_no": (b.get("unit_no") or "").strip(), "floor": (b.get("floor") or "").strip(), "utype": (b.get("utype") or "").strip(),
           "area_sqft": float(b.get("area_sqft") or 0), "parking": (b.get("parking") or "").strip(), "owner_name": (b.get("owner_name") or "").strip(), "owner_phone": (b.get("owner_phone") or "").strip(),
           "status": b.get("status") if b.get("status") in UNIT_STATUS else "occupied", "maint_override": float(b.get("maint_override") or 0), "notes": (b.get("notes") or "")[:500], "updated": time.time()}
    if not row["unit_no"]:
        raise HTTPException(400, "unit number")
    dup = db.one("SELECT id FROM units WHERE block=? AND unit_no=?", (row["block"], row["unit_no"]))
    with db.tx() as c:
        if b.get("id"):
            if dup and dup["id"] != b["id"]:
                raise HTTPException(409, "that unit already exists")
            db.update(c, "units", b["id"], row); uid = b["id"]
        else:
            if dup:
                raise HTTPException(409, "that unit already exists")
            row["created"] = time.time(); uid = db.insert(c, "units", row)
        db.audit(c, user["id"], "unit.save", "unit", uid, unit_label(row))
    return {"ok": True, "id": uid}


@router.post("/units/bulk")
async def bulk_units(request: Request, user=Depends(require("members.manage"))):
    """Lines of 'block, unit, floor, type, area' (block optional): the quickest way to set up a building."""
    b = await request.json()
    n = 0
    with db.tx() as c:
        for line in (b.get("lines") or "").splitlines():
            parts = [p.strip() for p in line.replace("\t", ",").split(",")]
            if not parts or not parts[0]:
                continue
            if len(parts) == 1:
                parts = ["", parts[0]]
            block, unit_no = parts[0], parts[1]
            if not unit_no or db.one("SELECT 1 FROM units WHERE block=? AND unit_no=?", (block, unit_no)):
                continue
            area = 0.0
            try:
                area = float(parts[4]) if len(parts) > 4 and parts[4] else 0.0
            except ValueError:
                pass
            now = time.time()
            db.insert(c, "units", {"block": block, "unit_no": unit_no, "floor": parts[2] if len(parts) > 2 else "", "utype": parts[3] if len(parts) > 3 else "", "area_sqft": area, "parking": "",
                                   "owner_name": "", "owner_phone": "", "status": "occupied", "maint_override": 0, "notes": "", "created": now, "updated": now})
            n += 1
        db.audit(c, user["id"], "unit.bulk", detail=f"{n} units")
    return {"ok": True, "created": n}


@router.post("/units/{uid}/residents")
async def assign_resident(uid: int, request: Request, user=Depends(require("members.manage"))):
    b = await request.json()
    _unit(uid)
    mid = int(b.get("member_id") or 0)
    if not db.one("SELECT 1 FROM members WHERE id=?", (mid,)):
        raise HTTPException(404, "member")
    occ = b.get("occupancy") if b.get("occupancy") in OCCUPANCY else "owner"
    with db.tx() as c:
        if b.get("remove"):
            c.execute("UPDATE members SET unit_id=NULL, updated=? WHERE id=? AND unit_id=?", (time.time(), mid, uid))
        else:
            c.execute("UPDATE members SET unit_id=?, occupancy=?, updated=? WHERE id=?", (uid, occ, time.time(), mid))
        db.audit(c, user["id"], "unit.resident", "unit", uid, f"{mid} {occ}{' removed' if b.get('remove') else ''}")
    return {"ok": True}


# ---------- maintenance billing ----------
def maint_rules():
    s = db.settings_all()
    try:
        rate = float(s.get("maint_rate") or 0)
    except ValueError:
        rate = 0.0
    try:
        late = float(s.get("maint_late_fee") or 0)
    except ValueError:
        late = 0.0
    return {"basis": s.get("maint_basis") if s.get("maint_basis") in ("flat", "sqft", "type") else "flat", "rate": rate, "by_type": db.setting_json("maint_rates_by_type", {}),
            "period": "quarterly" if s.get("maint_period") == "quarterly" else "monthly", "due_day": max(1, min(28, int(s.get("maint_due_day") or 10))), "late_fee": late,
            "unit_types": db.setting_json("unit_types", ["1BHK", "2BHK", "3BHK", "Villa", "Shop"])}


def period_label(d=None):
    r = maint_rules(); d = d or dt.date.today()
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}" if r["period"] == "quarterly" else d.strftime("%Y-%m")


def period_bounds(period):
    """First day and due date of a period label ('2026-04' or '2026-Q2')."""
    r = maint_rules()
    try:
        if "-Q" in period:
            y, qn = int(period[:4]), int(period[-1])
            start = dt.date(y, (qn - 1) * 3 + 1, 1)
        else:
            y, m = int(period[:4]), int(period[5:7])
            start = dt.date(y, m, 1)
    except (ValueError, IndexError):
        raise HTTPException(400, "period")
    return start.isoformat(), dt.date(start.year, start.month, r["due_day"]).isoformat()


def bill_amount(u, r=None):
    r = r or maint_rules()
    if u.get("maint_override"):
        return float(u["maint_override"])
    if r["basis"] == "sqft":
        return round(float(u.get("area_sqft") or 0) * r["rate"], 2)
    if r["basis"] == "type":
        try:
            return float(r["by_type"].get(u.get("utype") or "", r["rate"]) or 0)
        except (TypeError, ValueError):
            return r["rate"]
    return r["rate"]


def resettle_unit(c, unit_id):
    """Recompute what each bill has received: maintenance receipts of the unit settle bills oldest first (idempotent,
    so voids and back-dated receipts just re-run it)."""
    bills = [dict(r) for r in c.execute("SELECT * FROM maint_bills WHERE unit_id=? AND status<>'waived' ORDER BY period, id", (unit_id,))]
    pool = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE unit_id=? AND kind='receipt' AND head='maintenance' AND void=0", (unit_id,)).fetchone()[0]
    for b in bills:
        owed = b["amount"] + b["late_fee"]
        paid = min(owed, pool); pool -= paid
        c.execute("UPDATE maint_bills SET paid=?, status=? WHERE id=?", (paid, "paid" if paid >= owed - 0.005 else "due", b["id"]))
    return pool   # advance, if any


def on_receipt(c, row):
    """Called by finance.record for every receipt: a maintenance receipt attaches to the payer's unit and settles its bills."""
    if row.get("head") != "maintenance":
        return
    uid = row.get("unit_id")
    if not uid and row.get("member_id"):
        m = c.execute("SELECT unit_id FROM members WHERE id=?", (row["member_id"],)).fetchone()
        uid = m[0] if m else None
        if uid:
            c.execute("UPDATE transactions SET unit_id=? WHERE id=?", (uid, row["id"]))
            row["unit_id"] = uid
    if uid:
        resettle_unit(c, uid)


def apply_late_fees(c=None):
    """Daily: bills still due after the due day get the late fee once."""
    r = maint_rules()
    if r["late_fee"] <= 0:
        return 0
    today = dt.date.today().isoformat()
    rows = db.q("SELECT id, unit_id FROM maint_bills WHERE status='due' AND late_fee=0 AND due_on<?", (today,))
    if not rows:
        return 0
    own = c is None
    cm = db.tx() if own else None
    c = cm.__enter__() if own else c
    try:
        for b in rows:
            c.execute("UPDATE maint_bills SET late_fee=? WHERE id=?", (r["late_fee"], b["id"]))
        for uid in {b["unit_id"] for b in rows}:
            resettle_unit(c, uid)
    finally:
        if own:
            cm.__exit__(None, None, None)
    return len(rows)


@router.get("/maintenance")
def maintenance(period: str = "", user=Depends(require("finance.view"))):
    period = period or period_label()
    bills = db.q("SELECT b.*, u.block, u.unit_no, u.utype, u.area_sqft, (SELECT GROUP_CONCAT(name_en, ', ') FROM members m WHERE m.unit_id=u.id AND m.status='active') names FROM maint_bills b JOIN units u ON u.id=b.unit_id "
                 "WHERE b.period=? ORDER BY u.block, LENGTH(u.unit_no), u.unit_no", (period,))
    for b in bills:
        b["label"] = unit_label(b); b["balance"] = b["amount"] + b["late_fee"] - b["paid"]
    periods = [r["period"] for r in db.q("SELECT DISTINCT period FROM maint_bills ORDER BY period DESC")]
    if period not in periods:
        periods.insert(0, period)
    totals = {"billed": sum(b["amount"] + b["late_fee"] for b in bills), "paid": sum(b["paid"] for b in bills), "due": sum(b["balance"] for b in bills if b["status"] == "due"), "units": len(bills),
              "paid_units": sum(1 for b in bills if b["status"] == "paid")}
    return {"period": period, "periods": periods, "rules": maint_rules(), "bills": bills, "totals": totals, "active_units": db.one("SELECT COUNT(*) n FROM units WHERE status<>'inactive'")["n"]}


@router.post("/maintenance/generate")
async def generate_bills(request: Request, user=Depends(require("finance.manage"))):
    b = await request.json()
    period = b.get("period") or period_label()
    start, due_on = period_bounds(period)
    r = maint_rules()
    n = 0
    with db.tx() as c:
        for u in db.q("SELECT * FROM units WHERE status<>'inactive'"):
            amt = bill_amount(u, r)
            if amt <= 0:
                continue
            cur = c.execute("INSERT OR IGNORE INTO maint_bills(unit_id, period, amount, late_fee, paid, status, due_on, created, note) VALUES(?,?,?,?,?,?,?,?,?)",
                            (u["id"], period, amt, 0, 0, "due", due_on, time.time(), ""))
            n += cur.rowcount
        for u in db.q("SELECT DISTINCT unit_id FROM maint_bills WHERE period=?", (period,)):
            resettle_unit(c, u["unit_id"])
        db.audit(c, user["id"], "maintenance.generate", detail=f"{period}: {n}")
    return {"ok": True, "period": period, "created": n}


@router.post("/maintenance/bills/{bid}")
async def edit_bill(bid: int, request: Request, user=Depends(require("finance.manage"))):
    """Adjust one bill: amount, late fee, waive, note."""
    b = await request.json()
    bill = db.one("SELECT * FROM maint_bills WHERE id=?", (bid,))
    if not bill:
        raise HTTPException(404)
    row = {}
    if "amount" in b:
        row["amount"] = float(b["amount"] or 0)
    if "late_fee" in b:
        row["late_fee"] = float(b["late_fee"] or 0)
    if "note" in b:
        row["note"] = (b["note"] or "")[:300]
    if b.get("waive"):
        row.update({"status": "waived", "paid": 0})
    elif b.get("unwaive") or ("waive" in b and not b["waive"] and bill["status"] == "waived"):
        row["status"] = "due"
    with db.tx() as c:
        if row:
            db.update(c, "maint_bills", bid, row)
        resettle_unit(c, bill["unit_id"])
        db.audit(c, user["id"], "maintenance.edit", "bill", bid, str(row))
    return {"ok": True}


@router.get("/maintenance/defaulters")
def defaulters(user=Depends(require("finance.view"))):
    rows = db.q("SELECT u.id unit_id, u.block, u.unit_no, COUNT(b.id) periods, SUM(b.amount+b.late_fee-b.paid) due, MIN(b.period) oldest, "
                "(SELECT GROUP_CONCAT(name_en, ', ') FROM members m WHERE m.unit_id=u.id AND m.status='active') names, "
                "(SELECT phone FROM members m WHERE m.unit_id=u.id AND m.status='active' ORDER BY CASE occupancy WHEN 'owner' THEN 0 ELSE 1 END LIMIT 1) phone "
                "FROM maint_bills b JOIN units u ON u.id=b.unit_id WHERE b.status='due' GROUP BY u.id ORDER BY due DESC")
    for r in rows:
        r["label"] = unit_label(r); r["wa_link"] = comms.wa_link(r["phone"])
    return rows


@router.post("/maintenance/remind")
async def remind(request: Request, user=Depends(require("finance.manage"))):
    b = await request.json()
    channels = b.get("channels") or ["app", "whatsapp", "sms"]
    n = units = 0
    with db.tx() as c:
        for d in defaulters(user):
            residents = [m["id"] for m in unit_residents(d["unit_id"])]
            if not residents:
                continue
            units += 1
            n += comms.notify_members(c, residents, "maintenance_due", {"unit": d["label"], "amount": f"{d['due']:,.0f}", "periods": str(d["periods"])}, channels, ref_kind="unit", ref_id=d["unit_id"],
                                      batch_id=comms.new_batch(), created_by=user["id"])
        c.execute("UPDATE maint_bills SET reminded_at=? WHERE status='due'", (time.time(),))
    return {"ok": True, "units": units, "queued": n}


def my_bills(member_id):
    m = db.one("SELECT unit_id FROM members WHERE id=?", (member_id,))
    if not m or not m["unit_id"]:
        return {"unit": None, "bills": [], "due": 0}
    u = db.one("SELECT * FROM units WHERE id=?", (m["unit_id"],))
    bills = db.q("SELECT * FROM maint_bills WHERE unit_id=? ORDER BY period DESC LIMIT 36", (u["id"],))
    return {"unit": {"id": u["id"], "label": unit_label(u), "block": u["block"], "unit_no": u["unit_no"]}, "bills": bills, "due": sum(x["amount"] + x["late_fee"] - x["paid"] for x in bills if x["status"] == "due")}


# ---------- unit statement (printable) ----------
UL = {"en": {"title": "Statement of account", "unit": "Unit", "residents": "Residents", "period": "Period", "billed": "Billed", "late": "Late fee", "paid": "Paid", "balance": "Balance", "receipt": "Receipt", "date": "Date",
             "amount": "Amount", "mode": "Mode", "outstanding": "Outstanding", "bills": "Maintenance bills", "receipts": "Receipts", "treasurer": "Treasurer", "asof": "as on"},
      "ml": {"title": "കണക്ക് സ്റ്റേറ്റ്മെന്റ്", "unit": "യൂണിറ്റ്", "residents": "താമസക്കാർ", "period": "കാലയളവ്", "billed": "ബിൽ തുക", "late": "പിഴ", "paid": "അടച്ചത്", "balance": "ബാക്കി", "receipt": "രസീത്", "date": "തീയതി",
             "amount": "തുക", "mode": "രീതി", "outstanding": "അടയ്ക്കാനുള്ളത്", "bills": "മെയിന്റനൻസ് ബില്ലുകൾ", "receipts": "രസീതുകൾ", "treasurer": "ട്രഷറർ", "asof": "തീയതി പ്രകാരം"}}


@router.get("/units/{uid}/statement")
def unit_statement(uid: int, lang: str = "ml", user=Depends(current_user)):
    own = db.one("SELECT unit_id FROM members WHERE id=?", (user.get("member_id") or -1,))
    if not (can(user, "finance.view") or (own and own["unit_id"] == uid)):
        raise HTTPException(403)
    lang = lang if lang in ("en", "ml") else "en"
    L = UL[lang]; e = html.escape
    u = _unit(uid); s = db.settings_all(); c = brand.colors(s)
    bills = db.q("SELECT * FROM maint_bills WHERE unit_id=? ORDER BY period", (uid,))
    rec = db.q("SELECT t.* FROM transactions t WHERE t.unit_id=? AND t.void=0 AND t.kind='receipt' ORDER BY t.tx_date, t.id", (uid,))
    res = ", ".join(f"{i18n.pick(m, 'name', lang)} ({m['occupancy']})" for m in unit_residents(uid))
    due = sum(b["amount"] + b["late_fee"] - b["paid"] for b in bills if b["status"] == "due")
    bt = "".join(f"<tr><td>{e(b['period'])}</td><td class=n>{b['amount']:,.2f}</td><td class=n>{b['late_fee']:,.2f}</td><td class=n>{b['paid']:,.2f}</td><td class=n>{(b['amount'] + b['late_fee'] - b['paid']) if b['status'] != 'waived' else 0:,.2f}</td><td>{e(b['status'])}</td></tr>" for b in bills)
    rt = "".join(f"<tr><td>{e(r['tx_date'])}</td><td>{e(r['no'])}</td><td>{e(r['mode'])}{(' · ' + e(r['ref'])) if r['ref'] else ''}</td><td class=n>{r['amount']:,.2f}</td></tr>" for r in rec)
    body = f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{L['title']} {e(unit_label(u))}</title>{brand.html_head(s)}
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;max-width:800px;margin:0 auto;padding:24px;color:#1d2a28;line-height:1.45;font-size:.92rem}}h1{{margin:0;color:{c['primary']}}}h2{{border-bottom:2px solid {c['primary']};padding-bottom:4px;margin:22px 0 6px;font-size:1.02rem}}
.m{{color:#666;font-size:.85rem}}table{{width:100%;border-collapse:collapse;margin:6px 0}}td,th{{border:1px solid #bbb;padding:4px 8px;text-align:left}}td.n,th.n{{text-align:right;font-family:Inter;white-space:nowrap}}.big{{font-size:1.3rem;font-weight:700}}
.sign{{margin-top:40px;text-align:right}}@media print{{body{{padding:0}}}}</style></head><body>
{brand.logo_img(s, height=50)}<div class=m>{e(s['club_name_ml' if lang == 'ml' else 'club_name_en'])}{(' · ' + e(s['club_reg_no'])) if s['club_reg_no'] else ''}</div>
<h1>{L['title']} · {L['unit']} {e(unit_label(u))}</h1><div class=m>{L['residents']}: {e(res or '-')} · {L['asof']} {dt.date.today().isoformat()}</div>
<p class=big>{L['outstanding']}: ₹{due:,.2f}</p>
<h2>{L['bills']}</h2><table><tr><th>{L['period']}</th><th class=n>{L['billed']}</th><th class=n>{L['late']}</th><th class=n>{L['paid']}</th><th class=n>{L['balance']}</th><th></th></tr>{bt or '<tr><td colspan=6>-</td></tr>'}</table>
<h2>{L['receipts']}</h2><table><tr><th>{L['date']}</th><th>{L['receipt']}</th><th>{L['mode']}</th><th class=n>{L['amount']}</th></tr>{rt or '<tr><td colspan=4>-</td></tr>'}</table>
<div class=sign>{L['treasurer']}<br><br>______________</div><script>setTimeout(()=>window.print(),500)</script></body></html>"""
    return HTMLResponse(body)


# ---------- helpdesk ----------
def _ticket(tid):
    t = db.one("SELECT t.*, m.name_en, m.name_ml, m.phone, u.block, u.unit_no, a.name AS assignee FROM tickets t LEFT JOIN members m ON m.id=t.member_id LEFT JOIN units u ON u.id=t.unit_id LEFT JOIN users a ON a.id=t.assigned_to WHERE t.id=?", (tid,))
    if not t:
        raise HTTPException(404)
    t["unit"] = unit_label(t) if t.get("unit_no") else ""
    return t


def _officers():
    return [r["member_id"] for r in db.q("SELECT member_id FROM users WHERE role IN ('admin','president','secretary') AND member_id IS NOT NULL AND active=1")]


@router.get("/tickets")
def list_tickets(status: str = "", category: str = "", mine: str = "", user=Depends(current_user)):
    manage = can(user, "helpdesk.manage")
    where, args = ["1=1"], []
    if not manage or mine:
        where.append("t.member_id=?"); args.append(user.get("member_id") or -1)
    if status == "open":
        where.append("t.status IN ('open','in_progress','on_hold')")
    elif status:
        where.append("t.status=?"); args.append(status)
    if category:
        where.append("t.category=?"); args.append(category)
    rows = db.q(f"SELECT t.*, m.name_en, m.name_ml, u.block, u.unit_no, a.name AS assignee, (SELECT COUNT(*) FROM ticket_notes n WHERE n.ticket_id=t.id) notes FROM tickets t LEFT JOIN members m ON m.id=t.member_id "
                f"LEFT JOIN units u ON u.id=t.unit_id LEFT JOIN users a ON a.id=t.assigned_to WHERE {' AND '.join(where)} ORDER BY CASE t.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 WHEN 'on_hold' THEN 2 ELSE 3 END, "
                f"CASE t.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, t.id DESC LIMIT 300", args)
    for r in rows:
        r["unit"] = unit_label(r) if r.get("unit_no") else ""
    counts = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) n FROM tickets GROUP BY status")} if manage else {}
    return {"rows": rows, "counts": counts, "categories": TICKET_CATEGORIES, "statuses": TICKET_STATUS, "priorities": TICKET_PRIORITY}


@router.post("/tickets")
async def create_ticket(request: Request, user=Depends(current_user)):
    b = await request.json()
    title = (b.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title")
    manage = can(user, "helpdesk.manage")
    mid = int(b.get("member_id") or 0) if manage and b.get("member_id") else (user.get("member_id") or None)
    if not mid and not manage:
        raise HTTPException(403)
    unit_id = b.get("unit_id")
    if not unit_id and mid:
        m = db.one("SELECT unit_id FROM members WHERE id=?", (mid,))
        unit_id = m["unit_id"] if m else None
    now = time.time()
    with db.tx() as c:
        seq = db.next_counter(c, f"ticket:{dt.date.today().year}")
        row = {"no": f"T/{dt.date.today().year}/{seq:04d}", "member_id": mid, "unit_id": unit_id, "category": b.get("category") if b.get("category") in TICKET_CATEGORIES else "other", "title": title[:160],
               "details": (b.get("details") or "")[:3000], "photo": (b.get("photo") or "")[:300], "priority": b.get("priority") if b.get("priority") in TICKET_PRIORITY else "normal", "status": "open",
               "assigned_to": None, "created": now, "updated": now, "created_by": user["id"]}
        tid = db.insert(c, "tickets", row)
        for o in _officers():
            if o != mid:
                comms.queue(c, "app", "", f"Complaint {row['no']}: {title[:60]}", f"{row['category']} · {(b.get('details') or '')[:120]}", member_id=o, ref_kind="tickets", ref_id=tid)
        if mid:
            comms.notify_members(c, [mid], "ticket_created", {"no": row["no"], "title": title[:80]}, ("app",), ref_kind="ticket", ref_id=tid, created_by=user["id"])
        db.audit(c, user["id"], "ticket.create", "ticket", tid, title[:80])
    return {"ok": True, "id": tid, "no": row["no"]}


@router.get("/tickets/{tid}")
def get_ticket(tid: int, user=Depends(current_user)):
    t = _ticket(tid)
    if not (can(user, "helpdesk.manage") or t["member_id"] == user.get("member_id")):
        raise HTTPException(403)
    t["notes_list"] = db.q("SELECT n.*, u.name AS by_name FROM ticket_notes n LEFT JOIN users u ON u.id=n.user_id WHERE n.ticket_id=? ORDER BY n.id", (tid,))
    if can(user, "helpdesk.manage"):
        t["staff"] = db.q("SELECT id, name, role FROM users WHERE active=1 AND role<>'member' ORDER BY name")
    return t


@router.post("/tickets/{tid}")
async def update_ticket(tid: int, request: Request, user=Depends(current_user)):
    """Office: status, assignee, priority, note. The resident who raised it: a note, or closing it."""
    b = await request.json()
    t = _ticket(tid)
    manage = can(user, "helpdesk.manage")
    own = t["member_id"] == user.get("member_id")
    if not (manage or own):
        raise HTTPException(403)
    row, change = {}, ""
    st = b.get("status")
    if st and st in TICKET_STATUS and st != t["status"]:
        if not manage and st != "closed":
            raise HTTPException(403, "only the office changes the status")
        row["status"] = st; change = st
        if st == "resolved":
            row["resolved_at"] = time.time()
        if st == "closed":
            row["closed_at"] = time.time()
    if manage:
        if "assigned_to" in b:
            row["assigned_to"] = int(b["assigned_to"]) if b["assigned_to"] else None
        if b.get("priority") in TICKET_PRIORITY:
            row["priority"] = b["priority"]
        if b.get("category") in TICKET_CATEGORIES:
            row["category"] = b["category"]
    note = (b.get("note") or "").strip()[:2000]
    now = time.time()
    with db.tx() as c:
        if row:
            row["updated"] = now
            db.update(c, "tickets", tid, row)
        if note or change:
            db.insert(c, "ticket_notes", {"ticket_id": tid, "user_id": user["id"], "ts": now, "text": note, "status_change": change})
        if (change or note) and t["member_id"] and not own:
            comms.notify_members(c, [t["member_id"]], "ticket_update", {"no": t["no"], "title": t["title"][:60], "status": change or t["status"], "note": note[:200]}, ("app", "whatsapp"), ref_kind="ticket", ref_id=tid, created_by=user["id"])
        if own and not manage:
            for o in _officers():
                comms.queue(c, "app", "", f"{t['no']}: {t['title'][:60]}", note[:120] or change, member_id=o, ref_kind="tickets", ref_id=tid)
        db.audit(c, user["id"], "ticket.update", "ticket", tid, f"{change} {note[:60]}".strip())
    return {"ok": True}


def dashboard_extra(user):
    out = {}
    if feature("helpdesk"):
        out["tickets_open"] = db.one("SELECT COUNT(*) n FROM tickets WHERE status IN ('open','in_progress','on_hold')")["n"]
        if user.get("member_id"):
            out["my_tickets"] = db.one("SELECT COUNT(*) n FROM tickets WHERE member_id=? AND status IN ('open','in_progress','on_hold')", (user["member_id"],))["n"]
    if feature("maintenance"):
        out["maint_due_units"] = db.one("SELECT COUNT(DISTINCT unit_id) n FROM maint_bills WHERE status='due'")["n"]
        out["maint_due_amount"] = db.one("SELECT COALESCE(SUM(amount+late_fee-paid),0) n FROM maint_bills WHERE status='due'")["n"]
        if user.get("member_id"):
            out["my_maint_due"] = my_bills(user["member_id"])["due"]
    if feature("units"):
        out["units"] = db.one("SELECT COUNT(*) n FROM units WHERE status<>'inactive'")["n"]
        out["units_vacant"] = db.one("SELECT COUNT(*) n FROM units WHERE status='vacant'")["n"]
    return out
