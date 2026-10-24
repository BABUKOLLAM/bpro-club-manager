"""Society accounts: the books an auditor and a registered society's annual return expect, on top of the receipts and
vouchers the treasurer already enters. Financial years (April to March by default), opening balances, cash book and
bank book with contra entries, ledger by head, Receipts & Payments account, Income & Expenditure account, Balance
Sheet, year close that carries the balances forward and locks the year, and a Tally XML export.

Every head has a *nature*: income or expense (they meet in the Income & Expenditure account), asset (books, furniture,
building: a payment adds to the asset), liability (deposits received, refunded later) or fund (building fund, corpus).
Cash basis throughout, as clubs keep their books; subscription dues outstanding are shown as a memo."""
import datetime as dt
import html
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from . import brand, db, i18n
from .auth import require

router = APIRouter(prefix="/api/accounts")
NATURES = ["income", "expense", "asset", "liability", "fund"]
DEFAULT_NATURE = {"library_deposit": "liability", "books": "asset", "furniture": "asset", "building": "asset", "deposit_refund": "liability", "building_fund": "fund", "corpus": "fund"}
DEFAULT_ITEM = {"deposit_refund": "library_deposit"}   # heads that move the same balance-sheet item
CONTRA_HEADS = {"cash_to_bank": {"en": "Cash deposited in bank", "ml": "ബാങ്കിൽ നിക്ഷേപിച്ച പണം"}, "bank_to_cash": {"en": "Cash withdrawn from bank", "ml": "ബാങ്കിൽ നിന്ന് പിൻവലിച്ച പണം"}}
CASH_MODES = {"cash"}
TALLY_GROUPS = {"income": "Indirect Incomes", "expense": "Indirect Expenses", "asset": "Fixed Assets", "liability": "Current Liabilities", "fund": "Capital Account"}


# ---------- heads ----------
def custom_heads():
    out = []
    for h in db.setting_json("custom_heads", []):
        key = str(h.get("key") or "").strip().lower().replace(" ", "_")
        if not key or key in i18n.HEAD_LABELS or key in CONTRA_HEADS:
            continue
        out.append({"key": key, "en": h.get("en") or key, "ml": h.get("ml") or h.get("en") or key, "kind": h.get("kind") if h.get("kind") in ("receipt", "payment", "both") else "both",
                    "nature": h.get("nature") if h.get("nature") in NATURES else "expense", "item": str(h.get("item") or key).strip().lower().replace(" ", "_")})
    return out


def heads():
    """Every head in use: built-in (with the nature overrides from settings) and custom, in display order."""
    over = db.setting_json("head_nature", {})
    out = []
    for k in i18n.RECEIPT_HEADS:
        out.append({"key": k, "kind": "receipt", "nature": over.get(k) or DEFAULT_NATURE.get(k, "income"), "item": DEFAULT_ITEM.get(k, k), **i18n.HEAD_LABELS[k]})
    for k in i18n.PAYMENT_HEADS:
        out.append({"key": k, "kind": "payment", "nature": over.get(k) or DEFAULT_NATURE.get(k, "expense"), "item": DEFAULT_ITEM.get(k, k), **i18n.HEAD_LABELS[k]})
    out += custom_heads()
    return out


def heads_for(kind):
    return [h["key"] for h in heads() if h["kind"] in (kind, "both")]


def labels():
    return {**i18n.HEAD_LABELS, **{h["key"]: {"en": h["en"], "ml": h["ml"]} for h in custom_heads()}, **CONTRA_HEADS}


def nature_of(head):
    for h in heads():
        if h["key"] == head:
            return h["nature"]
    return "income"


# ---------- financial years ----------
def start_month():
    try:
        return min(12, max(1, int(db.setting("fy_start_month"))))
    except (TypeError, ValueError):
        return 4


def fy_label(start_year):
    return str(start_year) if start_month() == 1 else f"{start_year}-{str(start_year + 1)[2:]}"


def fy_bounds(fy):
    """(start_on, end_on) ISO dates for a label like '2026-27' or '2026'."""
    try:
        y = int(str(fy)[:4])
    except ValueError:
        raise HTTPException(400, "fy")
    m = start_month()
    start = dt.date(y, m, 1)
    end = (dt.date(y + 1, m, 1) if m > 1 else dt.date(y + 1, 1, 1)) - dt.timedelta(days=1)
    return start.isoformat(), end.isoformat()


def fy_of(date_iso):
    d = dt.date.fromisoformat(date_iso[:10])
    m = start_month()
    return fy_label(d.year if (m == 1 or d.month >= m) else d.year - 1)


def current_fy():
    return fy_of(dt.date.today().isoformat())


def fy_list():
    first = db.one("SELECT MIN(tx_date) d FROM transactions WHERE void=0")["d"]
    years = {current_fy()} | {r["fy"] for r in db.q("SELECT fy FROM fy_years")} | {r["fy"] for r in db.q("SELECT DISTINCT fy FROM fy_openings")}
    if first:
        y0 = int(fy_of(first)[:4]); y1 = int(current_fy()[:4])
        years |= {fy_label(y) for y in range(y0, y1 + 1)}
    return sorted(years, reverse=True)


def fy_row(fy):
    return db.one("SELECT * FROM fy_years WHERE fy=?", (fy,)) or {"fy": fy, "status": "open", "closed_at": None, "closed_by": None, "note": ""}


def is_closed(fy):
    return fy_row(fy)["status"] == "closed"


def assert_open(tx_date):
    """Called by finance.record and void: a closed year takes no new or changed entries."""
    fy = fy_of(tx_date)
    if is_closed(fy):
        raise HTTPException(423, f"accounts for {fy} are closed")


# ---------- openings ----------
def balance_items():
    """Items on the balance sheet other than cash and bank: one per asset / liability / fund head (heads that share an
    item, like deposits received and refunded, merge) plus any custom opening item."""
    items, seen = [], set()
    for h in heads():
        if h["nature"] in ("asset", "liability", "fund") and h["item"] not in seen:
            items.append({"item": h["item"], "side": "liability" if h["nature"] in ("liability", "fund") else "asset", "nature": h["nature"], "en": h["en"], "ml": h["ml"], "heads": [x["key"] for x in heads() if x["item"] == h["item"]]})
            seen.add(h["item"])
    for r in db.q("SELECT DISTINCT item, side, label_en, label_ml FROM fy_openings WHERE item LIKE 'x:%'"):
        if r["item"] not in seen:
            items.append({"item": r["item"], "side": r["side"] or "asset", "nature": "custom", "en": r["label_en"] or r["item"][2:], "ml": r["label_ml"] or r["label_en"] or r["item"][2:]}); seen.add(r["item"])
    return items


def openings(fy):
    rows = {r["item"]: r for r in db.q("SELECT * FROM fy_openings WHERE fy=?", (fy,))}
    out = {"cash": 0.0, "bank": 0.0, "items": {}, "derived": any(r["derived"] for r in rows.values()), "labels": {}}
    for item, r in rows.items():
        if item == "cash":
            out["cash"] = r["amount"]
        elif item == "bank":
            out["bank"] = r["amount"]
        else:
            out["items"][item] = r["amount"]
            if item.startswith("x:"):
                out["labels"][item] = {"side": r["side"], "en": r["label_en"], "ml": r["label_ml"]}
    return out


# ---------- the statements ----------
def _lbl(lab, key):
    return lab.get(key) or {"en": key, "ml": key}


def statements(fy):
    start, end = fy_bounds(fy)
    lab = labels()
    rows = db.q("SELECT kind, head, mode, SUM(amount) total, COUNT(*) n FROM transactions WHERE void=0 AND tx_date>=? AND tx_date<=? GROUP BY kind, head, mode", (start, end))
    agg = {}   # (kind, head) -> {cash, bank, n}
    for r in rows:
        a = agg.setdefault((r["kind"], r["head"]), {"cash": 0.0, "bank": 0.0, "n": 0})
        a["cash" if r["mode"] in CASH_MODES else "bank"] += r["total"]; a["n"] += r["n"]
    natures = {h["key"]: h["nature"] for h in heads()}
    order = [h["key"] for h in heads()]

    def lines(kind):
        out = []
        for (k, head), a in agg.items():
            if k != kind:
                continue
            out.append({"head": head, "nature": natures.get(head, "income" if kind == "receipt" else "expense"), "cash": a["cash"], "bank": a["bank"], "total": a["cash"] + a["bank"], "n": a["n"], **_lbl(lab, head)})
        return sorted(out, key=lambda x: (order.index(x["head"]) if x["head"] in order else 999, x["head"]))

    receipts, payments = lines("receipt"), lines("payment")
    c2b = agg.get(("contra", "cash_to_bank"), {"cash": 0.0, "bank": 0.0})
    b2c = agg.get(("contra", "bank_to_cash"), {"cash": 0.0, "bank": 0.0})
    contra = {"cash_to_bank": c2b["cash"] + c2b["bank"], "bank_to_cash": b2c["cash"] + b2c["bank"]}
    op = openings(fy)
    rc, rb = sum(x["cash"] for x in receipts), sum(x["bank"] for x in receipts)
    pc, pb = sum(x["cash"] for x in payments), sum(x["bank"] for x in payments)
    closing_cash = op["cash"] + rc + contra["bank_to_cash"] - pc - contra["cash_to_bank"]
    closing_bank = op["bank"] + rb + contra["cash_to_bank"] - pb - contra["bank_to_cash"]
    income = [x for x in receipts if x["nature"] == "income"]
    expense = [x for x in payments if x["nature"] == "expense"]
    total_income, total_expense = sum(x["total"] for x in income), sum(x["total"] for x in expense)
    surplus = total_income - total_expense
    # balance sheet items
    items = []
    for it in balance_items():
        opening = op["items"].get(it["item"], 0.0)
        rec = sum(x["total"] for x in receipts if x["head"] in it.get("heads", [it["item"]]))
        pay = sum(x["total"] for x in payments if x["head"] in it.get("heads", [it["item"]]))
        if it["side"] == "asset":
            closing, add, less = opening + pay - rec, pay, rec
        else:
            closing, add, less = opening + rec - pay, rec, pay
        if opening or add or less:
            items.append({**it, "opening": opening, "added": add, "less": less, "closing": closing})
    for item, amt in op["items"].items():      # custom opening items without a head
        if item.startswith("x:") and not any(i["item"] == item for i in items):
            L = op["labels"].get(item, {})
            items.append({"item": item, "side": L.get("side") or "asset", "nature": "custom", "en": L.get("en") or item[2:], "ml": L.get("ml") or L.get("en") or item[2:], "opening": amt, "added": 0.0, "less": 0.0, "closing": amt})
    assets = [i for i in items if i["side"] == "asset"]
    liabs = [i for i in items if i["side"] == "liability"]
    gf_open = op["cash"] + op["bank"] + sum(i["opening"] for i in assets) - sum(i["opening"] for i in liabs)
    gf_close = gf_open + surplus
    total_assets = closing_cash + closing_bank + sum(i["closing"] for i in assets)
    total_liabs = gf_close + sum(i["closing"] for i in liabs)
    dues = db.one("SELECT COALESCE(SUM(s.amount-s.paid),0) n FROM subscriptions s JOIN members m ON m.id=s.member_id WHERE s.status='due' AND m.status='active'")["n"]
    return {"fy": fy, "start_on": start, "end_on": end, "status": fy_row(fy)["status"], "closed_at": fy_row(fy).get("closed_at"), "years": fy_list(),
            "opening": {"cash": op["cash"], "bank": op["bank"], "derived": op["derived"]}, "closing": {"cash": closing_cash, "bank": closing_bank},
            "receipts": receipts, "payments": payments, "contra": contra,
            "rp": {"receipts_cash": rc, "receipts_bank": rb, "payments_cash": pc, "payments_bank": pb,
                   "total_receipts": op["cash"] + op["bank"] + rc + rb + contra["cash_to_bank"] + contra["bank_to_cash"],
                   "total_payments": pc + pb + contra["cash_to_bank"] + contra["bank_to_cash"] + closing_cash + closing_bank},
            "ie": {"income": income, "expense": expense, "total_income": total_income, "total_expense": total_expense, "surplus": surplus},
            "bs": {"assets": assets, "liabilities": liabs, "general_fund": {"opening": gf_open, "surplus": surplus, "closing": gf_close}, "total_assets": total_assets, "total_liabilities": total_liabs,
                   "balanced": abs(total_assets - total_liabs) < 0.005},
            "memo": {"dues_outstanding": dues, "entries": sum(a["n"] for a in agg.values())}}


def daybook(fy, book):
    """Cash book or bank book: every entry with a running balance from the opening."""
    start, end = fy_bounds(fy)
    lab = labels()
    rows = db.q("SELECT t.id, t.kind, t.no, t.tx_date, t.head, t.mode, t.amount, t.party, t.ref, t.note, m.name_en, m.name_ml, m.member_no FROM transactions t LEFT JOIN members m ON m.id=t.member_id "
                "WHERE t.void=0 AND t.tx_date>=? AND t.tx_date<=? ORDER BY t.tx_date, t.id", (start, end))
    op = openings(fy)
    bal = op["cash"] if book == "cash" else op["bank"]
    out = []
    for r in rows:
        in_cash = r["mode"] in CASH_MODES
        dr = cr = 0.0
        if r["kind"] == "contra":
            if book == "cash":
                dr, cr = (r["amount"], 0.0) if r["head"] == "bank_to_cash" else (0.0, r["amount"])
            else:
                dr, cr = (r["amount"], 0.0) if r["head"] == "cash_to_bank" else (0.0, r["amount"])
        elif (book == "cash") == in_cash:
            dr, cr = (r["amount"], 0.0) if r["kind"] == "receipt" else (0.0, r["amount"])
        else:
            continue
        bal += dr - cr
        out.append({**r, "dr": dr, "cr": cr, "balance": bal, **_lbl(lab, r["head"])})
    return {"fy": fy, "book": book, "opening": op["cash"] if book == "cash" else op["bank"], "closing": bal, "rows": out,
            "total_dr": sum(x["dr"] for x in out), "total_cr": sum(x["cr"] for x in out)}


# ---------- endpoints ----------
@router.get("/heads")
def list_heads(user=Depends(require("finance.view"))):
    return {"heads": heads(), "contra": CONTRA_HEADS, "natures": NATURES, "fy_start_month": start_month(), "current_fy": current_fy()}


@router.get("/statements")
def get_statements(fy: str = "", user=Depends(require("finance.view"))):
    return statements(fy or current_fy())


@router.get("/book")
def get_book(fy: str = "", book: str = "cash", user=Depends(require("finance.view"))):
    return daybook(fy or current_fy(), "bank" if book == "bank" else "cash")


@router.get("/ledger")
def get_ledger(head: str, fy: str = "", user=Depends(require("finance.view"))):
    start, end = fy_bounds(fy or current_fy())
    rows = db.q("SELECT t.*, m.name_en, m.name_ml, m.member_no FROM transactions t LEFT JOIN members m ON m.id=t.member_id WHERE t.void=0 AND t.head=? AND t.tx_date>=? AND t.tx_date<=? ORDER BY t.tx_date, t.id", (head, start, end))
    run = 0.0
    for r in rows:
        run += r["amount"]; r["running"] = run
    return {"head": head, "label": _lbl(labels(), head), "nature": nature_of(head), "rows": rows, "total": run}


@router.get("/openings")
def get_openings(fy: str = "", user=Depends(require("finance.view"))):
    fy = fy or current_fy()
    op = openings(fy)
    items = [{**it, "amount": op["items"].get(it["item"], 0.0)} for it in balance_items()]
    return {"fy": fy, "cash": op["cash"], "bank": op["bank"], "items": items, "derived": op["derived"], "locked": op["derived"] or is_closed(fy)}


@router.post("/openings")
async def save_openings(request: Request, user=Depends(require("finance.manage"))):
    """Opening balances for the first year the club keeps its books here. Later years are carried forward by the year close."""
    b = await request.json()
    fy = b.get("fy") or current_fy()
    fy_bounds(fy)
    if is_closed(fy):
        raise HTTPException(423, "closed")
    if openings(fy)["derived"]:
        raise HTTPException(409, "carried forward from the previous year: reopen that year to change them")
    with db.tx() as c:
        c.execute("DELETE FROM fy_openings WHERE fy=?", (fy,))
        for item in ("cash", "bank"):
            db.insert(c, "fy_openings", {"fy": fy, "item": item, "amount": float(b.get(item) or 0), "side": "asset", "derived": 0})
        for it in b.get("items") or []:
            key = str(it.get("item") or "").strip()
            amt = float(it.get("amount") or 0)
            if not key:
                continue
            if key.startswith("x:") or key not in {x["item"] for x in balance_items()}:
                key = key if key.startswith("x:") else "x:" + key.lower().replace(" ", "_")
                db.insert(c, "fy_openings", {"fy": fy, "item": key, "amount": amt, "side": "liability" if it.get("side") == "liability" else "asset",
                                             "label_en": (it.get("en") or it.get("label_en") or key[2:])[:80], "label_ml": (it.get("ml") or it.get("label_ml") or "")[:80], "derived": 0})
            elif amt:
                db.insert(c, "fy_openings", {"fy": fy, "item": key, "amount": amt, "side": "", "derived": 0})
        db.audit(c, user["id"], "accounts.openings", "fy", None, fy)
    return {"ok": True}


@router.post("/contra")
async def add_contra(request: Request, user=Depends(require("finance.manage"))):
    """Cash deposited into the bank or drawn from it: moves money between the two books, no income or expense."""
    b = await request.json()
    head = b.get("head")
    if head not in CONTRA_HEADS:
        raise HTTPException(400, "head")
    amount = float(b.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(400, "amount")
    tx_date = b.get("tx_date") or dt.date.today().isoformat()
    assert_open(tx_date)
    year = int(tx_date[:4])
    with db.tx() as c:
        seq = db.next_counter(c, f"contra:{year}")
        row = {"kind": "contra", "no": f"C/{year}/{seq:04d}", "tx_date": tx_date, "head": head, "party": "", "amount": amount, "mode": "bank" if head == "cash_to_bank" else "cash",
               "ref": (b.get("ref") or "").strip(), "note": (b.get("note") or "").strip(), "year": year, "created_by": user["id"], "created": time.time()}
        row["id"] = db.insert(c, "transactions", row)
        db.audit(c, user["id"], "contra.record", "transaction", row["id"], f"{head} {amount}")
    return {"ok": True, "id": row["id"], "no": row["no"]}


def _earlier_open(fy):
    """The earliest financial year before `fy` that has entries and is not closed, if any."""
    start, _ = fy_bounds(fy)
    first = db.one("SELECT MIN(tx_date) d FROM transactions WHERE void=0 AND tx_date<?", (start,))["d"]
    if not first:
        return None
    y = int(fy_of(first)[:4])
    while y < int(fy[:4]):
        f = fy_label(y)
        if not is_closed(f):
            return f
        y += 1
    return None


@router.post("/close")
async def close_year(request: Request, user=Depends(require("finance.close"))):
    b = await request.json()
    fy = b.get("fy") or ""
    start, end = fy_bounds(fy)
    if is_closed(fy):
        raise HTTPException(409, "already closed")
    if end >= dt.date.today().isoformat():
        raise HTTPException(400, "the year has not ended yet")
    earlier = _earlier_open(fy)
    if earlier:
        raise HTTPException(409, f"close {earlier} first")
    st = statements(fy)
    nxt = fy_label(int(fy[:4]) + 1)
    if is_closed(nxt):
        raise HTTPException(409, f"{nxt} is already closed")
    with db.tx() as c:
        c.execute("DELETE FROM fy_years WHERE fy=?", (fy,))
        db.insert(c, "fy_years", {"fy": fy, "start_on": start, "end_on": end, "status": "closed", "closed_at": time.time(), "closed_by": user["id"], "note": (b.get("note") or "")[:500],
                                  "summary": json.dumps({"closing": st["closing"], "surplus": st["ie"]["surplus"], "general_fund": st["bs"]["general_fund"]["closing"], "total_assets": st["bs"]["total_assets"]})})
        c.execute("DELETE FROM fy_openings WHERE fy=?", (nxt,))
        db.insert(c, "fy_openings", {"fy": nxt, "item": "cash", "amount": st["closing"]["cash"], "side": "asset", "derived": 1})
        db.insert(c, "fy_openings", {"fy": nxt, "item": "bank", "amount": st["closing"]["bank"], "side": "asset", "derived": 1})
        for it in st["bs"]["assets"] + st["bs"]["liabilities"]:
            if it["closing"]:
                db.insert(c, "fy_openings", {"fy": nxt, "item": it["item"], "amount": it["closing"], "side": it["side"], "label_en": it["en"] if it["item"].startswith("x:") else "", "label_ml": it["ml"] if it["item"].startswith("x:") else "", "derived": 1})
        db.audit(c, user["id"], "accounts.close", "fy", None, f"{fy}: surplus {st['ie']['surplus']:.2f}, carried to {nxt}")
    return {"ok": True, "fy": fy, "next": nxt, "closing": st["closing"], "surplus": st["ie"]["surplus"]}


@router.post("/reopen")
async def reopen_year(request: Request, user=Depends(require("finance.close"))):
    b = await request.json()
    fy = b.get("fy") or ""
    fy_bounds(fy)
    if not is_closed(fy):
        raise HTTPException(409, "not closed")
    nxt = fy_label(int(fy[:4]) + 1)
    if is_closed(nxt):
        raise HTTPException(409, f"reopen {nxt} first")
    with db.tx() as c:
        c.execute("UPDATE fy_years SET status='open', note=? WHERE fy=?", ((b.get("note") or "")[:500], fy))
        c.execute("DELETE FROM fy_openings WHERE fy=? AND derived=1", (nxt,))
        db.audit(c, user["id"], "accounts.reopen", "fy", None, fy)
    return {"ok": True}


# ---------- Tally XML ----------
def _x(s):
    return html.escape(str(s or ""), quote=True)


@router.get("/tally.xml")
def tally_xml(fy: str = "", user=Depends(require("finance.view"))):
    """Vouchers of the year as Tally 'Import Data' XML (Gateway of Tally > Import > Vouchers), with the ledger masters
    they need. Debits are ISDEEMEDPOSITIVE=Yes with a negative amount, credits positive, as Tally expects."""
    fy = fy or current_fy()
    start, end = fy_bounds(fy)
    lab = labels(); natures = {h["key"]: h["nature"] for h in heads()}
    company = db.setting("club_name_en")
    rows = db.q("SELECT t.*, m.name_en FROM transactions t LEFT JOIN members m ON m.id=t.member_id WHERE t.void=0 AND t.tx_date>=? AND t.tx_date<=? ORDER BY t.tx_date, t.id", (start, end))
    msgs = ['<TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER NAME="Cash" ACTION="Create"><NAME.LIST><NAME>Cash</NAME></NAME.LIST><PARENT>Cash-in-Hand</PARENT></LEDGER></TALLYMESSAGE>',
            '<TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER NAME="Bank" ACTION="Create"><NAME.LIST><NAME>Bank</NAME></NAME.LIST><PARENT>Bank Accounts</PARENT></LEDGER></TALLYMESSAGE>']
    for head in sorted({r["head"] for r in rows if r["kind"] != "contra"}):
        name = _lbl(lab, head)["en"]
        msgs.append(f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><LEDGER NAME="{_x(name)}" ACTION="Create"><NAME.LIST><NAME>{_x(name)}</NAME></NAME.LIST><PARENT>{TALLY_GROUPS[natures.get(head, "income")]}</PARENT></LEDGER></TALLYMESSAGE>')

    def entry(ledger, amount, debit):
        return f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{_x(ledger)}</LEDGERNAME><ISDEEMEDPOSITIVE>{'Yes' if debit else 'No'}</ISDEEMEDPOSITIVE><AMOUNT>{-amount if debit else amount:.2f}</AMOUNT></ALLLEDGERENTRIES.LIST>"

    for r in rows:
        book = "Cash" if r["mode"] in CASH_MODES else "Bank"
        narration = " · ".join(x for x in [r.get("name_en") or r["party"], r["ref"], r["note"]] if x)
        if r["kind"] == "receipt":
            vtype, lines = "Receipt", entry(book, r["amount"], True) + entry(_lbl(lab, r["head"])["en"], r["amount"], False)
        elif r["kind"] == "payment":
            vtype, lines = "Payment", entry(_lbl(lab, r["head"])["en"], r["amount"], True) + entry(book, r["amount"], False)
        else:
            vtype = "Contra"
            lines = (entry("Bank", r["amount"], True) + entry("Cash", r["amount"], False)) if r["head"] == "cash_to_bank" else (entry("Cash", r["amount"], True) + entry("Bank", r["amount"], False))
        msgs.append(f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="{vtype}" ACTION="Create" OBJVIEW="Accounting Voucher View"><DATE>{r["tx_date"].replace("-", "")}</DATE>'
                    f'<VOUCHERTYPENAME>{vtype}</VOUCHERTYPENAME><VOUCHERNUMBER>{_x(r["no"])}</VOUCHERNUMBER><NARRATION>{_x(narration)}</NARRATION><PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>{lines}</VOUCHER></TALLYMESSAGE>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?><ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME>'
           f'<STATICVARIABLES><SVCURRENTCOMPANY>{_x(company)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC><REQUESTDATA>{"".join(msgs)}</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>')
    return Response(xml, media_type="application/xml", headers={"Content-Disposition": f"attachment; filename=clubpro-vouchers-{fy}.xml"})


# ---------- printable statements ----------
L = {"en": {"title": "Annual Accounts", "rp": "Receipts and Payments Account", "ie": "Income and Expenditure Account", "bs": "Balance Sheet", "for": "for the year", "asat": "as at",
            "receipts": "Receipts", "payments": "Payments", "income": "Income", "expenditure": "Expenditure", "cash": "Cash", "bank": "Bank", "total": "Total", "opening": "Opening balance",
            "closing": "Closing balance", "surplus": "Surplus for the year", "deficit": "Deficit for the year", "liabilities": "Liabilities", "assets": "Assets", "general_fund": "General fund",
            "add_surplus": "Add: surplus", "less_deficit": "Less: deficit", "cash_in_hand": "Cash in hand", "cash_at_bank": "Cash at bank", "additions": "additions", "memo": "Memo: subscription dues outstanding",
            "treasurer": "Treasurer", "secretary": "Secretary", "president": "President", "auditor": "Auditor", "cash_book": "Cash book", "bank_book": "Bank book", "date": "Date", "no": "No.",
            "particulars": "Particulars", "dr": "Receipts", "cr": "Payments", "balance": "Balance", "status_closed": "Accounts closed", "status_open": "Provisional"},
     "ml": {"title": "വാർഷിക കണക്കുകൾ", "rp": "വരവ് ചെലവ് കണക്ക് (Receipts & Payments)", "ie": "വരുമാന ചെലവ് കണക്ക് (Income & Expenditure)", "bs": "ബാലൻസ് ഷീറ്റ്", "for": "വർഷം", "asat": "തീയതിയിൽ",
            "receipts": "വരവ്", "payments": "ചെലവ്", "income": "വരുമാനം", "expenditure": "ചെലവ്", "cash": "പണം", "bank": "ബാങ്ക്", "total": "ആകെ", "opening": "ആരംഭ ബാക്കി",
            "closing": "അവസാന ബാക്കി", "surplus": "വർഷത്തെ മിച്ചം", "deficit": "വർഷത്തെ കമ്മി", "liabilities": "ബാധ്യതകൾ", "assets": "ആസ്തികൾ", "general_fund": "പൊതു ഫണ്ട്",
            "add_surplus": "കൂട്ടുക: മിച്ചം", "less_deficit": "കുറയ്ക്കുക: കമ്മി", "cash_in_hand": "കൈയിലുള്ള പണം", "cash_at_bank": "ബാങ്കിലുള്ള പണം", "additions": "കൂട്ടിച്ചേർത്തത്", "memo": "കുറിപ്പ്: വരിസംഖ്യ കുടിശ്ശിക",
            "treasurer": "ട്രഷറർ", "secretary": "സെക്രട്ടറി", "president": "പ്രസിഡന്റ്", "auditor": "ഓഡിറ്റർ", "cash_book": "ക്യാഷ് ബുക്ക്", "bank_book": "ബാങ്ക് ബുക്ക്", "date": "തീയതി", "no": "നം.",
            "particulars": "വിവരം", "dr": "വരവ്", "cr": "ചെലവ്", "balance": "ബാക്കി", "status_closed": "കണക്കുകൾ അടച്ചു", "status_open": "താൽക്കാലികം"}}


def _page(lang, title, body, s):
    c = brand.colors(s); e = html.escape
    return HTMLResponse(f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(title)}</title>{brand.html_head(s)}
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;max-width:900px;margin:0 auto;padding:24px;color:#1d2a28;line-height:1.45;font-size:.92rem}}h1{{margin:0;color:{c['primary']}}}h2{{border-bottom:2px solid {c['primary']};padding-bottom:4px;margin:26px 0 6px;font-size:1.05rem}}
.m{{color:#666;font-size:.85rem}}table{{width:100%;border-collapse:collapse;margin:6px 0}}td,th{{border:1px solid #bbb;padding:4px 8px;text-align:left;vertical-align:top}}td.n,th.n{{text-align:right;font-family:Inter;white-space:nowrap}}
tr.tot td{{font-weight:700;background:#f3f4f6}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:0}}.two table{{margin:0}}.two table:first-child td,.two table:first-child th{{border-right:0}}
.sign{{margin-top:46px;display:grid;grid-template-columns:repeat(4,1fr);gap:12px;text-align:center}}.sign div{{border-top:1px solid #999;padding-top:6px}}.pill{{display:inline-block;border-radius:999px;padding:1px 10px;font-size:.78rem;background:#eef;color:#334}}
@media print{{body{{padding:0;font-size:.85rem}}h2{{break-after:avoid}}table{{break-inside:auto}}tr{{break-inside:avoid}}.pb{{break-before:page}}}}</style></head><body>
{brand.logo_img(s, height=50)}<div class=m>{e(s['club_name_ml' if lang == 'ml' else 'club_name_en'])}{(' · ' + e(s['club_reg_no'])) if s['club_reg_no'] else ''}{(' · ' + e(s['club_place_' + lang])) if s.get('club_place_' + lang) else ''}</div>
{body}<script>setTimeout(()=>window.print(),500)</script></body></html>""")


def _money(n):
    return f"{n:,.2f}"


@router.get("/statements/print")
def statements_print(fy: str = "", lang: str = "ml", user=Depends(require("finance.view"))):
    lang = lang if lang in ("en", "ml") else "en"
    T = L[lang]; e = html.escape
    st = statements(fy or current_fy())
    s = db.settings_all()
    lab = lambda x: e(x[lang] or x["en"])  # noqa: E731
    period = f"{st['start_on'][8:10]}-{st['start_on'][5:7]}-{st['start_on'][:4]} – {st['end_on'][8:10]}-{st['end_on'][5:7]}-{st['end_on'][:4]}"
    # Receipts & Payments, two columns, cash and bank
    left = [f"<tr><td>{T['opening']} · {T['cash']}</td><td class=n>{_money(st['opening']['cash'])}</td></tr><tr><td>{T['opening']} · {T['bank']}</td><td class=n>{_money(st['opening']['bank'])}</td></tr>"]
    left += [f"<tr><td>{lab(x)}</td><td class=n>{_money(x['total'])}</td></tr>" for x in st["receipts"]]
    if st["contra"]["cash_to_bank"]:
        left.append(f"<tr><td>{lab(CONTRA_HEADS['cash_to_bank'])}</td><td class=n>{_money(st['contra']['cash_to_bank'])}</td></tr>")
    if st["contra"]["bank_to_cash"]:
        left.append(f"<tr><td>{lab(CONTRA_HEADS['bank_to_cash'])}</td><td class=n>{_money(st['contra']['bank_to_cash'])}</td></tr>")
    right = [f"<tr><td>{lab(x)}</td><td class=n>{_money(x['total'])}</td></tr>" for x in st["payments"]]
    if st["contra"]["cash_to_bank"]:
        right.append(f"<tr><td>{lab(CONTRA_HEADS['cash_to_bank'])}</td><td class=n>{_money(st['contra']['cash_to_bank'])}</td></tr>")
    if st["contra"]["bank_to_cash"]:
        right.append(f"<tr><td>{lab(CONTRA_HEADS['bank_to_cash'])}</td><td class=n>{_money(st['contra']['bank_to_cash'])}</td></tr>")
    right += [f"<tr><td>{T['closing']} · {T['cash']}</td><td class=n>{_money(st['closing']['cash'])}</td></tr><tr><td>{T['closing']} · {T['bank']}</td><td class=n>{_money(st['closing']['bank'])}</td></tr>"]
    while len(left) < len(right):
        left.append("<tr><td>&nbsp;</td><td></td></tr>")
    while len(right) < len(left):
        right.append("<tr><td>&nbsp;</td><td></td></tr>")
    rp = (f"<div class=two><table><tr><th>{T['receipts']}</th><th class=n>₹</th></tr>{''.join(left)}<tr class=tot><td>{T['total']}</td><td class=n>{_money(st['rp']['total_receipts'])}</td></tr></table>"
          f"<table><tr><th>{T['payments']}</th><th class=n>₹</th></tr>{''.join(right)}<tr class=tot><td>{T['total']}</td><td class=n>{_money(st['rp']['total_payments'])}</td></tr></table></div>")
    ie = st["ie"]
    li = [f"<tr><td>{lab(x)}</td><td class=n>{_money(x['total'])}</td></tr>" for x in ie["income"]]
    le = [f"<tr><td>{lab(x)}</td><td class=n>{_money(x['total'])}</td></tr>" for x in ie["expense"]]
    if ie["surplus"] >= 0:
        le.append(f"<tr><td><b>{T['surplus']}</b></td><td class=n>{_money(ie['surplus'])}</td></tr>")
    else:
        li.append(f"<tr><td><b>{T['deficit']}</b></td><td class=n>{_money(-ie['surplus'])}</td></tr>")
    while len(li) < len(le):
        li.append("<tr><td>&nbsp;</td><td></td></tr>")
    while len(le) < len(li):
        le.append("<tr><td>&nbsp;</td><td></td></tr>")
    tot = max(ie["total_income"], ie["total_expense"])
    iehtml = (f"<div class=two><table><tr><th>{T['income']}</th><th class=n>₹</th></tr>{''.join(li)}<tr class=tot><td>{T['total']}</td><td class=n>{_money(tot)}</td></tr></table>"
              f"<table><tr><th>{T['expenditure']}</th><th class=n>₹</th></tr>{''.join(le)}<tr class=tot><td>{T['total']}</td><td class=n>{_money(tot)}</td></tr></table></div>")
    bs = st["bs"]; gf = bs["general_fund"]
    ll = [f"<tr><td>{T['general_fund']}<div class=m>{T['opening']} {_money(gf['opening'])} · {T['add_surplus'] if gf['surplus'] >= 0 else T['less_deficit']} {_money(abs(gf['surplus']))}</div></td><td class=n>{_money(gf['closing'])}</td></tr>"]
    ll += [f"<tr><td>{lab(x)}<div class=m>{T['opening']} {_money(x['opening'])} + {_money(x['added'])} − {_money(x['less'])}</div></td><td class=n>{_money(x['closing'])}</td></tr>" for x in bs["liabilities"]]
    la = [f"<tr><td>{lab(x)}<div class=m>{T['opening']} {_money(x['opening'])} + {T['additions']} {_money(x['added'])} − {_money(x['less'])}</div></td><td class=n>{_money(x['closing'])}</td></tr>" for x in bs["assets"]]
    la += [f"<tr><td>{T['cash_in_hand']}</td><td class=n>{_money(st['closing']['cash'])}</td></tr><tr><td>{T['cash_at_bank']}</td><td class=n>{_money(st['closing']['bank'])}</td></tr>"]
    while len(ll) < len(la):
        ll.append("<tr><td>&nbsp;</td><td></td></tr>")
    while len(la) < len(ll):
        la.append("<tr><td>&nbsp;</td><td></td></tr>")
    bshtml = (f"<div class=two><table><tr><th>{T['liabilities']}</th><th class=n>₹</th></tr>{''.join(ll)}<tr class=tot><td>{T['total']}</td><td class=n>{_money(bs['total_liabilities'])}</td></tr></table>"
              f"<table><tr><th>{T['assets']}</th><th class=n>₹</th></tr>{''.join(la)}<tr class=tot><td>{T['total']}</td><td class=n>{_money(bs['total_assets'])}</td></tr></table></div>"
              f"<p class=m>{T['memo']}: ₹{_money(st['memo']['dues_outstanding'])}</p>")
    sign = f"<div class=sign><div>{T['treasurer']}</div><div>{T['secretary']}</div><div>{T['president']}</div><div>{T['auditor']}</div></div>"
    body = (f"<h1>{T['title']} {e(st['fy'])}</h1><div class=m>{T['for']} {period} · <span class=pill>{T['status_closed'] if st['status'] == 'closed' else T['status_open']}</span></div>"
            f"<h2>{T['rp']}</h2>{rp}{sign}<h2 class=pb>{T['ie']}</h2>{iehtml}{sign}<h2 class=pb>{T['bs']} · {T['asat']} {st['end_on'][8:10]}-{st['end_on'][5:7]}-{st['end_on'][:4]}</h2>{bshtml}{sign}")
    return _page(lang, f"{T['title']} {st['fy']}", body, s)


@router.get("/book/print")
def book_print(fy: str = "", book: str = "cash", lang: str = "ml", user=Depends(require("finance.view"))):
    lang = lang if lang in ("en", "ml") else "en"
    T = L[lang]; e = html.escape
    d = daybook(fy or current_fy(), "bank" if book == "bank" else "cash")
    s = db.settings_all()
    rows = "".join(f"<tr><td>{e(r['tx_date'][8:10])}-{e(r['tx_date'][5:7])}-{e(r['tx_date'][:4])}</td><td>{e(r['no'])}</td><td>{e(r[lang] or r['en'])}{(' · ' + e(i18n.pick(r, 'name', lang) or r['party'])) if (r.get('name_en') or r['party']) else ''}{(' · ' + e(r['ref'])) if r['ref'] else ''}</td>"
                   f"<td class=n>{_money(r['dr']) if r['dr'] else ''}</td><td class=n>{_money(r['cr']) if r['cr'] else ''}</td><td class=n>{_money(r['balance'])}</td></tr>" for r in d["rows"])
    body = (f"<h1>{T['cash_book'] if d['book'] == 'cash' else T['bank_book']} {e(d['fy'])}</h1>"
            f"<table><tr><th>{T['date']}</th><th>{T['no']}</th><th>{T['particulars']}</th><th class=n>{T['dr']}</th><th class=n>{T['cr']}</th><th class=n>{T['balance']}</th></tr>"
            f"<tr><td></td><td></td><td>{T['opening']}</td><td class=n></td><td class=n></td><td class=n>{_money(d['opening'])}</td></tr>{rows}"
            f"<tr class=tot><td></td><td></td><td>{T['total']} · {T['closing']}</td><td class=n>{_money(d['total_dr'])}</td><td class=n>{_money(d['total_cr'])}</td><td class=n>{_money(d['closing'])}</td></tr></table>"
            f"<div class=sign><div>{T['treasurer']}</div><div>{T['secretary']}</div><div>{T['president']}</div><div>{T['auditor']}</div></div>")
    return _page(lang, f"{T['cash_book']} {d['fy']}", body, s)
