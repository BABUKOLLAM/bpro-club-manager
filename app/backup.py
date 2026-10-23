"""Backups: a consistent SQLite copy plus the uploads folder, kept locally with rotation and, when a Google service
account is configured, pushed to a Drive folder. Runs nightly from the scheduler and on demand from Settings.

Environment: CLUB_GDRIVE_SA_JSON (path to the service-account key file, or the JSON itself), CLUB_GDRIVE_FOLDER
(the folder ID shared with the service account's e-mail), CLUB_BACKUP_DIR (default <data>/backups).
"""
import base64
import datetime as dt
import json
import os
import sqlite3
import tarfile
import time
import urllib.parse
import urllib.request

from . import db

_upload_override = None       # tests: fn(name, path) -> file_id
_list_override = None         # tests: fn() -> [{id, name, createdTime}]
_delete_override = None


def set_drive_fake(upload=None, list_=None, delete=None):
    global _upload_override, _list_override, _delete_override
    _upload_override, _list_override, _delete_override = upload, list_, delete


def backup_dir():
    base = os.environ.get("CLUB_BACKUP_DIR") or os.path.join(db.DATA_DIR, "backups")
    return base if db.slug() == "default" else os.path.join(base, db.slug())


def drive_configured():
    return bool(os.environ.get("CLUB_GDRIVE_SA_JSON") and os.environ.get("CLUB_GDRIVE_FOLDER")) or bool(_upload_override)


def make_local():
    """Write club-YYYYmmdd-HHMM.db (sqlite online backup) and uploads-....tgz. Returns their paths."""
    out = backup_dir()
    os.makedirs(out, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dbp = os.path.join(out, f"club-{stamp}.db")
    src = db.conn()
    dst = sqlite3.connect(dbp)
    with dst:
        src.backup(dst)
    dst.close()
    tgz = os.path.join(out, f"uploads-{stamp}.tgz")
    with tarfile.open(tgz, "w:gz") as tar:
        if os.path.isdir(db.upload_dir()):
            tar.add(db.upload_dir(), arcname="uploads")
    rotate_local(int(db.setting("backup_keep") or 14))
    return [dbp, tgz]


def rotate_local(keep):
    out = backup_dir()
    for prefix in ("club-", "uploads-"):
        files = sorted(f for f in os.listdir(out) if f.startswith(prefix))
        for f in files[:-keep] if keep > 0 else []:
            try:
                os.remove(os.path.join(out, f))
            except OSError:
                pass


# ---------- Google Drive with a service account ----------
def _sa():
    raw = os.environ["CLUB_GDRIVE_SA_JSON"]
    if raw.strip().startswith("{"):
        return json.loads(raw)
    with open(raw) as f:
        return json.load(f)


def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def access_token():
    """OAuth2 JWT bearer flow for the service account (RS256 with cryptography)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    sa = _sa()
    now = int(time.time())
    header = _b64u(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64u(json.dumps({"iss": sa["client_email"], "scope": "https://www.googleapis.com/auth/drive.file", "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
    jwt = f"{header}.{claims}.{_b64u(sig)}"
    data = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": jwt}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST"), timeout=20) as r:
        return json.loads(r.read().decode())["access_token"]


def drive_upload(name, path):
    if _upload_override:
        return _upload_override(name, path)
    token = access_token()
    folder = os.environ["CLUB_GDRIVE_FOLDER"]
    meta = json.dumps({"name": name, "parents": [folder]}).encode()
    boundary = "clubbackup" + str(int(time.time()))
    with open(path, "rb") as f:
        content = f.read()
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + meta + f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + content + f"\r\n--{boundary}--".encode())
    req = urllib.request.Request("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true", data=body,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/related; boundary={boundary}"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())["id"]


def drive_list():
    if _list_override:
        return _list_override()
    token = access_token()
    folder = os.environ["CLUB_GDRIVE_FOLDER"]
    q = urllib.parse.quote(f"'{folder}' in parents and trashed=false")
    req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files?q={q}&fields=files(id,name,createdTime)&pageSize=200&supportsAllDrives=true&includeItemsFromAllDrives=true",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()).get("files", [])


def drive_delete(file_id):
    if _delete_override:
        return _delete_override(file_id)
    token = access_token()
    req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{file_id}?supportsAllDrives=true", headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    with urllib.request.urlopen(req, timeout=30):
        return True


def run(reason="manual"):
    """Local backup, then Drive upload with retention. The outcome is kept in settings for the Settings screen."""
    started = time.time()
    result = {"at": started, "reason": reason, "files": [], "drive": None, "error": ""}
    prefix = "" if db.slug() == "default" else db.slug() + "-"
    try:
        paths = make_local()
        result["files"] = [os.path.basename(p) for p in paths]
        if drive_configured():
            ids = [drive_upload(prefix + os.path.basename(p), p) for p in paths]
            keep = int(db.setting("backup_keep") or 14)
            removed = 0
            for kind in ("club-", "uploads-"):
                ours = sorted((f for f in drive_list() if (f.get("name") or "").startswith(prefix + kind)), key=lambda f: f.get("name"))
                for f in ours[:-keep] if keep > 0 else []:
                    try:
                        drive_delete(f["id"]); removed += 1
                    except Exception:  # noqa: BLE001
                        pass
            result["drive"] = {"uploaded": ids, "removed": removed}
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"[:300]
    result["seconds"] = round(time.time() - started, 1)
    with db.tx() as c:
        db.set_setting(c, "last_backup", json.dumps(result))
    return result


def status():
    try:
        last = json.loads(db.setting("last_backup", "") or "null")
    except Exception:  # noqa: BLE001
        last = None
    out = backup_dir()
    local = sorted(os.listdir(out))[-10:] if os.path.isdir(out) else []
    return {"last": last, "drive_configured": drive_configured(), "local_dir": out, "local_files": local, "keep": int(db.setting("backup_keep") or 14)}
