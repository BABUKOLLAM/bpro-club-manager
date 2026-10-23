"""Builds the ClubPro handbook: docs/handbook/handbook.html -> docs/handbook/ClubPro-Handbook.pdf.
Screenshots come from docs/handbook/img (captured from a running demo). Run: python docs/handbook/build.py
Needs Node + Playwright (the render step) - see render.js next to this file."""
import html
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = "img"
e = html.escape
VERSION = "1.0 · October 2026"

# ---------- small builders ----------
def fig(name, caption, kind="desk", w=None):
    """kind: desk (full width), phone (framed), phones (several framed in a row), small (half width)"""
    if kind == "phones":
        names = name if isinstance(name, list) else [name]
        inner = "".join(f"<div class='phone'><img src='{IMG}/{n}.jpg' alt=''></div>" for n in names)
        return f"<figure class='phones'><div class='row'>{inner}</div><figcaption>{caption}</figcaption></figure>"
    if kind == "phone":
        return f"<figure class='phone-fig'><div class='phone'><img src='{IMG}/{name}.jpg' alt=''></div><figcaption>{caption}</figcaption></figure>"
    cls = "small" if kind == "small" else "desk"
    ext = "png" if name == "ecard" else "jpg"
    style = f" style='max-width:{w}'" if w else ""
    return f"<figure class='{cls}'{style}><img src='{IMG}/{name}.{ext}' alt=''><figcaption>{caption}</figcaption></figure>"


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


def chapter(num, title, sub, part):
    pre = close()
    _open[0] = True
    return pre + f"<section class='chapter' id='c{num}'><div class='ch-head'><div class='ch-part'>{e(part)}</div><div class='ch-num'>{num}</div><h1>{e(title)}</h1><p class='ch-sub'>{e(sub)}</p></div>"


def part_opener(letter, title, blurb, items):
    return close() + f"""<section class='part' id='p{letter}'><div class='part-in'><div class='part-letter'>Part {letter}</div><h1>{e(title)}</h1><p>{e(blurb)}</p>
<ul>{''.join(f'<li>{e(i)}</li>' for i in items)}</ul></div></section>"""


# ---------- diagrams (inline SVG) ----------
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manjari:wght@400;700&family=Noto+Sans+Malayalam:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="handbook.css"></head><body>""")
    # ----- cover -----
    A(f"""<section class='cover'>
<div class='cover-top'><div class='brand'>ClubPro</div><div class='by'>Powered by Team Bpro</div></div>
<div class='cover-mid'><h1>User Manual<br>&amp; Handbook</h1><p class='lead'>Membership · Library &amp; reading room · Events &amp; competitions · Committees &amp; minutes · Accounts &amp; dues · WhatsApp, SMS and e-mail</p>
<p class='lead2'>For members, office bearers and the club's operator. In English, with every screen also available in Malayalam.</p></div>
<div class='cover-shots'><img class='c1' src='{IMG}/d-dashboard.jpg' alt=''><img class='c2' src='{IMG}/m-me.jpg' alt=''></div>
<div class='cover-foot'><span>Version {VERSION}</span><span>clubpro · for arts &amp; sports clubs, libraries and reading rooms</span></div></section>""")

    # ----- contents -----
    toc = [("A", "Welcome", ["How to use this book", "Three kinds of reader", "Languages, phones and the installed app"]),
           ("B", "Members' guide", ["Getting started", "Applying for membership", "Signing in and forgotten passwords", "Home and the menu", "Profile, family and the e-card",
                                    "Notifications and preferences", "News, events and competitions", "Library and reading room", "Paying dues and fees", "Documents, bookings, polls, meetings, directory"]),
           ("C", "Office bearers' guide", ["Roles and who can do what", "The dashboard", "First-time setup", "Applications and the members register", "Publishing news, events and competitions",
                                           "Committees, meetings, minutes, actions and plans", "The library desk", "Accounts, dues and payments", "Facilities, assets and documents", "Broadcasts and the outbox",
                                           "Polls and elections", "Scan QR at the door", "Reports, annual report, audit and backups", "The public website and the in-app handbook", "Your ClubPro subscription"]),
           ("D", "Operator's guide", ["How the platform is built", "Installing on a server", "The platform console", "Clubs signing up by themselves", "Billing, reminders and suspension", "White label per club", "Message channels and payment gateways", "Backups and safety"]),
           ("E", "Reference", ["Permissions matrix", "Numbering formats", "Automatic messages", "Environment variables", "Glossary English · Malayalam", "Frequently asked questions"])]
    n = 1
    rows = []
    for letter, title, chs in toc:
        rows.append(f"<div class='toc-part'><span>Part {letter}</span>{e(title)}</div>")
        for c in chs:
            rows.append(f"<div class='toc-row'><span class='n'>{n}</span><span class='t'>{e(c)}</span></div>"); n += 1
    A(f"<section class='toc'><h1>Contents</h1><div class='toc-grid'>{''.join(rows)}</div><p class='toc-note'>Chapter numbers run through the whole book; the PDF's bookmarks (sidebar) jump to any chapter.</p></section>")

    # ================= PART A =================
    A(part_opener("A", "Welcome", "ClubPro runs a club's whole life in one place and in two languages. This book shows every screen, step by step.",
                  ["Who this book is for and how it is arranged", "What the symbols mean", "Phones, computers and the installed app"]))
    A(chapter(1, "How to use this book", "Three readers, one product", "Part A · Welcome"))
    A("""<p>ClubPro is used by three kinds of people, and this book has a part for each:</p>
<div class='three'><div class='card'><b>Members</b><p>Apply, sign in, keep the e-card, register for events, borrow books, pay dues, vote. Mostly on a phone. <span class='ref'>Part B</span></p></div>
<div class='card'><b>Office bearers</b><p>Secretary, president, treasurer, librarian and the administrator: approvals, publishing, minutes, the library desk, accounts, broadcasts, settings. Usually on a laptop. <span class='ref'>Part C</span></p></div>
<div class='card'><b>The operator</b><p>Team Bpro, or whoever runs the server: installing, creating clubs, pricing, billing, channels, backups. <span class='ref'>Part D</span></p></div></div>
<p>Each chapter opens with <i>At a glance</i>, then numbered steps with the screen beside them. Symbols:</p>""")
    A(tip("<b>Tip</b> — a shortcut or a good habit."))
    A(tip("<b>Careful</b> — something that cannot be undone, or that members will notice.", "warn"))
    A(tip("<b>Note</b> — background that explains why the screen behaves as it does.", "note"))
    A(tip("<b>Malayalam</b> — the Malayalam name of the screen or button, as members see it.", "ml"))
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
    A(close())

    # ================= PART B =================
    A(part_opener("B", "Members' guide", "Everything a member does, from the first application to voting in the election, on a phone.",
                  ["Apply in six short steps, with a selfie", "Keep the membership e-card on the phone", "Register the family for events, borrow books, pay by UPI"]))
    A(chapter(4, "Getting started", "From the front page to your first sign-in", "Part B · Members"))
    A(glance(["Your phone number is your login once you are a member.", "Not a member yet? Apply from the front page; the committee approves and you receive your number by WhatsApp or SMS.",
              "Lost the password? One-time code to your phone."]))
    A(fig("m-home", "The member's home page after signing in: upcoming events, the latest news and the menu button (☰) at the top left.", "phone"))
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
    A(fig("m-me", "My profile: the e-card at the top, then your details. Tap <i>Edit</i> to update your phone, address or photo.", "phone"))
    A(fig("ecard", "The e-card as saved to the phone: the club's colours and logo, both scripts, membership type, number, blood group, joined date, validity and the QR.", "desk", "420px"))
    A(steps([("Save to phone", "renders the card as a picture in your gallery."), ("Share", "sends the picture through WhatsApp or any app."), ("Print", "opens a credit-card-sized printable version."),
             ("My family", "add spouse, children, parents; relation, date of birth, blood group, phone. The office marks each one <i>verified</i>."),
             ("Change password", "under the profile tabs; a strong password is 8 characters or more.")]))
    A(fig("m-family", "My family: the people you can register for events, and the blood groups the club's donor search uses.", "phone"))
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
    A(fig(["m-payments", "m-pay-upi"], "My payments, and the UPI sheet with the club's UPI ID, a QR for any UPI app and the <i>I have paid</i> form.", "phones"))
    A(steps([("Open My payments", "the amount due and the items it covers are at the top."), ("Pay by UPI", "scan the QR with Google Pay, PhonePe or any UPI app, or tap <i>Open UPI app</i>."),
             ("I have paid", "enter the 12-digit UTR or transaction ID from your UPI app."), ("Receipt", "the treasurer confirms the payment; your receipt arrives by WhatsApp or e-mail and stays under My payments.")]))
    A(tip("Paying at the office works as before: the treasurer records it and the receipt is messaged to you.", "note"))
    A(chapter(13, "Documents, bookings, polls, meetings, directory", "The rest of the menu", "Part B · Members"))
    A(fig(["m-documents", "m-bookings", "m-polls"], "Documents you may read, the hall and ground calendar with a booking request, and open polls.", "phones"))
    A(fig(["m-meetings", "m-directory"], "Meetings of your committees (and the general body), and the members directory.", "phones"))
    A(steps([("Documents", "bye-laws, circulars, certificates and minutes, each visible to the audience the office chose."),
             ("Hall &amp; ground booking", "pick a date and slot and send a request; the office confirms, and any charge appears under My payments."),
             ("Polls &amp; elections", "one vote per member; a secret ballot never records who chose what. Results appear when voting closes."),
             ("Meetings", "notices, agenda and, once published, the minutes and the action items assigned to you."),
             ("Directory", "members who allowed their phone to be shown; tap to call or WhatsApp.")]))
    A(close())

    # ================= PART C =================
    A(part_opener("C", "Office bearers' guide", "Running the club from a laptop: approvals, publishing, minutes, the library desk, accounts and broadcasts.",
                  ["Set the club up once: names, numbering, membership types, branding, channels", "Approve applications and keep the register", "Publish, broadcast, record minutes, close the accounts"]))
    A(chapter(14, "Roles and who can do what", "Five office roles, one administrator", "Part C · Office"))
    A(glance(["Roles are given under Office → Users by the administrator or secretary.", "A committee convener additionally manages their own committee's meetings and minutes.",
              "The full permissions matrix is in Part E."]))
    A(table(["Role", "Malayalam", "Can"],
            [["Administrator", "അഡ്മിനിസ്ട്രേറ്റർ", "everything, including Settings, Users, backups and the subscription"],
             ["President", "പ്രസിഡന്റ്", "members and applications, publishing, broadcasts, committees and minutes, accounts (view), reports"],
             ["Secretary", "സെക്രട്ടറി", "the same as the president, plus accounts entry, users and the library"],
             ["Treasurer", "ട്രഷറർ", "receipts, vouchers, dues, UPI confirmations, bookings charges, members (view), reports"],
             ["Librarian", "ലൈബ്രേറിയൻ", "catalogue, issue / return, reservations, reading room, periodicals, members (view)"],
             ["Member", "അംഗം", "Part B"]]))
    A(fig("d-landing", "The front page on a laptop. Office bearers sign in here with the e-mail or phone the administrator gave them.", "desk"))
    A(chapter(15, "The dashboard", "The club at a glance", "Part C · Office"))
    A(fig("d-dashboard", "Home for an office bearer: counters that need attention are coloured; each tile opens the matching screen.", "desk"))
    A(table(["Tile", "Means"], [["Pending applications", "applications waiting for approval → Office → Applications"], ["Minutes pending", "meetings that happened without published minutes"],
                               ["Open actions · Overdue", "action items from minutes, and those past their due date"], ["Books out · Overdue books", "loans, and loans past the due date (reminders go automatically)"],
                               ["Members with dues · Outstanding", "who has not paid this year and how much → Office → Dues"], ["Messages pending · failed", "the outbox; <i>demo</i> means a channel is not configured yet"]]))
    A(chapter(16, "First-time setup", "An hour, once", "Part C · Office"))
    A(glance(["Settings holds the club's identity, numbering, membership types, library rules, website, branding and channels.", "Users &amp; roles gives office bearers their sign-in.", "Import the old register from Excel; members then sign in with their phone number."]))
    A(fig("d-settings", "Settings → Club: names in both scripts, short name (used in membership numbers), registration number, place, address, phone, default language, self-registration, wards, UPI ID.", "desk"))
    A(steps([("Club", "names in both scripts, short name, registration number, address, phone, e-mail. Tick <i>Allow self-registration</i> if people may apply online. List the wards; enter the club's UPI ID so members can pay."),
             ("Numbering", "membership, receipt, voucher and accession number formats with placeholders ({prefix} {year} {yy} {seq:04d}); whether the sequence restarts each year; subscription due month."),
             ("Membership types &amp; fees", "life, ordinary, associate, student, honorary — or your own, with admission and annual fees in rupees. These drive dues."),
             ("Library", "loan period, books per member, fine per day, online renewals; event reminder days."),
             ("Website", "about text in both languages, map link, social links and a cover photo for the public website."),
             ("Branding", "logo, primary and accent colour, app name, footer credit (chapter 37 explains)."),
             ("Communication", "channel status and, if the club has its own WhatsApp / SMS / e-mail / Razorpay accounts, their keys."),
             ("Save", "the button at the bottom saves every card at once.")]))
    A(fig("d-settings-numbering", "Numbering: the formats and the sequence rule.", "desk"))
    A(fig("d-settings-brand", "Branding: the live preview shows the colours; the logo also becomes the phone icon and appears on the e-card.", "desk"))
    A(fig("d-settings-channels", "Communication: pills show which channels are on and whether the club's own account or the server's is in use.", "desk"))
    A(fig("d-users", "Office → Users: add an office bearer with login, role and, optionally, their member record; reset passwords; deactivate.", "desk"))
    A(tip("Give every office bearer their own login. The audit log then shows who approved, published or recorded what.", "tip"))
    A(chapter(17, "Applications and the members register", "Approve, number, maintain", "Part C · Office"))
    A(glance(["Approving issues the next membership number and messages the member their number and sign-in.", "The member page holds everything: details, family, payments, books, timeline, e-card.",
              "The old register can be imported from Excel in one go."]))
    A(flow([("Applied", "from the phone"), ("Approve / reject", "Office → Applications"), ("Number issued", "format from Settings"), ("Member messaged", "number + sign-in"), ("Active", "on the register")], accent=True))
    A(fig("d-applications", "Applications: every pending application with the details it was sent with.", "desk"))
    A(fig("d-application-detail", "Approve, reject (with a reason the applicant receives) or open the full details. WhatsApp and Call reach the applicant directly.", "desk"))
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
    A(chapter(18, "Publishing news, events and competitions", "One post, every channel", "Part C · Office"))
    A(glance(["A post can be news, an event, a camp, a social activity or a competition, with dates, venue, fee and registration.", "Publish and notify sends it to the chosen audience by WhatsApp, SMS, e-mail and push in one click.",
              "Competitions carry items, teams, fixtures, judges, scores and a points table; results are published to everyone."]))
    A(fig("d-posts", "News &amp; events for the office: drafts and published posts, with registrations and results.", "desk"))
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
    A(fig("d-meeting", "A meeting page: status, agenda with decisions, attendance and action items.", "desk"))
    A(fig("d-actions", "Action items across all meetings, with owner, due date and status.", "desk"))
    A(fig("d-plans", "Plans: programmes, owners, budgets and progress.", "desk"))
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
    A(chapter(21, "Accounts, dues and payments", "Receipts, vouchers, UPI and online", "Part C · Office"))
    A(glance(["Every rupee in or out is a receipt or a voucher under a standard head (admission, subscription, donation, event fee, rent, salary…).", "Dues are computed from membership types and the subscription year; reminders go automatically.",
              "Members' UPI claims are confirmed by the treasurer; online payments through Razorpay settle themselves."]))
    A(fig("d-finance", "Accounts: the cash book with receipts and vouchers, filters by head and period, totals.", "desk"))
    A(fig("d-tx-form", "Recording a receipt or voucher: head, member (for receipts), amount, mode, reference, note. The receipt is messaged to the member.", "desk"))
    A(steps([("Record", "a receipt (money in) or a voucher (money out); choose the head; for a member's payment pick the member and the receipt goes to them."),
             ("Dues", "who owes what this year; send reminders to all or to one; record a payment straight from the row."),
             ("UPI claims", "members who paid by UPI and sent the UTR; check your bank app, then confirm (receipt issued) or reject (the member is told why)."),
             ("Online payments", "orders and settlements from Razorpay, with the receipt each produced."),
             ("Reports", "the annual statement by head is in Reports → Annual report.")]))
    A(fig("d-dues", "Dues: outstanding amounts by member, with reminders and quick recording.", "desk"))
    A(fig("d-claims", "UPI claims waiting for confirmation.", "small"))
    A(fig("d-online", "Online payments received through Razorpay.", "small"))
    A(tip("Receipts cannot be deleted, only reversed with a voucher, so the cash book always matches what was messaged to members.", "warn"))
    A(chapter(22, "Facilities, assets and documents", "Halls, grounds, equipment, papers", "Part C · Office"))
    A(fig("d-bookings", "Hall &amp; ground booking: the calendar, requests to confirm, rates per facility.", "desk"))
    A(fig("d-facility-form", "Adding a facility with its rate and rules.", "small"))
    A(steps([("Facilities", "add the hall, ground, stage, sound system… with a rate (per hour or per day) and whether members may request online."),
             ("Bookings", "confirm or decline requests; a confirmed booking with a charge appears in the member's dues and the receipt is issued on payment."),
             ("Assets", "the asset register with categories, purchase details and value; lend an asset to a member and track its return."),
             ("Documents", "upload bye-laws, circulars, certificates, minutes; choose the audience (public, members, committee, office).")]))
    A(fig("d-assets", "Assets and lending.", "small"))
    A(fig("d-documents", "Documents with audience control.", "small"))
    A(fig("d-document-form", "Adding a document.", "small"))
    A(chapter(23, "Broadcasts and the outbox", "Reach everyone, see what was delivered", "Part C · Office"))
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
    A(chapter(24, "Polls and elections", "One member, one vote", "Part C · Office"))
    A(fig("d-polls", "Polls &amp; elections for the office: open, closed, results.", "desk"))
    A(fig("d-poll-form", "Creating a poll: question, options (or candidates), who may vote, secret or open, closing time.", "desk"))
    A(steps([("New poll", "a question with options, or an election with posts and candidates; choose the electorate (all members, a type, a committee)."),
             ("Secret ballot", "records that a member voted, never what they chose."), ("Open", "members are notified; the poll appears under Polls &amp; elections."),
             ("Close", "automatically at the closing time; results are published and notified.")]))
    A(chapter(25, "Scan QR at the door", "Meetings, events, reading room", "Part C · Office"))
    A(fig("d-scan", "Scan QR: point the laptop or phone camera at a member's e-card; the member is identified and marked present, registered or signed in to the reading room.", "desk"))
    A(tip("On a phone, Scan QR uses the back camera; the office bearer's phone becomes the attendance desk.", "tip"))
    A(chapter(26, "Reports, annual report, audit and backups", "Numbers for the general body", "Part C · Office"))
    A(fig("d-reports", "Reports: members by type, ward, gender, blood group, age band and joining year; events; library; accounts.", "desk"))
    A(fig("d-annual", "The annual report for the general body: office bearers, membership, events, meetings and resolutions, accounts by head, library; printable.", "desk"))
    A(fig("d-audit", "The audit log: who did what and when.", "desk"))
    A(steps([("Annual report", "pick the year; print or save as PDF for the general body."), ("Audit", "every approval, publication, receipt, settings change and sign-in, with the user and time."),
             ("Backups", "Settings → Backups shows the nightly copies and lets you take one now; with Google Drive configured, copies go off-site.")]))
    A(chapter(27, "The public website and the in-app handbook", "What the world sees", "Part C · Office"))
    A(fig("d-site", "The club's public website at /site: about, office bearers with photos, upcoming events, news, documents, photos, contact and social links; in both languages; shareable.", "desk"))
    A(fig("d-help", "The in-app handbook at /help: the short bilingual guide members and office bearers can open from the menu.", "desk"))
    A(chapter(28, "Your ClubPro subscription", "What the club pays, and what happens if it does not", "Part C · Office"))
    A(glance(["Office → Subscription plan shows the status, the end date, the active members and next year's price.", "Pay online (card / UPI) or by UPI with the transaction reference; the operator confirms it.",
              "After the end date there are 15 days of grace; then the club becomes read-only until paid. Nothing is deleted."]))
    A(lifecycle_svg())
    A(fig("d-plan", "Subscription plan: status, dates, members, price, and the payment history.", "desk"))
    A(fig("d-plan-upi", "Paying by UPI to the operator and sending the reference.", "desk"))
    A(table(["Active members", "Price per year"], [["up to 49", "₹2,500 flat"], ["50 to 99", "₹120 per member (₹6,000 – ₹11,880)"], ["100 and above", "₹120 per member"]]))
    A(tip("The price is worked out from the live member count on the day you pay, so a growing club simply pays a little more at its next renewal. Office bearers are reminded 7 days before the end.", "note"))
    A(close())

    # ================= PART D =================
    A(part_opener("D", "Operator's guide", "For Team Bpro or anyone running ClubPro as a service: the server, the console, pricing, billing and channels.",
                  ["One server, many clubs, each isolated", "Clubs sign up by themselves and pay yearly", "Operator keys, channels and backups"]))
    A(chapter(29, "How the platform is built", "One server, many clubs", "Part D · Operator"))
    A(arch_svg())
    A("""<p>ClubPro is a single Python application (FastAPI) with one SQLite database per club, a browser app that installs on phones, and background workers for messages, daily jobs and backups. Caddy in front provides HTTPS for every club's domain automatically. The first club on a server is the <i>default</i> club and lives directly in the data folder; every further club lives under <code>data/tenants/&lt;slug&gt;/</code>. The visitor's domain picks the club; the operator's own pages (<code>/signup</code>, <code>/pricing</code>, <code>/_platform</code>) answer on any domain.</p>""")
    A(chapter(30, "Installing on a server", "A VPS, a domain, fifteen minutes", "Part D · Operator"))
    A(steps([("Get a VPS", "Ubuntu or Debian, 1 vCPU / 2 GB is enough for dozens of clubs. Shared web hosting cannot run it (it is Python, not PHP)."),
             ("Point DNS", "an A record for the platform domain (e.g. clubpro.in) and a wildcard record (*.clubpro.in) at the server; clubs with their own domains point theirs the same way."),
             ("Run the installer", "<code>curl -fsSL https://raw.githubusercontent.com/BABUKOLLAM/bpro-club-manager/main/deploy/vps-install.sh | sudo bash -s -- clubpro.in admin@teambpro.in</code> installs Docker and Caddy, clones the app to /opt/club, writes .env and starts everything."),
             ("Multi-club Caddy", "replace the site file with <code>deploy/site-multi.caddy</code> so certificates are issued on demand for every registered domain."),
             ("Set the operator keys", "in /opt/club/.env: <code>CLUB_MASTER_KEY</code>, <code>CLUB_BASE_DOMAIN=clubpro.in</code>, <code>CLUBPRO_RZP_*</code>, and the server's SMS / WhatsApp / SMTP settings used for signup codes and as the default for clubs. Restart with <code>docker compose up -d</code>."),
             ("Open the console", "https://clubpro.in/_platform with the master key: set the product name, the footer credit, pricing, your UPI ID and support contact.")]))
    A(tip("Re-running the installer command updates the app in place. Data, uploads and .env are kept.", "tip"))
    A(chapter(31, "The platform console", "Every club, every rupee", "Part D · Operator"))
    A(fig("d-platform", "The console: subscriptions summary, per-club status and actions, the club list with sizes and backups, add a club, routing, pricing and the operator's UPI and support contact.", "desk"))
    A(steps([("Subscriptions", "clubs by status, yearly run-rate, amount collected, trials ending this week, UPI claims to confirm."),
             ("Per club", "Mark paid (amount and reference), Extend trial, Suspend / Reopen, Confirm or Reject a UPI claim."),
             ("Clubs", "members, applications, last backup; edit domains; deactivate / activate."),
             ("Add a club", "for clubs you onboard yourself: slug, names, domains, first administrator."),
             ("Routing", "the default club's domains; whether unknown host names show the default club or <i>no club at this address</i>."),
             ("Pricing", "flat price and member limit, per-member price, trial and grace days, UPI ID and payee name, support contact.")]))
    A(chapter(32, "Clubs signing up by themselves", "/signup and /pricing", "Part D · Operator"))
    A(fig("d-pricing", "The pricing page: the rule, the trial, and every service in both languages.", "desk"))
    A(fig("m-signup", "The signup form on a phone: club, web address, secretary, mobile, password, consent.", "phone"))
    A(flow([("Fill the form", "/signup"), ("Code by SMS", "operator's channel"), ("Club created", "<slug>.clubpro.in"), ("Trial", "30 days"), ("Pays", "online or UPI")], accent=True))
    A(tip("Signup codes go through the server's SMS or WhatsApp channel. If none is configured the club is created without a code — fine for a trial server, not for the public.", "warn"))
    A(chapter(33, "Billing, reminders and suspension", "Trial → active → due → read-only", "Part D · Operator"))
    A(lifecycle_svg())
    A(steps([("Online", "the club pays through your Razorpay account from its Subscription plan screen; the plan is extended by a year at once; the webhook is the safety net if the browser closes."),
             ("UPI", "the club pays to your UPI ID and sends the reference; it appears as a claim on the console; confirm after checking your bank."),
             ("Manual", "Mark paid for cash, cheque or bank transfer."),
             ("Reminders", "the daily job messages the club's office bearers 7 days before the end, when payment is due, and when the club becomes read-only."),
             ("Read-only", "sign-in, reading and paying keep working; every other change is refused with a clear message; nothing is deleted. Reopen from the console if needed.")]))
    A(chapter(34, "White label per club", "Their name, your product", "Part D · Operator"))
    A("""<p>Each club sets its own logo, colours, app name and footer under Settings → Branding (chapter 16). The platform's product name and the "Powered by" footer that new clubs start with are set on the console. A club may also enter its own WhatsApp, SMS, SMTP and Razorpay accounts; blank fields inherit the server's. Secrets are stored per club and shown masked.</p>""")
    A(fig("d-settings-brand", "Branding settings as a club sees them.", "desk"))
    A(chapter(35, "Message channels and payment gateways", "What to set up where", "Part D · Operator"))
    A(table(["Channel", "Provider", "Set up", "Notes"],
            [["WhatsApp", "Meta WhatsApp Cloud API", "a Meta business app, a phone number ID and a permanent system-user token; an approved message template with one {{1}} parameter", "needed to message members outside the 24-hour window; template approval takes a day or two"],
             ["SMS", "any HTTP gateway (Fast2SMS, Textlocal, MSG91…)", "the gateway URL with placeholders {to} {text} {sender} {dlt} {key}; a DLT-registered template", "Malayalam SMS is 70 characters per segment"],
             ["E-mail", "any SMTP account", "host, port, user, password, from address", "Gmail needs an app password"],
             ["Push", "built in", "nothing", "free; the app must be served over HTTPS"],
             ["Members' online payment", "Razorpay (club's account)", "key ID, secret, webhook secret; webhook URL /api/payments/razorpay/webhook", "per club under Settings or in the server's .env"],
             ["Subscription payment", "Razorpay (operator's account)", "CLUBPRO_RZP_KEY_ID / SECRET / WEBHOOK_SECRET; webhook URL /api/saas/webhook", "operator only"]]))
    A(chapter(36, "Backups and safety", "Sleep well", "Part D · Operator"))
    A(steps([("Nightly backups", "every club's database and uploads are copied each night; the console shows the last backup per club."),
             ("Google Drive", "a service account and a shared folder push copies off the server; retention is per club."),
             ("Protections", "HttpOnly cookies, a header on every change (no cross-site actions), scrypt passwords, one-time codes that expire, rate limits on public endpoints, re-encoded uploads, security headers and a content policy on every page."),
             ("Updates", "re-run the installer; the schema upgrades itself; restart with docker compose."),
             ("Data requests", "a club's data is one folder; export or delete it as a unit when a club leaves.")]))
    A(close())

    # ================= PART E =================
    A(part_opener("E", "Reference", "Tables to look things up: permissions, formats, messages, settings, words.", ["Permissions matrix", "Numbering and message templates", "Glossary and FAQ"]))
    A(chapter(37, "Permissions matrix", "", "Part E · Reference"))
    perms = [("members.view", "see the register", "A P S T L"), ("members.manage", "approve, edit, import", "A P S"), ("posts.manage", "publish news and events", "A P S"), ("broadcast.send", "broadcasts", "A P S"),
             ("committees.manage", "committees", "A P S"), ("meetings.manage", "meetings and minutes", "A P S"), ("library.manage", "the library desk", "A S L"), ("finance.view", "see accounts", "A P S T"),
             ("finance.manage", "record receipts and vouchers, confirm claims", "A S T"), ("reports.view", "reports and the annual report", "A P S T L"), ("outbox.view", "the outbox", "A P S"),
             ("users.manage", "office bearers' logins", "A S"), ("settings.manage", "settings, backups, subscription", "A")]
    A(table(["Permission", "Allows", "Admin", "President", "Secretary", "Treasurer", "Librarian"],
            [[f"<code>{p}</code>", d, *["●" if k in r.split() else "" for k in "A P S T L".split()]] for p, d, r in perms], "matrix"))
    A("<p class='small'>A committee convener (convener, secretary or chair of a committee) can also schedule that committee's meetings, mark attendance and write and publish its minutes.</p>")
    A(chapter(38, "Numbering formats", "", "Part E · Reference"))
    A(table(["Placeholder", "Means", "Example"], [["{prefix}", "the short name from Settings", "KASC"], ["{year}", "four-digit year", "2026"], ["{yy}", "two-digit year", "26"], ["{seq:04d}", "running number, zero-padded to 4", "0042"], ["{seq}", "running number", "42"]]))
    A("<p>Defaults: membership <code>{prefix}/{year}/{seq:04d}</code>, receipt <code>R/{year}/{seq:04d}</code>, voucher <code>V/{year}/{seq:04d}</code>, accession <code>{seq:05d}</code>. The sequence can restart every year.</p>")
    A(chapter(39, "Automatic messages", "What the app sends on its own", "Part E · Reference"))
    msgs = [("application_received", "to the applicant when the form is sent"), ("application_approved / rejected", "the number and sign-in, or the reason"), ("news / event", "on publish, to the audience"),
            ("event_reminder", "the day before an event the member registered for"), ("registration_confirmed", "on registering"), ("results", "when results are published"),
            ("meeting_notice / mom_published / action_assigned", "committee notices, minutes, action items"), ("book_issued / book_due / book_overdue / reservation_ready", "the library"),
            ("receipt / subscription_due / payment_claimed / payment_rejected / payment_success", "accounts"), ("booking_confirmed / booking_cancelled / asset_due", "facilities and assets"),
            ("blood_request", "to donors of a blood group"), ("poll_open / poll_results", "polls"), ("birthday", "on the member's birthday"), ("password_reset", "the one-time code"),
            ("saas_ending / saas_overdue / saas_suspended", "to office bearers about the club's subscription")]
    A(table(["Template", "When"], [[f"<code>{t}</code>", w] for t, w in msgs]))
    A("<p class='small'>Every template exists in English and Malayalam in <code>app/i18n.py</code>; the member's language decides.</p>")
    A(chapter(40, "Environment variables", "The server's .env", "Part E · Reference"))
    env = [("CLUB_ADMIN_LOGIN / PASSWORD / NAME", "the first administrator, created when the database is empty"), ("CLUB_PUBLIC_URL", "the address used in message links (single club)"), ("CLUB_DATA", "where databases and uploads live"),
           ("CLUB_WA_TOKEN / PHONE_ID / TEMPLATE / TEMPLATE_LANG", "WhatsApp Cloud API"), ("CLUB_SMS_URL / BODY / HEADERS / KEY / SENDER / DLT_TEMPLATE", "SMS gateway"), ("CLUB_SMTP_HOST / PORT / USER / PASS / FROM", "e-mail"),
           ("CLUB_RZP_KEY_ID / KEY_SECRET / WEBHOOK_SECRET", "members' online payments (default for clubs)"), ("CLUB_GDRIVE_SA_JSON / FOLDER, CLUB_BACKUP_HOUR / DIR", "backups"), ("CLUB_DAILY_HOUR", "when the daily jobs run"),
           ("CLUB_MASTER_KEY", "enables the platform console"), ("CLUB_BASE_DOMAIN", "clubs are reachable at <slug>.<base domain>"), ("CLUBPRO_RZP_KEY_ID / KEY_SECRET / WEBHOOK_SECRET", "the operator's Razorpay account for subscriptions")]
    A(table(["Variable", "Purpose"], [[f"<code>{v}</code>", p] for v, p in env]))
    A(chapter(41, "Glossary English · Malayalam", "", "Part E · Reference"))
    gl = [("Member · Membership number", "അംഗം · അംഗത്വ നമ്പർ"), ("Application · Approve · Reject", "അപേക്ഷ · അംഗീകരിക്കുക · നിരസിക്കുക"), ("E-card", "ഇ-കാർഡ്"), ("Family", "കുടുംബം"), ("Blood group", "രക്തഗ്രൂപ്പ്"),
          ("News · Event · Camp · Competition", "വാർത്ത · പരിപാടി · ക്യാമ്പ് · മത്സരം"), ("Register (for an event)", "രജിസ്റ്റർ ചെയ്യുക"), ("Committee · Meeting · Agenda · Minutes", "കമ്മിറ്റി · യോഗം · അജണ്ട · മിനിറ്റ്സ്"),
          ("Resolution · Action item · Plan", "പ്രമേയം · നടപടി · പദ്ധതി"), ("Library · Issue · Return · Renew · Reserve", "ലൈബ്രറി · ഇഷ്യൂ · തിരികെ · പുതുക്കുക · റിസർവ്"), ("Reading room · Periodicals", "വായനശാല · ആനുകാലികങ്ങൾ"),
          ("Subscription · Dues · Receipt · Voucher", "വരിസംഖ്യ · കുടിശ്ശിക · രസീത് · വൗച്ചർ"), ("Donation", "സംഭാവന"), ("Hall booking · Facility", "ഹാൾ ബുക്കിംഗ് · സൗകര്യം"), ("Broadcast · Outbox", "ബ്രോഡ്കാസ്റ്റ് · ഔട്ട്ബോക്സ്"),
          ("Poll · Election · Ballot", "വോട്ടെടുപ്പ് · തിരഞ്ഞെടുപ്പ് · ബാലറ്റ്"), ("Settings · Users · Audit", "ക്രമീകരണങ്ങൾ · ഉപയോക്താക്കൾ · ഓഡിറ്റ്"), ("Subscription plan (ClubPro)", "സബ്സ്ക്രിപ്ഷൻ പ്ലാൻ"), ("Read-only", "വായിക്കാൻ മാത്രം")]
    A(table(["English", "മലയാളം"], [[a, f"<span class='ml'>{b}</span>"] for a, b in gl]))
    A(chapter(42, "Frequently asked questions", "", "Part E · Reference"))
    faq = [("A member changed their phone number. How do they sign in?", "The office edits the phone on the member's page (Office → Members). The new number is the login from then on; set a password for them if needed."),
           ("Messages show as <i>demo</i> in the outbox.", "No channel is configured yet. Enter the club's own WhatsApp / SMS / e-mail account under Settings → Communication, or ask the operator to configure the server's. In-app notifications work regardless."),
           ("Can two clubs share one phone number for WhatsApp?", "Yes: leave the club's WhatsApp fields blank and the server's number is used. A club that enters its own number uses that instead."),
           ("We already have 400 members in Excel.", "Office → Members → Import register: download the template, paste your rows, upload. Existing numbers are kept; missing ones are issued."),
           ("Can a member belong to two clubs?", "Yes. Each club is separate; the member signs in to each at its own address, with the same phone number."),
           ("What if we stop paying ClubPro?", "After the end date and 15 days of grace the club becomes read-only: everyone can still sign in, read and export; nothing is deleted. Paying reopens it at once."),
           ("Is our data safe?", "Each club has its own database on the server with nightly backups, optionally copied to Google Drive. Passwords are hashed; every change is logged; uploads are re-encoded; public endpoints are rate-limited."),
           ("Can we use our own domain?", "Yes: point the domain at the server and add it on the platform console (or ask the operator). The certificate is issued automatically on the first visit."),
           ("How do we get help?", "The support contact set by the operator appears under Subscription plan and in reminder messages. The short in-app handbook is under Help in the menu.")]
    A("<dl class='faq'>" + "".join(f"<dt>{q}</dt><dd>{a}</dd>" for q, a in faq) + "</dl>")
    A(close())
    A(f"""<section class='back'><div class='brand'>ClubPro</div><p>Everything a club needs, under its own name.</p><p class='small'>Handbook version {VERSION} · Powered by Team Bpro</p></section>""")
    A("</body></html>")
    with open(os.path.join(HERE, "handbook.html"), "w", encoding="utf-8") as f:
        f.write("\n".join(P))
    print("handbook.html written")


if __name__ == "__main__":
    build()
    if os.environ.get("RENDER", "1") == "1":
        subprocess.run(["node", os.path.join(HERE, "render.js")], check=True)
