# Club Manager · ക്ലബ്ബ് മാനേജർ

Management app for an **Arts & Sports Club cum Library and Reading Room**: membership and family records, news and
events, committees and meetings with online minutes, the library and reading room, accounts, and bilingual
(English / Malayalam) communication by WhatsApp, SMS, e-mail and in-app notifications.

**ആർട്സ് & സ്പോർട്സ് ക്ലബ്ബ്, ലൈബ്രറി & വായനശാല** എന്നിവയ്ക്കുള്ള മാനേജ്മെന്റ് ആപ്പ്: അംഗത്വവും കുടുംബവിവരങ്ങളും, വാർത്തകളും
പരിപാടികളും, കമ്മിറ്റികളും യോഗങ്ങളും ഓൺലൈൻ മിനിറ്റ്സും, ലൈബ്രറിയും വായനശാലയും, കണക്കുകൾ, വാട്സ്ആപ്പ് / SMS / ഇ-മെയിൽ / ആപ്പ്
അറിയിപ്പുകൾ - ഇംഗ്ലീഷിലും മലയാളത്തിലും.

An exclusive product developed by Dr. Babu B., Team Bpro · [www.drbabu.in](https://www.drbabu.in) · [www.bpropms.com](https://www.bpropms.com).

## What it does

| Area | Features |
|---|---|
| **Membership** | Public self-registration (with family members and a password) → secretary approves → **membership number issued** automatically (`ASC/2026/0001`, format configurable) → member is told by WhatsApp / SMS / e-mail and can sign in with their phone. Membership types with admission and annual fees, status changes (active / inactive / suspended / resigned / deceased), office entry of old members with their existing numbers, printable **membership card with QR**, CSV export, timeline of every change. |
| **Family** | Members maintain their own family records (relation, DOB, blood group, education, occupation); the office verifies them. Family members can be registered for events and competitions. |
| **Directory** | Members see each other's name, house, ward, blood group (a blood-donor search) and phone if the member allows it, with one-tap call and WhatsApp. |
| **News & events** | News, notices, events, **camps**, **competitions** and social activities, each bilingual, with level (club / ward / panchayat / district / state / regional / national), venue, cover photo and gallery. Publish → **push to members** by the channels you tick. Public posts get a shareable page (`/p/123`) for WhatsApp groups. Registration with limits, wait-list, fees, family participants; competition items by age group; results entry and announcement. Automatic reminder the day before. |
| **Committees & meetings** | General body, executive and sub-committees with designations and terms. Meetings with bilingual agenda, **notice sent to the committee**, attendance and quorum, decisions and resolutions per agenda item (proposer, seconder, votes), **online minutes (MoM)** visible only to that committee: draft → published (members told) → signed off by the secretary / president and frozen. Printable minutes. **Action items** with owner, due date and progress (the owner is notified), annual **plans** with budget and progress. |
| **Library** | Catalogue with accession-numbered copies, bilingual titles and authors, categories and languages. Issue / return / renew with loan period, book limit, fines (collected as a receipt), reservations with "book ready" messages, due and overdue reminders. Members see their own loans and can renew once online. **Reading room register** and **newspaper / periodical register**. |
| **Accounts** | Receipts (admission, subscription, donation, event fee, fine, sponsorship, grant…) and payment vouchers, numbered per year; the member gets a receipt message. Annual subscription dues generated per membership type, defaulters list, bulk reminders, summaries by head and month, CSV export. Members see their own dues and receipts. |
| **Communication** | One **outbox** for WhatsApp (Meta Cloud API), SMS (any HTTP gateway, DLT-ready), e-mail (SMTP) and in-app notifications, with per-member consent and preferred language. **Broadcast** to all members, a ward, a membership type, a committee, an event's registrants, a blood group, defaulters or a hand-picked list. Until a channel is configured its messages are recorded as *demo* so everything can be tried first. Click-to-chat `wa.me` links everywhere a phone appears. |
| **Daily jobs** | Birthday wishes, event reminders, book due / overdue reminders - automatic, or from the Reports screen. |
| **Sign-in & records** | Forgot-password by a one-time code over WhatsApp / SMS / e-mail. **Excel import** of an existing register (template, preview with row-by-row errors, then commit), **batch printing of membership cards**, photo capture on the application form, a **document library** (bye-laws, circulars, minutes, audit reports) with public / members / committee audience. |
| **Payments by UPI** | A UPI QR and pay link on the member's dues screen, "I have paid" with the UTR, one-click confirmation by the treasurer that issues the receipt. No gateway fees. |
| **QR scanning** | Scan the membership card (or type the number) to mark meeting attendance, event attendance or a reading-room visit in one tap. |
| **Assets & bookings** | Register of chairs, sound system, sports kit and the like with a lending register and overdue reminders; **hall / ground booking** with a calendar, conflict check, member requests, office confirmation and receipt. |
| **Tournaments & fests** | Fixtures with scores and winners for sports; judges with per-item score sheets, average-based ranking and one-click results for arts; a **championship points table** by ward / house / team. |
| **Annual report** | Members, events, meetings and resolutions, library, accounts, bookings and assets for a year, on screen and as a printable bilingual report for the AGM. |
| **Online payments** | Razorpay Checkout (card / UPI / net banking) from the member's dues screen: the server creates the order, verifies the signature and the webhook, issues the receipt and messages the member. Off until the keys are set; the UPI route works without it. |
| **Backups** | A consistent SQLite copy plus the uploads folder every night, with rotation, and pushed to a **Google Drive** folder through a service account when configured. "Back up now" and the last result under Settings. |
| **Polls & elections** | Polls and elections for all members or one committee: candidates picked from the members, one ballot per member, secret ballot by default, seats per voter, results after close or live, voters told on open and on results. |
| **Public website** | `/site`: the club's page with about text, office bearers, upcoming public events, news, photos, documents, contact, map and social links, in English or Malayalam, with Open Graph tags for WhatsApp previews. |
| **Application form & e-card** | A step-by-step application on the phone (about you, contact, family with quick-add chips, selfie or gallery photo resized on the device, sign-in and consent, review) with the draft kept on the device. Every active member gets an **electronic membership card** on their profile: club colours, photo, name in both scripts, number, type, blood group, joined date, validity and the QR the office scans; save as PNG, share, or print. The office prints the same design in batches. |
| **Handbook** | `/help`: a bilingual guide for members and office bearers, printable, linked from the app and the landing page. |
| **Push & scheduling** | **Web Push** notifications to the phone / browser (VAPID, no third-party service), broadcasts scheduled for a later time, a "blood donor request" preset that targets one blood group. |
| **Admin** | Roles (admin, president, secretary, treasurer, librarian, member) with a permission table shown in-app, club settings, numbering formats, membership types and fees, library rules, audit log, dashboard. Installable PWA, works on phones, light and dark. |

## Roles

`PERMS` in `app/auth.py` is the single source of truth; the server checks it on every endpoint and the screens show
only what the signed-in role holds (the table is also visible under *Users & roles*). Committee conveners may manage
their own committee's meetings, minutes and actions without any office role.

| Capability | Admin | President | Secretary | Treasurer | Librarian | Member |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Own profile, family, directory, news, own books, own dues | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Approve applications, edit members, issue numbers | ✔ | ✔ | ✔ | – | – | – |
| Publish news / events, enter results, broadcast | ✔ | ✔ | ✔ | – | – | – |
| Committees, meetings, minutes sign-off | ✔ | ✔ | ✔ | – | – | convener only |
| Library catalogue, issue / return, reading room | ✔ | – | ✔ | – | ✔ | – |
| Accounts, receipts, dues | ✔ | view | ✔ | ✔ | – | – |
| Users & roles | ✔ | – | ✔ | – | – | – |
| Settings, audit log | ✔ | – | – | – | – | – |

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env                       # set CLUB_ADMIN_LOGIN / CLUB_ADMIN_PASSWORD at least
.venv/bin/python -m app.manage seed-demo   # optional: sample members, posts, books (members sign in with phone / member-pass-1)
.venv/bin/uvicorn app.main:app --reload --port 8810
```

Open http://127.0.0.1:8810 - the first administrator is created from `.env` when the database is empty.
With Docker: `docker compose up -d --build` (data in `./data`, port 8810 on localhost; put Caddy or nginx with HTTPS in
front - see `deploy/site.caddy`). Nightly backup: `deploy/backup.sh ./data ./backups`.

### On a VPS (Hostinger KVM, or any Ubuntu / Debian server)

The app is Python, so it needs a VPS rather than shared / Business / Cloud web hosting (those run static, PHP,
Node.js and WordPress only). Point the domain's A record at the server, then on the server:

```bash
curl -fsSL https://raw.githubusercontent.com/BABUKOLLAM/bpro-club-manager/main/deploy/vps-install.sh | sudo bash -s -- club.example.org admin@example.org
```

`deploy/vps-install.sh` installs Docker and Caddy, clones the repository to `/opt/club`, writes `.env` with the
first administrator (the password is printed once), starts the app behind Caddy with automatic HTTPS, opens the
firewall for SSH / 80 / 443 and schedules a nightly backup. Re-run the same command to update.

Tests: `.venv/bin/python -m pytest -q tests`. The suite runs the whole flow (registration → approval → number,
publishing with push, members-only minutes, circulation with fines, accounts, broadcasts, daily jobs) against a
throwaway database with a fake message transport.

## Switching the channels on

Everything works without any gateway: messages are recorded in the **Outbox** as *demo*. Set the variables in
`.env` and restart to go live - see the comments in `.env.example`.

* **WhatsApp** - Meta WhatsApp Cloud API (`CLUB_WA_TOKEN`, `CLUB_WA_PHONE_ID`). Register a message template with one
  `{{1}}` body parameter and set `CLUB_WA_TEMPLATE` so members can be messaged outside the 24-hour window.
* **SMS** - any HTTP gateway through a URL / body template (`CLUB_SMS_URL`, `CLUB_SMS_BODY`, `CLUB_SMS_HEADERS`) with
  `{to}`, `{text}`, `{sender}`, `{dlt}`, `{key}` placeholders; examples for Fast2SMS and MSG91 are in `.env.example`.
  Malayalam SMS is Unicode (70 characters per segment), so the SMS texts are kept short.
* **E-mail** - SMTP (`CLUB_SMTP_HOST/PORT/USER/PASS/FROM`).

Message texts live in `app/i18n.py` (English and Malayalam); UI strings in `app/static/i18n.js`.

**UPI**: enter the club's UPI ID and payee name under *Settings*; members then see a QR / pay link on *My payments*.
**Razorpay**: `CLUB_RZP_KEY_ID`, `CLUB_RZP_KEY_SECRET` and, for the webhook (`/api/payments/razorpay/webhook`, events
`payment.captured` and `order.paid`), `CLUB_RZP_WEBHOOK_SECRET`.
**Google Drive backups**: create a service account in Google Cloud with the Drive API enabled, download its JSON key,
share a Drive folder with the service account's e-mail, then set `CLUB_GDRIVE_SA_JSON` (path or the JSON itself) and
`CLUB_GDRIVE_FOLDER` (the folder ID). `CLUB_BACKUP_HOUR` (default 2) and *Copies to keep* under Settings control the rest.
**Web Push**: nothing to configure - the VAPID key pair is generated on first use and kept in the database. Members
turn notifications on under *My profile → Notification preferences* (the app must be served over HTTPS).

## Multi-club edition

One installation can serve many clubs. Each club has its own database, uploads and backups under
`data/tenants/<slug>/`, its own administrators and settings, and is chosen by the domain the visitor used. The
club that existed before stays the *default* club in `data/`, so a single-club installation keeps working unchanged.

1. Set `CLUB_MASTER_KEY` (a long random string) in `.env` and restart.
2. Open `/_platform`, enter the master key and create a club: slug, names in both languages, its domain(s) and the
   first administrator. From the command line: `python -m app.manage tenant-add kasc "Kottayam Arts & Sports Club" kasc.example.org admin@kasc.org 'password' KSC`.
3. Point the club's domain at the server. With `deploy/site-multi.caddy`, Caddy issues a certificate on the first
   visit, after checking with `/api/_platform/ask` that the domain is registered. Optionally set
   `CLUB_BASE_DOMAIN=clubs.example.org` so every club is also reachable at `<slug>.clubs.example.org`.
4. *Routing* on `/_platform`: list the default club's domains and switch on **strict** once every club has its own
   address, so an unknown host gets "no club at this address" instead of the default club.

A club can be deactivated (taken off the air, data kept) and reactivated. Background work (message outbox, daily
jobs, nightly backups) runs for every club; Drive backups are prefixed with the slug. `python -m app.manage tenants`
lists the clubs with their sizes.

## Protections

Sessions are HttpOnly, SameSite cookies (Secure outside `CLUB_DEV`); every state-changing call needs the `X-Club`
header, so a form on another site cannot act as a member. Passwords are scrypt-hashed; one-time codes are hashed,
single use, 10 minutes, 5 attempts. The public endpoints (sign-in, forgot password, application, applicant photo,
UPI claims, gateway orders) are rate-limited per IP in `app/security.py`, which also sets the security headers and a
Content-Security-Policy on every HTML page. Uploads are decoded and re-encoded (images) or magic-checked (PDF) before
they are stored, and served with `nosniff`. Every printable view escapes what members typed.

## Layout

```
app/main.py        app, sign-in, users, settings, uploads, notifications, outbox, broadcasts, dashboard
app/auth.py        sessions, password hashing, PERMS
app/db.py          SQLite schema (WAL), settings, counters
app/comms.py       outbox, WhatsApp / SMS / e-mail transports, worker
app/i18n.py        message templates EN / ML
app/members.py     applications, members, family, directory, audiences, card, CSV
app/news.py        posts, publish + push, registrations, results, public page
app/committees.py  committees, meetings, agenda, attendance, minutes, actions, plans
app/library.py     books, copies, issue / return / renew, reservations, reading room, periodicals
app/finance.py     receipts, vouchers, dues
app/reports.py     dashboard and reports
app/scheduler.py   daily jobs
app/facilities.py  assets and lending, facilities and bookings
app/push.py        Web Push (VAPID + aes128gcm) without a push library
app/payments.py    Razorpay orders, signature verification, webhook
app/backup.py      nightly backups, Google Drive upload and retention
app/polls.py       polls and elections
app/site.py        the public website page
app/security.py    rate limiting and security headers
app/tenancy.py     multi-club registry, host → club resolution, per-club directories
app/help.py        the bilingual handbook
app/manage.py      create-admin, seed-demo, daily, tenants, tenant-add
app/static/        the PWA: app.js (core) + one file per area, i18n.js, styles.css
tests/             workflow tests
```

Data lives in one SQLite file (`data/club.db`) plus `data/uploads/`; the schema upgrades itself on start. Extra clubs
live under `data/tenants/<slug>/` with the registry in `data/tenants.json`.
