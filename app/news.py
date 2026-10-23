"""News, events, camps, competitions and social activities: publishing with push to members, registrations
(members and their family), competition items and results, and a public page for sharing on WhatsApp groups."""
import datetime as dt
import html
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import auth, comms, db, i18n
from .auth import can, current_user, require

router = APIRouter()
KINDS = ["news", "event", "camp", "competition", "activity", "notice"]
LEVELS = ["club", "ward", "panchayat", "block", "district", "state", "regional", "national"]
FIELDS = ["kind", "title_en", "title_ml", "body_en", "body_ml", "category", "level", "starts_at", "ends_at", "venue_en", "venue_ml", "cover", "audience",
          "committee_id", "pinned", "reg_open", "reg_limit", "reg_fee", "reg_family", "reg_closes", "organiser", "contact_phone", "results_en", "results_ml"]
INTS = {"pinned", "reg_open", "reg_limit", "reg_family", "committee_id"}


def _clean(b):
    out = {}
    for k in FIELDS:
        if k not in b:
            continue
        v = b[k]
        if k in INTS:
            v = int(v or 0) if v not in ("", None, False) else 0
            if k == "committee_id" and not v:
                v = None
        elif k == "reg_fee":
            v = float(v or 0)
        else:
            v = (str(v) if v is not None else "").strip()
        out[k] = v
    if "kind" in out and out["kind"] not in KINDS:
        out["kind"] = "news"
    if "level" in out and out["level"] not in LEVELS:
        out["level"] = "club"
    if "audience" in out and out["audience"] not in ("public", "members", "committee"):
        out["audience"] = "members"
    return out


def visible(user, p):
    if p["audience"] == "public":
        return True
    if not user:
        return False
    if can(user, "posts.manage"):
        return True
    if p["audience"] == "members":
        return bool(user.get("member_id"))
    return bool(p.get("committee_id")) and auth.committee_role(user, p["committee_id"]) != ""


def _enrich(rows):
    for p in rows:
        p["reg_count"] = db.one("SELECT COUNT(*) n FROM registrations WHERE post_id=? AND status<>'cancelled'", (p["id"],))["n"]
    return rows


@router.get("/api/public/posts")
def public_posts(limit: int = 20):
    return _enrich(db.q("SELECT * FROM posts WHERE status='published' AND audience='public' AND deleted=0 ORDER BY pinned DESC, COALESCE(NULLIF(starts_at,''), '9999') DESC, published_at DESC LIMIT ?", (limit,)))


@router.get("/api/posts")
def list_posts(kind: str = "", status: str = "", upcoming: int = 0, user=Depends(current_user)):
    where, args = ["deleted=0"], []
    if kind:
        where.append("kind=?"); args.append(kind)
    if can(user, "posts.manage") and status:
        where.append("status=?"); args.append(status)
    elif not can(user, "posts.manage"):
        where.append("status='published'")
    if upcoming:
        where.append("(starts_at='' OR starts_at>=?)"); args.append(dt.date.today().isoformat())
    rows = db.q(f"SELECT * FROM posts WHERE {' AND '.join(where)} ORDER BY pinned DESC, COALESCE(published_at, created) DESC LIMIT 300", args)
    rows = [p for p in rows if visible(user, p)]
    if user.get("member_id"):
        mine = {r["post_id"] for r in db.q("SELECT post_id FROM registrations WHERE member_id=? AND status<>'cancelled'", (user["member_id"],))}
        for p in rows:
            p["registered"] = p["id"] in mine
    return _enrich(rows)


@router.get("/api/posts/{pid}")
def get_post(pid: int, user=Depends(current_user)):
    p = db.one("SELECT * FROM posts WHERE id=? AND deleted=0", (pid,))
    if not p or not visible(user, p) or (p["status"] != "published" and not can(user, "posts.manage")):
        raise HTTPException(404)
    p["files"] = db.q("SELECT * FROM post_files WHERE post_id=? ORDER BY id", (pid,))
    p["items"] = db.q("SELECT * FROM comp_items WHERE post_id=? ORDER BY idx, id", (pid,))
    p["results"] = db.q("SELECT r.*, ci.name_en AS item_en, ci.name_ml AS item_ml FROM results r LEFT JOIN comp_items ci ON ci.id=r.item_id WHERE r.post_id=? ORDER BY r.item_id, r.position", (pid,))
    p["reg_count"] = db.one("SELECT COUNT(*) n FROM registrations WHERE post_id=? AND status<>'cancelled'", (pid,))["n"]
    if user.get("member_id"):
        p["my_registrations"] = db.q("SELECT r.*, ci.name_en AS item_en, ci.name_ml AS item_ml FROM registrations r LEFT JOIN comp_items ci ON ci.id=r.item_id WHERE r.post_id=? AND r.member_id=? AND r.status<>'cancelled'", (pid, user["member_id"]))
    if can(user, "posts.manage"):
        p["registrations"] = db.q("SELECT r.*, m.name_en AS member_en, m.name_ml AS member_ml, m.phone, m.member_no, ci.name_en AS item_en, ci.name_ml AS item_ml "
                                  "FROM registrations r JOIN members m ON m.id=r.member_id LEFT JOIN comp_items ci ON ci.id=r.item_id WHERE r.post_id=? ORDER BY r.id", (pid,))
    return p


@router.post("/api/posts")
async def save_post(request: Request, user=Depends(require("posts.manage"))):
    b = await request.json()
    row = _clean(b)
    now = time.time()
    with db.tx() as c:
        if b.get("id"):
            row["updated"] = now
            db.update(c, "posts", b["id"], row)
            pid = b["id"]
        else:
            if not row.get("title_en") and not row.get("title_ml"):
                raise HTTPException(400, "title is required")
            row.setdefault("title_en", row.get("title_ml", ""))
            row.update({"status": "draft", "created_by": user["id"], "created": now, "updated": now})
            pid = db.insert(c, "posts", row)
        if "items" in b:
            keep = []
            for i, it in enumerate(b["items"] or []):
                if not (it.get("name_en") or it.get("name_ml")):
                    continue
                r = {"post_id": pid, "idx": i, "name_en": it.get("name_en") or it.get("name_ml"), "name_ml": it.get("name_ml") or "", "age_group": it.get("age_group") or "",
                     "gender": it.get("gender") or "", "kind": it.get("kind") or "individual", "max_entries": int(it.get("max_entries") or 0), "note": it.get("note") or ""}
                if it.get("id"):
                    db.update(c, "comp_items", it["id"], r); keep.append(it["id"])
                else:
                    keep.append(db.insert(c, "comp_items", r))
            marks = ",".join("?" for _ in keep) or "0"
            c.execute(f"DELETE FROM comp_items WHERE post_id=? AND id NOT IN ({marks})", [pid] + keep)
        db.audit(c, user["id"], "post.save", "post", pid, row.get("title_en", ""))
    return {"ok": True, "id": pid}


@router.post("/api/posts/{pid}/files")
async def add_post_file(pid: int, request: Request, user=Depends(require("posts.manage"))):
    b = await request.json()
    with db.tx() as c:
        fid = db.insert(c, "post_files", {"post_id": pid, "filename": b.get("filename") or "", "mime": b.get("mime") or "", "path": b["path"],
                                          "caption": b.get("caption") or "", "created": time.time(), "uploaded_by": user["id"]})
    return {"ok": True, "id": fid}


@router.delete("/api/posts/{pid}/files/{fid}")
def del_post_file(pid: int, fid: int, user=Depends(require("posts.manage"))):
    with db.tx() as c:
        c.execute("DELETE FROM post_files WHERE id=? AND post_id=?", (fid, pid))
    return {"ok": True}


def _when(p, lang):
    s = p.get("starts_at") or ""
    if not s:
        return ""
    try:
        d = dt.datetime.fromisoformat(s)
        out = d.strftime("%d-%m-%Y %I:%M %p") if len(s) > 10 else d.strftime("%d-%m-%Y")
    except ValueError:
        out = s
    if p.get("ends_at"):
        out += " - " + p["ends_at"][:10]
    return out


def audience_for_post(p):
    if p["audience"] == "committee" and p.get("committee_id"):
        return [r["member_id"] for r in db.q("SELECT cm.member_id FROM committee_members cm JOIN members m ON m.id=cm.member_id WHERE cm.committee_id=? AND cm.active=1 AND m.status='active'", (p["committee_id"],))]
    return [r["id"] for r in db.q("SELECT id FROM members WHERE status='active'")]


@router.post("/api/posts/{pid}/publish")
async def publish(pid: int, request: Request, user=Depends(require("posts.manage"))):
    """Publish, and push by the chosen channels to the post's audience. Re-publishing with notify=false just edits."""
    b = await request.json()
    p = db.one("SELECT * FROM posts WHERE id=? AND deleted=0", (pid,))
    if not p:
        raise HTTPException(404)
    channels = [ch for ch in (b.get("channels") or ["app", "whatsapp"]) if ch in comms.CHANNELS]
    now = time.time()
    n = 0
    with db.tx() as c:
        db.update(c, "posts", pid, {"status": "published", "published_at": p["published_at"] or now, "updated": now})
        if b.get("notify", True):
            ids = audience_for_post(p)
            link = f"{comms.club_ctx()['link']}/p/{pid}" if p["audience"] == "public" else f"{comms.club_ctx()['link']}/#/posts/{pid}"
            tmpl = "news" if p["kind"] in ("news", "notice") else "event"

            def per(m):
                lang = m.get("lang") or "ml"
                body = i18n.pick(p, "body", lang)
                return {"title": i18n.pick(p, "title", lang), "summary": (body[:160] + "…") if len(body) > 160 else body,
                        "kind_label": i18n.label(i18n.KIND_LABELS, p["kind"], lang), "when": _when(p, lang), "venue": i18n.pick(p, "venue", lang), "link": link}

            n = comms.notify_members(c, ids, tmpl, {}, channels, ref_kind="post", ref_id=pid, batch_id=comms.new_batch(), created_by=user["id"], per_member=per)
            c.execute("UPDATE posts SET notified_at=? WHERE id=?", (now, pid))
        db.audit(c, user["id"], "post.publish", "post", pid, f"{n} messages")
    return {"ok": True, "queued": n}


@router.post("/api/posts/{pid}/status")
async def post_status(pid: int, request: Request, user=Depends(require("posts.manage"))):
    st = (await request.json()).get("status")
    if st not in ("draft", "published", "cancelled", "closed"):
        raise HTTPException(400, "status")
    with db.tx() as c:
        db.update(c, "posts", pid, {"status": st, "updated": time.time()})
    return {"ok": True}


@router.delete("/api/posts/{pid}")
def delete_post(pid: int, user=Depends(require("posts.manage"))):
    with db.tx() as c:
        db.update(c, "posts", pid, {"deleted": 1, "updated": time.time()})
    return {"ok": True}


# ---------- registrations ----------
@router.post("/api/posts/{pid}/register")
async def register(pid: int, request: Request, user=Depends(current_user)):
    if not user.get("member_id"):
        raise HTTPException(403, "members only")
    p = db.one("SELECT * FROM posts WHERE id=? AND deleted=0 AND status='published'", (pid,))
    if not p or not visible(user, p) or not p["reg_open"]:
        raise HTTPException(400, "registration is not open")
    if p["reg_closes"] and p["reg_closes"] < dt.date.today().isoformat():
        raise HTTPException(400, "registration has closed")
    b = await request.json()
    fam_id = b.get("family_id")
    item_id = b.get("item_id")
    name = user["name"]
    if fam_id:
        if not p["reg_family"]:
            raise HTTPException(400, "family registration is not allowed for this")
        f = db.one("SELECT * FROM family WHERE id=? AND member_id=? AND deleted=0", (fam_id, user["member_id"]))
        if not f:
            raise HTTPException(404, "family member")
        name = f["name_en"]
    else:
        m = db.one("SELECT name_en FROM members WHERE id=?", (user["member_id"],))
        name = m["name_en"]
    if item_id and not db.one("SELECT 1 FROM comp_items WHERE id=? AND post_id=?", (item_id, pid)):
        raise HTTPException(404, "item")
    with db.tx() as c:
        if db.one("SELECT 1 FROM registrations WHERE post_id=? AND member_id=? AND COALESCE(family_id,0)=? AND COALESCE(item_id,0)=? AND status<>'cancelled'",
                  (pid, user["member_id"], fam_id or 0, item_id or 0)):
            raise HTTPException(409, "already registered")
        count = db.one("SELECT COUNT(*) n FROM registrations WHERE post_id=? AND status='registered'", (pid,))["n"]
        status = "waitlisted" if p["reg_limit"] and count >= p["reg_limit"] else "registered"
        if item_id:
            it = db.one("SELECT max_entries FROM comp_items WHERE id=?", (item_id,))
            if it["max_entries"] and db.one("SELECT COUNT(*) n FROM registrations WHERE item_id=? AND status='registered'", (item_id,))["n"] >= it["max_entries"]:
                status = "waitlisted"
        team = (b.get("team") or "").strip() or (db.one("SELECT team, ward FROM members WHERE id=?", (user["member_id"],)) or {}).get("team") or ""
        rid = db.insert(c, "registrations", {"post_id": pid, "member_id": user["member_id"], "family_id": fam_id, "item_id": item_id, "participant_name": name,
                                             "status": status, "note": (b.get("note") or "")[:500], "team": team[:60], "created": time.time(), "updated": time.time()})
        item = db.one("SELECT * FROM comp_items WHERE id=?", (item_id,)) if item_id else None
        comms.notify_members(c, [user["member_id"]], "registration_confirmed", {}, ("app", "whatsapp"), ref_kind="post", ref_id=pid,
                             per_member=lambda m: {"participant": name, "title": i18n.pick(p, "title", m["lang"]), "item": i18n.pick(item, "name", m["lang"]) if item else "-",
                                                   "when": _when(p, m["lang"]), "venue": i18n.pick(p, "venue", m["lang"])})
    return {"ok": True, "id": rid, "status": status}


@router.post("/api/registrations/{rid}/status")
async def registration_status(rid: int, request: Request, user=Depends(current_user)):
    r = db.one("SELECT * FROM registrations WHERE id=?", (rid,))
    if not r:
        raise HTTPException(404)
    st = (await request.json()).get("status")
    own = r["member_id"] == user.get("member_id")
    if own and st != "cancelled":
        raise HTTPException(403, "you may only cancel")
    if not own and not can(user, "posts.manage"):
        raise HTTPException(403, "no")
    if st not in ("registered", "waitlisted", "cancelled", "attended"):
        raise HTTPException(400, "status")
    with db.tx() as c:
        db.update(c, "registrations", rid, {"status": st, "updated": time.time()})
    return {"ok": True}


@router.post("/api/posts/{pid}/attend")
async def attend_by_scan(pid: int, request: Request, user=Depends(require("posts.manage"))):
    """Mark a scanned member as attended: their registration if one exists, else a new 'attended' registration."""
    b = await request.json()
    m = db.one("SELECT id, name_en FROM members WHERE id=? AND status='active'", (b.get("member_id"),))
    if not m:
        raise HTTPException(404, "member")
    with db.tx() as c:
        regs = db.q("SELECT id FROM registrations WHERE post_id=? AND member_id=? AND family_id IS NULL AND status<>'cancelled'", (pid, m["id"]))
        if regs:
            for r in regs:
                db.update(c, "registrations", r["id"], {"status": "attended", "updated": time.time()})
            return {"ok": True, "registration_id": regs[0]["id"], "new": False}
        rid = db.insert(c, "registrations", {"post_id": pid, "member_id": m["id"], "participant_name": m["name_en"], "status": "attended", "created": time.time(), "updated": time.time()})
    return {"ok": True, "registration_id": rid, "new": True}


# ---------- results ----------
@router.post("/api/posts/{pid}/results")
async def save_results(pid: int, request: Request, user=Depends(require("posts.manage"))):
    b = await request.json()
    rows = b.get("results") or []
    with db.tx() as c:
        c.execute("DELETE FROM results WHERE post_id=?", (pid,))
        for r in rows:
            if not (r.get("participant_name") or r.get("registration_id")):
                continue
            name = r.get("participant_name") or ""
            if r.get("registration_id") and not name:
                reg = db.one("SELECT participant_name FROM registrations WHERE id=?", (r["registration_id"],))
                name = reg["participant_name"] if reg else ""
            db.insert(c, "results", {"post_id": pid, "item_id": r.get("item_id") or None, "position": int(r.get("position") or 1), "registration_id": r.get("registration_id") or None,
                                     "participant_name": name, "team": r.get("team") or "", "points": float(r.get("points") or 0), "remark": r.get("remark") or "", "created": time.time()})
        db.update(c, "posts", pid, {"results_en": b.get("results_en") or "", "results_ml": b.get("results_ml") or "", "results_at": time.time(), "updated": time.time()})
        n = 0
        if b.get("notify"):
            p = db.one("SELECT * FROM posts WHERE id=?", (pid,))
            link = f"{comms.club_ctx()['link']}/#/posts/{pid}"
            n = comms.notify_members(c, audience_for_post(p), "results", {"link": link}, b.get("channels") or ["app", "whatsapp"], ref_kind="post", ref_id=pid,
                                     batch_id=comms.new_batch(), created_by=user["id"], per_member=lambda m: {"title": i18n.pick(p, "title", m["lang"])})
    return {"ok": True, "queued": n}


# ---------- public share page ----------
@router.get("/p/{pid}", response_class=HTMLResponse)
def public_page(pid: int, request: Request, lang: str = ""):
    p = db.one("SELECT * FROM posts WHERE id=? AND deleted=0 AND status='published'", (pid,))
    user = auth.user_from_request(request)
    if not p or not visible(user, p):
        raise HTTPException(404)
    s = db.settings_all()
    lang = lang or s["default_lang"]
    title, body, venue = i18n.pick(p, "title", lang), i18n.pick(p, "body", lang), i18n.pick(p, "venue", lang)
    club = s["club_name_ml" if lang == "ml" else "club_name_en"]
    cover = f"<img class='cover' src='/uploads/{html.escape(p['cover'])}'>" if p["cover"] else ""
    og = f"<meta property='og:image' content='{comms.club_ctx()['link']}/uploads/{html.escape(p['cover'])}'>" if p["cover"] else ""
    when = _when(p, lang)
    meta = " · ".join(x for x in [i18n.label(i18n.KIND_LABELS, p["kind"], lang), when, venue] if x)
    other = "en" if lang == "ml" else "ml"
    results = i18n.pick(p, "results", lang)
    res_html = f"<h2>{'ഫലങ്ങൾ' if lang == 'ml' else 'Results'}</h2><pre>{html.escape(results)}</pre>" if results else ""
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · {html.escape(s['club_short'])}</title>
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(meta)}">{og}
<link href="https://fonts.googleapis.com/css2?family=Manjari:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
<style>body{{font-family:Inter,Manjari,sans-serif;margin:0;background:#F7F4EC;color:#1d2a28}}header{{background:#0F4C45;color:#fff;padding:14px 18px;font-weight:700}}
main{{max-width:720px;margin:0 auto;padding:18px}}.cover{{width:100%;border-radius:12px;max-height:420px;object-fit:cover}}h1{{font-size:1.5rem;margin:.6em 0 .2em}}
.meta{{color:#5b6b68;margin-bottom:1em}}pre{{white-space:pre-wrap;font:inherit;line-height:1.55}}a.btn{{display:inline-block;background:#C9542A;color:#fff;padding:10px 16px;border-radius:10px;text-decoration:none;margin-top:1em}}
footer{{text-align:center;color:#8a948f;font-size:.8rem;padding:24px}}.lang{{float:right;color:#fff;opacity:.8;font-weight:400;font-size:.85rem}}</style></head>
<body><header>{html.escape(club)}<a class="lang" href="?lang={other}">{'English' if lang == 'ml' else 'മലയാളം'}</a></header><main>{cover}
<h1>{html.escape(title)}</h1><div class="meta">{html.escape(meta)}</div><pre>{html.escape(body)}</pre>{res_html}
{"<a class='btn' href='/#/posts/" + str(pid) + "'>" + ('രജിസ്റ്റർ ചെയ്യുക' if lang == 'ml' else 'Register') + "</a>" if p['reg_open'] else ""}
</main><footer>{html.escape(s['footer_credit'])}</footer></body></html>"""


# ---------- fixtures (sports) ----------
def _post_for_manage(pid):
    p = db.one("SELECT * FROM posts WHERE id=? AND deleted=0", (pid,))
    if not p:
        raise HTTPException(404)
    return p


@router.get("/api/posts/{pid}/fixtures")
def list_fixtures(pid: int, user=Depends(current_user)):
    p = db.one("SELECT * FROM posts WHERE id=? AND deleted=0", (pid,))
    if not p or not visible(user, p):
        raise HTTPException(404)
    return db.q("SELECT f.*, ci.name_en AS item_en, ci.name_ml AS item_ml FROM fixtures f LEFT JOIN comp_items ci ON ci.id=f.item_id WHERE f.post_id=? ORDER BY f.round, f.idx, f.id", (pid,))


@router.post("/api/posts/{pid}/fixtures")
async def save_fixture(pid: int, request: Request, user=Depends(require("posts.manage"))):
    _post_for_manage(pid)
    b = await request.json()
    row = {k: (b.get(k) or "") for k in ("round", "side_a", "side_b", "scheduled_at", "venue", "score_a", "score_b", "winner", "note")}
    row["item_id"] = b.get("item_id") or None
    row["idx"] = int(b.get("idx") or 0)
    row["status"] = b.get("status") if b.get("status") in ("scheduled", "live", "done", "cancelled") else "scheduled"
    if not (row["side_a"] and row["side_b"]):
        raise HTTPException(400, "both sides are needed")
    if row["status"] == "done" and not row["winner"]:
        try:
            a, bb = float(row["score_a"]), float(row["score_b"])
            row["winner"] = row["side_a"] if a > bb else row["side_b"] if bb > a else "draw"
        except ValueError:
            pass
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "fixtures", b["id"], row); fid = b["id"]
        else:
            row["post_id"] = pid; fid = db.insert(c, "fixtures", row)
    return {"ok": True, "id": fid, "winner": row["winner"]}


@router.delete("/api/posts/{pid}/fixtures/{fid}")
def delete_fixture(pid: int, fid: int, user=Depends(require("posts.manage"))):
    with db.tx() as c:
        c.execute("DELETE FROM fixtures WHERE id=? AND post_id=?", (fid, pid))
    return {"ok": True}


# ---------- judges and scoring (arts) ----------
@router.get("/api/posts/{pid}/judges")
def list_judges(pid: int, user=Depends(require("posts.manage"))):
    return db.q("SELECT j.*, u.name, u.login FROM post_judges j JOIN users u ON u.id=j.user_id WHERE j.post_id=?", (pid,))


@router.post("/api/posts/{pid}/judges")
async def save_judges(pid: int, request: Request, user=Depends(require("posts.manage"))):
    """judges: [{user_id, item_ids: [..] or [] for all}]"""
    _post_for_manage(pid)
    b = await request.json()
    with db.tx() as c:
        c.execute("DELETE FROM post_judges WHERE post_id=?", (pid,))
        for j in b.get("judges") or []:
            if j.get("user_id") and db.one("SELECT 1 FROM users WHERE id=? AND active=1", (j["user_id"],)):
                c.execute("INSERT OR REPLACE INTO post_judges(post_id, user_id, item_ids) VALUES(?,?,?)", (pid, int(j["user_id"]), ",".join(str(x) for x in (j.get("item_ids") or []))))
    return {"ok": True}


@router.get("/api/judging")
def my_judging(user=Depends(current_user)):
    """Events where the signed-in user is a judge."""
    return db.q("SELECT p.id, p.title_en, p.title_ml, p.starts_at, j.item_ids FROM post_judges j JOIN posts p ON p.id=j.post_id WHERE j.user_id=? AND p.deleted=0 ORDER BY p.starts_at DESC", (user["id"],))


def _judge_items(pid, user):
    j = db.one("SELECT item_ids FROM post_judges WHERE post_id=? AND user_id=?", (pid, user["id"]))
    if not j and not can(user, "posts.manage"):
        raise HTTPException(403, "not a judge for this event")
    ids = [int(x) for x in (j["item_ids"] if j else "").split(",") if x.strip().isdigit()]
    return ids


@router.get("/api/posts/{pid}/judging")
def judging_sheet(pid: int, user=Depends(current_user)):
    ids = _judge_items(pid, user)
    items = db.q("SELECT * FROM comp_items WHERE post_id=? ORDER BY idx, id", (pid,))
    if ids:
        items = [i for i in items if i["id"] in ids]
    regs = db.q("SELECT r.id, r.item_id, r.participant_name, r.team, r.status FROM registrations r WHERE r.post_id=? AND r.status IN ('registered','attended') ORDER BY r.item_id, r.id", (pid,))
    mine = {(s["registration_id"], s["item_id"]): s for s in db.q("SELECT * FROM scores WHERE post_id=? AND judge_id=?", (pid, user["id"]))}
    for r in regs:
        sc = mine.get((r["id"], r["item_id"]))
        r["score"], r["remark"] = (sc["score"], sc["remark"]) if sc else (None, "")
    return {"items": items, "registrations": regs}


@router.post("/api/posts/{pid}/scores")
async def save_scores(pid: int, request: Request, user=Depends(current_user)):
    ids = _judge_items(pid, user)
    b = await request.json()
    n = 0
    with db.tx() as c:
        for s_ in b.get("scores") or []:
            reg = db.one("SELECT item_id FROM registrations WHERE id=? AND post_id=?", (s_.get("registration_id"), pid))
            if not reg or (ids and reg["item_id"] not in ids):
                continue
            c.execute("INSERT INTO scores(post_id, item_id, registration_id, judge_id, score, remark, created) VALUES(?,?,?,?,?,?,?) "
                      "ON CONFLICT(registration_id, judge_id, item_id) DO UPDATE SET score=excluded.score, remark=excluded.remark",
                      (pid, reg["item_id"], s_["registration_id"], user["id"], float(s_.get("score") or 0), (s_.get("remark") or "")[:300], time.time()))
            n += 1
    return {"ok": True, "saved": n}


@router.get("/api/posts/{pid}/ranking")
def ranking(pid: int, user=Depends(require("posts.manage"))):
    """Average of the judges' scores per participant, ranked within each item."""
    rows = db.q("SELECT s.item_id, s.registration_id, r.participant_name, r.team, AVG(s.score) avg_score, COUNT(DISTINCT s.judge_id) judges, ci.name_en AS item_en, ci.name_ml AS item_ml "
                "FROM scores s JOIN registrations r ON r.id=s.registration_id LEFT JOIN comp_items ci ON ci.id=s.item_id WHERE s.post_id=? GROUP BY s.item_id, s.registration_id ORDER BY s.item_id, avg_score DESC", (pid,))
    out, pos, last_item = [], 0, None
    for r in rows:
        if r["item_id"] != last_item:
            pos, last_item = 0, r["item_id"]
        pos += 1
        r["position"] = pos
        r["avg_score"] = round(r["avg_score"], 2)
        out.append(r)
    return out


@router.post("/api/posts/{pid}/results/from-ranking")
async def results_from_ranking(pid: int, request: Request, user=Depends(require("posts.manage"))):
    """Fill the results table from the ranking: top N per item with points N..1 (default 3: 5/3/1)."""
    b = await request.json()
    points = b.get("points") or [5, 3, 1]
    rows = ranking(pid, user)
    with db.tx() as c:
        c.execute("DELETE FROM results WHERE post_id=?", (pid,))
        for r in rows:
            if r["position"] <= len(points):
                db.insert(c, "results", {"post_id": pid, "item_id": r["item_id"], "position": r["position"], "registration_id": r["registration_id"], "participant_name": r["participant_name"],
                                         "team": r["team"], "points": points[r["position"] - 1], "remark": f"avg {r['avg_score']}", "created": time.time()})
        db.update(c, "posts", pid, {"results_at": time.time(), "updated": time.time()})
    return {"ok": True, "results": sum(1 for r in rows if r["position"] <= len(points))}


@router.get("/api/posts/{pid}/points")
def points_table(pid: int, user=Depends(current_user)):
    """Championship points by team (ward / house), from results and from won fixtures (3 points a win, 1 a draw)."""
    p = db.one("SELECT * FROM posts WHERE id=? AND deleted=0", (pid,))
    if not p or not visible(user, p):
        raise HTTPException(404)
    table = {}
    for r in db.q("SELECT team, SUM(points) pts, COUNT(*) n, SUM(CASE WHEN position=1 THEN 1 ELSE 0 END) firsts FROM results WHERE post_id=? AND team<>'' GROUP BY team", (pid,)):
        table[r["team"]] = {"team": r["team"], "points": r["pts"] or 0, "results": r["n"], "firsts": r["firsts"], "wins": 0, "draws": 0}
    for f in db.q("SELECT side_a, side_b, winner FROM fixtures WHERE post_id=? AND status='done'", (pid,)):
        for side in (f["side_a"], f["side_b"]):
            table.setdefault(side, {"team": side, "points": 0, "results": 0, "firsts": 0, "wins": 0, "draws": 0})
        if f["winner"] == "draw":
            for side in (f["side_a"], f["side_b"]):
                table[side]["points"] += 1; table[side]["draws"] += 1
        elif f["winner"] in table:
            table[f["winner"]]["points"] += 3; table[f["winner"]]["wins"] += 1
    return sorted(table.values(), key=lambda t: (-t["points"], -t["firsts"], t["team"]))
