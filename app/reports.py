"""The dashboard and the reports screen: counts that tell the office what needs doing today."""
import datetime as dt

from fastapi import APIRouter, Depends

from . import db
from .auth import can, current_user, require

router = APIRouter(prefix="/api/reports")


def _n(sql, args=()):
    return db.one(sql, args)["n"]


def dashboard(user):
    today = dt.date.today()
    t = today.isoformat()
    out = {"today": t}
    mid = user.get("member_id")
    out["upcoming"] = db.q("SELECT id, kind, title_en, title_ml, starts_at, venue_en, venue_ml, reg_open, audience FROM posts WHERE status='published' AND deleted=0 AND starts_at>=? "
                           "AND audience IN ('public','members') ORDER BY starts_at LIMIT 6", (t,))
    out["latest"] = db.q("SELECT id, kind, title_en, title_ml, published_at, cover, audience FROM posts WHERE status='published' AND deleted=0 AND audience IN ('public','members') "
                         "ORDER BY pinned DESC, published_at DESC LIMIT 6")
    out["birthdays"] = db.q("SELECT id, name_en, name_ml, dob FROM members WHERE status='active' AND substr(dob,6,5)=? ORDER BY name_en", (t[5:],))
    if mid:
        out["my_meetings"] = db.q("SELECT m.id, m.title_en, m.title_ml, m.scheduled_at, c.name_en AS committee_en, c.name_ml AS committee_ml FROM meetings m JOIN committees c ON c.id=m.committee_id "
                                  "WHERE m.deleted=0 AND m.status='scheduled' AND m.scheduled_at>=? AND (c.kind='general' OR m.committee_id IN (SELECT committee_id FROM committee_members WHERE member_id=? AND active=1)) "
                                  "ORDER BY m.scheduled_at LIMIT 5", (t, mid))
        out["my_actions"] = _n("SELECT COUNT(*) n FROM actions WHERE owner_member_id=? AND status IN ('open','in_progress')", (mid,))
        out["my_books"] = db.q("SELECT i.id, i.due_on, b.title_en, b.title_ml FROM issues i JOIN books b ON b.id=i.book_id WHERE i.member_id=? AND i.returned_on='' ORDER BY i.due_on", (mid,))
        out["my_dues"] = db.one("SELECT COALESCE(SUM(amount-paid),0) n FROM subscriptions WHERE member_id=? AND status='due'", (mid,))["n"]
        out["unread"] = _n("SELECT COUNT(*) n FROM notifications WHERE member_id=? AND read_at IS NULL", (mid,))
    if can(user, "members.view") or can(user, "library.manage") or can(user, "finance.view"):
        month = t[:7]
        out["office"] = {
            "members_active": _n("SELECT COUNT(*) n FROM members WHERE status='active'"),
            "applications": _n("SELECT COUNT(*) n FROM members WHERE status='applied'"),
            "new_this_month": _n("SELECT COUNT(*) n FROM members WHERE status='active' AND joined_on LIKE ?", (month + "%",)),
            "family": _n("SELECT COUNT(*) n FROM family f JOIN members m ON m.id=f.member_id WHERE f.deleted=0 AND m.status='active'"),
            "meetings_month": _n("SELECT COUNT(*) n FROM meetings WHERE deleted=0 AND scheduled_at LIKE ?", (month + "%",)),
            "mom_drafts": _n("SELECT COUNT(*) n FROM meetings WHERE deleted=0 AND status IN ('held','scheduled') AND scheduled_at<? AND mom_status='draft'", (t,)),
            "actions_open": _n("SELECT COUNT(*) n FROM actions WHERE status IN ('open','in_progress')"),
            "actions_overdue": _n("SELECT COUNT(*) n FROM actions WHERE status IN ('open','in_progress') AND due<>'' AND due<?", (t,)),
            "books": _n("SELECT COUNT(*) n FROM copies WHERE status<>'withdrawn'"),
            "books_out": _n("SELECT COUNT(*) n FROM issues WHERE returned_on=''"),
            "books_overdue": _n("SELECT COUNT(*) n FROM issues WHERE returned_on='' AND due_on<?", (t,)),
            "reading_room_today": _n("SELECT COUNT(*) n FROM reading_room WHERE visited_on=?", (t,)),
            "dues_members": _n("SELECT COUNT(DISTINCT s.member_id) n FROM subscriptions s JOIN members m ON m.id=s.member_id WHERE s.status='due' AND m.status='active'"),
            "dues_amount": db.one("SELECT COALESCE(SUM(s.amount-s.paid),0) n FROM subscriptions s JOIN members m ON m.id=s.member_id WHERE s.status='due' AND m.status='active'")["n"],
            "receipts_month": db.one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE void=0 AND kind='receipt' AND tx_date LIKE ?", (month + "%",))["n"],
            "payments_month": db.one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE void=0 AND kind='payment' AND tx_date LIKE ?", (month + "%",))["n"],
            "outbox_pending": _n("SELECT COUNT(*) n FROM outbox WHERE status='pending'"),
            "outbox_failed": _n("SELECT COUNT(*) n FROM outbox WHERE status='failed'"),
            "outbox_demo": _n("SELECT COUNT(*) n FROM outbox WHERE status='demo'"),
        }
    return out


@router.get("/overview")
def overview(user=Depends(require("reports.view"))):
    year = dt.date.today().year
    return {
        "by_type": db.q("SELECT membership_type k, COUNT(*) n FROM members WHERE status='active' GROUP BY membership_type ORDER BY n DESC"),
        "by_ward": db.q("SELECT ward k, COUNT(*) n FROM members WHERE status='active' GROUP BY ward ORDER BY n DESC"),
        "by_gender": db.q("SELECT gender k, COUNT(*) n FROM members WHERE status='active' GROUP BY gender"),
        "by_blood": db.q("SELECT blood_group k, COUNT(*) n FROM members WHERE status='active' AND blood_group<>'' GROUP BY blood_group ORDER BY k"),
        "by_status": db.q("SELECT status k, COUNT(*) n FROM members GROUP BY status"),
        "joined_by_year": db.q("SELECT substr(joined_on,1,4) k, COUNT(*) n FROM members WHERE status='active' AND joined_on<>'' GROUP BY k ORDER BY k"),
        "age_bands": db.q("SELECT CASE WHEN dob='' THEN 'unknown' WHEN (?-CAST(substr(dob,1,4) AS INTEGER))<18 THEN '<18' WHEN (?-CAST(substr(dob,1,4) AS INTEGER))<36 THEN '18-35' "
                          "WHEN (?-CAST(substr(dob,1,4) AS INTEGER))<60 THEN '36-59' ELSE '60+' END k, COUNT(*) n FROM members WHERE status='active' GROUP BY k", (year, year, year)),
        "events_by_kind": db.q("SELECT kind k, COUNT(*) n FROM posts WHERE deleted=0 AND status='published' AND published_at>=? GROUP BY kind", (dt.datetime(year, 1, 1).timestamp(),)),
        "participation": db.q("SELECT p.id, p.title_en, p.title_ml, p.kind, p.starts_at, COUNT(r.id) n FROM posts p JOIN registrations r ON r.post_id=p.id AND r.status<>'cancelled' "
                              "WHERE p.deleted=0 GROUP BY p.id ORDER BY p.starts_at DESC LIMIT 20"),
        "meeting_attendance": db.q("SELECT c.name_en, c.name_ml, COUNT(DISTINCT m.id) meetings, COUNT(a.member_id) present FROM meetings m JOIN committees c ON c.id=m.committee_id "
                                   "LEFT JOIN attendance a ON a.meeting_id=m.id AND a.status IN ('present','online') WHERE m.deleted=0 AND m.status='held' GROUP BY c.id"),
        "library_popular": db.q("SELECT b.title_en, b.title_ml, b.author_en, COUNT(i.id) n FROM issues i JOIN books b ON b.id=i.book_id GROUP BY b.id ORDER BY n DESC LIMIT 15"),
        "library_by_language": db.q("SELECT b.language k, COUNT(c.id) n FROM copies c JOIN books b ON b.id=c.book_id WHERE b.deleted=0 GROUP BY b.language"),
        "library_monthly": db.q("SELECT substr(issued_on,1,7) k, COUNT(*) n FROM issues WHERE issued_on LIKE ? GROUP BY k ORDER BY k", (f"{year}%",)),
        "active_readers": db.q("SELECT m.name_en, m.name_ml, m.member_no, COUNT(i.id) n FROM issues i JOIN members m ON m.id=i.member_id WHERE i.issued_on LIKE ? GROUP BY m.id ORDER BY n DESC LIMIT 15", (f"{year}%",)),
        "reading_room_monthly": db.q("SELECT substr(visited_on,1,7) k, COUNT(*) n FROM reading_room WHERE visited_on LIKE ? GROUP BY k ORDER BY k", (f"{year}%",)),
        "comms": db.q("SELECT channel, status, COUNT(*) n FROM outbox GROUP BY channel, status"),
    }
