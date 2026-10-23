"""Polls and elections: one ballot per eligible member, anonymous by default, results after close (or live)."""
import datetime as dt
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from . import auth, comms, db, i18n
from .auth import can, committee_role, current_user, require

router = APIRouter(prefix="/api/polls")


def _poll(pid):
    p = db.one("SELECT p.*, c.name_en AS committee_en, c.name_ml AS committee_ml FROM polls p LEFT JOIN committees c ON c.id=p.committee_id WHERE p.id=? AND p.deleted=0", (pid,))
    if not p:
        raise HTTPException(404)
    return p


def eligible(user, p):
    if not user.get("member_id") or user.get("member_status") != "active":
        return False
    if p["audience"] == "committee":
        return committee_role(user, p["committee_id"] or 0) != ""
    return True


def voter_ids(p):
    if p["audience"] == "committee":
        return [r["member_id"] for r in db.q("SELECT cm.member_id FROM committee_members cm JOIN members m ON m.id=cm.member_id WHERE cm.committee_id=? AND cm.active=1 AND m.status='active'", (p["committee_id"],))]
    return [r["id"] for r in db.q("SELECT id FROM members WHERE status='active'")]


def _is_open(p):
    now = dt.datetime.now().strftime("%Y-%m-%dT%H:%M")
    return p["status"] == "open" and (not p["ends_at"] or p["ends_at"] >= now) and (not p["starts_at"] or p["starts_at"] <= now)


def results(p):
    rows = db.q("SELECT o.*, m.name_en AS cand_en, m.name_ml AS cand_ml, m.photo, (SELECT COUNT(*) FROM votes v WHERE v.option_id=o.id) AS votes FROM poll_options o LEFT JOIN members m ON m.id=o.member_id WHERE o.poll_id=? ORDER BY o.idx, o.id", (p["id"],))
    total = db.one("SELECT COUNT(*) n FROM ballots WHERE poll_id=?", (p["id"],))["n"]
    for r in rows:
        r["pct"] = round(100 * r["votes"] / total, 1) if total else 0
    return {"options": rows, "ballots": total, "eligible": len(voter_ids(p))}


@router.get("")
def list_polls(user=Depends(current_user)):
    rows = db.q("SELECT p.*, c.name_en AS committee_en, c.name_ml AS committee_ml, (SELECT COUNT(*) FROM ballots b WHERE b.poll_id=p.id) AS ballots FROM polls p LEFT JOIN committees c ON c.id=p.committee_id WHERE p.deleted=0 ORDER BY p.id DESC")
    out = []
    for p in rows:
        manage = can(user, "posts.manage") or (p["committee_id"] and committee_role(user, p["committee_id"]) == "manage")
        if p["status"] == "draft" and not manage:
            continue
        if not (manage or eligible(user, p)):
            continue
        p["open_now"] = _is_open(p)
        p["voted"] = bool(db.one("SELECT 1 FROM ballots WHERE poll_id=? AND member_id=?", (p["id"], user.get("member_id") or -1)))
        p["can_manage"] = bool(manage)
        out.append(p)
    return out


@router.get("/{pid}")
def get_poll(pid: int, user=Depends(current_user)):
    p = _poll(pid)
    manage = can(user, "posts.manage") or (p["committee_id"] and committee_role(user, p["committee_id"]) == "manage")
    if not (manage or (p["status"] != "draft" and eligible(user, p))):
        raise HTTPException(403, "not for you")
    p["open_now"] = _is_open(p)
    p["can_manage"] = bool(manage)
    p["eligible"] = eligible(user, p)
    p["voted"] = bool(db.one("SELECT 1 FROM ballots WHERE poll_id=? AND member_id=?", (pid, user.get("member_id") or -1)))
    p["options"] = db.q("SELECT o.*, m.name_en AS cand_en, m.name_ml AS cand_ml, m.photo, m.member_no FROM poll_options o LEFT JOIN members m ON m.id=o.member_id WHERE o.poll_id=? ORDER BY o.idx, o.id", (pid,))
    show = p["status"] == "closed" or (p["results_live"] and p["open_now"]) or manage
    p["results"] = results(p) if show else {"ballots": db.one("SELECT COUNT(*) n FROM ballots WHERE poll_id=?", (pid,))["n"], "eligible": len(voter_ids(p))}
    if not p["anonymous"] and manage:
        p["voters"] = db.q("SELECT b.member_id, m.name_en, m.name_ml, b.created, GROUP_CONCAT(o.label_en, ', ') AS chosen FROM ballots b JOIN members m ON m.id=b.member_id LEFT JOIN votes v ON v.poll_id=b.poll_id AND v.member_id=b.member_id LEFT JOIN poll_options o ON o.id=v.option_id WHERE b.poll_id=? GROUP BY b.member_id ORDER BY b.created", (pid,))
    return p


@router.post("")
async def save_poll(request: Request, user=Depends(current_user)):
    b = await request.json()
    cid = b.get("committee_id") or None
    if cid:
        if committee_role(user, cid) != "manage":
            raise HTTPException(403, "no")
    elif not can(user, "posts.manage"):
        raise HTTPException(403, "no")
    row = {"kind": b.get("kind") if b.get("kind") in ("poll", "election") else "poll", "title_en": b.get("title_en") or b.get("title_ml") or "", "title_ml": b.get("title_ml") or "",
           "description_en": b.get("description_en") or "", "description_ml": b.get("description_ml") or "", "audience": "committee" if cid else "members", "committee_id": cid,
           "starts_at": (b.get("starts_at") or "")[:16], "ends_at": (b.get("ends_at") or "")[:16], "anonymous": 1 if b.get("anonymous", 1) else 0,
           "max_choices": max(1, int(b.get("max_choices") or 1)), "results_live": 1 if b.get("results_live") else 0, "updated": time.time()}
    if not row["title_en"]:
        raise HTTPException(400, "title")
    with db.tx() as c:
        if b.get("id"):
            p = _poll(b["id"])
            if p["status"] != "draft":
                row = {k: row[k] for k in ("title_en", "title_ml", "description_en", "description_ml", "ends_at", "results_live", "updated")}
            db.update(c, "polls", b["id"], row); pid = b["id"]
        else:
            row.update({"status": "draft", "created_by": user["id"], "created": time.time()}); pid = db.insert(c, "polls", row)
        if "options" in b and (not b.get("id") or _poll(pid)["status"] == "draft"):
            keep = []
            for i, o in enumerate(b["options"] or []):
                label = o.get("label_en") or o.get("label_ml") or ""
                if o.get("member_id") and not label:
                    m = db.one("SELECT name_en, name_ml FROM members WHERE id=?", (o["member_id"],))
                    if m:
                        label, o["label_ml"] = m["name_en"], m["name_ml"]
                if not label:
                    continue
                r = {"poll_id": pid, "idx": i, "label_en": label, "label_ml": o.get("label_ml") or "", "member_id": o.get("member_id") or None, "note": o.get("note") or ""}
                if o.get("id"):
                    db.update(c, "poll_options", o["id"], r); keep.append(o["id"])
                else:
                    keep.append(db.insert(c, "poll_options", r))
            marks = ",".join("?" for _ in keep) or "0"
            c.execute(f"DELETE FROM poll_options WHERE poll_id=? AND id NOT IN ({marks})", [pid] + keep)
        db.audit(c, user["id"], "poll.save", "poll", pid, row.get("title_en", ""))
    return {"ok": True, "id": pid}


@router.post("/{pid}/status")
async def poll_status(pid: int, request: Request, user=Depends(current_user)):
    p = _poll(pid)
    manage = can(user, "posts.manage") or (p["committee_id"] and committee_role(user, p["committee_id"]) == "manage")
    if not manage:
        raise HTTPException(403, "no")
    b = await request.json()
    st = b.get("status")
    if st not in ("open", "closed", "draft"):
        raise HTTPException(400, "status")
    n = 0
    with db.tx() as c:
        if st == "open":
            if db.one("SELECT COUNT(*) n FROM poll_options WHERE poll_id=?", (pid,))["n"] < 2:
                raise HTTPException(400, "at least two options are needed")
            db.update(c, "polls", pid, {"status": "open", "opened_at": p["opened_at"] or time.time(), "updated": time.time()})
            if b.get("notify", True):
                link = f"{comms.club_ctx()['link']}/#/polls/{pid}"
                n = comms.notify_members(c, voter_ids(p), "poll_open", {"link": link, "ends": p["ends_at"].replace("T", " ") or "-"}, b.get("channels") or ["app", "whatsapp"],
                                         ref_kind="poll", ref_id=pid, batch_id=comms.new_batch(), created_by=user["id"],
                                         per_member=lambda m: {"title": i18n.pick(p, "title", m["lang"]), "kind": i18n.label(i18n.POLL_KIND_LABELS, p["kind"], m["lang"])})
        elif st == "closed":
            db.update(c, "polls", pid, {"status": "closed", "closed_at": time.time(), "updated": time.time()})
            if b.get("notify", True):
                res = results(p)
                top = sorted(res["options"], key=lambda o: -o["votes"])[:3]
                link = f"{comms.club_ctx()['link']}/#/polls/{pid}"
                n = comms.notify_members(c, voter_ids(p), "poll_results", {"link": link}, b.get("channels") or ["app"], ref_kind="poll", ref_id=pid, batch_id=comms.new_batch(), created_by=user["id"],
                                         per_member=lambda m: {"title": i18n.pick(p, "title", m["lang"]), "summary": "; ".join(f"{i18n.pick(o, 'label', m['lang'])}: {o['votes']}" for o in top)})
        else:
            if db.one("SELECT 1 FROM ballots WHERE poll_id=?", (pid,)):
                raise HTTPException(400, "votes have been cast - it cannot go back to draft")
            db.update(c, "polls", pid, {"status": "draft", "updated": time.time()})
        db.audit(c, user["id"], f"poll.{st}", "poll", pid, f"{n} messages")
    return {"ok": True, "queued": n}


@router.post("/{pid}/vote")
async def vote(pid: int, request: Request, user=Depends(current_user)):
    p = _poll(pid)
    if not eligible(user, p):
        raise HTTPException(403, "you are not eligible to vote in this")
    if not _is_open(p):
        raise HTTPException(400, "voting is not open")
    b = await request.json()
    choices = [int(x) for x in (b.get("option_ids") or []) if str(x).isdigit()]
    valid = {o["id"] for o in db.q("SELECT id FROM poll_options WHERE poll_id=?", (pid,))}
    choices = [x for x in dict.fromkeys(choices) if x in valid]
    if not choices or len(choices) > p["max_choices"]:
        raise HTTPException(400, f"choose between 1 and {p['max_choices']}")
    with db.tx() as c:
        if db.one("SELECT 1 FROM ballots WHERE poll_id=? AND member_id=?", (pid, user["member_id"])):
            raise HTTPException(409, "you have already voted")
        c.execute("INSERT INTO ballots(poll_id, member_id, created) VALUES(?,?,?)", (pid, user["member_id"], time.time()))
        for oid in choices:
            db.insert(c, "votes", {"poll_id": pid, "option_id": oid, "member_id": None if p["anonymous"] else user["member_id"], "created": time.time()})
    return {"ok": True}


@router.delete("/{pid}")
def delete_poll(pid: int, user=Depends(require("posts.manage"))):
    with db.tx() as c:
        db.update(c, "polls", pid, {"deleted": 1, "updated": time.time()})
    return {"ok": True}
