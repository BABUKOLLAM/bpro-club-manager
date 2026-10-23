"""Committees and their members, meetings with notice, agenda, attendance, online minutes (MoM) with sign-off,
action items and plans. Minutes are visible only to the members of that committee (the general body = everyone)."""
import datetime as dt
import html
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, comms, db, i18n
from .auth import can, committee_role, current_user, require

router = APIRouter(prefix="/api")

DEFAULT_COMMITTEES = [
    ("General Body", "പൊതുയോഗം", "general"),
    ("Executive Committee", "എക്സിക്യൂട്ടീവ് കമ്മിറ്റി", "executive"),
    ("Sports Committee", "സ്പോർട്സ് കമ്മിറ്റി", "sub"),
    ("Arts & Cultural Committee", "കലാ സാംസ്കാരിക കമ്മിറ്റി", "sub"),
    ("Library Committee", "ലൈബ്രറി കമ്മിറ്റി", "sub"),
    ("Women's Wing", "വനിതാ വിഭാഗം", "sub"),
    ("Youth Wing", "യുവജന വിഭാഗം", "sub"),
    ("Social Service Committee", "സാമൂഹ്യ സേവന കമ്മിറ്റി", "sub"),
]


def seed_defaults(c):
    if db.one("SELECT 1 FROM committees LIMIT 1"):
        return
    for i, (en, ml, kind) in enumerate(DEFAULT_COMMITTEES):
        db.insert(c, "committees", {"name_en": en, "name_ml": ml, "kind": kind, "created": time.time(), "sort": i})


def _need(user, committee_id, level="member"):
    role = committee_role(user, committee_id)
    if not role or (level == "manage" and role != "manage"):
        raise HTTPException(403, "not for you")
    return role


# ---------- committees ----------
@router.get("/committees")
def list_committees(user=Depends(current_user)):
    rows = db.q("SELECT c.*, (SELECT COUNT(*) FROM committee_members cm WHERE cm.committee_id=c.id AND cm.active=1) AS members, "
                "(SELECT COUNT(*) FROM meetings m WHERE m.committee_id=c.id AND m.deleted=0) AS meetings FROM committees c ORDER BY c.sort, c.id")
    for r in rows:
        r["my_role"] = committee_role(user, r["id"])
    return rows


@router.get("/committees/{cid}")
def get_committee(cid: int, user=Depends(current_user)):
    c = db.one("SELECT * FROM committees WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404)
    c["my_role"] = committee_role(user, cid)
    c["members"] = db.q("SELECT cm.*, m.name_en, m.name_ml, m.phone, m.member_no, m.photo, m.show_phone FROM committee_members cm JOIN members m ON m.id=cm.member_id "
                        "WHERE cm.committee_id=? ORDER BY cm.active DESC, cm.sort, cm.id", (cid,))
    if not c["my_role"] and not can(user, "committees.manage"):
        for m in c["members"]:
            if not m["show_phone"]:
                m["phone"] = ""
    c["meetings"] = db.q("SELECT id, title_en, title_ml, scheduled_at, status, mom_status, venue_en, venue_ml FROM meetings WHERE committee_id=? AND deleted=0 ORDER BY scheduled_at DESC LIMIT 100", (cid,)) if c["my_role"] else []
    c["plans"] = db.q("SELECT p.*, m.name_en AS owner_en, m.name_ml AS owner_ml FROM plans p LEFT JOIN members m ON m.id=p.owner_member_id WHERE p.committee_id=? ORDER BY p.id DESC", (cid,)) if c["my_role"] else []
    return c


@router.post("/committees")
async def save_committee(request: Request, user=Depends(require("committees.manage"))):
    b = await request.json()
    row = {k: (b.get(k) or "") for k in ("name_en", "name_ml", "kind", "description_en", "description_ml", "term_start", "term_end")}
    if row["kind"] not in ("general", "executive", "sub"):
        row["kind"] = "sub"
    row["active"] = 1 if b.get("active", 1) else 0
    row["sort"] = int(b.get("sort") or 0)
    if not (row["name_en"] or row["name_ml"]):
        raise HTTPException(400, "name")
    row["name_en"] = row["name_en"] or row["name_ml"]
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "committees", b["id"], row); cid = b["id"]
        else:
            row["created"] = time.time(); cid = db.insert(c, "committees", row)
        db.audit(c, user["id"], "committee.save", "committee", cid, row["name_en"])
    return {"ok": True, "id": cid}


@router.post("/committees/{cid}/members")
async def save_committee_member(cid: int, request: Request, user=Depends(require("committees.manage"))):
    b = await request.json()
    row = {"designation_en": b.get("designation_en") or "Member", "designation_ml": b.get("designation_ml") or "", "role": b.get("role") or "member",
           "term_start": b.get("term_start") or "", "term_end": b.get("term_end") or "", "active": 1 if b.get("active", 1) else 0, "sort": int(b.get("sort") or 0)}
    if row["role"] not in ("chair", "convener", "secretary", "member"):
        row["role"] = "member"
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "committee_members", b["id"], row); rid = b["id"]
        else:
            if not db.one("SELECT 1 FROM members WHERE id=? AND status='active'", (b.get("member_id"),)):
                raise HTTPException(404, "member")
            ex = db.one("SELECT id FROM committee_members WHERE committee_id=? AND member_id=?", (cid, b["member_id"]))
            if ex:
                db.update(c, "committee_members", ex["id"], row); rid = ex["id"]
            else:
                row.update({"committee_id": cid, "member_id": b["member_id"], "created": time.time()}); rid = db.insert(c, "committee_members", row)
        db.audit(c, user["id"], "committee.member", "committee", cid, str(rid))
    return {"ok": True, "id": rid}


@router.delete("/committees/{cid}/members/{rid}")
def remove_committee_member(cid: int, rid: int, user=Depends(require("committees.manage"))):
    with db.tx() as c:
        c.execute("UPDATE committee_members SET active=0 WHERE id=? AND committee_id=?", (rid, cid))
    return {"ok": True}


# ---------- meetings ----------
MEETING_FIELDS = ["title_en", "title_ml", "scheduled_at", "venue_en", "venue_ml", "mode", "link", "notice_en", "notice_ml", "quorum", "chaired_by", "recorded_by",
                  "started_at", "ended_at", "summary_en", "summary_ml", "next_meeting_at"]


def _meeting(mid):
    m = db.one("SELECT m.*, c.name_en AS committee_en, c.name_ml AS committee_ml, c.kind AS committee_kind FROM meetings m JOIN committees c ON c.id=m.committee_id WHERE m.id=? AND m.deleted=0", (mid,))
    if not m:
        raise HTTPException(404)
    return m


@router.get("/meetings")
def list_meetings(committee_id: int = 0, user=Depends(current_user)):
    rows = db.q("SELECT m.*, c.name_en AS committee_en, c.name_ml AS committee_ml FROM meetings m JOIN committees c ON c.id=m.committee_id WHERE m.deleted=0 "
                + ("AND m.committee_id=? " if committee_id else "") + "ORDER BY m.scheduled_at DESC LIMIT 300", (committee_id,) if committee_id else ())
    out = []
    for r in rows:
        role = committee_role(user, r["committee_id"])
        if role:
            r["my_role"] = role
            out.append(r)
    return out


@router.get("/meetings/{mid}")
def get_meeting(mid: int, user=Depends(current_user)):
    m = _meeting(mid)
    role = _need(user, m["committee_id"])
    m["my_role"] = role
    if role != "manage" and m["mom_status"] == "draft":
        # members see the notice and agenda before the minutes are published, not the draft decisions
        m["agenda"] = db.q("SELECT id, idx, kind, title_en, title_ml, detail_en, detail_ml FROM agenda_items WHERE meeting_id=? ORDER BY idx, id", (mid,))
        m["draft_hidden"] = True
    else:
        m["agenda"] = db.q("SELECT a.*, p.name_en AS proposed_en, p.name_ml AS proposed_ml, s.name_en AS seconded_en, s.name_ml AS seconded_ml FROM agenda_items a "
                           "LEFT JOIN members p ON p.id=a.proposed_by LEFT JOIN members s ON s.id=a.seconded_by WHERE a.meeting_id=? ORDER BY a.idx, a.id", (mid,))
    m["attendance"] = db.q("SELECT a.*, mm.name_en, mm.name_ml, mm.member_no FROM attendance a JOIN members mm ON mm.id=a.member_id WHERE a.meeting_id=? ORDER BY mm.name_en", (mid,))
    m["actions"] = db.q("SELECT a.*, mm.name_en AS owner_en, mm.name_ml AS owner_ml FROM actions a LEFT JOIN members mm ON mm.id=a.owner_member_id WHERE a.meeting_id=? ORDER BY a.id", (mid,))
    m["committee_members"] = db.q("SELECT cm.member_id, cm.designation_en, cm.designation_ml, cm.role, mm.name_en, mm.name_ml, mm.member_no FROM committee_members cm JOIN members mm ON mm.id=cm.member_id "
                                  "WHERE cm.committee_id=? AND cm.active=1 ORDER BY cm.sort, mm.name_en", (m["committee_id"],)) if m["committee_kind"] != "general" else []
    for who in ("chaired_by", "recorded_by", "mom_approved_by"):
        if m.get(who):
            x = db.one("SELECT name_en, name_ml FROM members WHERE id=?", (m[who],)) if who != "mom_approved_by" else db.one("SELECT name AS name_en, name AS name_ml FROM users WHERE id=?", (m[who],))
            m[who + "_name"] = x or {}
    return m


@router.post("/meetings")
async def save_meeting(request: Request, user=Depends(current_user)):
    b = await request.json()
    cid = int(b.get("committee_id") or 0)
    _need(user, cid, "manage")
    row = {k: b.get(k) for k in MEETING_FIELDS if k in b}
    for k in ("chaired_by", "recorded_by", "quorum"):
        if k in row:
            row[k] = int(row[k]) if row[k] not in ("", None) else (0 if k == "quorum" else None)
    for k in list(row):
        if row[k] is None and k not in ("chaired_by", "recorded_by"):
            row[k] = ""
    if "mode" in row and row["mode"] not in ("offline", "online", "hybrid"):
        row["mode"] = "offline"
    now = time.time()
    with db.tx() as c:
        if b.get("id"):
            m = _meeting(b["id"])
            if m["mom_status"] == "approved" and not can(user, "meetings.manage"):
                raise HTTPException(400, "approved minutes are frozen")
            row["updated"] = now
            db.update(c, "meetings", b["id"], row); mid = b["id"]
        else:
            if not row.get("scheduled_at") or not (row.get("title_en") or row.get("title_ml")):
                raise HTTPException(400, "title and date are required")
            row["title_en"] = row.get("title_en") or row.get("title_ml")
            row.update({"committee_id": cid, "created_by": user["id"], "created": now, "updated": now})
            mid = db.insert(c, "meetings", row)
        if "agenda" in b:
            keep = []
            for i, a in enumerate(b["agenda"] or []):
                if not (a.get("title_en") or a.get("title_ml")):
                    continue
                r = {"meeting_id": mid, "idx": i, "kind": a.get("kind") or "discussion", "title_en": a.get("title_en") or a.get("title_ml"), "title_ml": a.get("title_ml") or "",
                     "detail_en": a.get("detail_en") or "", "detail_ml": a.get("detail_ml") or "", "decision_en": a.get("decision_en") or "", "decision_ml": a.get("decision_ml") or "",
                     "resolution_no": a.get("resolution_no") or "", "proposed_by": a.get("proposed_by") or None, "seconded_by": a.get("seconded_by") or None,
                     "votes_for": int(a.get("votes_for") or 0), "votes_against": int(a.get("votes_against") or 0), "outcome": a.get("outcome") or ""}
                if a.get("id"):
                    db.update(c, "agenda_items", a["id"], r); keep.append(a["id"])
                else:
                    keep.append(db.insert(c, "agenda_items", r))
            marks = ",".join("?" for _ in keep) or "0"
            c.execute(f"DELETE FROM agenda_items WHERE meeting_id=? AND id NOT IN ({marks})", [mid] + keep)
        db.audit(c, user["id"], "meeting.save", "meeting", mid)
    return {"ok": True, "id": mid}


def _committee_member_ids(cid, kind):
    if kind == "general":
        return [r["id"] for r in db.q("SELECT id FROM members WHERE status='active'")]
    return [r["member_id"] for r in db.q("SELECT cm.member_id FROM committee_members cm JOIN members m ON m.id=cm.member_id WHERE cm.committee_id=? AND cm.active=1 AND m.status='active'", (cid,))]


def _fmt_when(s):
    try:
        d = dt.datetime.fromisoformat(s)
        return d.strftime("%d-%m-%Y %I:%M %p") if len(s) > 10 else d.strftime("%d-%m-%Y")
    except ValueError:
        return s


@router.post("/meetings/{mid}/notice")
async def send_notice(mid: int, request: Request, user=Depends(current_user)):
    m = _meeting(mid)
    _need(user, m["committee_id"], "manage")
    b = await request.json()
    channels = [ch for ch in (b.get("channels") or ["app", "whatsapp"]) if ch in comms.CHANNELS]
    agenda = db.q("SELECT title_en, title_ml FROM agenda_items WHERE meeting_id=? ORDER BY idx", (mid,))
    convener = db.one("SELECT name FROM users WHERE id=?", (user["id"],))["name"]
    with db.tx() as c:
        n = comms.notify_members(c, _committee_member_ids(m["committee_id"], m["committee_kind"]), "meeting_notice", {"convener": convener}, channels,
                                 ref_kind="meeting", ref_id=mid, batch_id=comms.new_batch(), created_by=user["id"],
                                 per_member=lambda mm: {"title": i18n.pick(m, "title", mm["lang"]), "committee": i18n.pick(m, "committee", mm["lang"]),
                                                        "when": _fmt_when(m["scheduled_at"]), "venue": i18n.pick(m, "venue", mm["lang"]) or m["link"],
                                                        "agenda": "\n".join(f"{i + 1}. {i18n.pick(a, 'title', mm['lang'])}" for i, a in enumerate(agenda))})
        db.update(c, "meetings", mid, {"notice_sent_at": time.time()})
        db.audit(c, user["id"], "meeting.notice", "meeting", mid, f"{n} messages")
    return {"ok": True, "queued": n}


@router.post("/meetings/{mid}/attendance")
async def mark_attendance(mid: int, request: Request, user=Depends(current_user)):
    m = _meeting(mid)
    _need(user, m["committee_id"], "manage")
    rows = (await request.json()).get("attendance") or []
    with db.tx() as c:
        for r in rows:
            st = r.get("status") or "present"
            if st not in ("present", "absent", "apology", "online"):
                st = "present"
            c.execute("INSERT INTO attendance(meeting_id, member_id, status, marked_at, marked_by) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(meeting_id, member_id) DO UPDATE SET status=excluded.status, marked_at=excluded.marked_at, marked_by=excluded.marked_by",
                      (mid, int(r["member_id"]), st, time.time(), user["id"]))
        db.update(c, "meetings", mid, {"updated": time.time()})
    present = db.one("SELECT COUNT(*) n FROM attendance WHERE meeting_id=? AND status IN ('present','online')", (mid,))["n"]
    return {"ok": True, "present": present, "quorum_met": present >= (m["quorum"] or 0)}


@router.post("/meetings/{mid}/status")
async def meeting_status(mid: int, request: Request, user=Depends(current_user)):
    m = _meeting(mid)
    _need(user, m["committee_id"], "manage")
    b = await request.json()
    st = b.get("status")
    if st not in ("scheduled", "held", "cancelled", "postponed"):
        raise HTTPException(400, "status")
    row = {"status": st, "updated": time.time()}
    if st == "postponed" and b.get("scheduled_at"):
        row["scheduled_at"] = b["scheduled_at"]
    with db.tx() as c:
        db.update(c, "meetings", mid, row)
    return {"ok": True}


@router.post("/meetings/{mid}/mom")
async def mom_status(mid: int, request: Request, user=Depends(current_user)):
    """draft -> published (members of the committee can read; they are told) -> approved (frozen, signed off)."""
    m = _meeting(mid)
    _need(user, m["committee_id"], "manage")
    b = await request.json()
    st = b.get("status")
    if st not in ("draft", "published", "approved"):
        raise HTTPException(400, "status")
    now = time.time()
    row = {"mom_status": st, "updated": now}
    n = 0
    with db.tx() as c:
        if st == "published":
            row["mom_published_at"] = m["mom_published_at"] or now
            row["status"] = "held"
            if b.get("notify", True):
                link = f"{comms.club_ctx()['link']}/#/meetings/{mid}"
                n = comms.notify_members(c, _committee_member_ids(m["committee_id"], m["committee_kind"]), "mom_published", {"link": link, "when": _fmt_when(m["scheduled_at"])},
                                         b.get("channels") or ["app", "whatsapp"], ref_kind="meeting", ref_id=mid, batch_id=comms.new_batch(), created_by=user["id"],
                                         per_member=lambda mm: {"title": i18n.pick(m, "title", mm["lang"]), "committee": i18n.pick(m, "committee", mm["lang"])})
        elif st == "approved":
            if not can(user, "meetings.manage"):
                raise HTTPException(403, "only the secretary or president signs off minutes")
            row.update({"mom_approved_by": user["id"], "mom_approved_at": now, "status": "held"})
        else:
            if m["mom_status"] == "approved" and not can(user, "meetings.manage"):
                raise HTTPException(403, "approved minutes are frozen")
            row.update({"mom_approved_by": None, "mom_approved_at": None})
        db.update(c, "meetings", mid, row)
        db.audit(c, user["id"], f"mom.{st}", "meeting", mid, f"{n} messages")
    return {"ok": True, "queued": n}


@router.delete("/meetings/{mid}")
def delete_meeting(mid: int, user=Depends(require("meetings.manage"))):
    with db.tx() as c:
        db.update(c, "meetings", mid, {"deleted": 1, "updated": time.time()})
    return {"ok": True}


@router.get("/meetings/{mid}/print", response_class=HTMLResponse)
def print_mom(mid: int, request: Request, lang: str = "ml"):
    user = auth.user_from_request(request)
    if not user:
        raise HTTPException(401, "sign in")
    m = _meeting(mid)
    role = _need(user, m["committee_id"])
    if role != "manage" and m["mom_status"] == "draft":
        raise HTTPException(403, "minutes not published yet")
    lang = lang if lang in ("en", "ml") else "en"
    L = {"en": ("Minutes of the meeting", "Date", "Venue", "Chaired by", "Recorded by", "Present", "Agenda and decisions", "Decision", "Resolution", "Action items", "Owner", "Due", "Next meeting", "Approved by", "DRAFT - not yet published"),
         "ml": ("യോഗത്തിന്റെ മിനിറ്റ്സ്", "തീയതി", "സ്ഥലം", "അധ്യക്ഷൻ", "രേഖപ്പെടുത്തിയത്", "പങ്കെടുത്തവർ", "അജണ്ടയും തീരുമാനങ്ങളും", "തീരുമാനം", "പ്രമേയം", "ചുമതലകൾ", "ചുമതലക്കാരൻ", "അവസാന തീയതി", "അടുത്ത യോഗം", "അംഗീകരിച്ചത്", "കരട് - പ്രസിദ്ധീകരിച്ചിട്ടില്ല")}[lang]
    s = db.settings_all()
    agenda = db.q("SELECT * FROM agenda_items WHERE meeting_id=? ORDER BY idx, id", (mid,))
    att = db.q("SELECT a.status, mm.name_en, mm.name_ml FROM attendance a JOIN members mm ON mm.id=a.member_id WHERE a.meeting_id=? AND a.status IN ('present','online') ORDER BY mm.name_en", (mid,))
    acts = db.q("SELECT a.*, mm.name_en AS owner_en, mm.name_ml AS owner_ml FROM actions a LEFT JOIN members mm ON mm.id=a.owner_member_id WHERE a.meeting_id=? ORDER BY a.id", (mid,))
    chair = db.one("SELECT name_en, name_ml FROM members WHERE id=?", (m["chaired_by"],)) if m["chaired_by"] else None
    rec = db.one("SELECT name_en, name_ml FROM members WHERE id=?", (m["recorded_by"],)) if m["recorded_by"] else None
    appr = db.one("SELECT name FROM users WHERE id=?", (m["mom_approved_by"],)) if m["mom_approved_by"] else None
    e = html.escape
    items = ""
    for i, a in enumerate(agenda):
        items += f"<div class='item'><h3>{i + 1}. {e(i18n.pick(a, 'title', lang))}{(' <span class=res>' + L[8] + ' ' + e(a['resolution_no']) + '</span>') if a['resolution_no'] else ''}</h3>"
        if i18n.pick(a, "detail", lang):
            items += f"<pre>{e(i18n.pick(a, 'detail', lang))}</pre>"
        if i18n.pick(a, "decision", lang):
            items += f"<div class='dec'><b>{L[7]}:</b> <pre>{e(i18n.pick(a, 'decision', lang))}</pre></div>"
        items += "</div>"
    acts_html = "".join(f"<tr><td>{e(i18n.pick(a, 'title', lang))}</td><td>{e(i18n.pick(a, 'owner', lang) or '-')}</td><td>{e(a['due'] or '-')}</td><td>{e(a['status'])}</td></tr>" for a in acts)
    draft = f"<div class='draft'>{L[14]}</div>" if m["mom_status"] == "draft" else ""
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{e(i18n.pick(m, 'title', lang))}</title>
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;max-width:800px;margin:0 auto;padding:24px;color:#1d2a28;line-height:1.5}}h1{{margin:0;font-size:1.3rem}}
.club{{color:#0F4C45;font-weight:700}}.kv{{display:grid;grid-template-columns:140px 1fr;gap:2px 10px;margin:14px 0;font-size:.95rem}}
.item{{margin:12px 0;padding:8px 12px;border-left:3px solid #0F4C45;background:#f6f8f7}}h3{{margin:0 0 4px;font-size:1rem}}pre{{white-space:pre-wrap;font:inherit;margin:4px 0}}
.dec{{margin-top:6px}}.res{{font-size:.8rem;color:#C9542A}}table{{width:100%;border-collapse:collapse;font-size:.9rem}}td,th{{border:1px solid #ccc;padding:5px 8px;text-align:left}}
.draft{{background:#fde8e0;color:#8a2a0a;padding:6px 10px;border-radius:6px;margin:10px 0;font-weight:700}}.sign{{display:flex;justify-content:space-between;margin-top:50px}}
@media print{{body{{padding:0}}}}</style></head><body>
<div class="club">{e(s['club_name_ml' if lang == 'ml' else 'club_name_en'])}</div><h1>{e(i18n.pick(m, 'committee', lang))} - {L[0]}</h1><div>{e(i18n.pick(m, 'title', lang))}</div>{draft}
<div class="kv"><div>{L[1]}</div><div>{e(_fmt_when(m['scheduled_at']))}</div><div>{L[2]}</div><div>{e(i18n.pick(m, 'venue', lang) or m['link'] or '-')}</div>
<div>{L[3]}</div><div>{e(i18n.pick(chair, 'name', lang)) if chair else '-'}</div><div>{L[4]}</div><div>{e(i18n.pick(rec, 'name', lang)) if rec else '-'}</div>
<div>{L[5]}</div><div>{len(att)}: {e(', '.join(i18n.pick(a, 'name', lang) for a in att))}</div></div>
<h2>{L[6]}</h2>{items}
{('<pre>' + e(i18n.pick(m, 'summary', lang)) + '</pre>') if i18n.pick(m, 'summary', lang) else ''}
{('<h2>' + L[9] + '</h2><table><tr><th></th><th>' + L[10] + '</th><th>' + L[11] + '</th><th></th></tr>' + acts_html + '</table>') if acts else ''}
{('<p><b>' + L[12] + ':</b> ' + e(_fmt_when(m['next_meeting_at'])) + '</p>') if m['next_meeting_at'] else ''}
<div class="sign"><div>{L[4]}<br><br>______________</div><div>{L[3]}<br><br>______________</div></div>
{('<p style="color:#0F4C45">' + L[13] + ': ' + e(appr['name']) + ' · ' + dt.datetime.fromtimestamp(m['mom_approved_at']).strftime('%d-%m-%Y') + '</p>') if appr else ''}
<script>setTimeout(()=>window.print(),400)</script></body></html>"""


# ---------- actions ----------
@router.get("/actions")
def list_actions(status: str = "", mine: int = 0, committee_id: int = 0, user=Depends(current_user)):
    where, args = ["1=1"], []
    if status:
        where.append("a.status=?"); args.append(status)
    if committee_id:
        where.append("a.committee_id=?"); args.append(committee_id)
    if mine or not (can(user, "meetings.manage") or user.get("convenes")):
        where.append("a.owner_member_id=?"); args.append(user.get("member_id") or -1)
    rows = db.q(f"SELECT a.*, mm.name_en AS owner_en, mm.name_ml AS owner_ml, c.name_en AS committee_en, c.name_ml AS committee_ml, me.title_en AS meeting_en, me.title_ml AS meeting_ml "
                f"FROM actions a LEFT JOIN members mm ON mm.id=a.owner_member_id LEFT JOIN committees c ON c.id=a.committee_id LEFT JOIN meetings me ON me.id=a.meeting_id "
                f"WHERE {' AND '.join(where)} ORDER BY CASE a.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END, a.due, a.id DESC LIMIT 500", args)
    if not mine and not can(user, "meetings.manage"):
        rows = [r for r in rows if r["committee_id"] in user.get("convenes", []) or r["owner_member_id"] == user.get("member_id")]
    return rows


@router.post("/actions")
async def save_action(request: Request, user=Depends(current_user)):
    b = await request.json()
    now = time.time()
    with db.tx() as c:
        if b.get("id"):
            a = db.one("SELECT * FROM actions WHERE id=?", (b["id"],))
            if not a:
                raise HTTPException(404)
            owner = a["owner_member_id"] == user.get("member_id")
            manager = committee_role(user, a["committee_id"]) == "manage" if a["committee_id"] else can(user, "meetings.manage")
            if not (owner or manager):
                raise HTTPException(403, "no")
            row = {"updated": now}
            if manager:
                for k in ("title_en", "title_ml", "detail_en", "detail_ml", "due", "priority"):
                    if k in b:
                        row[k] = b[k] or ""
                if "owner_member_id" in b:
                    row["owner_member_id"] = b["owner_member_id"] or None
            if "status" in b and b["status"] in ("open", "in_progress", "done", "dropped"):
                row["status"] = b["status"]
                row["done_at"] = now if b["status"] == "done" else None
            if "progress_note" in b:
                row["progress_note"] = b["progress_note"] or ""
            db.update(c, "actions", a["id"], row)
            aid = a["id"]
            new_owner = row.get("owner_member_id") if "owner_member_id" in row and row["owner_member_id"] != a["owner_member_id"] else None
        else:
            cid = b.get("committee_id") or None
            meeting = db.one("SELECT committee_id FROM meetings WHERE id=?", (b.get("meeting_id"),)) if b.get("meeting_id") else None
            if meeting:
                cid = meeting["committee_id"]
            if cid:
                _need(user, cid, "manage")
            elif not can(user, "meetings.manage"):
                raise HTTPException(403, "no")
            if not (b.get("title_en") or b.get("title_ml")):
                raise HTTPException(400, "title")
            row = {"committee_id": cid, "meeting_id": b.get("meeting_id") or None, "agenda_item_id": b.get("agenda_item_id") or None, "plan_id": b.get("plan_id") or None,
                   "title_en": b.get("title_en") or b.get("title_ml"), "title_ml": b.get("title_ml") or "", "detail_en": b.get("detail_en") or "", "detail_ml": b.get("detail_ml") or "",
                   "owner_member_id": b.get("owner_member_id") or None, "due": b.get("due") or "", "status": "open", "priority": b.get("priority") or "normal",
                   "created_by": user["id"], "created": now, "updated": now}
            aid = db.insert(c, "actions", row)
            new_owner = row["owner_member_id"]
        if new_owner and b.get("notify", True):
            a = db.one("SELECT a.*, c.name_en AS committee_en, c.name_ml AS committee_ml FROM actions a LEFT JOIN committees c ON c.id=a.committee_id WHERE a.id=?", (aid,))
            comms.notify_members(c, [new_owner], "action_assigned", {"due": a["due"] or "-", "link": f"{comms.club_ctx()['link']}/#/actions"}, ("app", "whatsapp"),
                                 ref_kind="action", ref_id=aid, created_by=user["id"],
                                 per_member=lambda mm: {"title": i18n.pick(a, "title", mm["lang"]), "committee": i18n.pick(a, "committee", mm["lang"])})
            c.execute("UPDATE actions SET notified_at=? WHERE id=?", (now, aid))
    return {"ok": True, "id": aid}


# ---------- plans ----------
@router.get("/plans")
def list_plans(user=Depends(current_user)):
    rows = db.q("SELECT p.*, m.name_en AS owner_en, m.name_ml AS owner_ml, c.name_en AS committee_en, c.name_ml AS committee_ml, "
                "(SELECT COUNT(*) FROM actions a WHERE a.plan_id=p.id) AS actions_total, (SELECT COUNT(*) FROM actions a WHERE a.plan_id=p.id AND a.status='done') AS actions_done "
                "FROM plans p LEFT JOIN members m ON m.id=p.owner_member_id LEFT JOIN committees c ON c.id=p.committee_id ORDER BY p.period DESC, p.id DESC")
    return [r for r in rows if not r["committee_id"] or committee_role(user, r["committee_id"])]


@router.post("/plans")
async def save_plan(request: Request, user=Depends(current_user)):
    b = await request.json()
    cid = b.get("committee_id") or None
    if cid:
        _need(user, cid, "manage")
    elif not can(user, "meetings.manage"):
        raise HTTPException(403, "no")
    row = {"committee_id": cid, "title_en": b.get("title_en") or b.get("title_ml") or "", "title_ml": b.get("title_ml") or "", "detail_en": b.get("detail_en") or "",
           "detail_ml": b.get("detail_ml") or "", "period": b.get("period") or "", "budget": float(b.get("budget") or 0), "owner_member_id": b.get("owner_member_id") or None,
           "status": b.get("status") or "proposed", "progress_pct": max(0, min(100, int(b.get("progress_pct") or 0))), "updated": time.time()}
    if not row["title_en"]:
        raise HTTPException(400, "title")
    if row["status"] not in ("proposed", "approved", "in_progress", "done", "dropped"):
        row["status"] = "proposed"
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "plans", b["id"], row); pid = b["id"]
        else:
            row.update({"created_by": user["id"], "created": time.time()}); pid = db.insert(c, "plans", row)
    return {"ok": True, "id": pid}
