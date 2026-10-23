"""Library and reading room: catalogue with accession-numbered copies, issue / return / renew with fines,
reservations, the reading room register and the newspaper & periodical register."""
import csv
import datetime as dt
import io
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from . import comms, db, i18n
from .auth import can, current_user, require

router = APIRouter(prefix="/api/library")
BOOK_FIELDS = ["title_en", "title_ml", "author_en", "author_ml", "publisher", "language", "category", "isbn", "year", "price", "rack", "pages", "notes", "donated_by", "cover"]
CATEGORIES = ["novel", "story", "poetry", "drama", "essay", "biography", "history", "science", "children", "reference", "religion", "politics", "travel", "self_help", "textbook", "other"]


def rules():
    return {"loan_days": int(db.setting("library_loan_days")), "max_books": int(db.setting("library_max_books")),
            "fine_per_day": float(db.setting("library_fine_per_day")), "max_renewals": int(db.setting("library_max_renewals"))}


def _book(bid):
    b = db.one("SELECT * FROM books WHERE id=? AND deleted=0", (bid,))
    if not b:
        raise HTTPException(404)
    return b


def _next_accession(c):
    seq = db.next_counter(c, "accession")
    return db.setting("accession_format").format(seq=seq, year=dt.date.today().year)


def fine_for(due_on, returned_on=None):
    r = rules()
    end = dt.date.fromisoformat(returned_on) if returned_on else dt.date.today()
    late = (end - dt.date.fromisoformat(due_on)).days
    return (max(0, late) * r["fine_per_day"], max(0, late))


# ---------- catalogue ----------
@router.get("/books")
def list_books(q: str = "", category: str = "", language: str = "", available: int = 0, user=Depends(current_user)):
    where, args = ["b.deleted=0"], []
    if q:
        like = f"%{q.strip()}%"
        where.append("(b.title_en LIKE ? OR b.title_ml LIKE ? OR b.author_en LIKE ? OR b.author_ml LIKE ? OR b.isbn LIKE ? OR EXISTS(SELECT 1 FROM copies c WHERE c.book_id=b.id AND c.accession_no LIKE ?))")
        args += [like] * 6
    if category:
        where.append("b.category=?"); args.append(category)
    if language:
        where.append("b.language=?"); args.append(language)
    rows = db.q(f"SELECT b.*, (SELECT COUNT(*) FROM copies c WHERE c.book_id=b.id AND c.status<>'withdrawn') AS copies, "
                f"(SELECT COUNT(*) FROM copies c WHERE c.book_id=b.id AND c.status='available') AS available, "
                f"(SELECT COUNT(*) FROM reservations r WHERE r.book_id=b.id AND r.status='waiting') AS waiting "
                f"FROM books b WHERE {' AND '.join(where)} ORDER BY b.title_en LIMIT 500", args)
    if available:
        rows = [r for r in rows if r["available"]]
    return rows


@router.get("/books/{bid}")
def get_book(bid: int, user=Depends(current_user)):
    b = _book(bid)
    b["copies"] = db.q("SELECT c.*, (SELECT i.member_id FROM issues i WHERE i.copy_id=c.id AND i.returned_on='' LIMIT 1) AS issued_to, "
                       "(SELECT i.due_on FROM issues i WHERE i.copy_id=c.id AND i.returned_on='' LIMIT 1) AS due_on FROM copies c WHERE c.book_id=? ORDER BY c.accession_no", (bid,))
    if can(user, "library.manage"):
        b["history"] = db.q("SELECT i.*, m.name_en, m.name_ml, m.member_no, c.accession_no FROM issues i JOIN members m ON m.id=i.member_id JOIN copies c ON c.id=i.copy_id WHERE i.book_id=? ORDER BY i.id DESC LIMIT 30", (bid,))
        b["reservations"] = db.q("SELECT r.*, m.name_en, m.name_ml, m.phone FROM reservations r JOIN members m ON m.id=r.member_id WHERE r.book_id=? AND r.status IN ('waiting','ready') ORDER BY r.id", (bid,))
    else:
        for cp in b["copies"]:
            cp.pop("issued_to", None)
        b["my_reservation"] = db.one("SELECT * FROM reservations WHERE book_id=? AND member_id=? AND status IN ('waiting','ready')", (bid, user.get("member_id") or -1))
    return b


@router.post("/books")
async def save_book(request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    row = {k: b.get(k) for k in BOOK_FIELDS if k in b}
    for k in list(row):
        if k == "price":
            row[k] = float(row[k] or 0)
        elif k == "pages":
            row[k] = int(row[k] or 0)
        else:
            row[k] = (row[k] or "").strip()
    if "category" in row and row["category"] not in CATEGORIES:
        row["category"] = "other"
    now = time.time()
    with db.tx() as c:
        if b.get("id"):
            row["updated"] = now
            db.update(c, "books", b["id"], row); bid = b["id"]
        else:
            if not (row.get("title_en") or row.get("title_ml")):
                raise HTTPException(400, "title")
            row["title_en"] = row.get("title_en") or row.get("title_ml")
            row.update({"created": now, "updated": now}); bid = db.insert(c, "books", row)
        new_copies = int(b.get("add_copies") or (0 if b.get("id") else 1))
        accs = []
        for i in range(new_copies):
            given = (b.get("accession_nos") or [])[i:i + 1]
            acc = (given[0].strip() if given and given[0] else "") or _next_accession(c)
            if db.one("SELECT 1 FROM copies WHERE accession_no=?", (acc,)):
                raise HTTPException(409, f"accession {acc} already exists")
            db.insert(c, "copies", {"book_id": bid, "accession_no": acc, "status": "available", "rack": row.get("rack", ""), "added": now})
            accs.append(acc)
        db.audit(c, user["id"], "book.save", "book", bid, ",".join(accs))
    return {"ok": True, "id": bid, "accession_nos": accs}


@router.post("/copies/{cid}/status")
async def copy_status(cid: int, request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    st = b.get("status")
    if st not in ("available", "lost", "damaged", "withdrawn", "binding"):
        raise HTTPException(400, "status")
    if db.one("SELECT 1 FROM issues WHERE copy_id=? AND returned_on=''", (cid,)):
        raise HTTPException(400, "copy is issued - return it first")
    with db.tx() as c:
        db.update(c, "copies", cid, {"status": st, "note": b.get("note") or "", "rack": b.get("rack") if b.get("rack") is not None else db.one("SELECT rack FROM copies WHERE id=?", (cid,))["rack"]})
    return {"ok": True}


# ---------- circulation ----------
@router.get("/issues")
def list_issues(open_only: int = 1, overdue: int = 0, member_id: int = 0, user=Depends(current_user)):
    where, args = ["1=1"], []
    if not can(user, "library.manage"):
        member_id = user.get("member_id") or -1
    if member_id:
        where.append("i.member_id=?"); args.append(member_id)
    if open_only:
        where.append("i.returned_on=''")
    if overdue:
        where.append("i.returned_on='' AND i.due_on<?"); args.append(dt.date.today().isoformat())
    rows = db.q(f"SELECT i.*, b.title_en, b.title_ml, b.author_en, b.author_ml, c.accession_no, m.name_en, m.name_ml, m.member_no, m.phone "
                f"FROM issues i JOIN books b ON b.id=i.book_id JOIN copies c ON c.id=i.copy_id JOIN members m ON m.id=i.member_id WHERE {' AND '.join(where)} ORDER BY i.due_on, i.id DESC LIMIT 500", args)
    today = dt.date.today().isoformat()
    for r in rows:
        if not r["returned_on"]:
            r["fine_now"], r["days_late"] = fine_for(r["due_on"])
            r["overdue"] = r["due_on"] < today
    return rows


@router.post("/issue")
async def issue_book(request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    r = rules()
    member_id = int(b.get("member_id") or 0)
    m = db.one("SELECT * FROM members WHERE id=? AND status='active'", (member_id,))
    if not m:
        raise HTTPException(404, "member not active")
    if b.get("accession_no"):
        cp = db.one("SELECT * FROM copies WHERE accession_no=?", (b["accession_no"].strip(),))
    else:
        cp = db.one("SELECT * FROM copies WHERE book_id=? AND status='available' ORDER BY accession_no LIMIT 1", (b.get("book_id"),))
    if not cp:
        raise HTTPException(404, "no available copy")
    if cp["status"] != "available":
        raise HTTPException(400, f"copy is {cp['status']}")
    out = db.one("SELECT COUNT(*) n FROM issues WHERE member_id=? AND returned_on=''", (member_id,))["n"]
    if out >= r["max_books"] and not b.get("override"):
        raise HTTPException(400, f"member already has {out} books (limit {r['max_books']})")
    if db.one("SELECT 1 FROM issues WHERE member_id=? AND returned_on='' AND due_on<?", (member_id, dt.date.today().isoformat())) and not b.get("override"):
        raise HTTPException(400, "member has an overdue book")
    # a waiting reservation by someone else blocks the copy unless this member is first in line
    res = db.one("SELECT * FROM reservations WHERE book_id=? AND status IN ('waiting','ready') ORDER BY id LIMIT 1", (cp["book_id"],))
    if res and res["member_id"] != member_id and not b.get("override"):
        avail = db.one("SELECT COUNT(*) n FROM copies WHERE book_id=? AND status='available'", (cp["book_id"],))["n"]
        if avail <= 1:
            raise HTTPException(400, "the last copy is reserved for another member")
    today = dt.date.today()
    due = (today + dt.timedelta(days=int(b.get("days") or r["loan_days"]))).isoformat()
    book = _book(cp["book_id"])
    with db.tx() as c:
        iid = db.insert(c, "issues", {"copy_id": cp["id"], "book_id": cp["book_id"], "member_id": member_id, "issued_on": today.isoformat(), "due_on": due,
                                      "issued_by": user["id"], "created": time.time(), "note": b.get("note") or ""})
        db.update(c, "copies", cp["id"], {"status": "issued"})
        if res and res["member_id"] == member_id:
            db.update(c, "reservations", res["id"], {"status": "fulfilled", "closed_at": time.time()})
        if b.get("notify", True):
            comms.notify_members(c, [member_id], "book_issued", {"acc": cp["accession_no"], "due": due}, ("app", "whatsapp"), ref_kind="issue", ref_id=iid,
                                 per_member=lambda mm: {"book": i18n.pick(book, "title", mm["lang"])})
        db.audit(c, user["id"], "book.issue", "issue", iid, cp["accession_no"])
    return {"ok": True, "id": iid, "due_on": due, "accession_no": cp["accession_no"]}


@router.post("/return")
async def return_book(request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    if b.get("issue_id"):
        i = db.one("SELECT * FROM issues WHERE id=? AND returned_on=''", (b["issue_id"],))
    else:
        i = db.one("SELECT i.* FROM issues i JOIN copies c ON c.id=i.copy_id WHERE c.accession_no=? AND i.returned_on=''", ((b.get("accession_no") or "").strip(),))
    if not i:
        raise HTTPException(404, "no open issue for that")
    today = dt.date.today().isoformat()
    fine, _ = fine_for(i["due_on"], today)
    if b.get("waive"):
        fine = 0
    with db.tx() as c:
        db.update(c, "issues", i["id"], {"returned_on": today, "fine": fine, "returned_by": user["id"], "fine_paid": 1 if (fine == 0) else 0})
        db.update(c, "copies", i["copy_id"], {"status": b.get("condition") or "available"})
        receipt = None
        if fine and b.get("collect_fine", True):
            from . import finance
            receipt = finance.record(c, user["id"], {"kind": "receipt", "head": "library_fine", "member_id": i["member_id"], "amount": fine, "mode": b.get("mode") or "cash",
                                                     "note": f"issue #{i['id']}"}, notify=False)
            db.update(c, "issues", i["id"], {"fine_paid": 1, "receipt_id": receipt["id"]})
        # next in the reservation queue
        res = db.one("SELECT * FROM reservations WHERE book_id=? AND status='waiting' ORDER BY id LIMIT 1", (i["book_id"],))
        if res:
            book = _book(i["book_id"])
            db.update(c, "reservations", res["id"], {"status": "ready", "notified_at": time.time()})
            comms.notify_members(c, [res["member_id"]], "reservation_ready", {}, ("app", "whatsapp", "sms"), ref_kind="book", ref_id=i["book_id"],
                                 per_member=lambda mm: {"book": i18n.pick(book, "title", mm["lang"])})
        db.audit(c, user["id"], "book.return", "issue", i["id"], f"fine {fine}")
    return {"ok": True, "fine": fine, "receipt": receipt}


@router.post("/renew")
async def renew(request: Request, user=Depends(current_user)):
    b = await request.json()
    i = db.one("SELECT * FROM issues WHERE id=? AND returned_on=''", (b.get("issue_id"),))
    if not i:
        raise HTTPException(404)
    if not (can(user, "library.manage") or i["member_id"] == user.get("member_id")):
        raise HTTPException(403, "no")
    r = rules()
    if i["renewals"] >= r["max_renewals"] and not can(user, "library.manage"):
        raise HTTPException(400, "no renewals left - please visit the library")
    if i["due_on"] < dt.date.today().isoformat() and not can(user, "library.manage"):
        raise HTTPException(400, "overdue books cannot be renewed online")
    if db.one("SELECT 1 FROM reservations WHERE book_id=? AND status='waiting'", (i["book_id"],)):
        raise HTTPException(400, "another member is waiting for this book")
    due = (dt.date.fromisoformat(i["due_on"]) + dt.timedelta(days=r["loan_days"])).isoformat()
    with db.tx() as c:
        db.update(c, "issues", i["id"], {"due_on": due, "renewals": i["renewals"] + 1})
    return {"ok": True, "due_on": due}


@router.post("/reserve")
async def reserve(request: Request, user=Depends(current_user)):
    b = await request.json()
    mid = b.get("member_id") if can(user, "library.manage") and b.get("member_id") else user.get("member_id")
    if not mid:
        raise HTTPException(403, "members only")
    book = _book(b.get("book_id"))
    if db.one("SELECT 1 FROM reservations WHERE book_id=? AND member_id=? AND status IN ('waiting','ready')", (book["id"], mid)):
        raise HTTPException(409, "already reserved")
    with db.tx() as c:
        rid = db.insert(c, "reservations", {"book_id": book["id"], "member_id": mid, "status": "waiting", "created": time.time()})
    return {"ok": True, "id": rid}


@router.post("/reservations/{rid}/cancel")
def cancel_reservation(rid: int, user=Depends(current_user)):
    r = db.one("SELECT * FROM reservations WHERE id=?", (rid,))
    if not r or not (can(user, "library.manage") or r["member_id"] == user.get("member_id")):
        raise HTTPException(404)
    with db.tx() as c:
        db.update(c, "reservations", rid, {"status": "cancelled", "closed_at": time.time()})
    return {"ok": True}


# ---------- reading room ----------
@router.get("/reading-room")
def reading_room(date: str = "", user=Depends(require("library.manage"))):
    date = date or dt.date.today().isoformat()
    rows = db.q("SELECT r.*, m.name_en, m.name_ml, m.member_no FROM reading_room r LEFT JOIN members m ON m.id=r.member_id WHERE r.visited_on=? ORDER BY r.id", (date,))
    month = db.q("SELECT visited_on, COUNT(*) n FROM reading_room WHERE visited_on LIKE ? GROUP BY visited_on ORDER BY visited_on", (date[:7] + "%",))
    return {"rows": rows, "month": month}


@router.post("/reading-room")
async def reading_room_add(request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    with db.tx() as c:
        rid = db.insert(c, "reading_room", {"member_id": b.get("member_id") or None, "visitor_name": b.get("visitor_name") or "", "visited_on": b.get("visited_on") or dt.date.today().isoformat(),
                                            "time_in": b.get("time_in") or dt.datetime.now().strftime("%H:%M"), "time_out": b.get("time_out") or "", "purpose": b.get("purpose") or "",
                                            "created": time.time(), "recorded_by": user["id"]})
    return {"ok": True, "id": rid}


@router.post("/reading-room/{rid}/out")
def reading_room_out(rid: int, user=Depends(require("library.manage"))):
    with db.tx() as c:
        db.update(c, "reading_room", rid, {"time_out": dt.datetime.now().strftime("%H:%M")})
    return {"ok": True}


# ---------- periodicals ----------
@router.get("/periodicals")
def periodicals(user=Depends(current_user)):
    rows = db.q("SELECT p.*, (SELECT MAX(received_on) FROM periodical_receipts r WHERE r.periodical_id=p.id) AS last_received FROM periodicals p ORDER BY p.active DESC, p.kind, p.title_en")
    return rows


@router.post("/periodicals")
async def save_periodical(request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    row = {"title_en": b.get("title_en") or b.get("title_ml") or "", "title_ml": b.get("title_ml") or "", "kind": b.get("kind") or "newspaper", "language": b.get("language") or "ml",
           "agent": b.get("agent") or "", "sub_from": b.get("sub_from") or "", "sub_to": b.get("sub_to") or "", "cost": float(b.get("cost") or 0), "active": 1 if b.get("active", 1) else 0}
    if not row["title_en"]:
        raise HTTPException(400, "title")
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "periodicals", b["id"], row); pid = b["id"]
        else:
            row["created"] = time.time(); pid = db.insert(c, "periodicals", row)
    return {"ok": True, "id": pid}


@router.post("/periodicals/{pid}/received")
async def periodical_received(pid: int, request: Request, user=Depends(require("library.manage"))):
    b = await request.json()
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO periodical_receipts(periodical_id, received_on, issue_ref, created, recorded_by) VALUES(?,?,?,?,?)",
                  (pid, b.get("received_on") or dt.date.today().isoformat(), b.get("issue_ref") or "", time.time(), user["id"]))
    return {"ok": True}


@router.get("/periodicals/{pid}/receipts")
def periodical_receipts(pid: int, month: str = "", user=Depends(require("library.manage"))):
    month = month or dt.date.today().strftime("%Y-%m")
    return db.q("SELECT * FROM periodical_receipts WHERE periodical_id=? AND received_on LIKE ? ORDER BY received_on", (pid, month + "%"))


@router.get("/export/catalogue.csv")
def export_catalogue(user=Depends(require("library.manage"))):
    rows = db.q("SELECT c.accession_no, b.title_en, b.title_ml, b.author_en, b.author_ml, b.publisher, b.language, b.category, b.isbn, b.year, b.price, c.rack, c.status "
                "FROM copies c JOIN books b ON b.id=c.book_id WHERE b.deleted=0 ORDER BY c.accession_no")
    buf = io.StringIO(); buf.write("﻿"); w = csv.writer(buf)
    if rows:
        w.writerow(rows[0].keys())
        for r in rows:
            w.writerow(r.values())
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=catalogue.csv"})
