"""White label: every club carries its own logo, colours and app name. The palette is derived from two colours the
club picks (primary and accent) so that the app, the public website, the handbook, printed pages and the membership
card all follow the club's identity, in light and dark mode, without the club having to think about shades.

Settings: brand_logo (upload path), brand_primary, brand_accent (hex), brand_app_name (title of the installed app).
Generated files live under <uploads>/brand/ (icon-192.png, icon-512.png, apple-touch-icon.png).
"""
import io
import os
import re

from . import db

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_PRIMARY = "#0F4C45"
DEFAULT_ACCENT = "#C9542A"
ICON_SIZES = (192, 512, 180)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(a, b, t):
    """t = 0 -> a, t = 1 -> b."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def lighten(h, t):
    return mix(h, "#FFFFFF", t)


def darken(h, t):
    return mix(h, "#000000", t)


def luminance(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ink_on(h):
    """White or near-black text, whichever reads better on the colour."""
    return "#FFFFFF" if luminance(h) < 0.4 else "#1D2A28"


def valid_hex(v, default):
    v = (v or "").strip()
    return v.upper() if HEX_RE.match(v) else default


def colors(s=None):
    s = s or db.settings_all()
    p = valid_hex(s.get("brand_primary"), DEFAULT_PRIMARY)
    a = valid_hex(s.get("brand_accent"), DEFAULT_ACCENT)
    dark_p = lighten(p, 0.22) if luminance(p) < 0.25 else p
    return {
        "primary": p, "primary_2": lighten(p, 0.12), "primary_3": lighten(p, 0.26), "primary_ink": ink_on(p),
        "accent": a, "accent_soft": mix(a, "#FFFFFF", 0.86), "accent_ink": ink_on(a),
        "dark_primary": dark_p, "dark_primary_2": lighten(dark_p, 0.12), "dark_accent": lighten(a, 0.12), "dark_accent_soft": mix(a, "#1A2422", 0.72),
    }


def palette(s=None):
    """What the browser needs: colours, logo URL, icon URLs, app name, and the CSS that applies them."""
    s = s or db.settings_all()
    c = colors(s)
    logo = s.get("brand_logo") or ""
    return {
        **c,
        "logo": f"/uploads/{logo}" if logo else "",
        "icon_192": "/brand/icon-192.png", "icon_512": "/brand/icon-512.png", "apple_icon": "/brand/apple-touch-icon.png",
        "favicon": "/brand/icon-192.png" if logo else "/static/icons/icon.svg",
        "app_name": s.get("brand_app_name") or s.get("club_short") or "Club",
        "css": css(c),
    }


def css(c):
    return (f":root{{--brand:{c['primary']};--brand-2:{c['primary_2']};--brand-3:{c['primary_3']};--brand-ink:{c['primary_ink']};--accent:{c['accent']};--accent-soft:{c['accent_soft']};--accent-ink:{c['accent_ink']}}}"
            f"@media (prefers-color-scheme:dark){{:root:not([data-theme=\"light\"]){{--brand:{c['dark_primary']};--brand-2:{c['dark_primary_2']};--brand-3:{lighten(c['dark_primary'], 0.24)};--accent:{c['dark_accent']};--accent-soft:{c['dark_accent_soft']}}}}}"
            f":root[data-theme=\"dark\"]{{--brand:{c['dark_primary']};--brand-2:{c['dark_primary_2']};--brand-3:{lighten(c['dark_primary'], 0.24)};--accent:{c['dark_accent']};--accent-soft:{c['dark_accent_soft']}}}")


def gradient(c):
    return f"linear-gradient(120deg,{c['primary']},{c['primary_2']} 70%,{c['primary_3']})"


# ---------- icons generated from the logo ----------
def brand_dir():
    return os.path.join(db.upload_dir(), "brand")


def icon_path(size):
    return os.path.join(brand_dir(), "apple-touch-icon.png" if size == 180 else f"icon-{size}.png")


def make_icons(logo_rel, s=None):
    """Square PNG icons on the primary colour with the logo centred in the safe zone (maskable-friendly)."""
    from PIL import Image
    c = colors(s)
    src = os.path.join(db.upload_dir(), logo_rel)
    with Image.open(src) as im:
        im = im.convert("RGBA")
        os.makedirs(brand_dir(), exist_ok=True)
        for size in ICON_SIZES:
            canvas = Image.new("RGBA", (size, size), _rgb(c["primary"]) + (255,))
            inner = int(size * 0.72)
            logo = im.copy()
            logo.thumbnail((inner, inner), Image.LANCZOS)
            pos = ((size - logo.width) // 2, (size - logo.height) // 2)
            canvas.alpha_composite(logo, pos)
            canvas.convert("RGB").save(icon_path(size), "PNG", optimize=True)


def clear_icons():
    for size in ICON_SIZES:
        try:
            os.remove(icon_path(size))
        except FileNotFoundError:
            pass


def icon_file(size):
    """The generated icon for this club, or the stock icon when the club has no logo."""
    p = icon_path(size)
    if os.path.isfile(p):
        return p
    static = os.path.join(os.path.dirname(__file__), "static", "icons")
    return os.path.join(static, "icon-512.png" if size == 512 else "icon-192.png")


def stock_icon_png(size):
    """Stock icon as PNG bytes for the apple-touch-icon when there is no logo."""
    return icon_file(192 if size == 180 else size)


def html_head(s=None):
    """Tags for server-rendered pages: favicon, theme colour and the palette variables."""
    p = palette(s)
    return (f'<meta name="theme-color" content="{p["primary"]}"><link rel="icon" href="{p["favicon"]}">'
            f'<link rel="apple-touch-icon" href="{p["apple_icon"]}"><style id="brand">{p["css"]}</style>')


def logo_img(s=None, cls="logo", height=40):
    """An <img> for the logo, or '' when the club has none."""
    s = s or db.settings_all()
    logo = s.get("brand_logo") or ""
    return f'<img class="{cls}" src="/uploads/{logo}" alt="" style="height:{height}px;max-width:160px;object-fit:contain">' if logo else ""
