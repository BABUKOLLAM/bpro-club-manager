"""SQLite storage for the club app. One file database in WAL mode, a single writer lock, JSON in a few columns.

Every table is created with IF NOT EXISTS and new columns are added by `_migrate`, so an old database opens on a
new build without a separate migration tool.
"""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager

from . import tenancy

DATA_DIR = os.environ.get("CLUB_DATA", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
_locks = {}
_locks_guard = threading.Lock()


def slug():
    return tenancy.current.get()


def data_dir():
    return tenancy.tenant_dir(slug())


def db_path():
    return os.path.join(data_dir(), "club.db")


def upload_dir():
    return os.path.join(data_dir(), "uploads")


def _lock_for(s=None):
    s = s or slug()
    with _locks_guard:
        if s not in _locks:
            _locks[s] = threading.RLock()
        return _locks[s]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, login TEXT UNIQUE NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
  pw_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, member_id INTEGER, lang TEXT NOT NULL DEFAULT 'en', created REAL NOT NULL,
  last_login REAL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL, last_seen REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS counters(key TEXT PRIMARY KEY, value INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY, member_no TEXT UNIQUE, status TEXT NOT NULL DEFAULT 'applied',
  name_en TEXT NOT NULL, name_ml TEXT NOT NULL DEFAULT '', gender TEXT NOT NULL DEFAULT '', dob TEXT NOT NULL DEFAULT '',
  blood_group TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', whatsapp TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
  house_en TEXT NOT NULL DEFAULT '', house_ml TEXT NOT NULL DEFAULT '', address_en TEXT NOT NULL DEFAULT '', address_ml TEXT NOT NULL DEFAULT '',
  ward TEXT NOT NULL DEFAULT '', pincode TEXT NOT NULL DEFAULT '', occupation TEXT NOT NULL DEFAULT '', education TEXT NOT NULL DEFAULT '',
  membership_type TEXT NOT NULL DEFAULT 'ordinary', interests TEXT NOT NULL DEFAULT '', id_proof TEXT NOT NULL DEFAULT '',
  photo TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  notify_whatsapp INTEGER NOT NULL DEFAULT 1, notify_sms INTEGER NOT NULL DEFAULT 1, notify_email INTEGER NOT NULL DEFAULT 1,
  show_phone INTEGER NOT NULL DEFAULT 1, lang TEXT NOT NULL DEFAULT 'ml',
  applied_at REAL NOT NULL, approved_at REAL, approved_by INTEGER, joined_on TEXT NOT NULL DEFAULT '', decision_note TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL, updated REAL NOT NULL, introduced_by INTEGER);
CREATE INDEX IF NOT EXISTS ix_members_status ON members(status);
CREATE INDEX IF NOT EXISTS ix_members_phone ON members(phone);
CREATE TABLE IF NOT EXISTS family(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, name_en TEXT NOT NULL, name_ml TEXT NOT NULL DEFAULT '',
  relation TEXT NOT NULL DEFAULT '', gender TEXT NOT NULL DEFAULT '', dob TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
  blood_group TEXT NOT NULL DEFAULT '', education TEXT NOT NULL DEFAULT '', occupation TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL, updated REAL NOT NULL, verified INTEGER NOT NULL DEFAULT 0, deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_family_member ON family(member_id);
CREATE TABLE IF NOT EXISTS member_log(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, ts REAL NOT NULL, user_id INTEGER, kind TEXT NOT NULL, text TEXT NOT NULL DEFAULT '');

CREATE TABLE IF NOT EXISTS posts(id INTEGER PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'news', status TEXT NOT NULL DEFAULT 'draft',
  title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '', body_en TEXT NOT NULL DEFAULT '', body_ml TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '', level TEXT NOT NULL DEFAULT 'club', starts_at TEXT NOT NULL DEFAULT '', ends_at TEXT NOT NULL DEFAULT '',
  venue_en TEXT NOT NULL DEFAULT '', venue_ml TEXT NOT NULL DEFAULT '', cover TEXT NOT NULL DEFAULT '', audience TEXT NOT NULL DEFAULT 'members',
  committee_id INTEGER, pinned INTEGER NOT NULL DEFAULT 0, reg_open INTEGER NOT NULL DEFAULT 0, reg_limit INTEGER NOT NULL DEFAULT 0,
  reg_fee REAL NOT NULL DEFAULT 0, reg_family INTEGER NOT NULL DEFAULT 1, reg_closes TEXT NOT NULL DEFAULT '',
  organiser TEXT NOT NULL DEFAULT '', contact_phone TEXT NOT NULL DEFAULT '',
  results_en TEXT NOT NULL DEFAULT '', results_ml TEXT NOT NULL DEFAULT '', results_at REAL,
  created_by INTEGER NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, published_at REAL, notified_at REAL, reminded_at REAL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_posts_kind ON posts(kind, status, starts_at);
CREATE TABLE IF NOT EXISTS post_files(id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, filename TEXT NOT NULL, mime TEXT NOT NULL, path TEXT NOT NULL,
  caption TEXT NOT NULL DEFAULT '', created REAL NOT NULL, uploaded_by INTEGER);
CREATE TABLE IF NOT EXISTS comp_items(id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, idx INTEGER NOT NULL DEFAULT 0, name_en TEXT NOT NULL, name_ml TEXT NOT NULL DEFAULT '',
  age_group TEXT NOT NULL DEFAULT '', gender TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'individual', max_entries INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS registrations(id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, member_id INTEGER NOT NULL, family_id INTEGER,
  item_id INTEGER, participant_name TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'registered', note TEXT NOT NULL DEFAULT '',
  fee_paid INTEGER NOT NULL DEFAULT 0, receipt_id INTEGER, created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_reg_post ON registrations(post_id, status);
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, item_id INTEGER, position INTEGER NOT NULL DEFAULT 1,
  registration_id INTEGER, participant_name TEXT NOT NULL DEFAULT '', team TEXT NOT NULL DEFAULT '', points REAL NOT NULL DEFAULT 0,
  remark TEXT NOT NULL DEFAULT '', created REAL NOT NULL);

CREATE TABLE IF NOT EXISTS committees(id INTEGER PRIMARY KEY, name_en TEXT NOT NULL, name_ml TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'sub',
  description_en TEXT NOT NULL DEFAULT '', description_ml TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
  term_start TEXT NOT NULL DEFAULT '', term_end TEXT NOT NULL DEFAULT '', created REAL NOT NULL, sort INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS committee_members(id INTEGER PRIMARY KEY, committee_id INTEGER NOT NULL, member_id INTEGER NOT NULL,
  designation_en TEXT NOT NULL DEFAULT 'Member', designation_ml TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT 'member',
  term_start TEXT NOT NULL DEFAULT '', term_end TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_cm_committee ON committee_members(committee_id, active);
CREATE INDEX IF NOT EXISTS ix_cm_member ON committee_members(member_id, active);
CREATE TABLE IF NOT EXISTS meetings(id INTEGER PRIMARY KEY, committee_id INTEGER NOT NULL, title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '',
  scheduled_at TEXT NOT NULL, venue_en TEXT NOT NULL DEFAULT '', venue_ml TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'offline', link TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'scheduled', notice_en TEXT NOT NULL DEFAULT '', notice_ml TEXT NOT NULL DEFAULT '', notice_sent_at REAL,
  quorum INTEGER NOT NULL DEFAULT 0, chaired_by INTEGER, recorded_by INTEGER, started_at TEXT NOT NULL DEFAULT '', ended_at TEXT NOT NULL DEFAULT '',
  mom_status TEXT NOT NULL DEFAULT 'draft', mom_published_at REAL, mom_approved_by INTEGER, mom_approved_at REAL,
  summary_en TEXT NOT NULL DEFAULT '', summary_ml TEXT NOT NULL DEFAULT '', next_meeting_at TEXT NOT NULL DEFAULT '',
  created_by INTEGER NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_meetings_committee ON meetings(committee_id, scheduled_at);
CREATE TABLE IF NOT EXISTS agenda_items(id INTEGER PRIMARY KEY, meeting_id INTEGER NOT NULL, idx INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL DEFAULT 'discussion',
  title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '', detail_en TEXT NOT NULL DEFAULT '', detail_ml TEXT NOT NULL DEFAULT '',
  decision_en TEXT NOT NULL DEFAULT '', decision_ml TEXT NOT NULL DEFAULT '', resolution_no TEXT NOT NULL DEFAULT '',
  proposed_by INTEGER, seconded_by INTEGER, votes_for INTEGER NOT NULL DEFAULT 0, votes_against INTEGER NOT NULL DEFAULT 0, outcome TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_agenda_meeting ON agenda_items(meeting_id, idx);
CREATE TABLE IF NOT EXISTS attendance(meeting_id INTEGER NOT NULL, member_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'present',
  marked_at REAL NOT NULL, marked_by INTEGER, PRIMARY KEY(meeting_id, member_id));
CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY, committee_id INTEGER, meeting_id INTEGER, agenda_item_id INTEGER, plan_id INTEGER,
  title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '', detail_en TEXT NOT NULL DEFAULT '', detail_ml TEXT NOT NULL DEFAULT '',
  owner_member_id INTEGER, due TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', priority TEXT NOT NULL DEFAULT 'normal',
  progress_note TEXT NOT NULL DEFAULT '', done_at REAL, created_by INTEGER, created REAL NOT NULL, updated REAL NOT NULL, notified_at REAL);
CREATE INDEX IF NOT EXISTS ix_actions_status ON actions(status, due);
CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, committee_id INTEGER, title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '',
  detail_en TEXT NOT NULL DEFAULT '', detail_ml TEXT NOT NULL DEFAULT '', period TEXT NOT NULL DEFAULT '', budget REAL NOT NULL DEFAULT 0,
  owner_member_id INTEGER, status TEXT NOT NULL DEFAULT 'proposed', progress_pct INTEGER NOT NULL DEFAULT 0, created_by INTEGER, created REAL NOT NULL, updated REAL NOT NULL);

CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY, title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '', author_en TEXT NOT NULL DEFAULT '', author_ml TEXT NOT NULL DEFAULT '',
  publisher TEXT NOT NULL DEFAULT '', language TEXT NOT NULL DEFAULT 'ml', category TEXT NOT NULL DEFAULT '', isbn TEXT NOT NULL DEFAULT '', year TEXT NOT NULL DEFAULT '',
  price REAL NOT NULL DEFAULT 0, rack TEXT NOT NULL DEFAULT '', pages INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', donated_by TEXT NOT NULL DEFAULT '',
  cover TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS copies(id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL, accession_no TEXT UNIQUE NOT NULL, status TEXT NOT NULL DEFAULT 'available',
  rack TEXT NOT NULL DEFAULT '', condition TEXT NOT NULL DEFAULT 'good', added REAL NOT NULL, note TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_copies_book ON copies(book_id, status);
CREATE TABLE IF NOT EXISTS issues(id INTEGER PRIMARY KEY, copy_id INTEGER NOT NULL, book_id INTEGER NOT NULL, member_id INTEGER NOT NULL,
  issued_on TEXT NOT NULL, due_on TEXT NOT NULL, returned_on TEXT NOT NULL DEFAULT '', renewals INTEGER NOT NULL DEFAULT 0,
  fine REAL NOT NULL DEFAULT 0, fine_paid INTEGER NOT NULL DEFAULT 0, receipt_id INTEGER, issued_by INTEGER, returned_by INTEGER,
  created REAL NOT NULL, reminded_at REAL, note TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_issues_member ON issues(member_id, returned_on);
CREATE INDEX IF NOT EXISTS ix_issues_open ON issues(returned_on, due_on);
CREATE TABLE IF NOT EXISTS reservations(id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL, member_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'waiting',
  created REAL NOT NULL, notified_at REAL, closed_at REAL);
CREATE TABLE IF NOT EXISTS reading_room(id INTEGER PRIMARY KEY, member_id INTEGER, visitor_name TEXT NOT NULL DEFAULT '', visited_on TEXT NOT NULL,
  time_in TEXT NOT NULL DEFAULT '', time_out TEXT NOT NULL DEFAULT '', purpose TEXT NOT NULL DEFAULT '', created REAL NOT NULL, recorded_by INTEGER);
CREATE INDEX IF NOT EXISTS ix_rr_date ON reading_room(visited_on);
CREATE TABLE IF NOT EXISTS periodicals(id INTEGER PRIMARY KEY, title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'newspaper',
  language TEXT NOT NULL DEFAULT 'ml', agent TEXT NOT NULL DEFAULT '', sub_from TEXT NOT NULL DEFAULT '', sub_to TEXT NOT NULL DEFAULT '', cost REAL NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS periodical_receipts(id INTEGER PRIMARY KEY, periodical_id INTEGER NOT NULL, received_on TEXT NOT NULL, issue_ref TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL, recorded_by INTEGER, UNIQUE(periodical_id, received_on, issue_ref));

CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY, kind TEXT NOT NULL, no TEXT UNIQUE, tx_date TEXT NOT NULL, head TEXT NOT NULL,
  member_id INTEGER, post_id INTEGER, party TEXT NOT NULL DEFAULT '', amount REAL NOT NULL, mode TEXT NOT NULL DEFAULT 'cash', ref TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '', year INTEGER, created_by INTEGER, created REAL NOT NULL, void INTEGER NOT NULL DEFAULT 0, void_note TEXT NOT NULL DEFAULT '', notified_at REAL);
CREATE INDEX IF NOT EXISTS ix_tx_date ON transactions(tx_date, kind);
CREATE INDEX IF NOT EXISTS ix_tx_member ON transactions(member_id);
CREATE TABLE IF NOT EXISTS units(id INTEGER PRIMARY KEY, block TEXT NOT NULL DEFAULT '', unit_no TEXT NOT NULL, floor TEXT NOT NULL DEFAULT '', utype TEXT NOT NULL DEFAULT '',
  area_sqft REAL NOT NULL DEFAULT 0, parking TEXT NOT NULL DEFAULT '', owner_name TEXT NOT NULL DEFAULT '', owner_phone TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'occupied',
  maint_override REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL, updated REAL NOT NULL, UNIQUE(block, unit_no));
CREATE TABLE IF NOT EXISTS maint_bills(id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL, period TEXT NOT NULL, amount REAL NOT NULL, late_fee REAL NOT NULL DEFAULT 0, paid REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'due', due_on TEXT NOT NULL DEFAULT '', created REAL NOT NULL, reminded_at REAL, note TEXT NOT NULL DEFAULT '', UNIQUE(unit_id, period));
CREATE INDEX IF NOT EXISTS ix_bills_status ON maint_bills(status, period);
CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, no TEXT UNIQUE, member_id INTEGER, unit_id INTEGER, category TEXT NOT NULL DEFAULT 'other', title TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
  photo TEXT NOT NULL DEFAULT '', priority TEXT NOT NULL DEFAULT 'normal', status TEXT NOT NULL DEFAULT 'open', assigned_to INTEGER, created REAL NOT NULL, updated REAL NOT NULL, created_by INTEGER,
  resolved_at REAL, closed_at REAL);
CREATE INDEX IF NOT EXISTS ix_tickets_status ON tickets(status);
CREATE TABLE IF NOT EXISTS ticket_notes(id INTEGER PRIMARY KEY, ticket_id INTEGER NOT NULL, user_id INTEGER, ts REAL NOT NULL, text TEXT NOT NULL DEFAULT '', status_change TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS fy_years(fy TEXT PRIMARY KEY, start_on TEXT NOT NULL, end_on TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', closed_at REAL, closed_by INTEGER,
  summary TEXT NOT NULL DEFAULT '{}', note TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS fy_openings(fy TEXT NOT NULL, item TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0, side TEXT NOT NULL DEFAULT '', label_en TEXT NOT NULL DEFAULT '',
  label_ml TEXT NOT NULL DEFAULT '', derived INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(fy, item));
CREATE TABLE IF NOT EXISTS grants(id INTEGER PRIMARY KEY, source TEXT NOT NULL, purpose_en TEXT NOT NULL DEFAULT '', purpose_ml TEXT NOT NULL DEFAULT '', sanction_no TEXT NOT NULL DEFAULT '',
  sanction_on TEXT NOT NULL DEFAULT '', amount REAL NOT NULL DEFAULT 0, received_on TEXT NOT NULL DEFAULT '', receipt_id INTEGER, fy TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open',
  note TEXT NOT NULL DEFAULT '', created REAL NOT NULL, created_by INTEGER);
CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, year INTEGER NOT NULL, amount REAL NOT NULL,
  paid REAL NOT NULL DEFAULT 0, receipt_id INTEGER, status TEXT NOT NULL DEFAULT 'due', due_on TEXT NOT NULL DEFAULT '', created REAL NOT NULL, reminded_at REAL,
  UNIQUE(member_id, year));

CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, created REAL NOT NULL, channel TEXT NOT NULL, to_addr TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL, lang TEXT NOT NULL DEFAULT 'en', status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
  sent_at REAL, provider_id TEXT NOT NULL DEFAULT '', template TEXT NOT NULL DEFAULT '', ref_kind TEXT NOT NULL DEFAULT '', ref_id INTEGER, member_id INTEGER,
  batch_id TEXT NOT NULL DEFAULT '', created_by INTEGER);
CREATE INDEX IF NOT EXISTS ix_outbox_status ON outbox(status, created);
CREATE INDEX IF NOT EXISTS ix_outbox_member ON outbox(member_id, created);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, created REAL NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
  link TEXT NOT NULL DEFAULT '', read_at REAL, ref_kind TEXT NOT NULL DEFAULT '', ref_id INTEGER);
CREATE INDEX IF NOT EXISTS ix_notif_member ON notifications(member_id, read_at);
CREATE TABLE IF NOT EXISTS broadcasts(id INTEGER PRIMARY KEY, created REAL NOT NULL, created_by INTEGER, audience TEXT NOT NULL, channels TEXT NOT NULL,
  subject TEXT NOT NULL DEFAULT '', body_en TEXT NOT NULL, body_ml TEXT NOT NULL DEFAULT '', recipients INTEGER NOT NULL DEFAULT 0, batch_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts REAL NOT NULL, user_id INTEGER, action TEXT NOT NULL, ref_kind TEXT NOT NULL DEFAULT '', ref_id INTEGER, detail TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit(ts);
CREATE TABLE IF NOT EXISTS login_codes(ticket_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, code_hash TEXT NOT NULL, expires REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS payment_claims(id INTEGER PRIMARY KEY, member_id INTEGER NOT NULL, amount REAL NOT NULL, utr TEXT NOT NULL DEFAULT '', paid_on TEXT NOT NULL DEFAULT '',
  head TEXT NOT NULL DEFAULT 'subscription', year INTEGER, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', receipt_id INTEGER, decided_by INTEGER, decided_at REAL,
  decision_note TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_claims_status ON payment_claims(status, created);
CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'other', path TEXT NOT NULL,
  mime TEXT NOT NULL DEFAULT '', size INTEGER NOT NULL DEFAULT 0, audience TEXT NOT NULL DEFAULT 'members', committee_id INTEGER, year TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
  created_by INTEGER, created REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY, code TEXT NOT NULL DEFAULT '', name_en TEXT NOT NULL, name_ml TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'other',
  qty INTEGER NOT NULL DEFAULT 1, location TEXT NOT NULL DEFAULT '', condition TEXT NOT NULL DEFAULT 'good', purchased_on TEXT NOT NULL DEFAULT '', cost REAL NOT NULL DEFAULT 0,
  notes TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS asset_loans(id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL, member_id INTEGER, party TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
  qty INTEGER NOT NULL DEFAULT 1, lent_on TEXT NOT NULL, due_on TEXT NOT NULL DEFAULT '', returned_on TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', lent_by INTEGER, returned_by INTEGER, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_loans_asset ON asset_loans(asset_id, returned_on);
CREATE TABLE IF NOT EXISTS facilities(id INTEGER PRIMARY KEY, name_en TEXT NOT NULL, name_ml TEXT NOT NULL DEFAULT '', description_en TEXT NOT NULL DEFAULT '', description_ml TEXT NOT NULL DEFAULT '',
  rate_day REAL NOT NULL DEFAULT 0, rate_hour REAL NOT NULL DEFAULT 0, deposit REAL NOT NULL DEFAULT 0, capacity INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY, facility_id INTEGER NOT NULL, member_id INTEGER, party TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
  purpose TEXT NOT NULL DEFAULT '', starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0, deposit REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'requested',
  receipt_id INTEGER, note TEXT NOT NULL DEFAULT '', created_by INTEGER, created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_bookings_time ON bookings(facility_id, starts_at, ends_at);
CREATE TABLE IF NOT EXISTS fixtures(id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, item_id INTEGER, round TEXT NOT NULL DEFAULT '', idx INTEGER NOT NULL DEFAULT 0,
  side_a TEXT NOT NULL, side_b TEXT NOT NULL, scheduled_at TEXT NOT NULL DEFAULT '', venue TEXT NOT NULL DEFAULT '', score_a TEXT NOT NULL DEFAULT '', score_b TEXT NOT NULL DEFAULT '',
  winner TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'scheduled', note TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_fixtures_post ON fixtures(post_id, idx);
CREATE TABLE IF NOT EXISTS post_judges(post_id INTEGER NOT NULL, user_id INTEGER NOT NULL, item_ids TEXT NOT NULL DEFAULT '', PRIMARY KEY(post_id, user_id));
CREATE TABLE IF NOT EXISTS scores(id INTEGER PRIMARY KEY, post_id INTEGER NOT NULL, item_id INTEGER, registration_id INTEGER NOT NULL, judge_id INTEGER NOT NULL,
  score REAL NOT NULL DEFAULT 0, remark TEXT NOT NULL DEFAULT '', created REAL NOT NULL, UNIQUE(registration_id, judge_id, item_id));
CREATE TABLE IF NOT EXISTS push_subs(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, member_id INTEGER, endpoint TEXT UNIQUE NOT NULL, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
  created REAL NOT NULL, last_ok REAL, failures INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_push_member ON push_subs(member_id);
CREATE TABLE IF NOT EXISTS gateway_orders(id INTEGER PRIMARY KEY, provider TEXT NOT NULL DEFAULT 'razorpay', order_id TEXT UNIQUE NOT NULL, member_id INTEGER, amount REAL NOT NULL,
  head TEXT NOT NULL DEFAULT 'subscription', year INTEGER, post_id INTEGER, booking_id INTEGER, note TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'created',
  payment_id TEXT NOT NULL DEFAULT '', receipt_id INTEGER, created REAL NOT NULL, paid_at REAL, raw TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_gw_member ON gateway_orders(member_id, status);
CREATE TABLE IF NOT EXISTS polls(id INTEGER PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'poll', title_en TEXT NOT NULL, title_ml TEXT NOT NULL DEFAULT '', description_en TEXT NOT NULL DEFAULT '',
  description_ml TEXT NOT NULL DEFAULT '', audience TEXT NOT NULL DEFAULT 'members', committee_id INTEGER, starts_at TEXT NOT NULL DEFAULT '', ends_at TEXT NOT NULL DEFAULT '',
  anonymous INTEGER NOT NULL DEFAULT 1, max_choices INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'draft', results_live INTEGER NOT NULL DEFAULT 0,
  created_by INTEGER, created REAL NOT NULL, updated REAL NOT NULL, opened_at REAL, closed_at REAL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS poll_options(id INTEGER PRIMARY KEY, poll_id INTEGER NOT NULL, idx INTEGER NOT NULL DEFAULT 0, label_en TEXT NOT NULL, label_ml TEXT NOT NULL DEFAULT '',
  member_id INTEGER, note TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_pollopt ON poll_options(poll_id, idx);
CREATE TABLE IF NOT EXISTS ballots(poll_id INTEGER NOT NULL, member_id INTEGER NOT NULL, created REAL NOT NULL, PRIMARY KEY(poll_id, member_id));
CREATE TABLE IF NOT EXISTS votes(id INTEGER PRIMARY KEY, poll_id INTEGER NOT NULL, option_id INTEGER NOT NULL, member_id INTEGER, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_votes_poll ON votes(poll_id, option_id);
"""

# (table, column, definition) added to databases created before the column existed
MIGRATIONS = [
    ("outbox", "not_before", "REAL"),
    ("broadcasts", "send_at", "REAL"),
    ("registrations", "team", "TEXT NOT NULL DEFAULT ''"),
    ("members", "team", "TEXT NOT NULL DEFAULT ''"),
    ("transactions", "grant_id", "INTEGER"),
    ("transactions", "unit_id", "INTEGER"),
    ("members", "unit_id", "INTEGER"),
    ("members", "occupancy", "TEXT NOT NULL DEFAULT ''"),
]


def connect():
    os.makedirs(data_dir(), exist_ok=True)
    os.makedirs(upload_dir(), exist_ok=True)
    c = sqlite3.connect(db_path(), timeout=30, check_same_thread=False, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute("PRAGMA busy_timeout=30000")
    return c


_local = threading.local()      # one connection per thread and per club: sqlite3 connections must not be shared
_all = []
_initialized = set()
_generation = {}   # slug -> bumped by forget(); a thread holding an older connection reconnects


def forget(s):
    """Drop every cached connection to a club's database (used when a club is created afresh on disk)."""
    with _locks_guard:
        _generation[s] = _generation.get(s, 0) + 1
    _initialized.discard(s)


def conn():
    conns = getattr(_local, "conns", None)
    if conns is None:
        conns = _local.conns = {}
    s = slug()
    gen = _generation.get(s, 0)
    entry = conns.get(s)
    if entry is not None and entry[0] != gen:
        try:
            entry[1].close()
        except Exception:  # noqa: BLE001
            pass
        entry = None
    if entry is None:
        if s not in _initialized:
            init()
        c = connect()
        conns[s] = (gen, c)
        _all.append(c)
        return c
    return entry[1]


def init():
    """Create or upgrade the current club's schema (idempotent, once per process per club)."""
    s = slug()
    with _lock_for(s):
        c = connect()
        try:
            c.executescript(SCHEMA)
            for table, col, ddl in MIGRATIONS:
                cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
                if col not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            # the 'maintenance' head became the residents' maintenance charge (a receipt); repair vouchers move to 'repairs'
            c.execute("UPDATE transactions SET head='repairs' WHERE kind='payment' AND head='maintenance'")
        finally:
            c.close()
        _initialized.add(s)


def init_all():
    for s in tenancy.all_slugs():
        with tenancy.use(s):
            init()


def reset_for_tests():
    """Close every connection so a test can point CLUB_DATA somewhere fresh."""
    for c in _all:
        try:
            c.close()
        except Exception:  # noqa: BLE001
            pass
    _all.clear()
    _initialized.clear()
    _local.conns = {}


@contextmanager
def tx():
    """Serialised write transaction. SQLite has one writer; the lock keeps the threads polite. Readers on other
    threads keep going (WAL) and see the transaction once it commits."""
    c = conn()
    with _lock_for():
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


def q(sql, args=()):
    return [dict(r) for r in conn().execute(sql, args)]


def one(sql, args=()):
    r = conn().execute(sql, args).fetchone()
    return dict(r) if r else None


def insert(c, table, row):
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    return c.execute(f"INSERT INTO {table}({cols}) VALUES({marks})", list(row.values())).lastrowid


def update(c, table, id_, row, key="id"):
    sets = ", ".join(f"{k}=?" for k in row)
    c.execute(f"UPDATE {table} SET {sets} WHERE {key}=?", list(row.values()) + [id_])


# ---------- settings ----------
DEFAULT_SETTINGS = {
    "club_name_en": "Arts & Sports Club, Library and Reading Room",
    "club_name_ml": "ആർട്സ് & സ്പോർട്സ് ക്ലബ്ബ്, ലൈബ്രറി & വായനശാല",
    "club_short": "ASC",
    "club_reg_no": "",
    "club_address_en": "",
    "club_address_ml": "",
    "club_phone": "",
    "club_email": "",
    "club_place_en": "",
    "club_place_ml": "",
    "member_no_format": "{prefix}/{year}/{seq:04d}",
    "member_no_prefix": "ASC",
    "member_no_yearly": "0",
    "receipt_no_format": "R/{year}/{seq:04d}",
    "voucher_no_format": "V/{year}/{seq:04d}",
    "accession_format": "{seq:05d}",
    "membership_types": json.dumps([
        {"key": "life", "en": "Life member", "ml": "ആജീവനാന്ത അംഗം", "admission": 1000, "annual": 0},
        {"key": "ordinary", "en": "Ordinary member", "ml": "സാധാരണ അംഗം", "admission": 100, "annual": 120},
        {"key": "associate", "en": "Associate member", "ml": "അസോസിയേറ്റ് അംഗം", "admission": 50, "annual": 60},
        {"key": "student", "en": "Student member", "ml": "വിദ്യാർത്ഥി അംഗം", "admission": 25, "annual": 30},
        {"key": "honorary", "en": "Honorary member", "ml": "ഓണററി അംഗം", "admission": 0, "annual": 0},
    ]),
    "wards": json.dumps([]),
    "library_loan_days": "14",
    "library_max_books": "2",
    "library_fine_per_day": "1",
    "library_max_renewals": "1",
    "subscription_due_month": "4",
    "public_registration": "1",
    "default_lang": "ml",
    "reminder_days_before_event": "1",
    "footer_credit": "",
    "brand_logo": "",
    "brand_primary": "#0F4C45",
    "brand_accent": "#C9542A",
    "brand_app_name": "",
    # per-club channel and gateway credentials; blank means "use the server's .env"
    "wa_token": "", "wa_phone_id": "", "wa_template": "", "wa_template_lang": "",
    "sms_url": "", "sms_body": "", "sms_headers": "", "sms_key": "", "sms_sender": "", "sms_dlt": "",
    "smtp_host": "", "smtp_port": "", "smtp_user": "", "smtp_pass": "", "smtp_from": "",
    "rzp_key_id": "", "rzp_key_secret": "", "rzp_webhook_secret": "",
    "upi_id": "",
    "upi_name": "",
    "teams": json.dumps([]),
    "asset_prefix": "AST",
    "about_en": "",
    "about_ml": "",
    "map_url": "",
    "social_facebook": "",
    "social_instagram": "",
    "social_youtube": "",
    "social_whatsapp": "",
    "site_cover": "",
    "backup_keep": "14",
    # society accounts
    "fy_start_month": "4",
    "custom_heads": json.dumps([]),
    "head_nature": json.dumps({}),
    # Library Council affiliation
    "council_reg_no": "",
    "council_grade": "",
    "council_district": "",
    "council_taluk": "",
    "library_hours": "",
    "librarian_name": "",
    "council_criteria": json.dumps({}),
    # residents' association mode
    "org_kind": "club",
    "features": json.dumps({}),
    "unit_types": json.dumps(["1BHK", "2BHK", "3BHK", "Villa", "Shop"]),
    "maint_basis": "flat",
    "maint_rate": "0",
    "maint_rates_by_type": json.dumps({}),
    "maint_period": "monthly",
    "maint_due_day": "10",
    "maint_late_fee": "0",
}


def setting(key, default=None):
    r = one("SELECT value FROM settings WHERE key=?", (key,))
    if r:
        return r["value"]
    return DEFAULT_SETTINGS.get(key, default)


def settings_all():
    out = dict(DEFAULT_SETTINGS)
    for r in q("SELECT key, value FROM settings"):
        out[r["key"]] = r["value"]
    return out


def set_setting(c, key, value):
    c.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def setting_json(key, default):
    try:
        return json.loads(setting(key, json.dumps(default)))
    except Exception:
        return default


def next_counter(c, key):
    """Atomic counter, must be called inside tx()."""
    c.execute("INSERT INTO counters(key, value) VALUES(?, 0) ON CONFLICT(key) DO NOTHING", (key,))
    c.execute("UPDATE counters SET value=value+1 WHERE key=?", (key,))
    return c.execute("SELECT value FROM counters WHERE key=?", (key,)).fetchone()[0]


def audit(c, user_id, action, ref_kind="", ref_id=None, detail=""):
    insert(c, "audit", {"ts": time.time(), "user_id": user_id, "action": action, "ref_kind": ref_kind, "ref_id": ref_id, "detail": detail[:2000]})


def now():
    return time.time()
