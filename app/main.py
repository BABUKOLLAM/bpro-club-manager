"""Club management: membership, family, news & events, committees & meetings with online minutes, library and
reading room, accounts, and bilingual (English / Malayalam) communication by WhatsApp, SMS, e-mail and in-app."""
import contextlib
import datetime as dt
import json
import logging
import mimetypes
import os
import secrets
import time

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import auth, comms, db, i18n, push, security
from .auth import can, current_user, require
from . import members, news, committees, library, finance, reports, scheduler, facilities, payments, backup, polls, site, help as helpdoc

log = logging.getLogger("club")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@contextlib.asynccontextmanager
async def _lifespan(_app):
    db.init()
    bootstrap_admin()
    comms.start_worker()
    scheduler.start()
    yield


app = FastAPI(title="Club", docs_url=None, redoc_url=None, openapi_url=None, lifespan=_lifespan)
app.add_middleware(security.EdgeMiddleware)


def bootstrap_admin():
    """The first administrator comes from the environment, only while the database has no users at all."""
    if db.one("SELECT 1 FROM users LIMIT 1"):
        return
    login, pw = os.environ.get("CLUB_ADMIN_LOGIN", ""), os.environ.get("CLUB_ADMIN_PASSWORD", "")
    if not (login and pw):
        return
    with db.tx() as c:
        db.insert(c, "users", {"login": auth.norm_login(login), "name": os.environ.get("CLUB_ADMIN_NAME", "Administrator"), "role": "admin",
                               "pw_hash": auth.hash_pw(pw), "active": 1, "created": time.time(), "lang": "en"})
        committees.seed_defaults(c)


# ---------- errors ----------
@app.exception_handler(HTTPException)
async def _http_err(request, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# ---------- public ----------
@app.get("/healthz")
def healthz():
    db.one("SELECT 1")
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"), headers={"Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def manifest():
    s = db.settings_all()
    return JSONResponse({"name": s["club_name_en"], "short_name": s["club_short"], "start_url": "/", "display": "standalone",
                         "background_color": "#F7F4EC", "theme_color": "#0F4C45", "lang": "ml",
                         "icons": [{"src": "/static/icons/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}]},
                        media_type="application/manifest+json")


@app.get("/sw.js")
def sw():
    return FileResponse(os.path.join(STATIC, "sw.js"), media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/api/public/info")
def public_info():
    s = db.settings_all()
    keys = ["club_name_en", "club_name_ml", "club_short", "club_reg_no", "club_address_en", "club_address_ml", "club_phone", "club_email",
            "club_place_en", "club_place_ml", "public_registration", "default_lang", "footer_credit"]
    out = {k: s[k] for k in keys}
    out["membership_types"] = json.loads(s["membership_types"])
    out["wards"] = json.loads(s["wards"])
    out["blood_groups"] = members.BLOOD_GROUPS
    out["relations"] = members.RELATIONS
    out["channels"] = comms.configured()
    out["upi_id"] = s["upi_id"]
    out["upi_name"] = s["upi_name"]
    return out


# ---------- auth ----------
@app.post("/api/auth/login")
async def login(request: Request, resp: Response):
    body = await request.json()
    login_, pw = auth.norm_login(body.get("login")), body.get("password") or ""
    u = db.one("SELECT * FROM users WHERE login=?", (login_,))
    if not u and login_ and "@" not in login_:
        # a member may sign in with the phone they registered with even if the login was created from e-mail
        m = db.one("SELECT id FROM members WHERE substr(replace(replace(phone,' ',''),'-',''), -10)=? AND status='active'", (login_,))
        if m:
            u = db.one("SELECT * FROM users WHERE member_id=?", (m["id"],))
    if not u or not auth.check_pw(pw, u["pw_hash"]):
        time.sleep(0.4)
        raise HTTPException(401, "wrong login or password")
    if not u["active"]:
        raise HTTPException(403, "account not active yet - awaiting approval")
    with db.tx() as c:
        token = auth.create_session(c, u["id"])
        db.audit(c, u["id"], "login")
    auth.set_cookie(resp, token)
    return {"ok": True, "token": token}


@app.post("/api/auth/logout")
def logout(request: Request, resp: Response):
    token = request.cookies.get(auth.COOKIE)
    if token:
        with db.tx() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (token,))
    auth.clear_cookie(resp)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    u = auth.user_from_request(request)
    if not u:
        return {"user": None, "info": public_info()}
    m = db.one("SELECT * FROM members WHERE id=?", (u["member_id"],)) if u["member_id"] else None
    unread = db.one("SELECT COUNT(*) n FROM notifications WHERE member_id=? AND read_at IS NULL", (u["member_id"] or -1,))["n"]
    judging = db.one("SELECT COUNT(*) n FROM post_judges j JOIN posts p ON p.id=j.post_id WHERE j.user_id=? AND p.deleted=0", (u["id"],))["n"]
    return {"user": u, "member": m, "unread": unread, "info": public_info(), "settings": settings_for(u), "judging": judging}


def settings_for(u):
    s = db.settings_all()
    s["membership_types"] = json.loads(s["membership_types"])
    s["wards"] = json.loads(s["wards"])
    s["channels"] = comms.configured()
    s["heads"] = {"receipt": i18n.RECEIPT_HEADS, "payment": i18n.PAYMENT_HEADS, "labels": i18n.HEAD_LABELS}
    s["roles"] = auth.ROLE_LABELS
    s["teams"] = json.loads(s["teams"])
    s["doc_categories"] = DOC_CATEGORIES
    s["gateway"] = payments.configured() or bool(payments._create_order_override)
    s["asset_categories"] = facilities.ASSET_CATEGORIES
    s["perms"] = {k: sorted(v) for k, v in auth.PERMS.items()}
    return s


@app.post("/api/auth/password")
async def change_password(request: Request, user=Depends(current_user)):
    body = await request.json()
    u = db.one("SELECT pw_hash FROM users WHERE id=?", (user["id"],))
    if not auth.check_pw(body.get("current") or "", u["pw_hash"]):
        raise HTTPException(400, "current password is wrong")
    new = body.get("new") or ""
    if len(new) < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    with db.tx() as c:
        c.execute("UPDATE users SET pw_hash=? WHERE id=?", (auth.hash_pw(new), user["id"]))
        c.execute("DELETE FROM sessions WHERE user_id=? AND token<>?", (user["id"], request.cookies.get(auth.COOKIE, "")))
    return {"ok": True}


@app.post("/api/auth/lang")
async def set_lang(request: Request, user=Depends(current_user)):
    lang = (await request.json()).get("lang")
    if lang not in ("en", "ml"):
        raise HTTPException(400, "lang")
    with db.tx() as c:
        c.execute("UPDATE users SET lang=? WHERE id=?", (lang, user["id"]))
        if user["member_id"]:
            c.execute("UPDATE members SET lang=? WHERE id=?", (lang, user["member_id"]))
    return {"ok": True}


@app.post("/api/auth/forgot")
async def forgot(request: Request):
    """Send a one-time code by WhatsApp / SMS / e-mail to the member's registered contact; answers the same whether
    or not the login exists, so it cannot be used to probe for members."""
    body = await request.json()
    login_ = auth.norm_login(body.get("login"))
    u = db.one("SELECT u.*, m.phone, m.whatsapp, m.email, m.lang AS mlang FROM users u LEFT JOIN members m ON m.id=u.member_id WHERE u.login=? AND u.active=1", (login_,))
    if not u and login_ and "@" not in login_:
        m = db.one("SELECT id FROM members WHERE substr(replace(replace(phone,' ',''),'-',''), -10)=? AND status='active'", (login_,))
        if m:
            u = db.one("SELECT u.*, m.phone, m.whatsapp, m.email, m.lang AS mlang FROM users u JOIN members m ON m.id=u.member_id WHERE u.member_id=? AND u.active=1", (m["id"],))
    ticket = secrets.token_urlsafe(24)
    if u:
        code = f"{secrets.randbelow(900000) + 100000}"
        phone = u.get("whatsapp") or u.get("phone") or (login_ if "@" not in login_ else "")
        email = u.get("email") or (login_ if "@" in login_ else "")
        with db.tx() as c:
            c.execute("DELETE FROM login_codes WHERE user_id=? OR expires<?", (u["id"], time.time()))
            c.execute("INSERT INTO login_codes(ticket_hash, user_id, code_hash, expires) VALUES(?,?,?,?)",
                      (auth.hash_token(ticket), u["id"], auth.hash_token(code), time.time() + 600))
            comms.notify_contact(c, phone, email, "password_reset", {"code": code}, u.get("mlang") or u.get("lang") or "ml", ("whatsapp", "sms", "email"), ref_kind="user", ref_id=u["id"])
            db.audit(c, u["id"], "password.code")
    else:
        time.sleep(0.3)
    return {"ok": True, "ticket": ticket, "channels": [k for k, v in comms.configured().items() if v and k != "app"]}


@app.post("/api/auth/reset")
async def reset(request: Request, resp: Response):
    body = await request.json()
    ticket, code, new = body.get("ticket") or "", (body.get("code") or "").strip(), body.get("password") or ""
    row = db.one("SELECT * FROM login_codes WHERE ticket_hash=?", (auth.hash_token(ticket),))
    if not row or row["expires"] < time.time():
        raise HTTPException(400, "code expired - request a new one")
    if row["attempts"] >= 5:
        raise HTTPException(429, "too many attempts - request a new code")
    if not secrets.compare_digest(auth.hash_token(code), row["code_hash"]):
        with db.tx() as c:
            c.execute("UPDATE login_codes SET attempts=attempts+1 WHERE ticket_hash=?", (row["ticket_hash"],))
        raise HTTPException(400, "wrong code")
    if len(new) < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    with db.tx() as c:
        c.execute("UPDATE users SET pw_hash=? WHERE id=?", (auth.hash_pw(new), row["user_id"]))
        c.execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
        c.execute("DELETE FROM login_codes WHERE ticket_hash=?", (row["ticket_hash"],))
        token = auth.create_session(c, row["user_id"])
        db.audit(c, row["user_id"], "password.reset")
    auth.set_cookie(resp, token)
    return {"ok": True}


@app.post("/api/public/photo")
def public_photo(file: UploadFile = File(...)):
    """An applicant's photo, before they have an account. Images only, 4 MB, stored with the member photos."""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "image only")
    rel, mime = save_upload(file, "members", max_mb=4)
    return {"path": rel}


@app.get("/api/scan/{code:path}")
def scan(code: str, user=Depends(current_user)):
    """Resolve the text in a membership-card QR (MEMBER:<no>|<name>) or a bare membership number to a member."""
    if not (can(user, "members.view") or can(user, "library.manage") or can(user, "posts.manage") or user.get("convenes")):
        raise HTTPException(403, "no")
    no = code.split("|")[0].replace("MEMBER:", "").strip()
    m = db.one("SELECT id, member_no, name_en, name_ml, status, photo, phone, blood_group FROM members WHERE member_no=?", (no,))
    if not m:
        raise HTTPException(404, "no member with that number")
    return m


@app.get("/api/push/key")
def push_key(user=Depends(current_user)):
    return {"key": push.public_key(), "subscribed": bool(db.one("SELECT 1 FROM push_subs WHERE user_id=?", (user["id"],)))}


@app.post("/api/push/subscribe")
async def push_subscribe(request: Request, user=Depends(current_user)):
    sub = await request.json()
    keys = sub.get("keys") or {}
    if not (sub.get("endpoint") and keys.get("p256dh") and keys.get("auth")):
        raise HTTPException(400, "subscription")
    with db.tx() as c:
        c.execute("INSERT INTO push_subs(user_id, member_id, endpoint, p256dh, auth, created) VALUES(?,?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id, member_id=excluded.member_id, p256dh=excluded.p256dh, auth=excluded.auth, failures=0",
                  (user["id"], user.get("member_id"), sub["endpoint"], keys["p256dh"], keys["auth"], time.time()))
    return {"ok": True}


@app.post("/api/push/unsubscribe")
async def push_unsubscribe(request: Request, user=Depends(current_user)):
    sub = await request.json()
    with db.tx() as c:
        if sub.get("endpoint"):
            c.execute("DELETE FROM push_subs WHERE endpoint=? AND user_id=?", (sub["endpoint"], user["id"]))
        else:
            c.execute("DELETE FROM push_subs WHERE user_id=?", (user["id"],))
    return {"ok": True}


# ---------- documents ----------
DOC_CATEGORIES = ["bylaws", "circular", "minutes", "report", "audit", "form", "certificate", "other"]


@app.get("/api/documents")
def list_documents(category: str = "", user=Depends(current_user)):
    rows = db.q("SELECT d.*, u.name AS by_name, c.name_en AS committee_en, c.name_ml AS committee_ml FROM documents d LEFT JOIN users u ON u.id=d.created_by LEFT JOIN committees c ON c.id=d.committee_id "
                "WHERE d.deleted=0 " + ("AND d.category=? " if category else "") + "ORDER BY d.category, d.year DESC, d.id DESC", (category,) if category else ())
    out = []
    for d in rows:
        if d["audience"] == "committee" and not (can(user, "posts.manage") or auth.committee_role(user, d["committee_id"] or 0)):
            continue
        if d["audience"] == "members" and not (user.get("member_id") or can(user, "posts.manage")):
            continue
        out.append(d)
    return out


@app.post("/api/documents")
async def save_document(request: Request, user=Depends(require("posts.manage"))):
    b = await request.json()
    row = {"title_en": b.get("title_en") or b.get("title_ml") or "", "title_ml": b.get("title_ml") or "", "category": b.get("category") if b.get("category") in DOC_CATEGORIES else "other",
           "audience": b.get("audience") if b.get("audience") in ("public", "members", "committee") else "members", "committee_id": b.get("committee_id") or None,
           "year": str(b.get("year") or ""), "note": b.get("note") or ""}
    if not row["title_en"]:
        raise HTTPException(400, "title")
    with db.tx() as c:
        if b.get("id"):
            db.update(c, "documents", b["id"], row); did = b["id"]
        else:
            if not b.get("path"):
                raise HTTPException(400, "file")
            row.update({"path": b["path"], "mime": b.get("mime") or "", "size": int(b.get("size") or 0), "created_by": user["id"], "created": time.time()})
            did = db.insert(c, "documents", row)
        db.audit(c, user["id"], "document.save", "document", did, row["title_en"])
    return {"ok": True, "id": did}


@app.delete("/api/documents/{did}")
def delete_document(did: int, user=Depends(require("posts.manage"))):
    with db.tx() as c:
        db.update(c, "documents", did, {"deleted": 1})
    return {"ok": True}


@app.get("/api/public/documents")
def public_documents():
    return db.q("SELECT id, title_en, title_ml, category, path, year FROM documents WHERE deleted=0 AND audience='public' ORDER BY category, year DESC")


# ---------- users (office bearers) ----------
@app.get("/api/users")
def list_users(user=Depends(require("users.manage"))):
    return db.q("SELECT u.id, u.login, u.name, u.role, u.active, u.member_id, u.lang, u.created, u.last_login, m.member_no "
                "FROM users u LEFT JOIN members m ON m.id=u.member_id ORDER BY u.role, u.name")


@app.post("/api/users")
async def upsert_user(request: Request, user=Depends(require("users.manage"))):
    b = await request.json()
    role = b.get("role", "member")
    if role not in auth.ROLES:
        raise HTTPException(400, "role")
    if role == "admin" and user["role"] != "admin":
        raise HTTPException(403, "only an administrator can grant admin")
    with db.tx() as c:
        if b.get("id"):
            row = {"role": role, "active": 1 if b.get("active", 1) else 0}
            if b.get("name"):
                row["name"] = b["name"]
            if b.get("password"):
                row["pw_hash"] = auth.hash_pw(b["password"])
            if b.get("login"):
                row["login"] = auth.norm_login(b["login"])
            db.update(c, "users", b["id"], row)
            if not row["active"]:
                c.execute("DELETE FROM sessions WHERE user_id=?", (b["id"],))
            uid = b["id"]
        else:
            login_ = auth.norm_login(b.get("login"))
            if not login_ or not b.get("password"):
                raise HTTPException(400, "login and password are required")
            if db.one("SELECT 1 FROM users WHERE login=?", (login_,)):
                raise HTTPException(409, "login already exists")
            uid = db.insert(c, "users", {"login": login_, "name": b.get("name") or login_, "role": role, "pw_hash": auth.hash_pw(b["password"]),
                                         "active": 1, "member_id": b.get("member_id"), "created": time.time(), "lang": b.get("lang") or "en"})
        db.audit(c, user["id"], "user.save", "user", uid, json.dumps({"role": role}))
    return {"ok": True, "id": uid}


# ---------- settings ----------
@app.get("/api/settings")
def get_settings(user=Depends(require("settings.manage"))):
    return settings_for(user)


@app.post("/api/settings")
async def save_settings(request: Request, user=Depends(require("settings.manage"))):
    b = await request.json()
    with db.tx() as c:
        for k, v in b.items():
            if k not in db.DEFAULT_SETTINGS:
                continue
            if k in ("membership_types", "wards", "teams"):
                v = json.dumps(v if isinstance(v, list) else json.loads(v or "[]"))
            db.set_setting(c, k, v)
        db.audit(c, user["id"], "settings.save", detail=",".join(b.keys()))
    return {"ok": True}


# ---------- uploads ----------
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


def save_upload(upload: UploadFile, folder, max_mb=8):
    mime = upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or ""
    if mime not in ALLOWED:
        raise HTTPException(400, "only JPEG, PNG, WebP or PDF")
    data = upload.file.read(max_mb * 1024 * 1024 + 1)
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(400, f"file over {max_mb} MB")
    rel = os.path.join(folder, dt.date.today().strftime("%Y%m"), secrets.token_hex(8) + ALLOWED[mime])
    path = os.path.join(db.UPLOAD_DIR, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if mime.startswith("image/"):
        # every image is decoded and re-encoded: whatever was uploaded, what we store is a plain JPEG / PNG / WebP
        try:
            from PIL import Image, ImageOps
            import io
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
            im.thumbnail((1600, 1600))
            if ALLOWED[mime] == ".png":
                im.save(path, optimize=True)
            else:
                im.convert("RGB").save(path, quality=82, optimize=True)
        except Exception:
            raise HTTPException(400, "that is not a readable image")
    else:
        if not data.startswith(b"%PDF"):
            raise HTTPException(400, "that is not a PDF")
        with open(path, "wb") as f:
            f.write(data)
    return rel.replace(os.sep, "/"), mime


@app.post("/api/upload/{folder}")
def upload(folder: str, file: UploadFile = File(...), user=Depends(current_user)):
    if folder not in ("posts", "members", "books", "docs"):
        raise HTTPException(400, "folder")
    if folder in ("posts", "books", "docs") and not (can(user, "posts.manage") or can(user, "library.manage")):
        raise HTTPException(403, "no")
    rel, mime = save_upload(file, folder, max_mb=20 if folder == "docs" else 8)
    return {"path": rel, "mime": mime, "url": f"/uploads/{rel}", "size": os.path.getsize(os.path.join(db.UPLOAD_DIR, rel))}


@app.get("/uploads/{path:path}")
def serve_upload(path: str, request: Request):
    if ".." in path or path.startswith("/"):
        raise HTTPException(404)
    if not path.startswith("posts/") and not auth.user_from_request(request):
        public_doc = path.startswith("docs/") and db.one("SELECT 1 FROM documents WHERE path=? AND audience='public' AND deleted=0", (path,))
        # office bearers' photos appear on the public website; every other member photo needs a sign-in
        office_photo = path.startswith("members/") and db.one("SELECT 1 FROM members m JOIN committee_members cm ON cm.member_id=m.id JOIN committees c ON c.id=cm.committee_id "
                                                              "WHERE m.photo=? AND m.status='active' AND cm.active=1 AND c.kind='executive'", (path,))
        if not (public_doc or office_photo):
            raise HTTPException(401, "sign in")
    full = os.path.join(db.UPLOAD_DIR, path)
    if not os.path.isfile(full):
        raise HTTPException(404)
    return FileResponse(full, headers={"Cache-Control": "private, max-age=86400"})


# ---------- notifications (in-app) ----------
@app.get("/api/notifications")
def my_notifications(user=Depends(current_user)):
    if not user["member_id"]:
        return []
    return db.q("SELECT * FROM notifications WHERE member_id=? ORDER BY id DESC LIMIT 100", (user["member_id"],))


@app.post("/api/notifications/read")
async def read_notifications(request: Request, user=Depends(current_user)):
    ids = (await request.json()).get("ids") or []
    with db.tx() as c:
        if ids:
            marks = ",".join("?" for _ in ids)
            c.execute(f"UPDATE notifications SET read_at=? WHERE member_id=? AND id IN ({marks})", [time.time(), user["member_id"]] + list(ids))
        else:
            c.execute("UPDATE notifications SET read_at=? WHERE member_id=? AND read_at IS NULL", (time.time(), user["member_id"]))
    return {"ok": True}


# ---------- outbox / broadcasts ----------
@app.get("/api/outbox")
def outbox(status: str = "", limit: int = 200, user=Depends(require("outbox.view"))):
    where, args = "", []
    if status:
        where, args = "WHERE o.status=?", [status]
    rows = db.q(f"SELECT o.*, m.name_en, m.name_ml FROM outbox o LEFT JOIN members m ON m.id=o.member_id {where} ORDER BY o.id DESC LIMIT ?", args + [limit])
    counts = {r["status"]: r["n"] for r in db.q("SELECT status, COUNT(*) n FROM outbox GROUP BY status")}
    return {"rows": rows, "counts": counts, "channels": comms.configured()}


@app.post("/api/outbox/retry")
async def outbox_retry(request: Request, user=Depends(require("outbox.view"))):
    ids = (await request.json()).get("ids")
    with db.tx() as c:
        comms.retry_failed(c, ids)
    return {"ok": True}


@app.post("/api/outbox/process")
def outbox_process(user=Depends(require("outbox.view"))):
    return {"processed": comms.process_outbox()}


@app.post("/api/broadcast/preview")
async def broadcast_preview(request: Request, user=Depends(require("broadcast.send"))):
    b = await request.json()
    ids = members.audience_ids(b.get("audience") or {})
    return {"recipients": len(ids)}


@app.post("/api/broadcast")
async def broadcast(request: Request, user=Depends(require("broadcast.send"))):
    b = await request.json()
    channels = [ch for ch in (b.get("channels") or []) if ch in comms.CHANNELS]
    if not channels:
        raise HTTPException(400, "pick at least one channel")
    body_en, body_ml = (b.get("body_en") or "").strip(), (b.get("body_ml") or "").strip()
    if not (body_en or body_ml):
        raise HTTPException(400, "message is empty")
    ids = members.audience_ids(b.get("audience") or {})
    batch = comms.new_batch()
    send_at = None
    if b.get("send_at"):
        try:
            send_at = dt.datetime.fromisoformat(b["send_at"]).timestamp()
        except ValueError:
            raise HTTPException(400, "send_at")
    with db.tx() as c:
        n = comms.notify_members(c, ids, "broadcast", {"subject": b.get("subject") or db.setting("club_short")}, channels, ref_kind="broadcast",
                                 batch_id=batch, created_by=user["id"], not_before=send_at,
                                 per_member=lambda m: {"body": (body_ml if (m.get("lang") == "ml" and body_ml) else (body_en or body_ml))})
        bid = db.insert(c, "broadcasts", {"created": time.time(), "created_by": user["id"], "audience": json.dumps(b.get("audience") or {}),
                                          "channels": ",".join(channels), "subject": b.get("subject") or "", "body_en": body_en, "body_ml": body_ml,
                                          "recipients": len(ids), "batch_id": batch, "send_at": send_at})
        db.audit(c, user["id"], "broadcast", "broadcast", bid, f"{len(ids)} members, {n} messages")
    return {"ok": True, "id": bid, "recipients": len(ids), "queued": n}


@app.post("/api/broadcasts/{bid}/cancel")
def cancel_broadcast(bid: int, user=Depends(require("broadcast.send"))):
    b = db.one("SELECT * FROM broadcasts WHERE id=?", (bid,))
    if not b:
        raise HTTPException(404)
    with db.tx() as c:
        n = c.execute("DELETE FROM outbox WHERE batch_id=? AND status='pending'", (b["batch_id"],)).rowcount
        db.audit(c, user["id"], "broadcast.cancel", "broadcast", bid, f"{n} removed")
    return {"ok": True, "removed": n}


@app.get("/api/broadcasts")
def broadcasts(user=Depends(require("broadcast.send"))):
    rows = db.q("SELECT b.*, u.name AS by_name FROM broadcasts b LEFT JOIN users u ON u.id=b.created_by ORDER BY b.id DESC LIMIT 100")
    for r in rows:
        st = {x["status"]: x["n"] for x in db.q("SELECT status, COUNT(*) n FROM outbox WHERE batch_id=? GROUP BY status", (r["batch_id"],))}
        r["delivery"] = st
    return rows


# ---------- audit ----------
@app.get("/api/audit")
def audit_log(limit: int = 300, user=Depends(require("settings.manage"))):
    return db.q("SELECT a.*, u.name AS by_name FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT ?", (limit,))


# ---------- dashboard ----------
@app.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    return reports.dashboard(user)


# ---------- backups ----------
@app.get("/api/backup")
def backup_status(user=Depends(require("settings.manage"))):
    return backup.status()


@app.post("/api/backup/run")
def backup_run(user=Depends(require("settings.manage"))):
    r = backup.run("manual")
    with db.tx() as c:
        db.audit(c, user["id"], "backup.run", detail=r.get("error") or ",".join(r.get("files") or []))
    return r


# ---------- daily jobs (also callable by hand) ----------
@app.post("/api/jobs/daily")
def run_daily(user=Depends(require("settings.manage"))):
    return scheduler.run_daily(force=True)


# ---------- routers ----------
app.include_router(members.router)
app.include_router(news.router)
app.include_router(committees.router)
app.include_router(library.router)
app.include_router(finance.router)
app.include_router(reports.router)
app.include_router(facilities.router)
app.include_router(payments.router)
app.include_router(polls.router)
app.include_router(site.router)
app.include_router(helpdoc.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
