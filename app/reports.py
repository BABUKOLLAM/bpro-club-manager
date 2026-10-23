"""The dashboard and the reports screen: counts that tell the office what needs doing today."""
import datetime as dt

from fastapi import APIRouter, Depends

from . import brand, db
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


# ---------- annual report ----------
def annual(year):
    y = str(year)
    like = y + "%"
    start = dt.datetime(year, 1, 1).timestamp(); end = dt.datetime(year + 1, 1, 1).timestamp()
    r = {"year": year}
    r["members"] = {"active": _n("SELECT COUNT(*) n FROM members WHERE status='active'"), "joined": _n("SELECT COUNT(*) n FROM members WHERE joined_on LIKE ? AND status<>'rejected'", (like,)),
                    "left": _n("SELECT COUNT(*) n FROM members WHERE status IN ('resigned','deceased','inactive') AND updated>=? AND updated<?", (start, end)),
                    "family": _n("SELECT COUNT(*) n FROM family f JOIN members m ON m.id=f.member_id WHERE f.deleted=0 AND m.status='active'"),
                    "by_type": db.q("SELECT membership_type k, COUNT(*) n FROM members WHERE status='active' GROUP BY k ORDER BY n DESC")}
    r["events"] = db.q("SELECT p.id, p.kind, p.title_en, p.title_ml, p.starts_at, p.level, (SELECT COUNT(*) FROM registrations x WHERE x.post_id=p.id AND x.status IN ('registered','attended')) participants "
                       "FROM posts p WHERE p.deleted=0 AND p.status='published' AND p.kind<>'news' AND (p.starts_at LIKE ? OR (p.starts_at='' AND p.published_at>=? AND p.published_at<?)) ORDER BY p.starts_at", (like, start, end))
    r["news_count"] = _n("SELECT COUNT(*) n FROM posts WHERE deleted=0 AND status='published' AND kind='news' AND published_at>=? AND published_at<?", (start, end))
    r["meetings"] = db.q("SELECT c.name_en, c.name_ml, COUNT(m.id) meetings, COALESCE(AVG((SELECT COUNT(*) FROM attendance a WHERE a.meeting_id=m.id AND a.status IN ('present','online'))),0) avg_present "
                         "FROM meetings m JOIN committees c ON c.id=m.committee_id WHERE m.deleted=0 AND m.status='held' AND m.scheduled_at LIKE ? GROUP BY c.id ORDER BY c.sort", (like,))
    r["resolutions"] = db.q("SELECT a.resolution_no, a.title_en, a.title_ml, a.decision_en, a.decision_ml, m.scheduled_at, c.name_en AS committee_en, c.name_ml AS committee_ml FROM agenda_items a JOIN meetings m ON m.id=a.meeting_id "
                            "JOIN committees c ON c.id=m.committee_id WHERE m.deleted=0 AND m.scheduled_at LIKE ? AND a.kind='resolution' AND (a.decision_en<>'' OR a.decision_ml<>'') ORDER BY m.scheduled_at", (like,))
    r["actions"] = {"done": _n("SELECT COUNT(*) n FROM actions WHERE status='done' AND done_at>=? AND done_at<?", (start, end)), "open": _n("SELECT COUNT(*) n FROM actions WHERE status IN ('open','in_progress')")}
    r["library"] = {"books": _n("SELECT COUNT(*) n FROM copies WHERE status<>'withdrawn'"), "added": _n("SELECT COUNT(*) n FROM copies WHERE added>=? AND added<?", (start, end)),
                    "issues": _n("SELECT COUNT(*) n FROM issues WHERE issued_on LIKE ?", (like,)), "readers": _n("SELECT COUNT(DISTINCT member_id) n FROM issues WHERE issued_on LIKE ?", (like,)),
                    "reading_room": _n("SELECT COUNT(*) n FROM reading_room WHERE visited_on LIKE ?", (like,)), "fines": db.one("SELECT COALESCE(SUM(amount),0) n FROM transactions WHERE void=0 AND head='library_fine' AND tx_date LIKE ?", (like,))["n"],
                    "popular": db.q("SELECT b.title_en, b.title_ml, COUNT(i.id) n FROM issues i JOIN books b ON b.id=i.book_id WHERE i.issued_on LIKE ? GROUP BY b.id ORDER BY n DESC LIMIT 5", (like,))}
    heads = db.q("SELECT kind, head, SUM(amount) total FROM transactions WHERE void=0 AND tx_date LIKE ? GROUP BY kind, head ORDER BY kind, total DESC", (like,))
    r["accounts"] = {"receipts": sum(h["total"] for h in heads if h["kind"] == "receipt"), "payments": sum(h["total"] for h in heads if h["kind"] == "payment"), "by_head": heads,
                     "dues": db.one("SELECT COALESCE(SUM(s.amount-s.paid),0) n FROM subscriptions s JOIN members m ON m.id=s.member_id WHERE s.status='due' AND m.status='active'")["n"]}
    r["bookings"] = _n("SELECT COUNT(*) n FROM bookings WHERE status IN ('confirmed','done') AND starts_at LIKE ?", (like,))
    r["assets"] = _n("SELECT COUNT(*) n FROM assets WHERE active=1")
    r["office_bearers"] = db.q("SELECT cm.designation_en, cm.designation_ml, m.name_en, m.name_ml FROM committee_members cm JOIN members m ON m.id=cm.member_id JOIN committees c ON c.id=cm.committee_id "
                               "WHERE cm.active=1 AND c.kind='executive' ORDER BY cm.sort, cm.id")
    r["years"] = sorted({x["y"] for x in db.q("SELECT DISTINCT substr(tx_date,1,4) y FROM transactions") } | {x["y"] for x in db.q("SELECT DISTINCT substr(starts_at,1,4) y FROM posts WHERE starts_at<>''")} | {str(dt.date.today().year)}, reverse=True)
    return r


@router.get("/annual")
def annual_report(year: int = 0, user=Depends(require("reports.view"))):
    return annual(year or dt.date.today().year)


@router.get("/annual/print")
def annual_print(year: int = 0, lang: str = "ml", user=Depends(require("reports.view"))):
    import html
    from fastapi.responses import HTMLResponse
    from . import i18n
    lang = lang if lang in ("en", "ml") else "en"
    r = annual(year or dt.date.today().year)
    s = db.settings_all(); e = html.escape
    L = {"en": ("Annual Report", "Office bearers", "Membership", "Active members", "Joined this year", "Family members", "Events and programmes", "Participants", "Meetings", "Average present",
                "Resolutions", "Library", "Books", "Added", "Issues", "Readers", "Reading room visits", "Most read", "Accounts", "Receipts", "Payments", "Surplus / deficit", "Subscription dues outstanding",
                "Hall bookings", "Assets", "Action items completed", "News items published", "Prepared by the Secretary"),
         "ml": ("വാർഷിക റിപ്പോർട്ട്", "ഭാരവാഹികൾ", "അംഗത്വം", "സജീവ അംഗങ്ങൾ", "ഈ വർഷം ചേർന്നവർ", "കുടുംബാംഗങ്ങൾ", "പരിപാടികൾ", "പങ്കാളികൾ", "യോഗങ്ങൾ", "ശരാശരി ഹാജർ",
                "പ്രമേയങ്ങൾ", "ലൈബ്രറി", "പുസ്തകങ്ങൾ", "ചേർത്തവ", "നൽകിയവ", "വായനക്കാർ", "വായനശാല സന്ദർശനങ്ങൾ", "ഏറ്റവും വായിച്ചവ", "കണക്കുകൾ", "വരവ്", "ചെലവ്", "മിച്ചം / കമ്മി", "വരിസംഖ്യ കുടിശ്ശിക",
                "ഹാൾ ബുക്കിംഗുകൾ", "ആസ്തികൾ", "പൂർത്തിയാക്കിയ ചുമതലകൾ", "പ്രസിദ്ധീകരിച്ച വാർത്തകൾ", "സെക്രട്ടറി തയ്യാറാക്കിയത്")}[lang]
    types = {t["key"]: t for t in __import__("json").loads(s["membership_types"])}
    money = lambda n: f"₹{n:,.0f}"
    ev = "".join(f"<tr><td>{e(i18n.pick(x, 'title', lang))}</td><td>{e(i18n.label(i18n.KIND_LABELS, x['kind'], lang))}</td><td>{e(x['starts_at'][:10])}</td><td class=n>{x['participants']}</td></tr>" for x in r["events"])
    mt = "".join(f"<tr><td>{e(i18n.pick(x, 'name', lang))}</td><td class=n>{x['meetings']}</td><td class=n>{x['avg_present']:.1f}</td></tr>" for x in r["meetings"])
    res = "".join(f"<li><b>{e(x['resolution_no'])}</b> {e(i18n.pick(x, 'title', lang))} <span class=m>({e(i18n.pick(x, 'committee', lang))}, {e(x['scheduled_at'][:10])})</span><br>{e(i18n.pick(x, 'decision', lang))}</li>" for x in r["resolutions"])
    heads = "".join(f"<tr><td>{'▲' if h['kind']=='receipt' else '▼'} {e(i18n.label(i18n.HEAD_LABELS, h['head'], lang))}</td><td class=n>{money(h['total'])}</td></tr>" for h in r["accounts"]["by_head"])
    ob = "".join(f"<tr><td>{e(i18n.pick(x, 'designation', lang))}</td><td>{e(i18n.pick(x, 'name', lang))}</td></tr>" for x in r["office_bearers"])
    bt = "".join(f"<tr><td>{e((types.get(x['k']) or {}).get(lang) or x['k'])}</td><td class=n>{x['n']}</td></tr>" for x in r["members"]["by_type"])
    pop = "".join(f"<li>{e(i18n.pick(x, 'title', lang))} ({x['n']})</li>" for x in r["library"]["popular"])
    a = r["accounts"]
    c = brand.colors(s)
    return HTMLResponse(f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{L[0]} {r['year']}</title>{brand.html_head(s)}
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;max-width:820px;margin:0 auto;padding:24px;color:#1d2a28;line-height:1.5}}h1{{margin:0;color:{c['primary']}}}h2{{border-bottom:2px solid {c['primary']};padding-bottom:4px;margin-top:22px;font-size:1.1rem}}
table{{width:100%;border-collapse:collapse;font-size:.92rem;margin:6px 0}}td,th{{border:1px solid #ccc;padding:5px 8px;text-align:left}}td.n{{text-align:right;font-family:Inter}}.m{{color:#777;font-size:.85rem}}
.kv{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin:8px 0}}.kv div{{border:1px solid #ddd;border-radius:8px;padding:8px}}.kv b{{display:block;font-size:1.3rem;font-family:Inter}}
.sign{{margin-top:50px;display:flex;justify-content:space-between}}@media print{{body{{padding:0}}}}</style></head><body>
{brand.logo_img(s, height=56)}<div class=m>{e(s['club_name_ml' if lang == 'ml' else 'club_name_en'])}{(' · ' + e(s['club_reg_no'])) if s['club_reg_no'] else ''}</div><h1>{L[0]} {r['year']}</h1>
{('<h2>' + L[1] + '</h2><table>' + ob + '</table>') if ob else ''}
<h2>{L[2]}</h2><div class=kv><div>{L[3]}<b>{r['members']['active']}</b></div><div>{L[4]}<b>{r['members']['joined']}</b></div><div>{L[5]}<b>{r['members']['family']}</b></div></div><table>{bt}</table>
<h2>{L[6]}</h2>{('<table><tr><th></th><th></th><th></th><th>' + L[7] + '</th></tr>' + ev + '</table>') if ev else '<p class=m>-</p>'}<p class=m>{L[26]}: {r["news_count"]}</p>
<h2>{L[8]}</h2>{('<table><tr><th></th><th>' + L[8] + '</th><th>' + L[9] + '</th></tr>' + mt + '</table>') if mt else '<p class=m>-</p>'}<p class=m>{L[25]}: {r["actions"]["done"]}</p>
{('<h2>' + L[10] + '</h2><ol>' + res + '</ol>') if res else ''}
<h2>{L[11]}</h2><div class=kv><div>{L[12]}<b>{r['library']['books']}</b></div><div>{L[13]}<b>{r['library']['added']}</b></div><div>{L[14]}<b>{r['library']['issues']}</b></div><div>{L[15]}<b>{r['library']['readers']}</b></div><div>{L[16]}<b>{r['library']['reading_room']}</b></div></div>
{('<p><b>' + L[17] + ':</b></p><ol>' + pop + '</ol>') if pop else ''}
<h2>{L[18]}</h2><div class=kv><div>{L[19]}<b>{money(a['receipts'])}</b></div><div>{L[20]}<b>{money(a['payments'])}</b></div><div>{L[21]}<b>{money(a['receipts'] - a['payments'])}</b></div><div>{L[22]}<b>{money(a['dues'])}</b></div></div><table>{heads}</table>
<p class=m>{L[23]}: {r['bookings']} · {L[24]}: {r['assets']}</p>
<div class=sign><div>{L[27]}<br><br>______________</div><div>President<br><br>______________</div></div>
<script>setTimeout(()=>window.print(),500)</script></body></html>""")
