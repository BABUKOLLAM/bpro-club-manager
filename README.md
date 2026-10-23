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
app/manage.py      create-admin, seed-demo, daily
app/static/        the PWA: app.js (core) + one file per area, i18n.js, styles.css
tests/             workflow tests
```

Data lives in one SQLite file (`data/club.db`) plus `data/uploads/`; the schema upgrades itself on start.
