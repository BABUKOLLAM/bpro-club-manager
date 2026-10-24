"""Sign-in, sessions and the permission table. `PERMS` is the single source of truth: every endpoint checks a
capability here, and the screens show only what the signed-in role holds."""
import hashlib
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request, Response

from . import db

ROLES = ["admin", "president", "secretary", "treasurer", "librarian", "member"]
ROLE_LABELS = {
    "admin": {"en": "Administrator", "ml": "അഡ്മിനിസ്ട്രേറ്റർ"},
    "president": {"en": "President", "ml": "പ്രസിഡന്റ്"},
    "secretary": {"en": "Secretary", "ml": "സെക്രട്ടറി"},
    "treasurer": {"en": "Treasurer", "ml": "ട്രഷറർ"},
    "librarian": {"en": "Librarian", "ml": "ലൈബ്രേറിയൻ"},
    "member": {"en": "Member", "ml": "അംഗം"},
}
PERMS = {
    "members.view":       {"admin", "president", "secretary", "treasurer", "librarian"},
    "members.manage":     {"admin", "president", "secretary"},
    "posts.manage":       {"admin", "president", "secretary"},
    "broadcast.send":     {"admin", "president", "secretary"},
    "committees.manage":  {"admin", "president", "secretary"},
    "meetings.manage":    {"admin", "president", "secretary"},
    "library.manage":     {"admin", "secretary", "librarian"},
    "finance.view":       {"admin", "president", "secretary", "treasurer"},
    "finance.manage":     {"admin", "secretary", "treasurer"},
    "finance.close":      {"admin", "treasurer"},
    "reports.view":       {"admin", "president", "secretary", "treasurer", "librarian"},
    "outbox.view":        {"admin", "president", "secretary"},
    "users.manage":       {"admin", "secretary"},
    "settings.manage":    {"admin"},
}
SESSION_DAYS = 30
COOKIE = "club_session"


def hash_pw(pw, salt=None):
    salt = salt or os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def hash_token(s):
    return hashlib.sha256(s.encode()).hexdigest()


def check_pw(pw, stored):
    try:
        _, salt, h = stored.split("$")
        return secrets.compare_digest(hash_pw(pw, bytes.fromhex(salt)).split("$")[2], h)
    except Exception:
        return False


def can(user, perm):
    return bool(user) and user.get("role") in PERMS.get(perm, set())


def perms_of(role):
    return sorted(p for p, roles in PERMS.items() if role in roles)


def norm_login(s):
    s = (s or "").strip().lower()
    digits = "".join(ch for ch in s if ch.isdigit())
    if "@" not in s and len(digits) >= 10:
        return digits[-10:]           # phone numbers are stored as the last ten digits
    return s


def create_session(c, user_id):
    token = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessions(token, user_id, expires, last_seen) VALUES(?,?,?,?)", (token, user_id, time.time() + SESSION_DAYS * 86400, time.time()))
    c.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), user_id))
    return token


def set_cookie(resp: Response, token):
    resp.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax", secure=not os.environ.get("CLUB_DEV"), path="/")


def clear_cookie(resp: Response):
    resp.delete_cookie(COOKIE, path="/")


def user_from_request(request: Request):
    token = request.cookies.get(COOKIE) or request.headers.get("X-Club-Token", "")
    if not token:
        return None
    s = db.one("SELECT user_id, expires FROM sessions WHERE token=?", (token,))
    if not s or s["expires"] < time.time():
        return None
    u = db.one("SELECT u.*, m.member_no, m.status AS member_status FROM users u LEFT JOIN members m ON m.id=u.member_id WHERE u.id=? AND u.active=1", (s["user_id"],))
    if not u:
        return None
    u.pop("pw_hash", None)
    u["perms"] = perms_of(u["role"])
    u["committees"] = [r["committee_id"] for r in db.q("SELECT committee_id FROM committee_members WHERE member_id=? AND active=1", (u["member_id"],))] if u["member_id"] else []
    u["convenes"] = [r["committee_id"] for r in db.q("SELECT committee_id FROM committee_members WHERE member_id=? AND active=1 AND role IN ('convener','secretary','chair')", (u["member_id"],))] if u["member_id"] else []
    return u


def current_user(request: Request):
    u = user_from_request(request)
    if not u:
        raise HTTPException(401, "sign in")
    # state-changing requests must carry the app header: a plain form post from another site cannot add it
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("X-Club") != "1":
        raise HTTPException(403, "missing X-Club header")
    return u


def require(perm):
    def dep(user=Depends(current_user)):
        if not can(user, perm):
            raise HTTPException(403, f"needs {perm}")
        return user
    return dep


def committee_role(user, committee_id):
    """'manage' for officers and conveners, 'member' for committee members, '' otherwise."""
    if can(user, "meetings.manage") or committee_id in user.get("convenes", []):
        return "manage"
    if committee_id in user.get("committees", []):
        return "member"
    c = db.one("SELECT kind FROM committees WHERE id=?", (committee_id,))
    if c and c["kind"] == "general" and user.get("member_id"):
        return "member"      # the general body is every member
    return ""
