"""Web Push without a push library: VAPID (RFC 8292) signing and the aes128gcm content encoding (RFC 8291), built on
`cryptography`. Keys are generated once and kept in settings; the browser subscribes through /api/push/subscribe."""
import base64
import json
import os
import struct
import time
import urllib.request
import urllib.error

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from . import db


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _keys():
    """(private_key, public_key_bytes_uncompressed). Generated on first use and stored in settings."""
    pem = db.setting("vapid_private", "")
    if not pem:
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        with db.tx() as c:
            db.set_setting(c, "vapid_private", pem)
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return key, pub


def public_key():
    return b64u(_keys()[1])


def vapid_headers(endpoint):
    key, pub = _keys()
    from urllib.parse import urlsplit
    u = urlsplit(endpoint)
    aud = f"{u.scheme}://{u.netloc}"
    header = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}).encode())
    claims = b64u(json.dumps({"aud": aud, "exp": int(time.time()) + 12 * 3600, "sub": "mailto:" + (db.setting("club_email") or os.environ.get("CLUB_SMTP_FROM") or "admin@example.org")}).encode())
    signing = f"{header}.{claims}".encode()
    der = key.sign(signing, ec.ECDSA(hashes.SHA256()))
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    r, s_ = decode_dss_signature(der)
    jwt = f"{header}.{claims}.{b64u(r.to_bytes(32, 'big') + s_.to_bytes(32, 'big'))}"
    return {"Authorization": f"vapid t={jwt}, k={b64u(pub)}"}


def encrypt(payload: bytes, p256dh: str, auth: str):
    """aes128gcm content encoding for one message. Returns the body to POST."""
    ua_pub = b64u_dec(p256dh)
    auth_secret = b64u_dec(auth)
    local = ec.generate_private_key(ec.SECP256R1())
    local_pub = local.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = local.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = HKDF(hashes.SHA256(), 32, auth_secret, b"WebPush: info\x00" + ua_pub + local_pub).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\x00").derive(ikm)
    record = payload + b"\x02"                      # last-record delimiter
    cipher = AESGCM(cek).encrypt(nonce, record, None)
    header = salt + struct.pack("!I", 4096) + bytes([len(local_pub)]) + local_pub
    return header + cipher


def decrypt_for_tests(body: bytes, ua_private, auth: str):
    """The browser's side, used by the tests to prove the round trip."""
    salt, rs, idlen = body[:16], body[16:20], body[20]
    local_pub = body[21:21 + idlen]
    cipher = body[21 + idlen:]
    ua_pub = ua_private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = ua_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), local_pub))
    ikm = HKDF(hashes.SHA256(), 32, b64u_dec(auth), b"WebPush: info\x00" + ua_pub + local_pub).derive(shared)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\x00").derive(ikm)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\x00").derive(ikm)
    return AESGCM(cek).decrypt(nonce, cipher, None).rstrip(b"\x00")[:-1]


def send(sub, title, body, link=""):
    """POST one notification to a subscription. Returns (ok, status_or_error)."""
    payload = json.dumps({"title": title, "body": body, "link": link}).encode()
    data = encrypt(payload, sub["p256dh"], sub["auth"])
    headers = {"Content-Type": "application/octet-stream", "Content-Encoding": "aes128gcm", "TTL": "86400", "Urgency": "normal"}
    headers.update(vapid_headers(sub["endpoint"]))
    req = urllib.request.Request(sub["endpoint"], data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return True, str(r.status)
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"[:200]
