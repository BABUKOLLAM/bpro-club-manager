"""Multi-club edition: one installation serves many clubs. Each club (tenant) has its own SQLite database, uploads
and backups under <data>/tenants/<slug>/, and is chosen by the request's host name. The club that existed before
this feature is the implicit 'default' tenant living directly in <data>, so an existing installation keeps working.

Registry: <data>/tenants.json  {"strict": false, "tenants": {"slug": {"name": ..., "domains": [...], "active": true}}}
Platform administration (/_platform) needs CLUB_MASTER_KEY in the environment.
"""
import contextlib
import contextvars
import json
import os
import re
import threading
import time

current = contextvars.ContextVar("club_tenant", default="default")
_lock = threading.Lock()
_cache = {"mtime": None, "data": None}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")
DEFAULT_PRODUCT = "ClubPro"
DEFAULT_POWERED_BY = "Powered by Team Bpro"


def data_root():
    from . import db
    return db.DATA_DIR


def registry_path():
    return os.path.join(data_root(), "tenants.json")


def registry():
    p = registry_path()
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {"strict": False, "tenants": {}}
    with _lock:
        if _cache["mtime"] != mt:
            with open(p) as f:
                _cache["data"] = json.load(f)
            _cache["mtime"] = mt
        return _cache["data"]


def save_registry(reg):
    os.makedirs(data_root(), exist_ok=True)
    tmp = registry_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(reg, f, indent=1, ensure_ascii=False)
    os.replace(tmp, registry_path())
    with _lock:
        _cache["mtime"] = None


def tenants():
    return registry().get("tenants", {})


def all_slugs():
    return ["default"] + [s for s, t in tenants().items() if t.get("active", True)]


def is_multi():
    return bool(tenants())


def tenant_dir(slug):
    return data_root() if slug == "default" else os.path.join(data_root(), "tenants", slug)


def resolve(host):
    """Host header -> slug, or None when the host is unknown and the registry is strict."""
    host = (host or "").split(":")[0].strip().lower()
    reg = registry()
    for slug, t in reg.get("tenants", {}).items():
        if t.get("active", True) and host in [d.lower() for d in t.get("domains", [])]:
            return slug
    base = (os.environ.get("CLUB_BASE_DOMAIN") or "").lower()
    if base and host.endswith("." + base):
        slug = host[: -len(base) - 1]
        if slug in reg.get("tenants", {}) and reg["tenants"][slug].get("active", True):
            return slug
    if reg.get("default_domains") and host not in [d.lower() for d in reg["default_domains"]] and reg.get("strict"):
        return None
    return None if reg.get("strict") and reg.get("tenants") and host not in [d.lower() for d in reg.get("default_domains", [])] else "default"


@contextlib.contextmanager
def use(slug):
    token = current.set(slug)
    try:
        yield
    finally:
        current.reset(token)


def base_url():
    """Public address of the current club, for the links inside messages."""
    slug = current.get()
    t = tenants().get(slug) if slug != "default" else None
    if t and t.get("domains"):
        return "https://" + t["domains"][0]
    reg = registry()
    if slug == "default" and reg.get("default_domains"):
        return "https://" + reg["default_domains"][0]
    return os.environ.get("CLUB_PUBLIC_URL", "").rstrip("/")


def create(slug, name_en, name_ml="", domains=(), admin_login="", admin_password="", short=""):
    """Register a club, create its database with the first administrator and the default committees."""
    from . import auth, committees, db
    slug = (slug or "").strip().lower()
    if not SLUG_RE.match(slug) or slug in ("default", "tenants", "admin", "api", "static", "uploads"):
        raise ValueError("slug: 2-31 lowercase letters, digits or hyphens")
    reg = registry()
    reg.setdefault("tenants", {})
    if slug in reg["tenants"]:
        raise ValueError("that slug already exists")
    domains = [d.strip().lower() for d in domains if d and d.strip()]
    for s, t in reg["tenants"].items():
        for d in domains:
            if d in [x.lower() for x in t.get("domains", [])]:
                raise ValueError(f"domain {d} already belongs to {s}")
    if not (admin_login and admin_password and len(admin_password) >= 8):
        raise ValueError("an administrator login and a password of 8+ characters are needed")
    if os.path.exists(os.path.join(tenant_dir(slug), "club.db")):
        raise ValueError("a database for that slug already exists on disk; remove or rename it first")
    reg["tenants"][slug] = {"name": name_en, "domains": domains, "active": True, "created": time.time()}
    os.makedirs(os.path.join(tenant_dir(slug), "uploads"), exist_ok=True)
    save_registry(reg)
    try:
        db.forget(slug)
        with use(slug):
            db.init()
            with db.tx() as c:
                db.set_setting(c, "club_name_en", name_en)
                db.set_setting(c, "club_name_ml", name_ml or name_en)
                db.set_setting(c, "footer_credit", reg.get("powered_by") or DEFAULT_POWERED_BY)
                if short:
                    db.set_setting(c, "club_short", short)
                    db.set_setting(c, "member_no_prefix", short)
                db.insert(c, "users", {"login": auth.norm_login(admin_login), "name": "Administrator", "role": "admin", "pw_hash": auth.hash_pw(admin_password), "active": 1, "created": time.time(), "lang": "en"})
                committees.seed_defaults(c)
    except Exception:
        reg = registry()
        reg.get("tenants", {}).pop(slug, None)
        save_registry(reg)
        raise
    return reg["tenants"][slug]


def update(slug, domains=None, active=None, name=None):
    reg = registry()
    t = reg.get("tenants", {}).get(slug)
    if not t:
        raise ValueError("unknown club")
    if domains is not None:
        t["domains"] = [d.strip().lower() for d in domains if d and d.strip()]
    if active is not None:
        t["active"] = bool(active)
    if name:
        t["name"] = name
    save_registry(reg)
    return t


def stats(slug):
    from . import db
    with use(slug):
        db.init()
        s = db.settings_all()
        return {"slug": slug, "club_name_en": s["club_name_en"], "club_short": s["club_short"], "members": db.one("SELECT COUNT(*) n FROM members WHERE status='active'")["n"],
                "applications": db.one("SELECT COUNT(*) n FROM members WHERE status='applied'")["n"], "users": db.one("SELECT COUNT(*) n FROM users WHERE active=1")["n"],
                "last_backup": db.setting("last_backup", "") or None}
