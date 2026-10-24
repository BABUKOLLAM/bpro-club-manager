"""Builds the ClubPro handbook: docs/handbook/handbook.html -> docs/handbook/ClubPro-Handbook.pdf.
Screenshots come from docs/handbook/img (captured from a running demo). Run: python docs/handbook/build.py
Needs Node + Playwright (the render step) - see render.js next to this file."""
import html
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = "img"
e = html.escape
VERSION = "1.3"
VERSION_DATE = "October 2026"
CREDIT_NAME = "Dr. Babu B"
CREDIT_QUALS = "MBA, MPhil, PGDTRM, PGDHRM, Ph.D. (UGC-NET)"
CREDIT_ORG = "Bpro Consulting & Technologies"
CREDIT_SITES = ["www.bpropms.com", "www.drbabu.in", "www.bprohrms.com", "www.copperliners.com"]
_SIZES = {}
LOGO_WHITE = "brand/bpro-logo-white.png"
LOGO_NAVY = "brand/bpro-logo-navy.png"
HISTORY = [  # version, date, what changed (nine releases over twenty months)
    ("0.2", "February 2025", "Discovery: workshops with three clubs in Kottayam, audit of paper registers and WhatsApp groups; requirements for membership, library and events agreed."),
    ("0.4", "June 2025", "Pilot: membership register with online application, approval and numbering; Malayalam interface; e-card prototype; first club live."),
    ("0.6", "September 2025", "Library and reading room; events with registration and reminders; WhatsApp / SMS / e-mail outbox; family details and blood groups."),
    ("0.8", "January 2026", "Committees, meetings and online minutes with resolutions; accounts, dues and UPI claims; facilities and assets; pilot widened to five clubs."),
    ("0.9", "April 2026", "Polls and elections, documents, public website, annual report; hardening (rate limits, security headers); online payments through Razorpay; Google Drive backups."),
    ("1.0", "October 2026", "Multi-club platform, white label per club, ClubPro as a service with signup, pricing and billing; first edition of this handbook."),
    ("1.1", "October 2026", "Visual edition: colour system, numbered pointers and tooltips, lens zoom-ins, sticky notes, missions and badges, barcodes on every page, contents with page numbers."),
    ("1.2", "October 2026", "Full-bleed cover, decorative page frames, the Bpro logo, release history."),
    ("1.3", "October 2026", "Society accounts (statements, cash book, year close, Tally), the Library Council pack, and a new part on residents' associations: units, maintenance billing, helpdesk."),
]


def img_size(name):
    if name not in _SIZES:
        from PIL import Image
        ext = "jpg"
        with Image.open(os.path.join(HERE, IMG, f"{name}.{ext}")) as im:
            _SIZES[name] = im.size
    return _SIZES[name]


# ---------- small builders ----------
def _win(name, inner=""):
    ext = "jpg"
    return f"<div class='win'><div class='bar'><i></i><i></i><i></i></div><div class='pinwrap'><img src='{IMG}/{name}.{ext}' alt=''>{inner}</div></div>"


def fig(name, caption, kind="desk", w=None):
    """kind: desk (full width, window frame), phone (framed), phones (several framed in a row), small (half width)"""
    if kind == "phones":
        names = name if isinstance(name, list) else [name]
        inner = "".join(f"<div class='phone'><img src='{IMG}/{n}.jpg' alt=''></div>" for n in names)
        return f"<figure class='phones'><div class='row'>{inner}</div><figcaption>{caption}</figcaption></figure>"
    if kind == "phone":
        return f"<figure class='phone-fig'><div class='phone'><img src='{IMG}/{name}.jpg' alt=''></div><figcaption>{caption}</figcaption></figure>"
    if kind == "plain":
        return f"<figure class='desk'{(' style=' + chr(39) + 'max-width:' + w + chr(39)) if w else ''}><img src='{IMG}/{name}.png' alt='' style='width:100%;border-radius:12px;box-shadow:0 10px 28px rgba(27,31,59,.18)'><figcaption>{caption}</figcaption></figure>"
    cls = "small" if kind == "small" else "desk"
    style = f" style='max-width:{w}'" if w else ""
    return f"<figure class='{cls}'{style}>{_win(name)}<figcaption>{caption}</figcaption></figure>"


def pins(name, points, caption, kind="desk"):
    """A screenshot with numbered pointers and tooltips. points: [(x%, y%, short tooltip, legend text, side)]"""
    marks = []
    for i, pt in enumerate(points, 1):
        x, y, short, legend = pt[:4]
        side = pt[4] if len(pt) > 4 else ("l" if x > 70 else "")
        marks.append(f"<span class='pin' style='left:{x}%;top:{y}%'>{i}</span><span class='tip {side}' style='left:{x}%;top:{y}%'>{e(short)}</span>")
    inner = "".join(marks)
    if kind == "phone":
        body = f"<div class='phone' style='width:62mm'><div class='pinwrap'><img src='{IMG}/{name}.jpg' alt='' style='max-height:none'>{inner}</div></div>"
        fig_html = f"<figure class='phone-fig'>{body}<div><figcaption style='margin-top:0'>{caption}</figcaption><ul class='legend' style='columns:1'>{''.join(f'<li><i>{i}</i>{e(pt[3])}</li>' for i, pt in enumerate(points, 1))}</ul></div></figure>"
        return fig_html
    legend = "".join(f"<li><i>{i}</i>{e(pt[3])}</li>" for i, pt in enumerate(points, 1))
    return f"<figure class='desk'>{_win(name, inner)}<figcaption>{caption}</figcaption><ul class='legend'>{legend}</ul></figure>"


def lens(name, x, y, zoom, title, text, d=46):
    """A circular magnifier on a point of a screenshot (x, y in %), beside a short explanation."""
    w, h = img_size(name)
    dm = d  # mm
    bw = zoom * dm
    bh = bw * h / w
    px = dm / 2 - bw * x / 100
    py = dm / 2 - bh * y / 100
    ext = "jpg"
    return (f"<div class='lens-wrap'><div class='lens-row'><div class='lens' style='background-image:url({IMG}/{name}.{ext});background-size:{bw:.1f}mm auto;background-position:{px:.1f}mm {py:.1f}mm'></div>"
            f"<div class='lens-txt'><b>{e(title)}</b>{text}</div></div></div>")


def sticky(text, color="", title=""):
    return f"<div class='sticky {color}'>{('<b>' + e(title) + '</b>') if title else ''}{text}</div>"


def aside(main_html, sticky_html):
    return f"<div class='aside'><div style='flex:1'>{main_html}</div>{sticky_html}</div>"


def dyk(text):
    return f"<div class='dyk'><b>Did you know?</b>{text}</div>"


def quest(title, items, xp=20):
    return f"<div class='quest'><span class='xp'>+{xp} XP</span><b class='t'>{e(title)}</b><ul>{''.join(f'<li>{i}</li>' for i in items)}</ul></div>"


def badges(items):
    return "<div class='badges'>" + "".join(f"<span class='badge {c}'><span class='i'>{ic}</span>{e(t)}</span>" for ic, t, c in items) + "</div>"


def steps(items):
    return "<ol class='steps'>" + "".join(f"<li><b>{e(t)}</b>{(' ' + d) if d else ''}</li>" for t, d in items) + "</ol>"


def tip(text, kind="tip"):
    icon = {"tip": "💡", "warn": "⚠️", "note": "ℹ️", "ml": "🗣️"}[kind]
    return f"<div class='call {kind}'><span class='ic'>{icon}</span><div>{text}</div></div>"


def glance(items):
    return "<div class='glance'><b>At a glance</b><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul></div>"


def table(head, rows, cls=""):
    return f"<table class='{cls}'><thead><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" + \
        "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>"


_open = [False]


def close():
    if _open[0]:
        _open[0] = False
        return "</section>"
    return ""


TOTAL_CH = 49
PAGES = {}   # chapter number -> page, filled by the second pass


def chapter(num, title, sub, part):
    pre = close()
    _open[0] = True
    letter = part.split(" ")[1] if part.startswith("Part ") else "A"
    pct = int(num / TOTAL_CH * 100)
    return pre + f"<section class='chapter' id='c{num}' data-ch='{num}'><div class='ch-head {letter}'><div class='ch-num'>{num:02d}</div><div class='ch-part'>{e(part)}</div><h1>{e(title)}</h1><p class='ch-sub'>{e(sub)}</p>" \
        f"<div class='prog'><span>Chapter {num} of {TOTAL_CH}</span><span class='bar'><i style='width:{pct}%'></i></span><span class='xp'>+10 XP</span></div></div>"


LEVELS = {"A": ("0", "Welcome", "read the map"), "B": ("1", "Member", "apply, e-card, events, library, pay"), "C": ("2", "Office bearer", "approve, publish, minutes, accounts"),
          "D": ("3", "Operator", "server, console, billing"), "E": ("4", "Association", "units, maintenance, complaints"), "F": ("★", "Reference", "look anything up")}


def part_opener(letter, title, blurb, items):
    n, lv, sub = LEVELS[letter]
    return close() + f"""<section class='part {letter}' id='p{letter}'><div class='part-in'><div class='part-letter'>Part {letter}</div><h1>{e(title)}</h1><p>{e(blurb)}</p>
<ul>{''.join(f'<li>{e(i)}</li>' for i in items)}</ul><div class='level'><span class='n'>{n}</span><span><b>Level {n} · {lv}</b><small>{sub}</small></span></div></div></section>"""


def flow(nodes, w=760, accent=False):
    """A left-to-right flow of pill nodes with arrows. nodes: [(title, sub)]"""
    n = len(nodes); gap = 28; bw = (w - gap * (n - 1)) / n; h = 74
    out = [f"<svg class='flow' viewBox='0 0 {w} {h}' xmlns='http://www.w3.org/2000/svg'>"]
    for i, (t, s) in enumerate(nodes):
        x = i * (bw + gap)
        fill = "#0F4C45" if i == 0 or (accent and i == n - 1) else "#FFFFFF"
        col = "#fff" if fill != "#FFFFFF" else "#0F4C45"
        out.append(f"<rect x='{x}' y='6' width='{bw}' height='{h - 12}' rx='12' fill='{fill}' stroke='#0F4C45' stroke-width='1.5'/>")
        out.append(f"<text x='{x + bw / 2}' y='{h / 2 - 4}' text-anchor='middle' font-size='13' font-weight='700' fill='{col}'>{e(t)}</text>")
        out.append(f"<text x='{x + bw / 2}' y='{h / 2 + 14}' text-anchor='middle' font-size='10.5' fill='{col}' opacity='.85'>{e(s)}</text>")
        if i < n - 1:
            ax = x + bw
            out.append(f"<path d='M{ax + 4} {h / 2} L{ax + gap - 6} {h / 2}' stroke='#C9542A' stroke-width='2.2' fill='none' marker-end='url(#ah)'/>")
    out.insert(1, "<defs><marker id='ah' markerWidth='8' markerHeight='8' refX='6' refY='4' orient='auto'><path d='M0 0 L8 4 L0 8 z' fill='#C9542A'/></marker></defs>")
    out.append("</svg>")
    return "".join(out)


def lifecycle_svg():
    return """<svg class='flow' viewBox='0 0 760 150' xmlns='http://www.w3.org/2000/svg'>
<defs><marker id='ah2' markerWidth='8' markerHeight='8' refX='6' refY='4' orient='auto'><path d='M0 0 L8 4 L0 8 z' fill='#C9542A'/></marker></defs>
<g font-family='Inter, sans-serif'>
<rect x='0' y='30' width='160' height='64' rx='12' fill='#FBF0D9' stroke='#A86A00'/><text x='80' y='57' text-anchor='middle' font-size='13' font-weight='700' fill='#A86A00'>Trial</text><text x='80' y='76' text-anchor='middle' font-size='10.5' fill='#A86A00'>30 days, every feature</text>
<rect x='200' y='30' width='160' height='64' rx='12' fill='#E4F3EA' stroke='#2E7D4F'/><text x='280' y='57' text-anchor='middle' font-size='13' font-weight='700' fill='#2E7D4F'>Active</text><text x='280' y='76' text-anchor='middle' font-size='10.5' fill='#2E7D4F'>paid for one year</text>
<rect x='400' y='30' width='160' height='64' rx='12' fill='#FBF0D9' stroke='#A86A00'/><text x='480' y='57' text-anchor='middle' font-size='13' font-weight='700' fill='#A86A00'>Payment due</text><text x='480' y='76' text-anchor='middle' font-size='10.5' fill='#A86A00'>15 days of grace, still writable</text>
<rect x='600' y='30' width='160' height='64' rx='12' fill='#FBE4E2' stroke='#B3261E'/><text x='680' y='57' text-anchor='middle' font-size='13' font-weight='700' fill='#B3261E'>Read-only</text><text x='680' y='76' text-anchor='middle' font-size='10.5' fill='#B3261E'>sign in, read, pay</text>
<path d='M164 62 L194 62' stroke='#C9542A' stroke-width='2.2' marker-end='url(#ah2)'/><path d='M364 62 L394 62' stroke='#C9542A' stroke-width='2.2' marker-end='url(#ah2)'/><path d='M564 62 L594 62' stroke='#C9542A' stroke-width='2.2' marker-end='url(#ah2)'/>
<path d='M160 40 C 250 -5, 350 -5, 400 40' stroke='#0F4C45' stroke-width='1.6' fill='none' stroke-dasharray='4 3' marker-end='url(#ah2)'/><text x='280' y='14' text-anchor='middle' font-size='10.5' fill='#0F4C45'>trial ends without payment</text>
<path d='M680 94 C 600 150, 360 150, 282 96' stroke='#2E7D4F' stroke-width='1.8' fill='none' marker-end='url(#ah2)'/><text x='480' y='138' text-anchor='middle' font-size='11' font-weight='600' fill='#2E7D4F'>payment received: reopened at once, paid until next year</text>
</g></svg>"""


def arch_svg():
    return """<svg class='flow' viewBox='0 0 760 230' xmlns='http://www.w3.org/2000/svg' font-family='Inter, sans-serif'>
<rect x='10' y='10' width='740' height='210' rx='16' fill='#F7F4EC' stroke='#E3DED2'/>
<text x='24' y='34' font-size='12' font-weight='700' fill='#5B6B68'>ONE SERVER (VPS) · Caddy with automatic HTTPS · the ClubPro app · nightly backups</text>
<g>
<rect x='24' y='50' width='170' height='110' rx='12' fill='#fff' stroke='#0F4C45' stroke-width='1.5'/><text x='109' y='74' text-anchor='middle' font-size='13' font-weight='700' fill='#0F4C45'>Kottayam ASC</text>
<text x='109' y='94' text-anchor='middle' font-size='10.5' fill='#5B6B68'>kottayamclub.in</text><text x='109' y='112' text-anchor='middle' font-size='10.5' fill='#5B6B68'>own database · uploads</text><text x='109' y='128' text-anchor='middle' font-size='10.5' fill='#5B6B68'>own logo, colours</text><text x='109' y='144' text-anchor='middle' font-size='10.5' fill='#5B6B68'>own WhatsApp number</text>
<rect x='214' y='50' width='170' height='110' rx='12' fill='#fff' stroke='#0F4C45' stroke-width='1.5'/><text x='299' y='74' text-anchor='middle' font-size='13' font-weight='700' fill='#0F4C45'>Pala Arts Club</text>
<text x='299' y='94' text-anchor='middle' font-size='10.5' fill='#5B6B68'>pala.clubpro.in</text><text x='299' y='112' text-anchor='middle' font-size='10.5' fill='#5B6B68'>own database · uploads</text><text x='299' y='128' text-anchor='middle' font-size='10.5' fill='#5B6B68'>own logo, colours</text><text x='299' y='144' text-anchor='middle' font-size='10.5' fill='#5B6B68'>shares the server's SMS</text>
<rect x='404' y='50' width='170' height='110' rx='12' fill='#fff' stroke='#0F4C45' stroke-width='1.5' stroke-dasharray='5 4'/><text x='489' y='74' text-anchor='middle' font-size='13' font-weight='700' fill='#0F4C45'>… any club</text>
<text x='489' y='94' text-anchor='middle' font-size='10.5' fill='#5B6B68'>signs up at /signup</text><text x='489' y='112' text-anchor='middle' font-size='10.5' fill='#5B6B68'>ready in a minute</text><text x='489' y='128' text-anchor='middle' font-size='10.5' fill='#5B6B68'>30-day trial</text>
<rect x='594' y='50' width='146' height='110' rx='12' fill='#0F4C45'/><text x='667' y='78' text-anchor='middle' font-size='13' font-weight='700' fill='#fff'>Platform console</text><text x='667' y='98' text-anchor='middle' font-size='10.5' fill='#fff' opacity='.9'>/_platform</text><text x='667' y='116' text-anchor='middle' font-size='10.5' fill='#fff' opacity='.9'>clubs · billing</text><text x='667' y='132' text-anchor='middle' font-size='10.5' fill='#fff' opacity='.9'>pricing · routing</text>
</g>
<text x='24' y='190' font-size='11' fill='#5B6B68'>Each club is isolated: its own SQLite database, uploads and backups under data/tenants/&lt;slug&gt;/. The visitor's domain decides which club answers.</text>
<text x='24' y='207' font-size='11' fill='#5B6B68'>Operator keys: CLUB_MASTER_KEY (console), CLUB_BASE_DOMAIN (sub-domains), CLUBPRO_RZP_* (subscription payments).</text>
</svg>"""


def msg_svg():
    return """<svg class='flow' viewBox='0 0 760 170' xmlns='http://www.w3.org/2000/svg' font-family='Inter, sans-serif'>
<defs><marker id='ah3' markerWidth='8' markerHeight='8' refX='6' refY='4' orient='auto'><path d='M0 0 L8 4 L0 8 z' fill='#C9542A'/></marker></defs>
<rect x='0' y='55' width='170' height='60' rx='12' fill='#0F4C45'/><text x='85' y='80' text-anchor='middle' font-size='13' font-weight='700' fill='#fff'>Something happens</text><text x='85' y='98' text-anchor='middle' font-size='10' fill='#fff' opacity='.85'>publish · approve · issue · due</text>
<rect x='220' y='55' width='170' height='60' rx='12' fill='#fff' stroke='#0F4C45' stroke-width='1.5'/><text x='305' y='80' text-anchor='middle' font-size='13' font-weight='700' fill='#0F4C45'>Outbox</text><text x='305' y='98' text-anchor='middle' font-size='10' fill='#5B6B68'>one row per member per channel</text>
<path d='M174 85 L214 85' stroke='#C9542A' stroke-width='2.2' marker-end='url(#ah3)'/>
<g font-size='11.5' font-weight='600' fill='#0F4C45'>
<rect x='450' y='4' width='130' height='30' rx='8' fill='#E4F3EA'/><text x='515' y='24' text-anchor='middle'>WhatsApp</text>
<rect x='450' y='44' width='130' height='30' rx='8' fill='#E4F3EA'/><text x='515' y='64' text-anchor='middle'>SMS</text>
<rect x='450' y='84' width='130' height='30' rx='8' fill='#E4F3EA'/><text x='515' y='104' text-anchor='middle'>E-mail</text>
<rect x='450' y='124' width='130' height='30' rx='8' fill='#E4F3EA'/><text x='515' y='144' text-anchor='middle'>In-app + phone push</text>
</g>
<path d='M394 85 C 420 85, 420 19, 446 19' stroke='#C9542A' stroke-width='1.8' fill='none' marker-end='url(#ah3)'/><path d='M394 85 C 420 85, 420 59, 446 59' stroke='#C9542A' stroke-width='1.8' fill='none' marker-end='url(#ah3)'/>
<path d='M394 85 C 420 85, 420 99, 446 99' stroke='#C9542A' stroke-width='1.8' fill='none' marker-end='url(#ah3)'/><path d='M394 85 C 420 85, 420 139, 446 139' stroke='#C9542A' stroke-width='1.8' fill='none' marker-end='url(#ah3)'/>
<text x='600' y='24' font-size='10.5' fill='#5B6B68'>Meta Cloud API, member's language</text><text x='600' y='64' font-size='10.5' fill='#5B6B68'>DLT template, short texts</text><text x='600' y='104' font-size='10.5' fill='#5B6B68'>SMTP</text><text x='600' y='144' font-size='10.5' fill='#5B6B68'>free, always on</text>
</svg>"""


# ---------- content ----------
def build():
    P = []  # pieces
    A = P.append
    A(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ClubPro Handbook</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@600;700;800&family=Caveat:wght@500;700&family=Manjari:wght@400;700&family=Noto+Sans+Malayalam:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="handbook.css"></head><body>""")
    # ----- cover placeholder (the real cover is rendered full-bleed and swapped in; see cover_html) -----
    A("<section class='full blank'></section>")
    # ----- colophon -----
    A(f"""<section class='colophon'><h1>About this handbook</h1>
<div class='credit-card'><img class='logo' src='{LOGO_WHITE}' alt='Bpro'><div><b>Designed &amp; Developed by {CREDIT_NAME}</b>{CREDIT_QUALS}<br>{CREDIT_ORG}<div class='sites'>{''.join(f'<span>{x}</span>' for x in CREDIT_SITES)}</div></div></div>
<div class='box'><b>Release history</b><table class='version-table'><tr><th>Version</th><th>Date</th><th>What changed</th></tr>
{''.join(f"<tr><td>{v}</td><td>{d}</td><td>{w}</td></tr>" for v, d, w in reversed(HISTORY))}</table></div>
<div class='box'><b>How the page furniture works</b><ul style='margin:4px 0 0;padding-left:18px'>
<li><b>Barcode</b> at the foot of every page encodes the handbook version and page (for example <code>CLUBPRO-HB-{VERSION}-P007</code>), so a photographed or printed page can always be traced to its edition.</li>
<li><b>Progress bar and XP</b> in each chapter head show how far you are through the book; <b>missions</b> at the end of chapters are things to try in the app; <b>badges</b> mark what you can do once a part is finished.</li>
<li><b>Pointers</b> on screenshots are numbered and explained under the picture; <b>lenses</b> zoom into one control; <b>sticky notes</b> carry the advice an experienced secretary would give you.</li>
<li><span class='hl'>Highlighted text</span> is the thing to remember from a paragraph.</li></ul></div>
<p class='small'>ClubPro is a product of {CREDIT_ORG}. Screens shown are from a demonstration club; names are fictitious. © {VERSION_DATE.split()[-1]} {CREDIT_ORG}.</p></section>""")
    # ----- contents -----
    toc = [("A", "Welcome", ["How to use this book", "Three kinds of reader", "Languages, phones and the installed app"]),
           ("B", "Members' guide", ["Getting started", "Applying for membership", "Signing in and forgotten passwords", "Home and the menu", "Profile, family and the e-card",
                                    "Notifications and preferences", "News, events and competitions", "Library and reading room", "Paying dues and fees", "Documents, bookings, polls, meetings, directory"]),
           ("C", "Office bearers' guide", ["Roles and who can do what", "The dashboard", "First-time setup", "Applications and the members register", "Publishing news, events and competitions",
                                           "Committees, meetings, minutes, actions and plans", "The library desk", "The Library Council pack", "Accounts, dues and payments", "Statements, cash book and the year close", "Facilities, assets and documents", "Broadcasts and the outbox",
                                           "Polls and elections", "Scan QR at the door", "Reports, annual report, audit and backups", "The public website and the in-app handbook", "Your ClubPro subscription"]),
           ("D", "Operator's guide", ["How the platform is built", "Installing on a server", "The platform console", "Clubs signing up by themselves", "Billing, reminders and suspension", "White label per club", "Message channels and payment gateways", "Backups and safety"]),
           ("E", "Residents' associations", ["Switching on association mode", "Units and residents", "Maintenance billing", "Complaints and the helpdesk", "A resident's phone"]),
           ("F", "Reference", ["Permissions matrix", "Numbering formats", "Automatic messages", "Environment variables", "Glossary English · Malayalam", "Frequently asked questions"])]
    n = 1
    rows = []
    for letter, title, chs in toc:
        rows.append(f"<div class='toc-part {letter}'><span>Part {letter}</span>{e(title)}</div>")
        for c in chs:
            pg = PAGES.get(n, "")
            rows.append(f"<div class='toc-row'><span class='n'>{n}</span><span class='t'>{e(c)}</span><span class='dots'></span><span class='pg'>{pg}</span></div>"); n += 1
    A(f"<section class='toc'><h1>Contents</h1><div class='toc-grid'>{''.join(rows)}</div><p class='toc-note small'>Page numbers refer to the printed page number at the foot of each page. The PDF's bookmarks (sidebar) jump to any chapter.</p></section>")

    # ================= PART A =================
    A(part_opener("A", "Welcome", "ClubPro runs a club's whole life in one place and in two languages. This book shows every screen, step by step.",
                  ["Who this book is for and how it is arranged", "What the symbols mean", "Phones, computers and the installed app"]))
    A(chapter(1, "How to use this book", "Three readers, one product", "Part A · Welcome"))
    A("""<p>ClubPro is used by three kinds of people, and this book has a part for each. <span class='hl'>You do not need to read it all</span>: members need Part B, office bearers Parts B and C, the operator Part D.</p>
<div class='three'><div class='card'><b>Members</b><p>Apply, sign in, keep the e-card, register for events, borrow books, pay dues, vote. Mostly on a phone. <span class='ref'>Part B</span></p></div>
<div class='card'><b>Office bearers</b><p>Secretary, president, treasurer, librarian and the administrator: approvals, publishing, minutes, the library desk, accounts, broadcasts, settings. Usually on a laptop. <span class='ref'>Part C</span></p></div>
<div class='card'><b>The operator</b><p>Team Bpro, or whoever runs the server: installing, creating clubs, pricing, billing, channels, backups. <span class='ref'>Part D</span></p></div></div>
<p>Each chapter opens with <i>At a glance</i>, then numbered steps with the screen beside them. Symbols:</p>""")
    A(tip("<b>Tip</b> — a shortcut or a good habit."))
    A(tip("<b>Careful</b> — something that cannot be undone, or that members will notice.", "warn"))
    A(tip("<b>Note</b> — background that explains why the screen behaves as it does.", "note"))
    A(tip("<b>Malayalam</b> — the Malayalam name of the screen or button, as members see it.", "ml"))
    A(aside(badges([("🎓", "Level 1 · Member", ""), ("🏅", "Level 2 · Office bearer", "gold"), ("🛠️", "Level 3 · Operator", "teal"), ("📚", "Reference", "pink")]),
                sticky("Each part is a level. Finish a level's missions in the app and you have earned its badge. No account on earth is checking; it is a way to make sure you tried every screen once.", "pink", "Why levels?")))
    A(chapter(2, "Three kinds of reader", "What each person sees", "Part A · Welcome"))
    A("""<p>Everyone opens the same web address. What appears depends on who signs in:</p>""")
    A(table(["Who", "Signs in with", "Sees", "Typical device"],
            [["A visitor", "nothing", "the front page, the public website, news that is public, the application form", "phone"],
             ["A member", "phone number + password", "everything in Part B: profile, e-card, events, library, payments, polls", "phone"],
             ["A committee member", "phone number + password", "the above, plus their committee's meetings, agenda and minutes", "phone / laptop"],
             ["An office bearer", "e-mail or phone + password", "the <b>Office</b> section of the menu for their role (Part C)", "laptop"],
             ["The administrator", "e-mail + password", "everything, including Settings, Users and Backups", "laptop"],
             ["The operator", "the master key", "the platform console at /_platform (Part D)", "laptop"]]))
    A(chapter(3, "Languages, phones and the installed app", "Malayalam and English everywhere", "Part A · Welcome"))
    A(glance(["Every screen, button and message exists in English and Malayalam.", "The language button sits at the top of every page; a member's choice is remembered and used for the messages the club sends them.",
              "On a phone the app installs to the home screen and opens full-screen, with notifications."]))
    A(fig(["m-landing-ml", "m-landing-en"], "The front page on a phone in Malayalam and in English. The button at the top switches at any time.", "phones"))
    A(steps([("Open the club's web address", "in Chrome (Android) or Safari (iPhone)."),
             ("Tap the browser menu", "and choose <i>Add to Home screen</i> (Android) or <i>Share → Add to Home Screen</i> (iPhone)."),
             ("Open it from the home screen", "it now runs full-screen like an app, with the club's own icon."),
             ("Allow notifications", "when asked under <i>My profile → Notification preferences</i>, so event reminders and receipts arrive even when the app is closed.")]))
    A(tip("The app keeps working on a weak connection: screens you have opened before load instantly, and a clear <i>You are offline</i> page appears instead of an error.", "note"))
    A(quest("Mission 1 · Get set up", ["Open the club's address on your phone and add it to the home screen", "Switch the language once each way", "Allow notifications when asked"], 10))
    A(close())

    # ================= PART B =================
    A(part_opener("B", "Members' guide", "Everything a member does, from the first application to voting in the election, on a phone.",
                  ["Apply in six short steps, with a selfie", "Keep the membership e-card on the phone", "Register the family for events, borrow books, pay by UPI"]))
    A(chapter(4, "Getting started", "From the front page to your first sign-in", "Part B · Members"))
    A(glance(["Your phone number is your login once you are a member.", "Not a member yet? Apply from the front page; the committee approves and you receive your number by WhatsApp or SMS.",
              "Lost the password? One-time code to your phone."]))
    A(pins("m-home", [(8, 3, "Menu", "The menu (☰): every screen is one tap away; office bearers see an extra Office group at the bottom."), (88, 3, "Language", "English / മലയാളം switch; also sets the language of the messages you receive."),
                      (50, 22, "Upcoming", "Events you can register for, with Registration open pills."), (50, 60, "Latest", "The newest news items; tap to read.")], "The member's home page after signing in.", "phone"))
    A(tip("<b>Malayalam</b>: Home = ഹോം · Sign in = പ്രവേശിക്കുക · Apply for membership = അംഗത്വത്തിന് അപേക്ഷിക്കുക", "ml"))
    A(chapter(5, "Applying for membership", "Six steps, two minutes", "Part B · Members"))
    A(glance(["The form saves itself as you go; a refresh loses nothing.", "Family members can be added now or later from your profile.", "The photo can be a selfie or a picture from the gallery; it becomes your e-card photo."]))
    A(flow([("Apply", "6-step form"), ("Review", "office checks details"), ("Approve", "number issued"), ("Message", "WhatsApp / SMS"), ("Sign in", "phone + password")], accent=True))
    A(fig(["m-apply-1", "m-apply-2", "m-apply-3"], "Steps 1 to 3: about you · contact and address · family (quick-add chips for spouse, son, daughter, parents).", "phones"))
    A(fig(["m-apply-4", "m-apply-5", "m-apply-6"], "Steps 4 to 6: photo (selfie or gallery, resized on the phone) · password and consent · review before sending.", "phones"))
    A(steps([("Tap Apply for membership", "on the front page."),
             ("About you", "name in English and, if you like, Malayalam; gender, date of birth, blood group. The blood group lets the club find donors in an emergency."),
             ("Contact and address", "your mobile becomes your login. WhatsApp number if different, e-mail, house name, ward, pincode."),
             ("Family", "tap a chip (spouse, son, daughter, father, mother) and fill the name and date of birth. Family members can be registered for events and competitions."),
             ("Photo", "<i>Take a selfie</i> opens the camera; <i>Choose from gallery</i> picks a file. It is resized on the phone before upload."),
             ("Password and consent", "8 characters or more; confirm that the details are true and that the club may message you."),
             ("Review and send", "check everything, then <i>Send application</i>. A <i>What happens next</i> page confirms it.")]))
    A(fig("m-apply-done", "After sending: what happens next, and a reminder that the number arrives by WhatsApp or SMS once approved.", "phone"))
    A(lens("m-apply-4", 50, 52, 2.2, "Selfie or gallery", "Step 4 offers both: <i>Take a selfie</i> opens the camera; <i>Choose from gallery</i> picks any picture. The photo is shrunk on the phone before it is sent, so it works on slow connections."))
    A(aside(dyk("The form keeps a draft in the phone's browser. Close the browser, come back tomorrow, and the steps you filled are still there until you send or clear them."),
            sticky("Ask the applicant to write the name in English exactly as on their ID. It goes on the e-card and the receipts.", "", "Secretary's tip")))
    A(quest("Mission 2 · Apply", ["Fill all six steps on a phone, including one family member", "Take a selfie for the photo", "Send the application and read the What happens next page"], 20))
    A(tip("If the office rejects an application the applicant is told why by message and can apply again with corrections.", "note"))
    A(chapter(6, "Signing in and forgotten passwords", "", "Part B · Members"))
    A(steps([("Sign in", "with the phone number used in the application (or the e-mail the office gave you) and your password."),
             ("Forgot password?", "tap the link under the sign-in form, enter your phone or e-mail, and a 6-digit code arrives by WhatsApp, SMS or e-mail."),
             ("Set a new password", "enter the code and the new password. The code works for 10 minutes and once only.")]))
    A(fig("m-forgot", "Forgot password: the one-time code goes to the phone or e-mail on record.", "phone"))
    A(tip("The sign-in page allows ten attempts a minute from one connection; after that it asks you to wait. This protects every member's account.", "warn"))
    A(chapter(7, "Home and the menu", "Where everything is", "Part B · Members"))
    A(fig(["m-home", "m-menu"], "Home, and the menu opened with ☰. Office bearers see an extra <i>Office</i> group at the bottom.", "phones"))
    A(table(["Menu item", "Malayalam", "What it is for"],
            [["Home", "ഹോം", "upcoming events and the latest news"], ["News &amp; events", "വാർത്തകളും പരിപാടികളും", "everything the club publishes; register from here"],
             ["My profile", "എന്റെ പ്രൊഫൈൽ", "your details, e-card, family, notification preferences, password"], ["Notifications", "അറിയിപ്പുകൾ", "every message the club sent you, in the app"],
             ["Members directory", "അംഗങ്ങളുടെ ഡയറക്ടറി", "members who chose to show their phone"], ["Committees · Meetings", "കമ്മിറ്റികൾ · യോഗങ്ങൾ", "office bearers, your committees, agenda and minutes"],
             ["Library · My books", "ലൈബ്രറി · എന്റെ പുസ്തകങ്ങൾ", "search the catalogue, reserve, see loans and due dates"], ["My payments", "എന്റെ പണമിടപാടുകൾ", "dues, UPI / online payment, receipts"],
             ["Documents", "രേഖകൾ", "bye-laws, circulars, certificates you may see"], ["Hall &amp; ground booking", "ഹാൾ & ഗ്രൗണ്ട് ബുക്കിംഗ്", "calendar and booking requests"],
             ["Polls &amp; elections", "വോട്ടെടുപ്പും തിരഞ്ഞെടുപ്പും", "open votes and results"]]))
    A(chapter(8, "Profile, family and the e-card", "Your membership in your pocket", "Part B · Members"))
    A(glance(["The e-card carries your photo, number, blood group, validity and a QR code the office scans.", "Save it as a picture or share it on WhatsApp; it is also printable.",
              "Add family with dates of birth and blood groups; the office verifies them."]))
    A(pins("m-me", [(40, 12, "Tabs", "Profile · Family · Preferences · Password."), (50, 25, "E-card", "Your electronic membership card with the QR the office scans."), (37, 41, "Save to phone", "Renders the card as a picture in your gallery."),
                     (33, 45, "Share · Print", "Send it on WhatsApp, or print a credit-card-size version."), (80, 62, "Edit", "Update phone, address, occupation or photo; the office verifies big changes.")], "My profile: the e-card at the top, then your details.", "phone"))
    A(lens("m-me", 80, 31, 2.4, "The QR on the e-card", "Encodes your membership number. At a meeting, an event or the reading room the office scans it with <i>Scan QR</i> and you are marked present or signed in without typing anything."))
    A(fig("ecard", "The e-card as saved to the phone: the club's colours and logo, both scripts, membership type, number, blood group, joined date, validity and the QR.", "desk", "420px"))
    A(steps([("Save to phone", "renders the card as a picture in your gallery."), ("Share", "sends the picture through WhatsApp or any app."), ("Print", "opens a credit-card-sized printable version."),
             ("My family", "add spouse, children, parents; relation, date of birth, blood group, phone. The office marks each one <i>verified</i>."),
             ("Change password", "under the profile tabs; a strong password is 8 characters or more.")]))
    A(fig("m-family", "My family: the people you can register for events, and the blood groups the club's donor search uses.", "phone"))
    A(quest("Mission 3 · Your card", ["Save the e-card to your phone and share it with yourself on WhatsApp", "Add one family member with a blood group", "Change your password"], 20))
    A(chapter(9, "Notifications and preferences", "Choose how the club reaches you", "Part B · Members"))
    A(fig(["m-preferences", "m-notifications"], "Notification preferences, and the in-app list of everything the club has sent you.", "phones"))
    A(steps([("Channels", "tick WhatsApp, SMS and e-mail as you like; the app notification is always kept."), ("Phone notifications", "turn on to get reminders and receipts on the lock screen (needs the installed app and HTTPS)."),
             ("Directory", "choose whether other members may see your phone number."), ("Language", "English or Malayalam for every message the club sends you.")]))
    A(chapter(10, "News, events and competitions", "Register yourself or the family", "Part B · Members"))
    A(glance(["Open an event and tap Register; choose a family member if the event is for them.", "Competitions have items (100 m, essay, chess…); pick the item and, for team events, the team.",
              "You get a confirmation at once and a reminder the day before; results and points tables appear on the same page."]))
    A(fig(["m-posts", "m-event"], "News &amp; events, and an event page with the Register button, the venue and the fee if any.", "phones"))
    A(tip("Public events have a <i>Share</i> button that sends a link to a WhatsApp group; people who are not members can read it and, if the club allows, register.", "tip"))
    A(chapter(11, "Library and reading room", "Search, reserve, renew", "Part B · Members"))
    A(fig(["m-library", "m-my-books"], "The catalogue with search, and My books with due dates and the online renewal.", "phones"))
    A(steps([("Search", "by title, author, subject or accession number; each card shows how many copies are in."), ("Reserve", "when every copy is out; you are messaged when it returns and it is held for you."),
             ("My books", "shows loans and due dates; <i>Renew</i> once online if nobody has reserved the book."), ("Fines", "appear here and under My payments; the librarian records the payment at the desk.")]))
    A(chapter(12, "Paying dues and fees", "UPI, online, or at the desk", "Part B · Members"))
    A(glance(["My payments shows what is due this year and every receipt the club has issued you.", "Pay by UPI: scan or tap, then tell the club the transaction number; the treasurer confirms and the receipt arrives.",
              "Where the club has online payment, Pay online settles it instantly with an automatic receipt."]))
    A(pins("m-payments", [(50, 18, "Dues", "What you owe this year and what it covers; green when nothing is due."), (30, 30, "Pay by UPI", "Opens the UPI sheet: the club's UPI ID, a QR, and a button that opens your UPI app with the amount filled in."),
                          (69, 30, "I have paid", "Tell the treasurer the UTR / transaction ID; your receipt follows once confirmed."), (50, 45, "Receipts", "Every receipt the club has issued you, with the number and the head.")], "My payments and the way to pay.", "phone"))
    A(fig("m-pay-upi", "The UPI sheet: the club's UPI ID, a QR for any UPI app and the <i>I have paid</i> form.", "phone"))
    A(sticky("Write the 12-digit UTR, not the amount. The treasurer matches it in the bank app in seconds.", "blue", "Member's tip"))
    A(steps([("Open My payments", "the amount due and the items it covers are at the top."), ("Pay by UPI", "scan the QR with Google Pay, PhonePe or any UPI app, or tap <i>Open UPI app</i>."),
             ("I have paid", "enter the 12-digit UTR or transaction ID from your UPI app."), ("Receipt", "the treasurer confirms the payment; your receipt arrives by WhatsApp or e-mail and stays under My payments.")]))
    A(tip("Paying at the office works as before: the treasurer records it and the receipt is messaged to you.", "note"))
    A(dyk("Receipts are never deleted. If one is wrong it is reversed with a voucher, so what you were messaged always matches the club's cash book."))
    A(chapter(13, "Documents, bookings, polls, meetings, directory", "The rest of the menu", "Part B · Members"))
    A(fig(["m-documents", "m-bookings", "m-polls"], "Documents you may read, the hall and ground calendar with a booking request, and open polls.", "phones"))
    A(fig(["m-meetings", "m-directory"], "Meetings of your committees (and the general body), and the members directory.", "phones"))
    A(steps([("Documents", "bye-laws, circulars, certificates and minutes, each visible to the audience the office chose."),
             ("Hall &amp; ground booking", "pick a date and slot and send a request; the office confirms, and any charge appears under My payments."),
             ("Polls &amp; elections", "one vote per member; a secret ballot never records who chose what. Results appear when voting closes."),
             ("Meetings", "notices, agenda and, once published, the minutes and the action items assigned to you."),
             ("Directory", "members who allowed their phone to be shown; tap to call or WhatsApp.")]))
    A(quest("Mission 4 · Around the club", ["Register yourself or a family member for an event", "Reserve a book that is out", "Vote in a poll (or open the polls page)", "Read a document"], 20))
    A(badges([("🎓", "Level 1 complete · Member", "gold")]))
    A(close())

    # ================= PART C =================
    A(part_opener("C", "Office bearers' guide", "Running the club from a laptop: approvals, publishing, minutes, the library desk, accounts and broadcasts.",
                  ["Set the club up once: names, numbering, membership types, branding, channels", "Approve applications and keep the register", "Publish, broadcast, record minutes, close the accounts"]))
    A(chapter(14, "Roles and who can do what", "Five office roles, one administrator", "Part C · Office"))
    A(glance(["Roles are given under Office → Users by the administrator or secretary.", "A committee convener additionally manages their own committee's meetings and minutes.",
              "The full permissions matrix is in Part F."]))
    A(table(["Role", "Malayalam", "Can"],
            [["Administrator", "അഡ്മിനിസ്ട്രേറ്റർ", "everything, including Settings, Users, backups and the subscription"],
             ["President", "പ്രസിഡന്റ്", "members and applications, publishing, broadcasts, committees and minutes, accounts (view), reports"],
             ["Secretary", "സെക്രട്ടറി", "the same as the president, plus accounts entry, users and the library"],
             ["Treasurer", "ട്രഷറർ", "receipts, vouchers, dues, UPI confirmations, bookings charges, members (view), reports"],
             ["Librarian", "ലൈബ്രേറിയൻ", "catalogue, issue / return, reservations, reading room, periodicals, members (view)"],
             ["Member", "അംഗം", "Part B"]]))
    A(fig("d-landing", "The front page on a laptop. Office bearers sign in here with the e-mail or phone the administrator gave them.", "desk"))
    A(chapter(15, "The dashboard", "The club at a glance", "Part C · Office"))
    A(pins("d-dashboard", [(10, 7, "Logo · club", "The club's logo and name; set under Settings → Branding."), (41, 17, "Pending applications", "Coloured when something needs you; opens Applications."),
                           (41, 40, "Dues", "Members with dues and the outstanding amount; opens Dues."), (40, 57, "Upcoming", "Events with registration state."), (78, 57, "Latest", "What was published last."), (9, 74, "Office", "The office menu: your role decides what is listed.", "")],
           "Home for an office bearer: counters that need attention are coloured; each tile opens the matching screen."))
    A(lens("d-dashboard", 41, 17, 2.6, "A tile that needs you", "Orange numbers are things waiting: applications to approve, overdue books, members with dues, failed messages. Green and black numbers are just facts."))
    A(table(["Tile", "Means"], [["Pending applications", "applications waiting for approval → Office → Applications"], ["Minutes pending", "meetings that happened without published minutes"],
                               ["Open actions · Overdue", "action items from minutes, and those past their due date"], ["Books out · Overdue books", "loans, and loans past the due date (reminders go automatically)"],
                               ["Members with dues · Outstanding", "who has not paid this year and how much → Office → Dues"], ["Messages pending · failed", "the outbox; <i>demo</i> means a channel is not configured yet"]]))
    A(chapter(16, "First-time setup", "An hour, once", "Part C · Office"))
    A(glance(["Settings holds the club's identity, numbering, membership types, library rules, website, branding and channels.", "Users &amp; roles gives office bearers their sign-in.", "Import the old register from Excel; members then sign in with their phone number."]))
    A(fig("d-settings", "Settings → Club: names in both scripts, short name (used in membership numbers), registration number, place, address, phone, default language, self-registration, wards, UPI ID.", "desk"))
    A(sticky("Do Settings before you import the register: the short name and the number format are baked into every membership number you issue.", "", "Do this first"))
    A(steps([("Club", "names in both scripts, short name, registration number, address, phone, e-mail. Tick <i>Allow self-registration</i> if people may apply online. List the wards; enter the club's UPI ID so members can pay."),
             ("Numbering", "membership, receipt, voucher and accession number formats with placeholders ({prefix} {year} {yy} {seq:04d}); whether the sequence restarts each year; subscription due month."),
             ("Membership types &amp; fees", "life, ordinary, associate, student, honorary — or your own, with admission and annual fees in rupees. These drive dues."),
             ("Library", "loan period, books per member, fine per day, online renewals; event reminder days."),
             ("Website", "about text in both languages, map link, social links and a cover photo for the public website."),
             ("Branding", "logo, primary and accent colour, app name, footer credit (chapter 44 explains)."),
             ("Communication", "channel status and, if the club has its own WhatsApp / SMS / e-mail / Razorpay accounts, their keys."),
             ("Save", "the button at the bottom saves every card at once.")]))
    A(fig("d-settings-numbering", "Numbering: the formats and the sequence rule.", "desk"))
    A(pins("d-settings-brand", [(60, 4, "Preview", "Shows the primary colour, the logo and the accent button as members will see them."), (42, 16, "Logo", "PNG with a transparent background; becomes the phone icon and goes on the e-card."),
                               (27, 31, "Primary", "The colour of the sidebar, buttons and the e-card band."), (63, 31, "Accent", "The colour of the Apply button, pills and the card stripe."), (42, 40, "App name", "The title and the name on the home screen."), (42, 58, "Numbering", "The formats that every membership, receipt and voucher number follows.")],
           "Branding and numbering as the administrator sees them."))
    A(fig("d-settings-channels", "Communication: pills show which channels are on and whether the club's own account or the server's is in use.", "desk"))
    A(fig("d-users", "Office → Users: add an office bearer with login, role and, optionally, their member record; reset passwords; deactivate.", "desk"))
    A(tip("Give every office bearer their own login. The audit log then shows who approved, published or recorded what.", "tip"))
    A(chapter(17, "Applications and the members register", "Approve, number, maintain", "Part C · Office"))
    A(glance(["Approving issues the next membership number and messages the member their number and sign-in.", "The member page holds everything: details, family, payments, books, timeline, e-card.",
              "The old register can be imported from Excel in one go."]))
    A(flow([("Applied", "from the phone"), ("Approve / reject", "Office → Applications"), ("Number issued", "format from Settings"), ("Member messaged", "number + sign-in"), ("Active", "on the register")], accent=True))
    A(fig("d-applications", "Applications: every pending application with the details it was sent with.", "desk"))
    A(pins("d-application-detail", [(88, 14, "WhatsApp · Call", "Reach the applicant before deciding, straight from the card.", "l"), (45, 30, "Details", "Everything from the form, in both scripts."), (30, 50, "Family", "Family members entered on the form, to be verified later."),
                                    (28, 57, "Approve", "Issues the next number and sends the welcome message with the sign-in."), (36, 57, "Reject", "Asks for a reason; the applicant receives it and may apply again.")],
           "An application waiting for a decision."))
    A(lens("d-application-detail", 28, 57, 2.8, "Approve", "One click does four things: sets the membership type, issues the next number in the club's format, activates the member, and sends the welcome message with their sign-in."))
    A(steps([("Approve", "sets the type (the applicant's choice can be changed), issues the number and sends the welcome message."),
             ("Members", "the register with search and filters (status, type, ward, blood group); export to CSV; print e-cards for a filter."),
             ("Member page", "tabs for details, family, payments, books and the timeline; buttons to edit, change status (active, inactive, expelled, deceased), set a password, and WhatsApp the member."),
             ("Family", "add or verify family members; each verified family member can be registered for events."),
             ("Import register", "download the Excel template, fill it (one row per member, number optional), upload; members get their numbers and can sign in with their phone and a first password you set.")]))
    A(fig("d-member", "A member's page with the e-card, details, committees and the action buttons.", "desk"))
    A(fig("d-member-edit", "Editing a member: both scripts, contact, address, type, photo, notes for the office.", "desk"))
    A(fig("d-import", "Import register: the Excel template and the upload; a preview reports problems before anything is written.", "desk"))
    A(fig("d-card-print", "Print cards: credit-card size, two per row, with crop-friendly margins; one member or a whole filter.", "desk"))
    A(tip("Changing a member's status to <i>inactive</i> keeps every record; <i>expelled</i> and <i>deceased</i> also stop messages. Nothing is deleted.", "warn"))
    A(quest("Mission 5 · The register", ["Approve one application and watch the welcome message appear in the Outbox", "Edit a member's photo and open their e-card", "Download the import template and look at its columns"], 30))
    A(chapter(18, "Publishing news, events and competitions", "One post, every channel", "Part C · Office"))
    A(glance(["A post can be news, an event, a camp, a social activity or a competition, with dates, venue, fee and registration.", "Publish and notify sends it to the chosen audience by WhatsApp, SMS, e-mail and push in one click.",
              "Competitions carry items, teams, fixtures, judges, scores and a points table; results are published to everyone."]))
    A(pins("d-posts", [(95, 5, "+ New", "Start a post: news, event, camp, competition, social activity or notice.", "l"), (45, 12, "Kind", "Filter by kind."), (33, 19, "State", "All, upcoming, past, drafts."), (60, 31, "Cards", "Each post with its registration count and whether it is public.")],
           "News &amp; events for the office: drafts and published posts, with registrations and results."))
    A(fig("d-post-form", "The post form: kind, title and body in both scripts, when and where, registration (limit, fee, family allowed), audience, cover photo, judges for competitions.", "desk"))
    A(steps([("New post (+)", "choose the kind; fill the title and body in English and Malayalam (the member's language is used)."),
             ("Registration", "tick <i>Registration open</i>, set a limit and a fee if any; family members may be allowed."),
             ("Publish and notify", "pick the audience (all members, a type, a ward, a committee, blood group…) and the channels; the outbox does the rest."),
             ("Registrations", "the list with participants, item and payment; mark attendance; export."),
             ("Fixtures and judging", "for competitions add fixtures (date, teams, venue), name judges from the members; judges score on their phones; the points table updates."),
             ("Results", "enter or publish results; members are notified and the public page shows them.")]))
    A(fig("d-event", "An event as the office sees it: registrations, attendance and the public link.", "desk"))
    A(fig("d-competition", "A competition: items, fixtures, judges, scores and the points table.", "desk"))
    A(fig("d-fixture-form", "Adding a fixture.", "small"))
    A(fig("d-public-post", "The public page of an event, shareable to WhatsApp groups, with a Register button.", "desk"))
    A(aside(dyk("<i>Publish and notify</i> writes one outbox row per member per channel. For 300 members on WhatsApp, SMS and app that is 900 rows, sent in the background while you carry on working."),
            sticky("Publish news without notification for small updates; keep WhatsApp for things members must act on. Members notice the difference.", "green", "Keep WhatsApp precious")))
    A(quest("Mission 6 · Publish", ["Create an event with registration open and a fee", "Publish and notify a small audience (one ward)", "Register a member for it and mark them attended"], 30))
    A(chapter(19, "Committees, meetings, minutes, actions and plans", "Governance without paper", "Part C · Office"))
    A(glance(["Committees hold members with designations; the executive committee's office bearers appear on the public website.", "A meeting has a notice, agenda, attendance, minutes (MoM) with decisions and resolution numbers, and action items.",
              "Plans are the year's programmes with owners, budgets and status."]))
    A(fig("d-committees", "Committees: the executive committee and sub-committees, each with its members and conveners.", "desk"))
    A(fig("d-committee", "A committee's page: members with designations and terms, its meetings and plans.", "desk"))
    A(steps([("New meeting", "committee, date and time, venue, mode (in person, online, hybrid), quorum; add agenda items with a type (information, discussion, resolution)."),
             ("Send notice", "the notice goes to the committee members on their channels; general body meetings go to every member."),
             ("Attendance", "mark present / absent / apology; the quorum pill turns green."),
             ("Minutes", "write the decision under each agenda item; resolutions get a running number; record who chaired and who recorded."),
             ("Publish minutes", "to the committee (or to all members for a general body); members are notified and the PDF-style print is available."),
             ("Action items", "assign to a member with a due date; they are reminded, and the dashboard counts overdue ones."),
             ("Plans", "the year's programmes with owner, budget, dates and progress; linked to the meetings that approved them.")]))
    A(fig("d-meeting-form", "Scheduling a meeting with its agenda.", "desk"))
    A(pins("d-meeting", [(45, 11, "Edit · Notice · Minutes", "The meeting's tools, in the order you use them."), (58, 11, "Publish minutes", "Sends the minutes to the committee; the status pill turns green.", "l"), (50, 46, "Agenda & decisions", "One decision per item; resolutions get a running number."),
                         (85, 67, "Attendance", "Mark present / absent / apology; the quorum pill reacts.", "l"), (70, 90, "Action items", "Who does what by when; the dashboard counts overdue ones.", "l")],
           "A meeting page: status, agenda with decisions, attendance and action items."))
    A(lens("d-meeting", 58, 11, 2.6, "Publish minutes to committee", "The one button that turns a draft into the official record: members of the committee are notified, the print view becomes available and action items start their reminders."))
    A(fig("d-actions", "Action items across all meetings, with owner, due date and status.", "desk"))
    A(fig("d-plans", "Plans: programmes, owners, budgets and progress.", "desk"))
    A(quest("Mission 7 · A meeting end to end", ["Schedule a meeting with three agenda items and send the notice", "Mark attendance and write one decision per item", "Publish the minutes and assign one action item"], 40))
    A(chapter(20, "The library desk", "Catalogue, circulation, reading room, periodicals", "Part C · Office"))
    A(glance(["Books have an accession number each; copies are tracked separately.", "Issue, return and renew with the member's number or by scanning the e-card; fines are computed from Settings.",
              "The reading room register and the periodicals subscriptions live here too."]))
    A(fig("d-library", "The catalogue for the librarian: add books, copies, categories; search; reservations waiting.", "desk"))
    A(fig("d-book", "A book: copies with accession numbers and status, current loans, reservations and history.", "desk"))
    A(steps([("Add book", "title in both scripts, author, publisher, year, category, language, price; copies get accession numbers from the format in Settings."),
             ("Issue / return", "pick the member (or scan the QR), then the copy; due dates follow the loan period; <i>Return</i> computes any fine and records it under the member's dues."),
             ("Renew", "once online by the member, or at the desk; blocked when the book is reserved."),
             ("Reservations", "when a copy returns the first reserver is messaged and the copy is held."),
             ("Reading room", "a daily register of visitors; scanning the e-card records the visit."),
             ("Newspapers &amp; periodicals", "subscriptions with vendor, period and cost; a renewal reminder before they lapse.")]))
    A(fig("d-circulation", "Issue / return: today's loans and returns, overdue items highlighted.", "desk"))
    A(fig("d-issue-form", "Issuing a book to a member.", "small"))
    A(fig("d-reading-room", "The reading room register.", "small"))
    A(fig("d-periodicals", "Newspapers and periodicals.", "small"))
    A(sticky("Print the accession numbers as labels from the catalogue; the issue desk then scans books as fast as e-cards.", "blue", "Librarian's tip"))
    A(quest("Mission 8 · The desk", ["Add a book with two copies", "Issue one copy to a member and return it after the due date to see the fine", "Record a reading-room visit by scanning an e-card"], 30))
    A(chapter(21, "The Library Council pack", "The affiliation return, a grade estimate, grants and utilisation certificates", "Part C · Office"))
    A(glance(["Library → Library Council reads the year's affiliation statement straight from the registers you already keep: stock, additions, members, circulation, reading room, newspapers, programmes, library accounts, grants and office bearers.",
              "A grade estimate scores the library against thresholds kept in Settings and shows, per criterion, what the next grade needs.",
              "Grants have a register; the vouchers paid from a grant are charged to it and the utilisation certificate prints with the certificate text for signature."]))
    A(fig("d-council", "Library Council: the grade estimate with every criterion, the thresholds, what was attained this year and the shortfall to the next grade; the grants register below.", "desk"))
    A(steps([("Settings first", "under Settings → Library Council affiliation enter the Council affiliation number, the grade the Council gave, district, taluk, working hours and the librarian; check the grade thresholds against the Council's current circular."),
             ("Grade estimate", "each criterion (stock, members, books issued, periodicals, reading-room visits, programmes, books added) earns points by the grade band it reaches; the overall estimate follows the points. The right-hand column says what the next band needs."),
             ("Annual statement", "the printable return for the year, in English or Malayalam, with signature lines for the librarian, secretary and president."),
             ("Grants", "record a grant when it arrives: the receipt is booked under <i>Grant</i> for you. Open <i>Vouchers charged</i> to tick the payment vouchers spent from it."),
             ("Utilisation certificate", "prints the grant, the vouchers charged, the unutilised balance and the certificate wording.")]))
    A(fig("d-grant", "Charging vouchers to a grant: what is charged so far, and the year's payment vouchers waiting to be ticked.", "desk"))
    A(fig("d-print-council", "The annual statement as it prints (Malayalam): stock, members, circulation by month, periodicals, programmes, accounts, grants, the grade table and office bearers.", "desk"))
    A(fig("d-print-uc", "A grant utilisation certificate.", "small"))
    A(tip("The thresholds shipped with the app are planning targets, not the Council's figures. Replace them in Settings with the numbers in the current circular; the screens and the printout both say the circular governs.", "warn"))
    A(sticky("Keep the reading-room register and the periodicals register up to date through the year: two of the seven criteria come straight from them.", "yellow", "Librarian's tip"))
    A(quest("Bonus mission · Affiliation", ["Enter the Council details and the current thresholds in Settings", "Record a grant and charge two vouchers to it", "Print the annual statement in Malayalam"], 30))
    A(chapter(22, "Accounts, dues and payments", "Receipts, vouchers, UPI and online", "Part C · Office"))
    A(glance(["Every rupee in or out is a receipt or a voucher under a standard head (admission, subscription, donation, event fee, rent, salary…).", "Dues are computed from membership types and the subscription year; reminders go automatically.",
              "Members' UPI claims are confirmed by the treasurer; online payments through Razorpay settle themselves."]))
    A(fig("d-finance", "Accounts: the cash book with receipts and vouchers, filters by head and period, totals.", "desk"))
    A(fig("d-tx-form", "Recording a receipt or voucher: head, member (for receipts), amount, mode, reference, note. The receipt is messaged to the member.", "desk"))
    A(steps([("Record", "a receipt (money in) or a voucher (money out); choose the head; for a member's payment pick the member and the receipt goes to them."),
             ("Dues", "who owes what this year; send reminders to all or to one; record a payment straight from the row."),
             ("UPI claims", "members who paid by UPI and sent the UTR; check your bank app, then confirm (receipt issued) or reject (the member is told why)."),
             ("Online payments", "orders and settlements from Razorpay, with the receipt each produced."),
             ("Reports", "the annual statement by head is in Reports → Annual report; the auditor's statements are the next chapter.")]))
    A(fig("d-dues", "Dues: outstanding amounts by member, with reminders and quick recording.", "desk"))
    A(fig("d-claims", "UPI claims waiting for confirmation.", "small"))
    A(fig("d-online", "Online payments received through Razorpay.", "small"))
    A(tip("Receipts cannot be deleted, only reversed with a voucher, so the cash book always matches what was messaged to members.", "warn"))
    A(quest("Mission 9 · Money", ["Record a subscription receipt and find the message in the Outbox", "Send a dues reminder to one member", "Confirm a UPI claim"], 30))
    A(chapter(23, "Statements, cash book and the year close", "Receipts & Payments, Income & Expenditure, Balance Sheet, Tally", "Part C · Office"))
    A(glance(["Accounts → Statements turns the receipts and vouchers into the three statements an auditor and the society's annual return expect, for a financial year (April to March unless Settings say otherwise).",
              "Every head has a <i>nature</i>: income and expense meet in Income & Expenditure; books, furniture and building are assets; deposits are liabilities; building fund and corpus are funds. The balance sheet balances by construction.",
              "The treasurer closes an audited year: entries lock, closing balances carry forward. Tally XML exports the vouchers for an accountant."]))
    A(fig("d-statements", "Statements for the year: opening and closing balances, surplus, the Receipts & Payments account, the Income & Expenditure account and the Balance Sheet, with the year's status.", "desk"))
    A(steps([("Opening balances", "once, for the first year kept here: cash in hand, cash at bank, the value of the library books and any deposits or funds. Later years are carried forward by the year close and locked."),
             ("Cash ⇄ bank", "record every deposit into the bank and every withdrawal as a contra entry from the Accounts screen; it moves money between the two books without touching income or expense."),
             ("Cash book · Bank book", "every entry with a running balance from the opening; print either for the audit file."),
             ("Statements", "the three statements for any year, provisional until the year is closed; <i>Print statements</i> gives the bilingual set with signature lines for treasurer, secretary, president and auditor."),
             ("Close the year", "after the audit, from the Statements screen (treasurer or administrator). Reopen if the auditor asks for a change; close again afterwards."),
             ("Tally XML", "the year's receipts, payments and contras with their ledger masters, importable into Tally.")]))
    A(fig("d-openings", "Entering the opening balances for the first year.", "small"))
    A(fig("d-contra", "A contra entry: cash deposited in the bank.", "small"))
    A(fig("d-cashbook", "The cash book with a running balance.", "desk"))
    A(fig("d-print-statements", "The printed set: Receipts and Payments, Income and Expenditure, Balance Sheet.", "desk"))
    A(fig("d-settings-accounts", "Settings → Accounts & financial year: the start month and the club's extra heads with their nature.", "desk"))
    A(table(["Nature", "Where it lands", "Examples"], [["Income", "Income & Expenditure (credit)", "subscription, admission, donation, fine, bank interest"], ["Expense", "Income & Expenditure (debit)", "rent, electricity, salary, printing, newspapers"],
             ["Asset", "Balance sheet: payments add to it", "books, furniture, building, fixed deposit"], ["Liability", "Balance sheet: received adds, refunded reduces", "library deposits"], ["Fund", "Balance sheet: a fund with its own balance", "building fund, corpus, sinking fund"]]))
    A(tip("Receipts and vouchers dated in a closed year are refused, and so are voids. That is the point: once the auditor has signed, the books do not move. Reopen the year to correct, then close it again.", "warn"))
    A(dyk("The balance sheet cannot fail to balance: the general fund is computed from the opening assets and liabilities and moves only by the year's surplus or deficit. If a figure looks wrong, the entry is wrong, not the arithmetic."))
    A(quest("Bonus mission · The audit file", ["Enter opening balances and record a contra entry", "Print the three statements and the cash book", "Close last year, then reopen it"], 30))
    A(chapter(24, "Facilities, assets and documents", "Halls, grounds, equipment, papers", "Part C · Office"))
    A(fig("d-bookings", "Hall &amp; ground booking: the calendar, requests to confirm, rates per facility.", "desk"))
    A(fig("d-facility-form", "Adding a facility with its rate and rules.", "small"))
    A(steps([("Facilities", "add the hall, ground, stage, sound system… with a rate (per hour or per day) and whether members may request online."),
             ("Bookings", "confirm or decline requests; a confirmed booking with a charge appears in the member's dues and the receipt is issued on payment."),
             ("Assets", "the asset register with categories, purchase details and value; lend an asset to a member and track its return."),
             ("Documents", "upload bye-laws, circulars, certificates, minutes; choose the audience (public, members, committee, office).")]))
    A(fig("d-assets", "Assets and lending.", "small"))
    A(fig("d-documents", "Documents with audience control.", "small"))
    A(fig("d-document-form", "Adding a document.", "small"))
    A(chapter(25, "Broadcasts and the outbox", "Reach everyone, see what was delivered", "Part C · Office"))
    A(glance(["A broadcast is a message to an audience on the channels you pick, now or at a scheduled time.", "The outbox shows every message, its channel and delivery status; failed ones can be retried.",
              "Blood donor request finds members and family members by blood group."]))
    A(msg_svg())
    A(fig("d-broadcast", "Broadcast: audience, channels, both languages, schedule.", "desk"))
    A(fig("d-blood", "Blood donor request: pick the group; donors and their family members are messaged at once.", "desk"))
    A(fig("d-outbox", "The outbox: every message with channel, status and provider reference. <i>demo</i> means the channel is not configured yet.", "desk"))
    A(steps([("Compose", "subject and text in both languages; members receive the one they chose."), ("Audience", "all, a membership type, a ward, a committee, a blood group, an event's participants."),
             ("Channels", "WhatsApp, SMS, e-mail, app; untick the costly ones for routine notes."), ("Send now or schedule", "a scheduled broadcast can be cancelled until it goes."),
             ("Outbox", "status per message; retry failed; see the provider's reference.")]))
    A(tip("SMS in Malayalam counts 70 characters per segment, so the automatic SMS texts are short; WhatsApp and e-mail carry the full text.", "note"))
    A(aside(dyk("The outbox retries a failed message three times before marking it failed, and shows the provider's own error text so you can see whether a number was wrong or a template was rejected."),
            sticky("Schedule the Sunday broadcast on Saturday night. The Outbox shows it as scheduled and you can still cancel it in the morning.", "pink", "Scheduling")))
    A(chapter(26, "Polls and elections", "One member, one vote", "Part C · Office"))
    A(fig("d-polls", "Polls &amp; elections for the office: open, closed, results.", "desk"))
    A(fig("d-poll-form", "Creating a poll: question, options (or candidates), who may vote, secret or open, closing time.", "desk"))
    A(steps([("New poll", "a question with options, or an election with posts and candidates; choose the electorate (all members, a type, a committee)."),
             ("Secret ballot", "records that a member voted, never what they chose."), ("Open", "members are notified; the poll appears under Polls &amp; elections."),
             ("Close", "automatically at the closing time; results are published and notified.")]))
    A(chapter(27, "Scan QR at the door", "Meetings, events, reading room", "Part C · Office"))
    A(fig("d-scan", "Scan QR: point the laptop or phone camera at a member's e-card; the member is identified and marked present, registered or signed in to the reading room.", "desk"))
    A(tip("On a phone, Scan QR uses the back camera; the office bearer's phone becomes the attendance desk.", "tip"))
    A(chapter(28, "Reports, annual report, audit and backups", "Numbers for the general body", "Part C · Office"))
    A(fig("d-reports", "Reports: members by type, ward, gender, blood group, age band and joining year; events; library; accounts.", "desk"))
    A(fig("d-annual", "The annual report for the general body: office bearers, membership, events, meetings and resolutions, accounts by head, library; printable.", "desk"))
    A(fig("d-audit", "The audit log: who did what and when.", "desk"))
    A(steps([("Annual report", "pick the year; print or save as PDF for the general body."), ("Audit", "every approval, publication, receipt, settings change and sign-in, with the user and time."),
             ("Backups", "Settings → Backups shows the nightly copies and lets you take one now; with Google Drive configured, copies go off-site.")]))
    A(chapter(29, "The public website and the in-app handbook", "What the world sees", "Part C · Office"))
    A(fig("d-site", "The club's public website at /site: about, office bearers with photos, upcoming events, news, documents, photos, contact and social links; in both languages; shareable.", "desk"))
    A(fig("d-help", "The in-app handbook at /help: the short bilingual guide members and office bearers can open from the menu.", "desk"))
    A(chapter(30, "Your ClubPro subscription", "What the club pays, and what happens if it does not", "Part C · Office"))
    A(glance(["Office → Subscription plan shows the status, the end date, the active members and next year's price.", "Pay online (card / UPI) or by UPI with the transaction reference; the operator confirms it.",
              "After the end date there are 15 days of grace; then the club becomes read-only until paid. Nothing is deleted."]))
    A(lifecycle_svg())
    A(fig("d-plan", "Subscription plan: status, dates, members, price, and the payment history.", "desk"))
    A(fig("d-plan-upi", "Paying by UPI to the operator and sending the reference.", "desk"))
    A(table(["Active members", "Price per year"], [["up to 49", "₹2,500 flat"], ["50 to 99", "₹120 per member (₹6,000 – ₹11,880)"], ["100 and above", "₹120 per member"]]))
    A(tip("The price is worked out from the live member count on the day you pay, so a growing club simply pays a little more at its next renewal. Office bearers are reminded 7 days before the end.", "note"))
    A(quest("Mission 10 · Keep the lights on", ["Open Subscription plan and note the end date", "Try Pay by UPI and read the reference form (cancel it)", "Set the support contact in your phone"], 20))
    A(badges([("🏅", "Level 2 complete · Office bearer", "gold"), ("📣", "First broadcast", ""), ("📝", "Minutes published", "teal"), ("🧾", "First receipt", "pink")]))
    A(close())

    # ================= PART D =================
    A(part_opener("D", "Operator's guide", "For Team Bpro or anyone running ClubPro as a service: the server, the console, pricing, billing and channels.",
                  ["One server, many clubs, each isolated", "Clubs sign up by themselves and pay yearly", "Operator keys, channels and backups"]))
    A(chapter(31, "How the platform is built", "One server, many clubs", "Part D · Operator"))
    A(arch_svg())
    A("""<p>ClubPro is a single Python application (FastAPI) with one SQLite database per club, a browser app that installs on phones, and background workers for messages, daily jobs and backups. Caddy in front provides HTTPS for every club's domain automatically. The first club on a server is the <i>default</i> club and lives directly in the data folder; every further club lives under <code>data/tenants/&lt;slug&gt;/</code>. The visitor's domain picks the club; the operator's own pages (<code>/signup</code>, <code>/pricing</code>, <code>/_platform</code>) answer on any domain.</p>""")
    A(chapter(32, "Installing on a server", "A VPS, a domain, fifteen minutes", "Part D · Operator"))
    A(steps([("Get a VPS", "Ubuntu or Debian, 1 vCPU / 2 GB is enough for dozens of clubs. Shared web hosting cannot run it (it is Python, not PHP)."),
             ("Point DNS", "an A record for the platform domain (e.g. clubpro.in) and a wildcard record (*.clubpro.in) at the server; clubs with their own domains point theirs the same way."),
             ("Run the installer", "<code>curl -fsSL https://raw.githubusercontent.com/BABUKOLLAM/bpro-club-manager/main/deploy/vps-install.sh | sudo bash -s -- clubpro.in admin@teambpro.in</code> installs Docker and Caddy, clones the app to /opt/club, writes .env and starts everything."),
             ("Multi-club Caddy", "replace the site file with <code>deploy/site-multi.caddy</code> so certificates are issued on demand for every registered domain."),
             ("Set the operator keys", "in /opt/club/.env: <code>CLUB_MASTER_KEY</code>, <code>CLUB_BASE_DOMAIN=clubpro.in</code>, <code>CLUBPRO_RZP_*</code>, and the server's SMS / WhatsApp / SMTP settings used for signup codes and as the default for clubs. Restart with <code>docker compose up -d</code>."),
             ("Open the console", "https://clubpro.in/_platform with the master key: set the product name, the footer credit, pricing, your UPI ID and support contact.")]))
    A(tip("Re-running the installer command updates the app in place. Data, uploads and .env are kept.", "tip"))
    A(sticky("Keep .env out of git and out of WhatsApp. It holds every key. Back it up with the server, nowhere else.", "", "Operator's rule"))
    A(chapter(33, "The platform console", "Every club, every rupee", "Part D · Operator"))
    A(pins("d-platform", [(20, 6, "Master key", "Open the console with CLUB_MASTER_KEY from .env."), (50, 11, "Summary", "Clubs by status, run-rate, collected, claims to confirm."), (65, 19, "Per club", "Mark paid, extend trial, suspend / reopen, confirm claims.", "l"),
                          (50, 33, "Clubs", "Sizes, domains, last backup, deactivate."), (50, 48, "Add a club", "For clubs you onboard yourself."), (50, 62, "Routing · pricing", "Default club's domains, product name, powered-by, prices, UPI, support.")],
           "The console: subscriptions summary, per-club status and actions, the club list, add a club, routing, pricing and the operator's UPI and support contact."))
    A(steps([("Subscriptions", "clubs by status, yearly run-rate, amount collected, trials ending this week, UPI claims to confirm."),
             ("Per club", "Mark paid (amount and reference), Extend trial, Suspend / Reopen, Confirm or Reject a UPI claim."),
             ("Clubs", "members, applications, last backup; edit domains; deactivate / activate."),
             ("Add a club", "for clubs you onboard yourself: slug, names, domains, first administrator."),
             ("Routing", "the default club's domains; whether unknown host names show the default club or <i>no club at this address</i>."),
             ("Pricing", "flat price and member limit, per-member price, trial and grace days, UPI ID and payee name, support contact.")]))
    A(chapter(34, "Clubs signing up by themselves", "/signup and /pricing", "Part D · Operator"))
    A(fig("d-pricing", "The pricing page: the rule, the trial, and every service in both languages.", "desk"))
    A(fig("m-signup", "The signup form on a phone: club, web address, secretary, mobile, password, consent.", "phone"))
    A(flow([("Fill the form", "/signup"), ("Code by SMS", "operator's channel"), ("Club created", "<slug>.clubpro.in"), ("Trial", "30 days"), ("Pays", "online or UPI")], accent=True))
    A(tip("Signup codes go through the server's SMS or WhatsApp channel. If none is configured the club is created without a code — fine for a trial server, not for the public.", "warn"))
    A(dyk("A club that signs up at /signup is live in under a minute: its database is created, the first administrator is set, the default committees are seeded and the trial clock starts."))
    A(chapter(35, "Billing, reminders and suspension", "Trial → active → due → read-only", "Part D · Operator"))
    A(lifecycle_svg())
    A(steps([("Online", "the club pays through your Razorpay account from its Subscription plan screen; the plan is extended by a year at once; the webhook is the safety net if the browser closes."),
             ("UPI", "the club pays to your UPI ID and sends the reference; it appears as a claim on the console; confirm after checking your bank."),
             ("Manual", "Mark paid for cash, cheque or bank transfer."),
             ("Reminders", "the daily job messages the club's office bearers 7 days before the end, when payment is due, and when the club becomes read-only."),
             ("Read-only", "sign-in, reading and paying keep working; every other change is refused with a clear message; nothing is deleted. Reopen from the console if needed.")]))
    A(chapter(36, "White label per club", "Their name, your product", "Part D · Operator"))
    A("""<p>Each club sets its own logo, colours, app name and footer under Settings → Branding (chapter 16). The platform's product name and the "Powered by" footer that new clubs start with are set on the console. A club may also enter its own WhatsApp, SMS, SMTP and Razorpay accounts; blank fields inherit the server's. Secrets are stored per club and shown masked.</p>""")
    A(fig("d-settings-brand", "Branding settings as a club sees them.", "desk"))
    A(chapter(37, "Message channels and payment gateways", "What to set up where", "Part D · Operator"))
    A(table(["Channel", "Provider", "Set up", "Notes"],
            [["WhatsApp", "Meta WhatsApp Cloud API", "a Meta business app, a phone number ID and a permanent system-user token; an approved message template with one {{1}} parameter", "needed to message members outside the 24-hour window; template approval takes a day or two"],
             ["SMS", "any HTTP gateway (Fast2SMS, Textlocal, MSG91…)", "the gateway URL with placeholders {to} {text} {sender} {dlt} {key}; a DLT-registered template", "Malayalam SMS is 70 characters per segment"],
             ["E-mail", "any SMTP account", "host, port, user, password, from address", "Gmail needs an app password"],
             ["Push", "built in", "nothing", "free; the app must be served over HTTPS"],
             ["Members' online payment", "Razorpay (club's account)", "key ID, secret, webhook secret; webhook URL /api/payments/razorpay/webhook", "per club under Settings or in the server's .env"],
             ["Subscription payment", "Razorpay (operator's account)", "CLUBPRO_RZP_KEY_ID / SECRET / WEBHOOK_SECRET; webhook URL /api/saas/webhook", "operator only"]]))
    A(chapter(38, "Backups and safety", "Sleep well", "Part D · Operator"))
    A(steps([("Nightly backups", "every club's database and uploads are copied each night; the console shows the last backup per club."),
             ("Google Drive", "a service account and a shared folder push copies off the server; retention is per club."),
             ("Protections", "HttpOnly cookies, a header on every change (no cross-site actions), scrypt passwords, one-time codes that expire, rate limits on public endpoints, re-encoded uploads, security headers and a content policy on every page."),
             ("Updates", "re-run the installer; the schema upgrades itself; restart with docker compose."),
             ("Data requests", "a club's data is one folder; export or delete it as a unit when a club leaves.")]))
    A(quest("Mission 11 · Operator", ["Create a club from the console and sign in to it", "Set pricing, UPI ID and support contact", "Sign a club up through /signup on your phone", "Mark a trial club paid and watch its status"], 40))
    A(badges([("🛠️", "Level 3 complete · Operator", "gold"), ("☁️", "Server installed", "teal"), ("💳", "First subscription", "pink")]))
    A(close())

    # ================= PART E =================
    # ================= PART E =================
    A(part_opener("E", "Residents' associations", "The same app runs a flat owners' or residents' welfare association: switch the mode and three modules appear.",
                  ["Units, blocks and residents as owner, tenant or family", "Maintenance billed per unit, settled oldest first, chased automatically", "A complaints helpdesk the office works and the resident watches"]))
    A(chapter(39, "Switching on association mode", "Residents, units, blocks; the library steps aside", "Part E · Association"))
    A(glance(["Settings → <i>This organisation is a…</i> → flat owners' / residents' association. The wording changes to residents, units and blocks in both languages, the library hides, and the units register, maintenance billing and the helpdesk switch on.",
              "Each module can be toggled on its own, so a club with flats can bill maintenance and keep its library.",
              "Everything else is unchanged: committees and minutes, AGM polls and elections, notices, documents, hall booking, accounts and the year close, backups and the website."]))
    A(fig("d-assoc-settings", "The organisation card in Settings: the kind, the modules, and the maintenance rule (basis, rate, period, due day, late fee, unit types, rates by type).", "desk"))
    A(steps([("Choose the kind", "and save. The menu, the registration form and the dashboard change at once."),
             ("Blocks", "the <i>Blocks / towers</i> list (the wards list in club mode) feeds the block selectors everywhere."),
             ("Unit types", "1BHK, 2BHK, 3BHK, Villa, Shop… edit freely; they drive the per-type maintenance rule."),
             ("Maintenance rule", "a flat amount per unit, an amount per square foot, or an amount by unit type; monthly or quarterly; the due day; a late fee charged once after it."),
             ("Resident categories", "the membership types list becomes resident categories (owner member, tenant…) with their admission and annual amounts, if the association collects any.")]))
    A(fig("d-assoc-home", "The dashboard in association mode: residents, units, vacant units, maintenance due and open complaints.", "desk"))
    A(sticky("Keep club mode for an arts & sports club that happens to own flats; switch on only <i>Units</i> and <i>Maintenance billing</i> under Modules.", "blue", "Mixed clubs"))
    A(chapter(40, "Units and residents", "The register the association is built on", "Part E · Association"))
    A(glance(["A unit is a flat, villa or shop: block, number, floor, type, area, parking, owner on record.", "Residents attach to a unit as owner, tenant or family member; one unit, many residents; a resident has one unit.",
              "A resident who registers from the front page names the block and unit; a unit the office has not entered yet is created on the spot."]))
    A(fig("d-units", "Units: the register with type and area, residents, status and maintenance due per unit.", "desk"))
    A(fig("d-units-bulk", "Adding a whole building in one go: one line per unit, block, number, floor, type, area.", "small"))
    A(fig("d-assign-resident", "Attaching a resident to a unit as owner, tenant or family.", "small"))
    A(fig("d-unit", "A unit: residents, owner on record, maintenance bills with their status, receipts, complaints, and the printable statement of account.", "desk"))
    A(steps([("Bulk entry", "Units → <i>Add units in bulk</i>: paste the list from the builder's schedule; only the unit number is required."),
             ("Residents", "open the unit and <i>Assign resident</i>, or set the unit on the resident's page (office edit); residents can also arrive through self-registration."),
             ("Vacant and inactive", "mark a unit vacant to keep it visible and billed, inactive to drop it from billing."),
             ("Fixed maintenance", "a unit that pays a negotiated amount gets it as <i>Fixed maintenance for this unit</i>; the rule is ignored for that unit."),
             ("Statement", "the unit's bills and receipts with the balance, printable for the owner or a buyer's NOC.")]))
    A(fig("d-residents", "The residents register: the unit and occupancy appear under each name; filter by block.", "desk"))
    A(chapter(41, "Maintenance billing", "Bills per unit, oldest settled first, reminders to the unit", "Part E · Association"))
    A(glance(["Accounts → Maintenance: generate the period's bills for every active unit on the rule; a unit with no area or rate gets none and the screen says so.",
              "A receipt under <i>Maintenance charges</i> settles the unit's bills oldest first; a part payment stays as a part payment on the oldest bill; voiding a receipt reopens what it had settled.",
              "After the due day the late fee is added once by the daily job. Defaulters are listed by unit with calls, WhatsApp and reminders to every resident of the unit."]))
    A(fig("d-maintenance", "Maintenance for a period: billed, paid and outstanding, every unit with its balance and status, and the generate and remind buttons.", "desk"))
    A(fig("d-generate-bills", "Generating the bills for a period (YYYY-MM, or YYYY-Q1 for quarterly billing).", "small"))
    A(fig("d-maint-due", "Maintenance due: units with outstanding bills, how many periods, the oldest, and quick contact.", "desk"))
    A(steps([("Generate", "once per period; running it again creates nothing twice. New units get their bill the next time."),
             ("Collect", "record the receipt from the unit page (<i>+ New receipt</i>, head and unit filled in) or from Accounts with the resident selected; the resident gets the receipt by WhatsApp."),
             ("Online", "residents pay by UPI with the transaction number, or online through Razorpay, from <i>My payments</i>; the receipt settles the bills the same way."),
             ("Adjust", "the … button on a bill edits the amount or late fee, adds a note, or waives the bill (a vacant month, a dispute settled)."),
             ("Remind", "<i>Send reminders</i> messages every resident of every unit in arrears with the amount and the number of periods."),
             ("Statements", "maintenance is income in the year's statements; sinking fund contributions are a fund on the balance sheet.")]))
    A(tip("Bill in advance: generate the month's bills on the first, so the due day and the late fee mean what the bye-laws say.", "tip"))
    A(quest("Mission 12 · Maintenance", ["Add three units in bulk and attach a resident to one", "Generate this month's bills and record a part payment", "Open the defaulters tab and send reminders"], 30))
    A(chapter(42, "Complaints and the helpdesk", "From a leaking tap to a closed ticket", "Part E · Association"))
    A(glance(["Residents raise complaints with a category, priority and photo; the office is told at once in the app.", "The office assigns a person, moves the status (open → in progress → on hold → resolved), adds notes; the resident is messaged on every change.",
              "The resident closes the complaint when satisfied, or the office does. Everything stays on the unit's page."]))
    A(fig("d-helpdesk", "The helpdesk for the office: open complaints first, urgent ones on top, counts by status.", "desk"))
    A(fig("d-ticket", "A complaint: details and photo, who raised it and from which unit, the assignee, and the notes timeline.", "desk"))
    A(fig("d-ticket-assign", "Assigning, re-prioritising and updating the status with a note.", "small"))
    A(steps([("Raise", "a resident taps <i>Raise a complaint</i>; the office can raise one on a resident's behalf (a call to the office, a note at the gate)."),
             ("Work", "<i>Assigned to</i> picks the secretary, the caretaker's login or any office bearer; <i>Mark resolved</i> when the job is done; notes keep the history."),
             ("Close", "the resident closes a resolved complaint, or reopens it from the same page if the problem returns."),
             ("Report", "the dashboard counts open complaints; the unit page lists the unit's history.")]))
    A(sticky("Give the caretaker or facility manager a <i>Secretary</i> login limited to the helpdesk by habit, or create a committee convener for the maintenance committee.", "pink", "Who works tickets"))
    A(chapter(43, "A resident's phone", "Register, see the bills, pay, complain", "Part E · Association"))
    A(fig(["m-assoc-apply", "m-assoc-home", "m-assoc-payments"], "Registration asks for block, unit and occupancy; home shows maintenance due and open complaints; My payments lists the unit's bills with UPI and online payment and the printable statement.", "phones"))
    A(fig(["m-assoc-helpdesk", "m-assoc-ticket-form", "m-assoc-ticket"], "Complaints on the phone: the list, raising one with a photo, and a complaint with its notes.", "phones"))
    A(steps([("Register", "front page → <i>Register as a resident</i>; the office approves and the resident number arrives by WhatsApp."),
             ("Bills", "<i>My payments</i> → the unit's bills with their status; <i>Statement</i> prints the account."),
             ("Pay", "<i>Pay by UPI</i> (QR and the transaction number) or <i>Pay online</i>; the receipt arrives by WhatsApp and the bill turns paid."),
             ("Complain", "<i>Complaints & helpdesk</i> → <i>Raise a complaint</i>; every update is a notification; close it when done.")]))
    A(quest("Mission 13 · As a resident", ["Register a resident against a unit and approve them", "Pay a maintenance bill by UPI claim and confirm it as treasurer", "Raise a complaint on the phone and close it after the office resolves it"], 30))
    A(badges([("🏢", "Association ready", "blue"), ("🧾", "Maintenance collected", "green"), ("🛠️", "Helpdesk master", "orange")]))
    A(part_opener("F", "Reference", "Tables to look things up: permissions, formats, messages, settings, words.", ["Permissions matrix", "Numbering and message templates", "Glossary and FAQ"]))
    A(chapter(44, "Permissions matrix", "", "Part F · Reference"))
    perms = [("members.view", "see the register", "A P S T L"), ("members.manage", "approve, edit, import", "A P S"), ("posts.manage", "publish news and events", "A P S"), ("broadcast.send", "broadcasts", "A P S"),
             ("committees.manage", "committees", "A P S"), ("meetings.manage", "meetings and minutes", "A P S"), ("library.manage", "the library desk", "A S L"), ("finance.view", "see accounts", "A P S T"),
             ("finance.manage", "record receipts and vouchers, confirm claims", "A S T"), ("reports.view", "reports and the annual report", "A P S T L"), ("outbox.view", "the outbox", "A P S"),
             ("finance.close", "close and reopen a financial year", "A T"), ("helpdesk.manage", "assign, update and close complaints", "A P S"),
             ("users.manage", "office bearers' logins", "A S"), ("settings.manage", "settings, backups, subscription", "A")]
    A(table(["Permission", "Allows", "Admin", "President", "Secretary", "Treasurer", "Librarian"],
            [[f"<code>{p}</code>", d, *["●" if k in r.split() else "" for k in "A P S T L".split()]] for p, d, r in perms], "matrix"))
    A("<p class='small'>A committee convener (convener, secretary or chair of a committee) can also schedule that committee's meetings, mark attendance and write and publish its minutes.</p>")
    A(chapter(45, "Numbering formats", "", "Part F · Reference"))
    A(table(["Placeholder", "Means", "Example"], [["{prefix}", "the short name from Settings", "KASC"], ["{year}", "four-digit year", "2026"], ["{yy}", "two-digit year", "26"], ["{seq:04d}", "running number, zero-padded to 4", "0042"], ["{seq}", "running number", "42"]]))
    A("<p>Defaults: membership <code>{prefix}/{year}/{seq:04d}</code>, receipt <code>R/{year}/{seq:04d}</code>, voucher <code>V/{year}/{seq:04d}</code>, accession <code>{seq:05d}</code>. The sequence can restart every year.</p>")
    A(chapter(46, "Automatic messages", "What the app sends on its own", "Part F · Reference"))
    msgs = [("application_received", "to the applicant when the form is sent"), ("application_approved / rejected", "the number and sign-in, or the reason"), ("news / event", "on publish, to the audience"),
            ("event_reminder", "the day before an event the member registered for"), ("registration_confirmed", "on registering"), ("results", "when results are published"),
            ("meeting_notice / mom_published / action_assigned", "committee notices, minutes, action items"), ("book_issued / book_due / book_overdue / reservation_ready", "the library"),
            ("receipt / subscription_due / payment_claimed / payment_rejected / payment_success", "accounts"), ("booking_confirmed / booking_cancelled / asset_due", "facilities and assets"),
            ("blood_request", "to donors of a blood group"), ("poll_open / poll_results", "polls"), ("birthday", "on the member's birthday"), ("password_reset", "the one-time code"),
            ("saas_ending / saas_overdue / saas_suspended", "to office bearers about the club's subscription"),
            ("maintenance_due", "to every resident of a unit in arrears, on <i>Send reminders</i>"), ("ticket_created / ticket_update", "to the resident when a complaint is registered and on every change")]
    A(table(["Template", "When"], [[f"<code>{t}</code>", w] for t, w in msgs]))
    A("<p class='small'>Every template exists in English and Malayalam in <code>app/i18n.py</code>; the member's language decides.</p>")
    A(chapter(47, "Environment variables", "The server's .env", "Part F · Reference"))
    env = [("CLUB_ADMIN_LOGIN / PASSWORD / NAME", "the first administrator, created when the database is empty"), ("CLUB_PUBLIC_URL", "the address used in message links (single club)"), ("CLUB_DATA", "where databases and uploads live"),
           ("CLUB_WA_TOKEN / PHONE_ID / TEMPLATE / TEMPLATE_LANG", "WhatsApp Cloud API"), ("CLUB_SMS_URL / BODY / HEADERS / KEY / SENDER / DLT_TEMPLATE", "SMS gateway"), ("CLUB_SMTP_HOST / PORT / USER / PASS / FROM", "e-mail"),
           ("CLUB_RZP_KEY_ID / KEY_SECRET / WEBHOOK_SECRET", "members' online payments (default for clubs)"), ("CLUB_GDRIVE_SA_JSON / FOLDER, CLUB_BACKUP_HOUR / DIR", "backups"), ("CLUB_DAILY_HOUR", "when the daily jobs run"),
           ("CLUB_MASTER_KEY", "enables the platform console"), ("CLUB_BASE_DOMAIN", "clubs are reachable at <slug>.<base domain>"), ("CLUBPRO_RZP_KEY_ID / KEY_SECRET / WEBHOOK_SECRET", "the operator's Razorpay account for subscriptions")]
    A(table(["Variable", "Purpose"], [[f"<code>{v}</code>", p] for v, p in env]))
    A(chapter(48, "Glossary English · Malayalam", "", "Part F · Reference"))
    gl = [("Member · Membership number", "അംഗം · അംഗത്വ നമ്പർ"), ("Application · Approve · Reject", "അപേക്ഷ · അംഗീകരിക്കുക · നിരസിക്കുക"), ("E-card", "ഇ-കാർഡ്"), ("Family", "കുടുംബം"), ("Blood group", "രക്തഗ്രൂപ്പ്"),
          ("News · Event · Camp · Competition", "വാർത്ത · പരിപാടി · ക്യാമ്പ് · മത്സരം"), ("Register (for an event)", "രജിസ്റ്റർ ചെയ്യുക"), ("Committee · Meeting · Agenda · Minutes", "കമ്മിറ്റി · യോഗം · അജണ്ട · മിനിറ്റ്സ്"),
          ("Resolution · Action item · Plan", "പ്രമേയം · നടപടി · പദ്ധതി"), ("Library · Issue · Return · Renew · Reserve", "ലൈബ്രറി · ഇഷ്യൂ · തിരികെ · പുതുക്കുക · റിസർവ്"), ("Reading room · Periodicals", "വായനശാല · ആനുകാലികങ്ങൾ"),
          ("Subscription · Dues · Receipt · Voucher", "വരിസംഖ്യ · കുടിശ്ശിക · രസീത് · വൗച്ചർ"), ("Donation", "സംഭാവന"), ("Hall booking · Facility", "ഹാൾ ബുക്കിംഗ് · സൗകര്യം"), ("Broadcast · Outbox", "ബ്രോഡ്കാസ്റ്റ് · ഔട്ട്ബോക്സ്"),
          ("Poll · Election · Ballot", "വോട്ടെടുപ്പ് · തിരഞ്ഞെടുപ്പ് · ബാലറ്റ്"), ("Settings · Users · Audit", "ക്രമീകരണങ്ങൾ · ഉപയോക്താക്കൾ · ഓഡിറ്റ്"), ("Subscription plan (ClubPro)", "സബ്സ്ക്രിപ്ഷൻ പ്ലാൻ"), ("Read-only", "വായിക്കാൻ മാത്രം")]
    gl += [("Receipts & Payments · Income & Expenditure · Balance sheet", "വരവ് ചെലവ് കണക്ക് · വരുമാന ചെലവ് കണക്ക് · ബാലൻസ് ഷീറ്റ്"), ("Opening balance · Closing balance · Year close", "ആരംഭ ബാക്കി · അവസാന ബാക്കി · വർഷം അടയ്ക്കൽ"),
           ("Grant · Utilisation certificate", "ഗ്രാന്റ് · വിനിയോഗ സാക്ഷ്യപത്രം"), ("Unit · Block · Resident · Owner · Tenant", "യൂണിറ്റ് · ബ്ലോക്ക് · താമസക്കാരൻ · ഉടമ · വാടകക്കാരൻ"),
           ("Maintenance · Late fee · Complaint", "മെയിന്റനൻസ് · പിഴ · പരാതി")]
    A(table(["English", "മലയാളം"], [[a, f"<span class='ml'>{b}</span>"] for a, b in gl]))
    A(chapter(49, "Frequently asked questions", "", "Part F · Reference"))
    faq = [("A member changed their phone number. How do they sign in?", "The office edits the phone on the member's page (Office → Members). The new number is the login from then on; set a password for them if needed."),
           ("Messages show as <i>demo</i> in the outbox.", "No channel is configured yet. Enter the club's own WhatsApp / SMS / e-mail account under Settings → Communication, or ask the operator to configure the server's. In-app notifications work regardless."),
           ("Can two clubs share one phone number for WhatsApp?", "Yes: leave the club's WhatsApp fields blank and the server's number is used. A club that enters its own number uses that instead."),
           ("We already have 400 members in Excel.", "Office → Members → Import register: download the template, paste your rows, upload. Existing numbers are kept; missing ones are issued."),
           ("Can a member belong to two clubs?", "Yes. Each club is separate; the member signs in to each at its own address, with the same phone number."),
           ("What if we stop paying ClubPro?", "After the end date and 15 days of grace the club becomes read-only: everyone can still sign in, read and export; nothing is deleted. Paying reopens it at once."),
           ("Is our data safe?", "Each club has its own database on the server with nightly backups, optionally copied to Google Drive. Passwords are hashed; every change is logged; uploads are re-encoded; public endpoints are rate-limited."),
           ("Can we use our own domain?", "Yes: point the domain at the server and add it on the platform console (or ask the operator). The certificate is issued automatically on the first visit."),
           ("Can a residents' association use ClubPro?", "Yes. Settings → <i>This organisation is a…</i> → association. Part E covers units, maintenance billing and the helpdesk; everything else works as for a club."),
           ("Our auditor wants Receipts & Payments and a Balance Sheet.", "Accounts → Statements, for any financial year, printable with signature lines; enter opening balances once and close the year after the audit (chapter 23)."),
           ("How do we get help?", "The support contact set by the operator appears under Subscription plan and in reminder messages. The short in-app handbook is under Help in the menu.")]
    A("<dl class='faq'>" + "".join(f"<dt>{q}</dt><dd>{a}</dd>" for q, a in faq) + "</dl>")
    A(close())
    A(close())
    A("<section class='full blank'></section>")
    A("</body></html>")
    with open(os.path.join(HERE, "handbook.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(P))
    print("handbook.html written")




# ---------- the cover and the back cover: full-bleed pages rendered on their own ----------
def _standalone(body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>cover</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Sora:wght@600;700;800&family=Manjari:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="handbook.css"><style>@page{{size:A4;margin:0}}body{{margin:0}}</style></head><body>{body}</body></html>"""


COVER_PARTS = [("A", "Welcome", "How to read this book"), ("B", "Members", "Join, pay, borrow, vote"), ("C", "Office bearers", "Run the club from a laptop"), ("D", "Operator", "Console, pricing, billing"), ("E", "Associations", "Units, maintenance, complaints"), ("F", "Reference", "Permissions, formats, glossary")]


def cover_html():
    return _standalone(f"""<section class='bleed cover'>
<div class='grid'>
  <div class='top'><img class='logo' src='{LOGO_WHITE}' alt='Bpro'><div class='pill'>User Manual &amp; Handbook · v{VERSION}</div></div>
  <div class='title'><div class='kicker'>ClubPro</div><h1>User Manual<br>&amp; Handbook</h1>
    <p class='lead'>Membership · Library &amp; reading room · Events &amp; competitions · Committees &amp; minutes · Accounts &amp; dues · WhatsApp, SMS and e-mail</p>
    <p class='lead2'>For members, office bearers and the club's operator. English, with every screen also in Malayalam.</p>
    <div class='stickers'><span class='sticker'>120 screenshots</span><span class='sticker b'>49 chapters · 6 levels</span><span class='sticker c'>ഇംഗ്ലീഷ് · മലയാളം</span></div></div>
  <div class='shots'><img class='c1' src='{IMG}/d-dashboard.jpg' alt=''><img class='c2' src='{IMG}/m-me.jpg' alt=''></div>
  <div class='cparts'>{''.join(f"<div class='cp'><div class='l' style='background:linear-gradient(135deg,{PART_COLOURS[k][0]},{PART_COLOURS[k][1]})'>{k}</div><div><b>{n}</b><span>{d}</span></div></div>" for k, n, d in COVER_PARTS)}</div>
  <div class='band'><div class='credit'><b>Designed &amp; Developed by {CREDIT_NAME}</b><span>{CREDIT_QUALS}</span><span>{CREDIT_ORG}</span><span class='sites'>{' | '.join(CREDIT_SITES[:2])}</span><span class='sites'>{' | '.join(CREDIT_SITES[2:])}</span></div>
    <div class='ver'><b>Version {VERSION}</b><span>{VERSION_DATE}</span><span>Powered by Team Bpro</span></div></div>
</div></section>""")


def back_html():
    return _standalone(f"""<section class='bleed back'><div class='in'><img class='logo' src='{LOGO_WHITE}' alt='Bpro'>
<div class='brand'>ClubPro</div><p class='tag'>Everything a club needs, under its own name.</p>
<p>Designed &amp; Developed by <b>{CREDIT_NAME}</b><br>{CREDIT_QUALS}<br>{CREDIT_ORG}<br>{' | '.join(CREDIT_SITES)}</p>
<p class='small' style='color:#fff;opacity:.85'>Handbook version {VERSION} · {VERSION_DATE} · Powered by Team Bpro</p></div></section>""")


# ---------- second pass: page numbers for the contents; frame and barcodes on every page ----------
PART_COLOURS = {"A": ("#4F46E5", "#06B6D4"), "B": ("#06B6D4", "#0D9488"), "C": ("#F97316", "#EC4899"), "D": ("#7C3AED", "#EC4899"), "E": ("#0EA5E9", "#6366F1"), "F": ("#84CC16", "#0D9488")}


def page_parts(pdf_path):
    """For every page: the part letter in force (carried forward), and whether the page is a full-bleed opener."""
    import pdfplumber
    import re as _re
    out = []
    part = "A"
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            m = _re.search(r"PART ([A-F]) ·", text)
            opener = bool(_re.search(r"Level [0-9★] ·", text)) and "Chapter" not in text
            if m:
                part = m.group(1)
            elif opener:
                pm = _re.search(r"Part ([A-F])\b", text)
                if pm:
                    part = pm.group(1)
            out.append((part, opener))
    return out


def find_pages(pdf_path):
    """Chapter number -> printed page number, by reading the chapter heads back from the first render."""
    import pdfplumber
    import re as _re
    pages = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            m = _re.search(r"Chapter (\d+) of %d" % TOTAL_CH, text)
            if m and int(m.group(1)) not in pages:
                pages[int(m.group(1))] = i
    return pages


def barcode_overlay(pages_info, out_html):
    """One A4 page per handbook page: a Code128 barcode for the page and, on content pages, a decorative frame in the
    margins coloured by part (a ribbon down the outer edge with the part letter, corner arcs, a hairline under the header)."""
    import barcode
    from barcode.writer import SVGWriter
    import re as _re
    parts = ["<!doctype html><html><head><meta charset='utf-8'><style>@page{size:A4;margin:0}body{margin:0;font-family:Sora,Inter,sans-serif}"
             ".pg{width:210mm;height:297mm;position:relative;page-break-after:always;overflow:hidden}"
             ".bc{position:absolute;right:16mm;bottom:7mm;width:34mm}.bc svg{width:100%;height:auto;display:block}.bc.tile{background:#fff;border-radius:2.5mm;padding:1.5mm 2mm;right:14mm;bottom:6mm;box-shadow:0 2px 6px rgba(0,0,0,.25)}"
             ".frame{position:absolute;inset:0}</style></head><body>"]
    for i, (part, opener) in enumerate(pages_info, 1):
        code = f"CLUBPRO-HB-{VERSION}-P{i:03d}"
        svg = barcode.get("code128", code, writer=SVGWriter()).render({"module_width": 0.2, "module_height": 6.0, "font_size": 5, "text_distance": 1.5, "quiet_zone": 1, "write_text": True}).decode()
        svg = _re.sub(r"<\?xml[^>]*>|<!DOCTYPE[^>]*>", "", svg)
        frame = ""
        if not opener and i > 1 and i < len(pages_info):
            c1, c2 = PART_COLOURS.get(part, PART_COLOURS["A"])
            left = i % 2 == 0  # ribbon on the outer edge: left on even pages, right on odd pages
            x = 5 if left else 201.5
            frame = f"""<svg class='frame' viewBox='0 0 210 297' xmlns='http://www.w3.org/2000/svg'>
<defs><linearGradient id='g{i}' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{c1}'/><stop offset='1' stop-color='{c2}'/></linearGradient>
<linearGradient id='h{i}' x1='0' y1='0' x2='1' y2='0'><stop offset='0' stop-color='{c1}'/><stop offset='1' stop-color='{c2}' stop-opacity='0'/></linearGradient></defs>
<rect x='{x}' y='24' width='3.5' height='249' rx='1.75' fill='url(#g{i})'/>
<circle cx='{x + 1.75}' cy='20' r='4.2' fill='{c1}'/><text x='{x + 1.75}' y='21.6' text-anchor='middle' font-size='4.6' font-weight='800' fill='#fff'>{part}</text>
<circle cx='{x + 1.75}' cy='277' r='1.6' fill='{c2}'/><circle cx='{x + 1.75}' cy='282' r='1.1' fill='{c2}' opacity='.6'/><circle cx='{x + 1.75}' cy='286' r='.7' fill='{c2}' opacity='.35'/>
<rect x='16' y='13.2' width='178' height='.5' fill='url(#h{i})' opacity='.9'/>
<path d='M194 6 a8 8 0 0 1 8 8' stroke='{c2}' stroke-width='.6' fill='none' opacity='.8'/><path d='M8 291 a8 8 0 0 0 8 -8' stroke='{c1}' stroke-width='.6' fill='none' opacity='.8'/>
</svg>"""
        tile = " tile" if i == 1 or i == len(pages_info) else ""
        parts.append(f"<div class='pg'>{frame}<div class='bc{tile}'>{svg}</div></div>")
    parts.append("</body></html>")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("".join(parts))


def stamp_barcodes(pdf_path, overlay_pdf, out_path):
    from pypdf import PdfReader, PdfWriter
    base, over = PdfReader(pdf_path), PdfReader(overlay_pdf)
    w = PdfWriter()
    for i, page in enumerate(base.pages):
        if i < len(over.pages):
            page.merge_page(over.pages[i])
        w.add_page(page)
    # the same screenshot is embedded once per use by Chromium; keep one copy per identical image stream
    import hashlib
    from pypdf.generic import NameObject
    first = {}
    for page in w.pages:
        xo = (page.get("/Resources") or {}).get("/XObject")
        if not xo:
            continue
        xo = xo.get_object()
        for key in list(xo.keys()):
            ref = xo.raw_get(key)
            obj = ref.get_object()
            if obj.get("/Subtype") != "/Image":
                continue
            h = hashlib.sha1(obj.get_data() if hasattr(obj, "get_data") else b"").hexdigest() + f"{obj.get('/Width')}x{obj.get('/Height')}{obj.get('/Filter')}"
            if h in first:
                xo[NameObject(key)] = first[h]
            else:
                first[h] = ref
    w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    w.add_metadata({"/Title": f"ClubPro User Manual & Handbook v{VERSION}", "/Author": f"{CREDIT_NAME}, {CREDIT_ORG}", "/Subject": "ClubPro: club, library and reading-room management", "/Creator": "ClubPro handbook builder"})
    with open(out_path, "wb") as f:
        w.write(f)


def full_build():
    from pypdf import PdfReader, PdfWriter
    render = os.path.join(HERE, "render.js")
    pdf = os.path.join(HERE, "ClubPro-Handbook.pdf")
    body_pdf = os.path.join(HERE, "_body.pdf")
    build()
    subprocess.run(["node", render, os.path.join(HERE, "handbook.html"), body_pdf], check=True)      # pass 1: layout
    PAGES.update(find_pages(body_pdf))
    build()
    subprocess.run(["node", render, os.path.join(HERE, "handbook.html"), body_pdf], check=True)      # pass 2: contents with page numbers
    # the cover and the back cover, full-bleed, swapped in for the placeholders
    extras = {}
    for name, html_fn in (("cover", cover_html), ("back", back_html)):
        h, o = os.path.join(HERE, f"_{name}.html"), os.path.join(HERE, f"_{name}.pdf")
        with open(h, "w", encoding="utf-8") as f:
            f.write(html_fn())
        subprocess.run(["node", render, h, o, "plain"], check=True)
        extras[name] = (h, o)
    body = PdfReader(body_pdf)
    cover, back = PdfReader(extras["cover"][1]), PdfReader(extras["back"][1])
    merged = PdfWriter()
    merged.add_page(cover.pages[0])
    for pg in body.pages[1:-1]:
        merged.add_page(pg)
    merged.add_page(back.pages[0])
    merged_pdf = os.path.join(HERE, "_merged.pdf")
    with open(merged_pdf, "wb") as f:
        merged.write(f)
    info = page_parts(merged_pdf)
    overlay_html = os.path.join(HERE, "_overlay.html")
    overlay_pdf = os.path.join(HERE, "_overlay.pdf")
    barcode_overlay(info, overlay_html)
    subprocess.run(["node", render, overlay_html, overlay_pdf, "plain"], check=True)
    stamp_barcodes(merged_pdf, overlay_pdf, pdf)
    for f in (overlay_html, overlay_pdf, merged_pdf, body_pdf, *[x for pair in extras.values() for x in pair]):
        os.remove(f)
    print(f"{len(info)} pages, contents mapped for {len(PAGES)} chapters, {sum(1 for _, o in info if o)} openers, frame and barcodes stamped")


if __name__ == "__main__":
    if os.environ.get("RENDER", "1") == "1":
        full_build()
    else:
        build()
