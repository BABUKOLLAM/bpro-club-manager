"""Library Council pack: what a library affiliated to the Kerala State Library Council files every year, read straight
from the registers the librarian already keeps. The grade estimate (A/B/C/D) scores the library against thresholds
the club keeps in Settings (the Council's current circular governs; the defaults are planning targets), with the
shortfall to the next grade per criterion. The annual statement prints bilingual. Grants have a register and a
utilisation certificate that lists the vouchers charged to each grant."""
import datetime as dt
import html
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import brand, db, i18n, ledger
from .auth import can, current_user, require

router = APIRouter(prefix="/api/council")
GRADES = ["A", "B", "C", "D"]
DEFAULT_CRITERIA = {"books": [5000, 3000, 1500, 500], "members": [300, 200, 100, 50], "issues": [3000, 2000, 1000, 300], "periodicals": [10, 6, 4, 2],
                    "reading_room": [3000, 1500, 600, 100], "programmes": [12, 8, 4, 1], "added": [300, 150, 60, 10]}
CRITERIA_LABELS = {"books": {"en": "Books in stock", "ml": "സ്റ്റോക്കിലുള്ള പുസ്തകങ്ങൾ"}, "members": {"en": "Active members", "ml": "സജീവ അംഗങ്ങൾ"},
                   "issues": {"en": "Books issued in the year", "ml": "വർഷത്തിൽ നൽകിയ പുസ്തകങ്ങൾ"}, "periodicals": {"en": "Newspapers & periodicals subscribed", "ml": "വരിക്കാരായ പത്രങ്ങളും ആനുകാലികങ്ങളും"},
                   "reading_room": {"en": "Reading room visits in the year", "ml": "വർഷത്തിലെ വായനശാല സന്ദർശനങ്ങൾ"}, "programmes": {"en": "Programmes held in the year", "ml": "വർഷത്തിൽ നടത്തിയ പരിപാടികൾ"},
                   "added": {"en": "Books added in the year", "ml": "വർഷത്തിൽ ചേർത്ത പുസ്തകങ്ങൾ"}}
GRADE_CUTS = [("A", .85), ("B", .65), ("C", .45), ("D", .25)]


def _n(sql, args=()):
    return db.one(sql, args)["n"]


def criteria():
    c = dict(DEFAULT_CRITERIA)
    for k, v in db.setting_json("council_criteria", {}).items():
        if k in c and isinstance(v, list) and len(v) == 4:
            try:
                c[k] = [float(x) for x in v]
            except (TypeError, ValueError):
                pass
    return c


def metrics(fy):
    start, end = ledger.fy_bounds(fy)
    ts0 = dt.datetime.fromisoformat(start).timestamp(); ts1 = (dt.datetime.fromisoformat(end) + dt.timedelta(days=1)).timestamp()
    stock = _n("SELECT COUNT(*) n FROM copies c JOIN books b ON b.id=c.book_id WHERE b.deleted=0 AND c.status<>'withdrawn'")
    added = db.q("SELECT CASE WHEN b.donated_by<>'' THEN 'donation' ELSE 'purchase' END k, COUNT(*) n FROM copies c JOIN books b ON b.id=c.book_id WHERE b.deleted=0 AND c.added>=? AND c.added<? GROUP BY k", (ts0, ts1))
    added_n = sum(r["n"] for r in added)
    m = {"fy": fy, "start_on": start, "end_on": end,
         "books": stock, "books_opening": stock - added_n, "added": added_n, "added_by": {r["k"]: r["n"] for r in added},
         "lost_damaged": _n("SELECT COUNT(*) n FROM copies WHERE status IN ('lost','damaged','withdrawn')"),
         "titles": _n("SELECT COUNT(*) n FROM books WHERE deleted=0"),
         "by_language": db.q("SELECT b.language k, COUNT(c.id) n FROM copies c JOIN books b ON b.id=c.book_id WHERE b.deleted=0 AND c.status<>'withdrawn' GROUP BY b.language ORDER BY n DESC"),
         "by_category": db.q("SELECT b.category k, COUNT(c.id) n FROM copies c JOIN books b ON b.id=c.book_id WHERE b.deleted=0 AND c.status<>'withdrawn' GROUP BY b.category ORDER BY n DESC"),
         "members": _n("SELECT COUNT(*) n FROM members WHERE status='active'"),
         "members_by_type": db.q("SELECT membership_type k, COUNT(*) n FROM members WHERE status='active' GROUP BY k ORDER BY n DESC"),
         "members_joined": _n("SELECT COUNT(*) n FROM members WHERE status='active' AND joined_on>=? AND joined_on<=?", (start, end)),
         "issues": _n("SELECT COUNT(*) n FROM issues WHERE issued_on>=? AND issued_on<=?", (start, end)),
         "readers": _n("SELECT COUNT(DISTINCT member_id) n FROM issues WHERE issued_on>=? AND issued_on<=?", (start, end)),
         "issues_by_month": db.q("SELECT substr(issued_on,1,7) k, COUNT(*) n FROM issues WHERE issued_on>=? AND issued_on<=? GROUP BY k ORDER BY k", (start, end)),
         "reading_room": _n("SELECT COUNT(*) n FROM reading_room WHERE visited_on>=? AND visited_on<=?", (start, end)),
         "reading_room_by_month": db.q("SELECT substr(visited_on,1,7) k, COUNT(*) n FROM reading_room WHERE visited_on>=? AND visited_on<=? GROUP BY k ORDER BY k", (start, end)),
         "periodicals_list": db.q("SELECT title_en, title_ml, kind, language, agent, cost FROM periodicals WHERE active=1 ORDER BY kind, title_en"),
         "programmes_list": db.q("SELECT id, kind, title_en, title_ml, starts_at, level, venue_en, venue_ml FROM posts WHERE deleted=0 AND status='published' AND kind IN ('event','camp','competition','activity') AND substr(starts_at,1,10)>=? AND substr(starts_at,1,10)<=? ORDER BY starts_at", (start, end)),
         "office_bearers": db.q("SELECT cm.designation_en, cm.designation_ml, m.name_en, m.name_ml, m.phone FROM committee_members cm JOIN members m ON m.id=cm.member_id JOIN committees c ON c.id=cm.committee_id WHERE cm.active=1 AND c.kind='executive' ORDER BY cm.sort, cm.id"),
         "librarians": db.q("SELECT name FROM users WHERE role='librarian' AND active=1 ORDER BY name"),
         "accounts": db.q("SELECT kind, head, SUM(amount) total FROM transactions WHERE void=0 AND tx_date>=? AND tx_date<=? AND head IN ('books','newspapers','library_fine','library_deposit','deposit_refund','grant','salary') GROUP BY kind, head ORDER BY kind, total DESC", (start, end)),
         "grants": db.q("SELECT g.*, (SELECT COALESCE(SUM(t.amount),0) FROM transactions t WHERE t.grant_id=g.id AND t.void=0 AND t.kind='payment') utilised FROM grants g WHERE g.fy=? OR (g.received_on>=? AND g.received_on<=?) ORDER BY g.received_on, g.id", (fy, start, end))}
    m["periodicals"] = len(m["periodicals_list"])
    m["programmes"] = len(m["programmes_list"])
    for g in m["grants"]:
        g["balance"] = g["amount"] - g["utilised"]
    return m


def grade_of(value, cuts):
    for g, cut in zip(GRADES, cuts):
        if value >= cut:
            return g
    return ""


def assessment(m):
    crit = criteria()
    rows, points = [], 0
    for key, cuts in crit.items():
        v = m.get(key, 0)
        g = grade_of(v, cuts)
        pts = (4 - GRADES.index(g)) if g else 0
        points += pts
        nxt = None
        if g != "A":
            target_grade = GRADES[GRADES.index(g) - 1] if g else "D"
            target = cuts[GRADES.index(target_grade)]
            nxt = {"grade": target_grade, "target": target, "shortfall": max(0, target - v)}
        rows.append({"key": key, **CRITERIA_LABELS[key], "value": v, "grade": g, "points": pts, "cuts": cuts, "next": nxt})
    score = points / (4 * len(crit)) if crit else 0
    overall = next((g for g, cut in GRADE_CUTS if score >= cut), "")
    return {"rows": rows, "points": points, "max_points": 4 * len(crit), "score": round(score, 3), "grade": overall, "declared": db.setting("council_grade")}


@router.get("/status")
def status(fy: str = "", user=Depends(current_user)):
    if not (can(user, "library.manage") or can(user, "reports.view")):
        raise HTTPException(403)
    fy = fy or ledger.current_fy()
    m = metrics(fy)
    return {"metrics": m, "assessment": assessment(m), "years": ledger.fy_list(), "council": {k: db.setting(k) for k in ("council_reg_no", "council_grade", "council_district", "council_taluk", "library_hours", "librarian_name")}}


# ---------- grants ----------
@router.get("/grants")
def grants(user=Depends(current_user)):
    if not (can(user, "finance.view") or can(user, "library.manage")):
        raise HTTPException(403)
    rows = db.q("SELECT g.*, (SELECT COALESCE(SUM(t.amount),0) FROM transactions t WHERE t.grant_id=g.id AND t.void=0 AND t.kind='payment') utilised, r.no AS receipt_no FROM grants g LEFT JOIN transactions r ON r.id=g.receipt_id ORDER BY g.received_on DESC, g.id DESC")
    for g in rows:
        g["balance"] = g["amount"] - g["utilised"]
    return rows


@router.post("/grants")
async def save_grant(request: Request, user=Depends(require("finance.manage"))):
    b = await request.json()
    amount = float(b.get("amount") or 0)
    if amount <= 0 or not (b.get("source") or "").strip():
        raise HTTPException(400, "source and amount")
    received_on = b.get("received_on") or dt.date.today().isoformat()
    row = {"source": b["source"].strip(), "purpose_en": (b.get("purpose_en") or "").strip(), "purpose_ml": (b.get("purpose_ml") or "").strip(), "sanction_no": (b.get("sanction_no") or "").strip(),
           "sanction_on": b.get("sanction_on") or "", "amount": amount, "received_on": received_on, "fy": ledger.fy_of(received_on), "status": b.get("status") if b.get("status") in ("open", "utilised", "closed") else "open",
           "note": (b.get("note") or "")[:500]}
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "grants", b["id"], row); gid = b["id"]
        else:
            row.update({"created": time.time(), "created_by": user["id"]}); gid = db.insert(c, "grants", row)
            if b.get("record_receipt", True):
                from . import finance
                r = finance.record(c, user["id"], {"kind": "receipt", "head": "grant", "party": row["source"], "amount": amount, "mode": b.get("mode") or "bank", "ref": row["sanction_no"],
                                                   "tx_date": received_on, "note": row["purpose_en"]}, notify=False)
                db.update(c, "grants", gid, {"receipt_id": r["id"]})
        db.audit(c, user["id"], "grant.save", "grant", gid, f"{row['source']} {amount}")
    return {"ok": True, "id": gid}


@router.get("/grants/{gid}")
def grant(gid: int, user=Depends(current_user)):
    if not (can(user, "finance.view") or can(user, "library.manage")):
        raise HTTPException(403)
    g = db.one("SELECT * FROM grants WHERE id=?", (gid,))
    if not g:
        raise HTTPException(404)
    lab = ledger.labels()
    g["vouchers"] = db.q("SELECT id, no, tx_date, head, party, amount, mode, ref, note FROM transactions WHERE grant_id=? AND void=0 AND kind='payment' ORDER BY tx_date, id", (gid,))
    for v in g["vouchers"]:
        v.update(lab.get(v["head"], {"en": v["head"], "ml": v["head"]}))
    g["utilised"] = sum(v["amount"] for v in g["vouchers"])
    g["balance"] = g["amount"] - g["utilised"]
    since = ledger.fy_bounds(g["fy"])[0] if g["fy"] else "0000"
    g["candidates"] = db.q("SELECT id, no, tx_date, head, party, amount FROM transactions WHERE kind='payment' AND void=0 AND grant_id IS NULL AND tx_date>=? ORDER BY tx_date DESC, id DESC LIMIT 200", (since,))
    for v in g["candidates"]:
        v.update(lab.get(v["head"], {"en": v["head"], "ml": v["head"]}))
    return g


@router.post("/grants/{gid}/link")
async def link_vouchers(gid: int, request: Request, user=Depends(require("finance.manage"))):
    """Charge payment vouchers to a grant (or release them): that is what the utilisation certificate lists."""
    b = await request.json()
    if not db.one("SELECT 1 FROM grants WHERE id=?", (gid,)):
        raise HTTPException(404)
    add = [int(x) for x in b.get("add") or []]
    remove = [int(x) for x in b.get("remove") or []]
    with db.tx() as c:
        for tid in add:
            c.execute("UPDATE transactions SET grant_id=? WHERE id=? AND kind='payment' AND void=0 AND grant_id IS NULL", (gid, tid))
        for tid in remove:
            c.execute("UPDATE transactions SET grant_id=NULL WHERE id=? AND grant_id=?", (tid, gid))
        db.audit(c, user["id"], "grant.link", "grant", gid, f"+{len(add)} -{len(remove)}")
    return {"ok": True}


# ---------- printable: annual statement and utilisation certificate ----------
T = {"en": {"stmt": "Annual Statement for Library Council Affiliation", "year": "Year", "reg": "Society reg. no.", "council": "Council affiliation no.", "district": "District", "taluk": "Taluk", "hours": "Working hours",
            "librarian": "Librarian", "stock": "Book stock", "opening": "Opening stock", "added": "Added during the year", "purchase": "by purchase", "donation": "by donation", "lost": "Lost / damaged / withdrawn (total)", "closing": "Closing stock",
            "titles": "Titles", "by_language": "By language", "by_category": "By category", "members": "Members", "active": "Active members", "joined": "Joined during the year", "circulation": "Circulation", "issues": "Books issued",
            "readers": "Readers", "per_month": "Per month", "reading_room": "Reading room", "visits": "Visits during the year", "periodicals": "Newspapers and periodicals", "programmes": "Programmes held", "accounts": "Library accounts",
            "grants": "Grants", "utilised": "Utilised", "balance": "Balance", "office": "Office bearers", "grade": "Grade estimate", "declared": "Grade as per Council", "criterion": "Criterion", "value": "This year", "attained": "Attained", "next": "For the next grade",
            "note": "Grade thresholds are the club's planning targets kept in Settings; the Council's current circular governs the actual grade.", "secretary": "Secretary", "president": "President", "treasurer": "Treasurer",
            "uc": "Grant Utilisation Certificate", "source": "Sanctioning authority", "purpose": "Purpose", "sanction": "Sanction no. / date", "received": "Amount received", "received_on": "Received on", "vouchers": "Vouchers charged to the grant",
            "unutilised": "Unutilised balance", "cert": "Certified that the grant stated above was received and that the amount shown as utilised was spent on the purpose for which it was sanctioned, as evidenced by the vouchers listed, which are available for audit.",
            "date": "Date", "no": "No.", "head": "Head", "party": "Paid to", "amount": "Amount"},
     "ml": {"stmt": "ലൈബ്രറി കൗൺസിൽ അഫിലിയേഷനുള്ള വാർഷിക സ്റ്റേറ്റ്മെന്റ്", "year": "വർഷം", "reg": "സൊസൈറ്റി രജി. നം.", "council": "കൗൺസിൽ അഫിലിയേഷൻ നം.", "district": "ജില്ല", "taluk": "താലൂക്ക്", "hours": "പ്രവർത്തന സമയം",
            "librarian": "ലൈബ്രേറിയൻ", "stock": "പുസ്തക സ്റ്റോക്ക്", "opening": "ആരംഭ സ്റ്റോക്ക്", "added": "വർഷത്തിൽ ചേർത്തത്", "purchase": "വാങ്ങിയത്", "donation": "സംഭാവന", "lost": "നഷ്ടപ്പെട്ടത് / കേടായത് / നീക്കിയത് (ആകെ)", "closing": "അവസാന സ്റ്റോക്ക്",
            "titles": "ശീർഷകങ്ങൾ", "by_language": "ഭാഷ തിരിച്ച്", "by_category": "വിഭാഗം തിരിച്ച്", "members": "അംഗങ്ങൾ", "active": "സജീവ അംഗങ്ങൾ", "joined": "വർഷത്തിൽ ചേർന്നവർ", "circulation": "വിതരണം", "issues": "നൽകിയ പുസ്തകങ്ങൾ",
            "readers": "വായനക്കാർ", "per_month": "മാസം തിരിച്ച്", "reading_room": "വായനശാല", "visits": "വർഷത്തിലെ സന്ദർശനങ്ങൾ", "periodicals": "പത്രങ്ങളും ആനുകാലികങ്ങളും", "programmes": "നടത്തിയ പരിപാടികൾ", "accounts": "ലൈബ്രറി കണക്കുകൾ",
            "grants": "ഗ്രാന്റുകൾ", "utilised": "വിനിയോഗിച്ചത്", "balance": "ബാക്കി", "office": "ഭാരവാഹികൾ", "grade": "ഗ്രേഡ് കണക്കാക്കൽ", "declared": "കൗൺസിൽ നൽകിയ ഗ്രേഡ്", "criterion": "മാനദണ്ഡം", "value": "ഈ വർഷം", "attained": "നേടിയത്", "next": "അടുത്ത ഗ്രേഡിന്",
            "note": "ഗ്രേഡ് പരിധികൾ ക്രമീകരണങ്ങളിൽ ക്ലബ്ബ് സൂക്ഷിക്കുന്ന ആസൂത്രണ ലക്ഷ്യങ്ങളാണ്; യഥാർത്ഥ ഗ്രേഡ് കൗൺസിലിന്റെ നിലവിലെ സർക്കുലർ പ്രകാരമാണ്.", "secretary": "സെക്രട്ടറി", "president": "പ്രസിഡന്റ്", "treasurer": "ട്രഷറർ",
            "uc": "ഗ്രാന്റ് വിനിയോഗ സാക്ഷ്യപത്രം", "source": "അനുവദിച്ച അധികാരി", "purpose": "ഉദ്ദേശ്യം", "sanction": "അനുമതി നം. / തീയതി", "received": "ലഭിച്ച തുക", "received_on": "ലഭിച്ച തീയതി", "vouchers": "ഗ്രാന്റിൽ ചേർത്ത വൗച്ചറുകൾ",
            "unutilised": "വിനിയോഗിക്കാത്ത ബാക്കി", "cert": "മുകളിൽ പറഞ്ഞ ഗ്രാന്റ് ലഭിച്ചുവെന്നും, വിനിയോഗിച്ചതായി കാണിച്ച തുക അനുവദിച്ച ഉദ്ദേശ്യത്തിനായി ചെലവഴിച്ചുവെന്നും, അതിനു തെളിവായ വൗച്ചറുകൾ ഓഡിറ്റിന് ലഭ്യമാണെന്നും ഇതിനാൽ സാക്ഷ്യപ്പെടുത്തുന്നു.",
            "date": "തീയതി", "no": "നം.", "head": "ഇനം", "party": "നൽകിയത്", "amount": "തുക"}}


def _fmt(d):
    return f"{d[8:10]}-{d[5:7]}-{d[:4]}" if d and len(d) >= 10 else (d or "")


@router.get("/statement/print")
def statement_print(fy: str = "", lang: str = "ml", user=Depends(current_user)):
    if not (can(user, "library.manage") or can(user, "reports.view")):
        raise HTTPException(403)
    lang = lang if lang in ("en", "ml") else "en"
    L = T[lang]; e = html.escape
    fy = fy or ledger.current_fy()
    m = metrics(fy); a = assessment(m); s = db.settings_all()
    types = {t["key"]: t for t in json.loads(s["membership_types"])}
    kv = lambda pairs: "<div class=kv>" + "".join(f"<div>{k}<b>{v}</b></div>" for k, v in pairs) + "</div>"  # noqa: E731
    lang_names = {"ml": "മലയാളം", "en": "English", "hi": "हिन्दी", "ta": "தமிழ்"}
    byl = "".join(f"<tr><td>{e(lang_names.get(r['k'], r['k']))}</td><td class=n>{r['n']}</td></tr>" for r in m["by_language"])
    byc = "".join(f"<tr><td>{e(r['k'])}</td><td class=n>{r['n']}</td></tr>" for r in m["by_category"])
    bt = "".join(f"<tr><td>{e((types.get(r['k']) or {}).get(lang) or r['k'])}</td><td class=n>{r['n']}</td></tr>" for r in m["members_by_type"])
    months = {r["k"]: r["n"] for r in m["issues_by_month"]}; rr = {r["k"]: r["n"] for r in m["reading_room_by_month"]}
    keys = sorted(set(months) | set(rr))
    pm = "".join(f"<tr><td>{e(k)}</td><td class=n>{months.get(k, 0)}</td><td class=n>{rr.get(k, 0)}</td></tr>" for k in keys)
    per = "".join(f"<tr><td>{e(i18n.pick(p, 'title', lang))}</td><td>{e(p['kind'])}</td><td>{e(lang_names.get(p['language'], p['language']))}</td><td>{e(p['agent'])}</td></tr>" for p in m["periodicals_list"])
    prog = "".join(f"<tr><td>{_fmt(p['starts_at'])}</td><td>{e(i18n.pick(p, 'title', lang))}</td><td>{e(i18n.label(i18n.KIND_LABELS, p['kind'], lang))}</td><td>{e(i18n.pick(p, 'venue', lang))}</td></tr>" for p in m["programmes_list"])
    lab = ledger.labels()
    acc = "".join(f"<tr><td>{'▲' if r['kind'] == 'receipt' else '▼'} {e((lab.get(r['head']) or {}).get(lang) or r['head'])}</td><td class=n>{r['total']:,.2f}</td></tr>" for r in m["accounts"])
    gr = "".join(f"<tr><td>{e(g['source'])}<div class=m>{e(i18n.pick(g, 'purpose', lang))} {e(g['sanction_no'])}</div></td><td>{_fmt(g['received_on'])}</td><td class=n>{g['amount']:,.2f}</td><td class=n>{g['utilised']:,.2f}</td><td class=n>{g['balance']:,.2f}</td></tr>" for g in m["grants"])
    ob = "".join(f"<tr><td>{e(i18n.pick(x, 'designation', lang))}</td><td>{e(i18n.pick(x, 'name', lang))}</td><td class=n>{e(x['phone'])}</td></tr>" for x in m["office_bearers"])
    def nxt(r):
        n = r["next"]
        return f"{e(n['grade'])}: {n['target']:g} (+{n['shortfall']:g})" if n else "✓"
    gt = "".join(f"<tr><td>{e(r[lang])}</td><td class=n>{r['value']:g}</td><td class=n>{e(r['grade'] or '–')}</td><td>{nxt(r)}</td></tr>" for r in a["rows"])
    c = brand.colors(s)
    body = f"""<h1>{L['stmt']}</h1><div class=m>{L['year']} {e(fy)} · {_fmt(m['start_on'])} – {_fmt(m['end_on'])}</div>
<table><tr><td>{L['reg']}</td><td>{e(s['club_reg_no'] or '-')}</td><td>{L['council']}</td><td>{e(s['council_reg_no'] or '-')}</td></tr>
<tr><td>{L['district']}</td><td>{e(s['council_district'] or '-')}</td><td>{L['taluk']}</td><td>{e(s['council_taluk'] or '-')}</td></tr>
<tr><td>{L['hours']}</td><td>{e(s['library_hours'] or '-')}</td><td>{L['librarian']}</td><td>{e(s['librarian_name'] or ', '.join(x['name'] for x in m['librarians']) or '-')}</td></tr>
<tr><td>{L['declared']}</td><td>{e(s['council_grade'] or '-')}</td><td>{L['grade']}</td><td><b>{e(a['grade'] or '–')}</b> ({a['points']}/{a['max_points']})</td></tr></table>
<h2>{L['stock']}</h2>{kv([(L['opening'], m['books_opening']), (L['added'], m['added']), (L['purchase'], m['added_by'].get('purchase', 0)), (L['donation'], m['added_by'].get('donation', 0)), (L['closing'], m['books']), (L['titles'], m['titles']), (L['lost'], m['lost_damaged'])])}
<div class=two><table><tr><th>{L['by_language']}</th><th class=n></th></tr>{byl}</table><table><tr><th>{L['by_category']}</th><th class=n></th></tr>{byc}</table></div>
<h2>{L['members']}</h2>{kv([(L['active'], m['members']), (L['joined'], m['members_joined'])])}<table>{bt}</table>
<h2>{L['circulation']} · {L['reading_room']}</h2>{kv([(L['issues'], m['issues']), (L['readers'], m['readers']), (L['visits'], m['reading_room'])])}
<table><tr><th>{L['per_month']}</th><th class=n>{L['issues']}</th><th class=n>{L['visits']}</th></tr>{pm}</table>
<h2>{L['periodicals']} ({m['periodicals']})</h2><table>{per or '<tr><td>-</td></tr>'}</table>
<h2>{L['programmes']} ({m['programmes']})</h2><table>{prog or '<tr><td>-</td></tr>'}</table>
<h2>{L['accounts']}</h2><table>{acc or '<tr><td>-</td></tr>'}</table>
<h2>{L['grants']}</h2><table><tr><th>{L['source']}</th><th>{L['received_on']}</th><th class=n>{L['received']}</th><th class=n>{L['utilised']}</th><th class=n>{L['balance']}</th></tr>{gr or '<tr><td colspan=5>-</td></tr>'}</table>
<h2>{L['grade']}</h2><table><tr><th>{L['criterion']}</th><th class=n>{L['value']}</th><th class=n>{L['attained']}</th><th>{L['next']}</th></tr>{gt}</table><p class=m>{L['note']}</p>
<h2>{L['office']}</h2><table>{ob or '<tr><td>-</td></tr>'}</table>
<div class=sign><div>{L['librarian']}</div><div>{L['secretary']}</div><div>{L['president']}</div></div>"""
    return _html(lang, f"{L['stmt']} {fy}", body, s, c)


def _html(lang, title, body, s, c):
    e = html.escape
    return HTMLResponse(f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(title)}</title>{brand.html_head(s)}
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;max-width:860px;margin:0 auto;padding:24px;color:#1d2a28;line-height:1.45;font-size:.92rem}}h1{{margin:0;color:{c['primary']};font-size:1.4rem}}h2{{border-bottom:2px solid {c['primary']};padding-bottom:4px;margin:22px 0 6px;font-size:1.02rem}}
.m{{color:#666;font-size:.85rem}}table{{width:100%;border-collapse:collapse;margin:6px 0}}td,th{{border:1px solid #bbb;padding:4px 8px;text-align:left;vertical-align:top}}td.n,th.n{{text-align:right;font-family:Inter;white-space:nowrap}}
.kv{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin:8px 0}}.kv div{{border:1px solid #ddd;border-radius:8px;padding:6px 8px;font-size:.85rem}}.kv b{{display:block;font-size:1.2rem;font-family:Inter}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.sign{{margin-top:46px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;text-align:center}}.sign div{{border-top:1px solid #999;padding-top:6px}}.cert{{border:1px solid {c['primary']};border-radius:10px;padding:12px 16px;margin:14px 0;font-size:1rem}}
@media print{{body{{padding:0;font-size:.85rem}}h2{{break-after:avoid}}tr{{break-inside:avoid}}}}</style></head><body>
{brand.logo_img(s, height=50)}<div class=m>{e(s['club_name_ml' if lang == 'ml' else 'club_name_en'])}{(' · ' + e(s['club_reg_no'])) if s['club_reg_no'] else ''}{(' · ' + e(s['club_place_' + lang])) if s.get('club_place_' + lang) else ''}</div>
{body}<script>setTimeout(()=>window.print(),500)</script></body></html>""")


@router.get("/grants/{gid}/uc/print")
def uc_print(gid: int, lang: str = "ml", user=Depends(current_user)):
    if not (can(user, "finance.view") or can(user, "library.manage")):
        raise HTTPException(403)
    lang = lang if lang in ("en", "ml") else "en"
    L = T[lang]; e = html.escape
    g = grant(gid, user); s = db.settings_all(); c = brand.colors(s)
    vs = "".join(f"<tr><td>{_fmt(v['tx_date'])}</td><td>{e(v['no'])}</td><td>{e(v[lang] or v['en'])}</td><td>{e(v['party'])}{(' · ' + e(v['ref'])) if v['ref'] else ''}</td><td class=n>{v['amount']:,.2f}</td></tr>" for v in g["vouchers"])
    body = f"""<h1>{L['uc']}</h1><div class=m>{L['year']} {e(g['fy'])}</div>
<table><tr><td>{L['source']}</td><td>{e(g['source'])}</td></tr><tr><td>{L['purpose']}</td><td>{e(i18n.pick(g, 'purpose', lang) or '-')}</td></tr><tr><td>{L['sanction']}</td><td>{e(g['sanction_no'] or '-')} {_fmt(g['sanction_on'])}</td></tr>
<tr><td>{L['received']}</td><td><b>₹{g['amount']:,.2f}</b> · {L['received_on']} {_fmt(g['received_on'])}</td></tr><tr><td>{L['utilised']}</td><td><b>₹{g['utilised']:,.2f}</b></td></tr><tr><td>{L['unutilised']}</td><td><b>₹{g['balance']:,.2f}</b></td></tr></table>
<h2>{L['vouchers']}</h2><table><tr><th>{L['date']}</th><th>{L['no']}</th><th>{L['head']}</th><th>{L['party']}</th><th class=n>{L['amount']}</th></tr>{vs or '<tr><td colspan=5>-</td></tr>'}<tr><td colspan=4><b>{L['utilised']}</b></td><td class=n><b>{g['utilised']:,.2f}</b></td></tr></table>
<div class=cert>{L['cert']}</div><p class=m>{L['date']}: {_fmt(dt.date.today().isoformat())}</p>
<div class=sign><div>{L['treasurer']}</div><div>{L['secretary']}</div><div>{L['president']}</div></div>"""
    return _html(lang, L["uc"], body, s, c)
