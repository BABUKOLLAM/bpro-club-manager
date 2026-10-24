"""Fill the demo club with enough realistic data that every handbook screenshot shows something worth reading.
Run once against the dev server before docs/handbook/capture.js and capture-v13.js:

    CLUB_DATA=/tmp/club-dev ... uvicorn app.main:app --port 8810      # after python -m app.manage seed-demo
    python docs/handbook/seed_demo.py http://127.0.0.1:8810 /tmp/club-dev/club.db

Everything goes through the public API (as the administrator or as the member concerned); the database file is only
touched to back-date two loans so the overdue screens have something to show. Safe to run twice: it checks before adding.
"""
import datetime as dt
import sqlite3
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8810"
DB = sys.argv[2] if len(sys.argv) > 2 else "/tmp/club-dev/club.db"
H = {"X-Club": "1"}
today = dt.date.today()
d = lambda n: (today - dt.timedelta(days=n)).isoformat()  # noqa: E731


def login(user, pw):
    c = httpx.Client(base_url=BASE, headers=H, timeout=30)
    r = c.post("/api/auth/login", json={"login": user, "password": pw})
    r.raise_for_status()
    return c


A = login("admin@club.test", "admin-password-1")
_clients = {}


def as_member(phone):
    """One cached sign-in per member: the server rate-limits logins, so never sign in twice for the same person."""
    if phone not in _clients:
        _clients[phone] = login(phone, "member-pass-1")
    return _clients[phone]


def post(path, body=None, c=None):
    r = (c or A).post(path, json=body or {})
    if r.status_code >= 400:
        print("  !", path, r.status_code, r.text[:120])
        return {}
    return r.json()


def get(path, c=None):
    return (c or A).get(path).json()


# ---------- members ----------
PEOPLE = [("Suresh Menon", "സുരേഷ് മേനോൻ", "9847012350", "A+", "7", "male", "1975-08-02", "Menon Bhavan", "മേനോൻ ഭവൻ", "ordinary"),
          ("Lakshmi Nair", "ലക്ഷ്മി നായർ", "9847012351", "B+", "7", "female", "1983-11-19", "Sreevalsam", "ശ്രീവത്സം", "ordinary"),
          ("George Thomas", "ജോർജ് തോമസ്", "9847012352", "O+", "8", "male", "1969-02-27", "Kuruvilla House", "കുരുവിള ഹൗസ്", "life"),
          ("Mariyamma Varghese", "മറിയാമ്മ വർഗീസ്", "9847012353", "AB-", "8", "female", "1958-06-09", "Pallivathukkal", "പള്ളിവാതുക്കൽ", "ordinary"),
          ("Rajesh Pillai", "രാജേഷ് പിള്ള", "9847012354", "A-", "9", "male", "1990-12-30", "Pillai Nivas", "പിള്ള നിവാസ്", "ordinary"),
          ("Nisha Abdul", "നിഷ അബ്ദുൽ", "9847012355", "O+", "9", "female", "1995-04-14", "Villa 12", "വില്ല 12", "student"),
          ("Biju Mathew", "ബിജു മാത്യു", "9847012356", "B-", "7", "male", "1982-09-05", "Mathew Villa", "മാത്യു വില്ല", "ordinary"),
          ("Divya Krishnan", "ദിവ്യ കൃഷ്ണൻ", "9847012357", "A+", "8", "female", "1998-01-23", "Krishna Sadanam", "കൃഷ്ണ സദനം", "associate"),
          ("Abdul Rahim", "അബ്ദുൽ റഹീം", "9847012358", "O+", "9", "male", "1971-07-17", "Rahim Manzil", "റഹീം മൻസിൽ", "ordinary"),
          ("Anjana Das", "അഞ്ജന ദാസ്", "9847012359", "B+", "7", "female", "2003-03-08", "Das Nivas", "ദാസ് നിവാസ്", "student")]
have = {m["phone"] for m in get("/api/members?status=active")}
for en, ml, ph, bg, ward, g, dob, hen, hml, mt in PEOPLE:
    if ph in have:
        continue
    post("/api/members", {"name_en": en, "name_ml": ml, "phone": ph, "whatsapp": ph, "blood_group": bg, "ward": ward, "gender": g, "dob": dob, "house_en": hen, "house_ml": hml,
                          "membership_type": mt, "password": "member-pass-1", "lang": "ml", "joined_on": d(400 - int(ph[-2:]) * 3), "occupation": "Teacher" if g == "female" else "Businessman"})
members = {m["name_en"]: m for m in get("/api/members?status=active")}
print("members:", len(members))

# ---------- money ----------
if len(get("/api/finance/transactions?frm=2026-04-01&to=2027-03-31")["rows"]) < 12:
    tx = [("receipt", "subscription", 1200, "upi", 190, "Suresh Menon"), ("receipt", "subscription", 1200, "cash", 180, "Lakshmi Nair"), ("receipt", "subscription", 600, "upi", 171, "Divya Krishnan"),
          ("receipt", "admission", 100, "cash", 160, "Rajesh Pillai"), ("receipt", "donation", 5000, "bank", 150, ""), ("receipt", "event_fee", 1500, "cash", 120, ""), ("receipt", "sponsorship", 15000, "bank", 100, ""),
          ("receipt", "donation", 2500, "cash", 70, ""), ("receipt", "bank_interest", 740, "bank", 40, ""), ("receipt", "subscription", 1200, "upi", 25, "George Thomas"),
          ("payment", "newspapers", 3600, "cash", 185, ""), ("payment", "electricity", 1850, "bank", 150, ""), ("payment", "books", 8200, "bank", 130, ""), ("payment", "printing", 2100, "cash", 115, ""),
          ("payment", "event_expense", 9400, "bank", 95, ""), ("payment", "electricity", 1760, "bank", 60, ""), ("payment", "furniture", 12500, "bank", 45, ""), ("payment", "repairs", 3300, "cash", 20, "")]
    for kind, head, amount, mode, ago, who in tx:
        body = {"kind": kind, "head": head, "amount": amount, "mode": mode, "tx_date": d(ago), "party": who or ("Local sponsors" if head == "sponsorship" else "Vendor"), "notify": False}
        if who and who in members:
            body["member_id"] = members[who]["id"]
        post("/api/finance/transactions", body)
    post("/api/accounts/contra", {"head": "cash_to_bank", "amount": 6000, "tx_date": d(80)})
    post("/api/accounts/contra", {"head": "bank_to_cash", "amount": 2000, "tx_date": d(30)})

# a UPI claim waiting for the treasurer
if not [c for c in get("/api/finance/claims") if c["utr"].startswith("402619")]:
    post("/api/finance/claims", {"amount": 1200, "utr": "402619887711", "head": "subscription", "note": "Annual subscription"}, as_member("9847012350"))
    post("/api/finance/claims", {"amount": 300, "utr": "402619887712", "head": "donation", "note": "Onam fund"}, as_member("9847012351"))

# ---------- library and reading room ----------
BOOKS = [("Manju", "മഞ്ഞ്", "M. T. Vasudevan Nair", "എം.ടി. വാസുദേവൻ നായർ", "novel", "ml"), ("Smaraka Silakal", "സ്മാരകശിലകൾ", "Punathil Kunjabdulla", "പുനത്തിൽ കുഞ്ഞബ്ദുള്ള", "novel", "ml"),
         ("Wings of Fire", "", "A. P. J. Abdul Kalam", "", "biography", "en"), ("Ente Katha", "എന്റെ കഥ", "Kamala Surayya", "കമലാ സുരയ്യ", "biography", "ml"),
         ("The God of Small Things", "", "Arundhati Roy", "", "novel", "en"), ("Kerala Charithram", "കേരള ചരിത്രം", "A. Sreedhara Menon", "എ. ശ്രീധര മേനോൻ", "history", "ml"),
         ("Balyakalasakhi", "ബാല്യകാലസഖി", "Vaikom Muhammad Basheer", "വൈക്കം മുഹമ്മദ് ബഷീർ", "novel", "ml"), ("Indulekha", "ഇന്ദുലേഖ", "O. Chandu Menon", "ഒ. ചന്തുമേനോൻ", "novel", "ml")]
have_t = {b["title_en"] for b in get("/api/library/books")}
for en, ml, aen, aml, cat, lang in BOOKS:
    if en not in have_t:
        post("/api/library/books", {"title_en": en, "title_ml": ml, "author_en": aen, "author_ml": aml, "category": cat, "language": lang, "price": 260, "rack": "B2", "add_copies": 2,
                                    "publisher": "DC Books" if lang == "ml" else "Penguin", "year": "1998"})
open_loans = get("/api/library/issues?open_only=1")
if len(open_loans) < 5:
    ids = {b["title_en"]: b["id"] for b in get("/api/library/books")}
    for who, title in [("Suresh Menon", "Manju"), ("Lakshmi Nair", "Wings of Fire"), ("George Thomas", "Kerala Charithram"), ("Biju Mathew", "Indulekha"), ("Anil Joseph", "Balyakalasakhi")]:
        if who in members and title in ids:
            post("/api/library/issue", {"member_id": members[who]["id"], "book_id": ids[title], "notify": False})
    db = sqlite3.connect(DB)
    ov = db.execute("SELECT id FROM issues WHERE returned_on='' ORDER BY id DESC LIMIT 2").fetchall()
    for (iid,) in ov:
        db.execute("UPDATE issues SET issued_on=?, due_on=? WHERE id=?", (d(26), d(12), iid))
    db.commit(); db.close()
vis = len(get("/api/library/reading-room")["month"])
if vis < 6:
    names = list(members.values())
    for i in range(24):
        m = names[i % len(names)]
        post("/api/library/reading-room", {"member_id": m["id"], "purpose": ["newspapers", "reference", "reading", "study"][i % 4], "visited_on": d(i // 3), "time_in": f"{9 + i % 8}:{(i * 7) % 60:02d}", "time_out": f"{10 + i % 8}:{(i * 7) % 60:02d}"})
for p in get("/api/library/periodicals"):
    post(f"/api/library/periodicals/{p['id']}/received", {"received_on": today.isoformat()})

# ---------- assets, hall, documents, plans, polls ----------
if not get("/api/assets"):
    for en, ml, cat, qty, loc in [("Plastic chairs", "പ്ലാസ്റ്റിക് കസേരകൾ", "furniture", 120, "Hall store"), ("Sound system", "സൗണ്ട് സിസ്റ്റം", "equipment", 1, "Office"),
                                  ("Carrom boards", "കാരംസ് ബോർഡുകൾ", "sports", 6, "Games room"), ("Volleyball kit", "വോളിബോൾ കിറ്റ്", "sports", 2, "Games room"), ("Stage platform", "സ്റ്റേജ് പ്ലാറ്റ്ഫോം", "furniture", 1, "Hall store")]:
        post("/api/assets", {"name_en": en, "name_ml": ml, "category": cat, "qty": qty, "location": loc, "value": qty * 450})
    ch = next(a for a in get("/api/assets") if a["name_en"] == "Plastic chairs")
    post(f"/api/assets/{ch['id']}/lend", {"member_id": members["Rajesh Pillai"]["id"], "qty": 30, "due_on": d(-4)})
if not get("/api/facilities"):
    hall = post("/api/facilities", {"name_en": "Community hall", "name_ml": "കമ്മ്യൂണിറ്റി ഹാൾ", "rate_hour": 400, "rate_day": 3500, "deposit": 1000, "capacity": 200})
    post("/api/facilities", {"name_en": "Playground", "name_ml": "കളിസ്ഥലം", "rate_hour": 200, "rate_day": 1500, "capacity": 400})
    for i, (who, purpose) in enumerate([("Lakshmi Nair", "Wedding reception"), ("Abdul Rahim", "Tuition class"), ("Biju Mathew", "Birthday party")]):
        mc = as_member(members[who]["phone"])
        day = (today + dt.timedelta(days=4 + i * 5)).isoformat()
        post("/api/bookings", {"facility_id": hall["id"], "starts_at": f"{day}T10:00", "ends_at": f"{day}T14:00", "purpose": purpose}, mc)
    for b in get("/api/bookings")[:2]:
        post(f"/api/bookings/{b['id']}/status", {"status": "confirmed"})
if not get("/api/documents"):
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    path = A.post("/api/upload/docs", files={"file": ("doc.pdf", pdf, "application/pdf")}).json().get("path")
    for en, ml, cat, aud, yr in [("Bye-laws 2024", "നിയമാവലി 2024", "bylaws", "public", "2024"), ("Audit report 2025-26", "ഓഡിറ്റ് റിപ്പോർട്ട് 2025-26", "audit", "members", "2026"),
                                 ("General body minutes, June", "പൊതുയോഗ മിനിറ്റ്സ്, ജൂൺ", "minutes", "members", "2026"), ("Membership form", "അംഗത്വ ഫോം", "form", "public", "2026")]:
        post("/api/documents", {"title_en": en, "title_ml": ml, "category": cat, "audience": aud, "year": yr, "path": path, "mime": "application/pdf", "size": len(pdf)})
coms = get("/api/committees")
sports = next(c for c in coms if c["name_en"].startswith("Sports"))
for com, rows in [(next(c for c in coms if c["name_en"].startswith("Executive")), [("Ramesh Kumar", "President", "chair"), ("Sreelatha P", "Secretary", "secretary"), ("Anil Joseph", "Treasurer", "member"), ("Fathima Beevi", "Librarian", "member"), ("Suresh Menon", "Joint Secretary", "member")]),
                  (sports, [("Anil Joseph", "Convener", "convener"), ("Biju Mathew", "Member", "member"), ("Abdul Rahim", "Member", "member")])]:
    if not (get(f"/api/committees/{com['id']}") or {}).get("members"):
        for n, des, role in rows:
            post(f"/api/committees/{com['id']}/members", {"member_id": members[n]["id"], "designation_en": des, "role": role})
if not get("/api/plans"):
    for t, per, bud, who in [("Build a badminton court", "2026-27", 150000, "Ramesh Kumar"), ("Library digitisation", "2026-27", 60000, "Sreelatha P"), ("Annual arts fest", "2026-27", 90000, "Anil Joseph")]:
        post("/api/plans", {"committee_id": sports["id"], "title_en": t, "period": per, "budget": bud, "owner_member_id": members[who]["id"]})
if len(get("/api/actions")) < 3:
    meetings = get("/api/meetings")
    if meetings:
        for t, who, due in [("Get three quotes for ground levelling", "Anil Joseph", (today + dt.timedelta(days=9)).isoformat()), ("Book the hall for Onam", "Sreelatha P", (today + dt.timedelta(days=15)).isoformat()),
                            ("Send audit papers to members", "Fathima Beevi", (today - dt.timedelta(days=3)).isoformat())]:
            post("/api/actions", {"meeting_id": meetings[0]["id"], "title_en": t, "owner_member_id": members[who]["id"], "due": due})
if not get("/api/polls"):
    p1 = post("/api/polls", {"kind": "election", "title_en": "Secretary 2027", "title_ml": "സെക്രട്ടറി 2027", "ends_at": (today + dt.timedelta(days=10)).isoformat() + "T18:00",
                             "options": [{"member_id": members["Ramesh Kumar"]["id"]}, {"member_id": members["Suresh Menon"]["id"]}, {"member_id": members["George Thomas"]["id"]}]})
    p2 = post("/api/polls", {"kind": "poll", "title_en": "Date for the Onam programme", "title_ml": "ഓണാഘോഷ തീയതി", "ends_at": (today + dt.timedelta(days=6)).isoformat() + "T18:00", "results_live": 1,
                             "options": [{"label_en": "Saturday, 5 September", "label_ml": "സെപ്റ്റംബർ 5, ശനി"}, {"label_en": "Sunday, 6 September", "label_ml": "സെപ്റ്റംബർ 6, ഞായർ"}]})
    for p in (p1, p2):
        if p.get("id"):
            post(f"/api/polls/{p['id']}/status", {"status": "open", "channels": ["app"]})
    for who in ("Lakshmi Nair", "Biju Mathew", "Abdul Rahim"):
        mc = as_member(members[who]["phone"])
        pl = get("/api/polls", mc)
        for p in pl:
            opts = get(f"/api/polls/{p['id']}", mc).get("options") or []
            if opts and not p.get("voted"):
                post(f"/api/polls/{p['id']}/vote", {"option_ids": [opts[hash(who) % len(opts)]["id"]]}, mc)

# ---------- residents' association data (used when the demo club is switched to association mode) ----------
if len(get("/api/units")) < 12:
    post("/api/units/bulk", {"lines": "\n".join(f"A, {n}, {int(str(n)[0])}, {t}, {a}" for n, t, a in [(101, "2BHK", 950), (102, "3BHK", 1200), (103, "2BHK", 950), (201, "2BHK", 950), (202, "3BHK", 1200), (203, "1BHK", 620)])
                              + "\n" + "\n".join(f"B, {n}, {int(str(n)[0])}, {t}, {a}" for n, t, a in [(101, "Villa", 1800), (102, "2BHK", 950), (201, "3BHK", 1200), (202, "2BHK", 950), (203, "2BHK", 950), (301, "Shop", 400)])})
units = {u["label"]: u["id"] for u in get("/api/units")}
for label, who, occ in [("A-101", "Ramesh Kumar", "owner"), ("A-102", "Suresh Menon", "owner"), ("A-103", "Rajesh Pillai", "tenant"), ("A-201", "George Thomas", "owner"), ("A-202", "Mariyamma Varghese", "owner"),
                        ("B-101", "Biju Mathew", "owner"), ("B-102", "Abdul Rahim", "owner"), ("B-201", "Lakshmi Nair", "tenant"), ("B-202", "Anil Joseph", "owner"), ("B-203", "Fathima Beevi", "owner"),
                        ("A-203", "Nisha Abdul", "tenant"), ("B-301", "Divya Krishnan", "owner")]:
    if label in units and who in members:
        post(f"/api/units/{units[label]}/residents", {"member_id": members[who]["id"], "occupancy": occ})
# maintenance for three months, paid by most units, and a handful of complaints at different stages
post("/api/settings", {"maint_basis": "sqft", "maint_rate": "2.5", "maint_period": "monthly", "maint_due_day": "10", "maint_late_fee": "100", "wards": ["A", "B"]})
months = [(today.replace(day=1) - dt.timedelta(days=62)).strftime("%Y-%m"), (today.replace(day=1) - dt.timedelta(days=31)).strftime("%Y-%m"), today.strftime("%Y-%m")]
for per in months:
    post("/api/maintenance/generate", {"period": per})
paid_units = ["A-101", "A-102", "A-201", "A-202", "B-101", "B-102", "B-202", "B-203", "A-203"]
if len(get("/api/finance/transactions?head=maintenance")["rows"]) < 6:
    for label in paid_units:
        amt = {"A-101": 2375 * 3, "A-102": 3000 * 3, "A-201": 2375 * 2, "A-202": 3000 * 3, "B-101": 4500 * 3, "B-102": 2375 * 3, "B-202": 2375 * 2, "B-203": 2375 * 3, "A-203": 1550 * 3}[label]
        post("/api/finance/transactions", {"kind": "receipt", "head": "maintenance", "unit_id": units[label], "amount": amt, "mode": "upi" if hash(label) % 2 else "bank", "party": label, "tx_date": d(5), "notify": False})
if len(get("/api/tickets")["rows"]) < 5:
    cases = [("A-101", "Ramesh Kumar", "lift", "Lift B making a grinding noise", "high"), ("A-102", "Suresh Menon", "plumbing", "Water leak from the terrace tank", "urgent"),
             ("B-102", "Abdul Rahim", "security", "Main gate camera not working", "normal"), ("A-201", "George Thomas", "housekeeping", "Stairwell not cleaned for three days", "normal"),
             ("B-101", "Biju Mathew", "parking", "Visitor car parked in my slot", "low")]
    pw = {"Ramesh Kumar": "member-pass-1"}
    for label, who, cat, title, prio in cases:
        mc = as_member(members[who]["phone"])
        post("/api/tickets", {"category": cat, "title": title, "details": "Please look into this at the earliest.", "priority": prio}, mc)
    rows = get("/api/tickets")["rows"]
    staff = get(f"/api/tickets/{rows[0]['id']}")["staff"]
    for i, t in enumerate(rows):
        if i == 0:
            post(f"/api/tickets/{t['id']}", {"status": "in_progress", "assigned_to": staff[0]["id"], "note": "Technician called; visit scheduled for tomorrow morning."})
        elif i == 1:
            post(f"/api/tickets/{t['id']}", {"status": "resolved", "assigned_to": staff[0]["id"], "note": "Float valve replaced; tank checked."})
        elif i == 2:
            post(f"/api/tickets/{t['id']}", {"status": "on_hold", "note": "Waiting for the camera vendor's quote."})
print("done: demo club is ready for the handbook screenshots")
