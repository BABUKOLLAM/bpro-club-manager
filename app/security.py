"""Edge protections: a small in-memory rate limiter for the public endpoints and security headers on every response.

The limiter is per process (one worker runs the app) and keyed by client IP and endpoint: enough to stop password
guessing and application spam, without any extra service."""
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# path -> (requests, window seconds)
LIMITS = {
    "/api/auth/login": (10, 60),
    "/api/auth/forgot": (5, 600),
    "/api/auth/reset": (10, 600),
    "/api/public/apply": (5, 3600),
    "/api/public/photo": (10, 3600),
    "/api/finance/claims": (20, 3600),
    "/api/payments/order": (30, 3600),
}
_hits = {}
_lock = threading.Lock()


def allow(key, limit, window):
    now = time.time()
    with _lock:
        q = [t for t in _hits.get(key, []) if t > now - window]
        if len(q) >= limit:
            _hits[key] = q
            return False
        q.append(now)
        _hits[key] = q
        if len(_hits) > 50000:          # never let the table grow without bound
            _hits.clear()
        return True


def reset():
    with _lock:
        _hits.clear()


CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://checkout.razorpay.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
       "font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob: https:; connect-src 'self' https://api.razorpay.com https://lumberjack.razorpay.com https://lumberjack-cx.razorpay.com; "
       "frame-src https://api.razorpay.com https://checkout.razorpay.com; media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'")


class EdgeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if request.method == "POST" and path in LIMITS:
            limit, window = LIMITS[path]
            ip = request.client.host if request.client else "?"
            if not allow(f"{ip}:{path}", limit, window):
                return JSONResponse({"error": "too many attempts - please wait a while"}, status_code=429, headers={"Retry-After": str(window)})
        resp = await call_next(request)
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "SAMEORIGIN")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=(), payment=(self \"https://api.razorpay.com\" \"https://checkout.razorpay.com\")")
        if "text/html" in (h.get("content-type") or ""):
            h.setdefault("Content-Security-Policy", CSP)
        if path.startswith("/uploads/"):
            h["Content-Disposition"] = "inline"
            h["X-Content-Type-Options"] = "nosniff"
        return resp
