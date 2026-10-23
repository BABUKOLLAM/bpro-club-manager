"""Command line chores: python -m app.manage create-admin LOGIN PASSWORD [NAME] | seed-demo | daily

seed-demo fills an empty database with a handful of members, committees, posts and books so the screens have
something to show. It never runs against a database that already has members."""
import datetime as dt
import sys
import time

from . import auth, db, committees


def create_admin(login, pw, name="Administrator"):
    db.init()
    with db.tx() as c:
        if db.one("SELECT 1 FROM users WHERE login=?", (auth.norm_login(login),)):
            c.execute("UPDATE users SET pw_hash=?, active=1, role='admin' WHERE login=?", (auth.hash_pw(pw), auth.norm_login(login)))
        else:
            db.insert(c, "users", {"login": auth.norm_login(login), "name": name, "role": "admin", "pw_hash": auth.hash_pw(pw), "active": 1, "created": time.time(), "lang": "en"})
        committees.seed_defaults(c)
    print("admin ready:", login)


def seed_demo():
    db.init()
    if db.one("SELECT 1 FROM members LIMIT 1"):
        print("database already has members - not seeding"); return
    now = time.time(); year = dt.date.today().year
    people = [("Ramesh Kumar", "രമേശ് കുമാർ", "9847012345", "O+", "7", "male", "1980-05-14", "Kizhakkethil", "കിഴക്കേതിൽ"), ("Sreelatha P", "ശ്രീലത പി", "9847012346", "A+", "7", "female", "1985-11-02", "Puthenveedu", "പുത്തൻവീട്"),
              ("Anil Joseph", "അനിൽ ജോസഫ്", "9847012347", "B+", "8", "male", "1992-03-21", "Thottathil", "തോട്ടത്തിൽ"), ("Fathima Beevi", "ഫാത്തിമ ബീവി", "9847012348", "AB+", "9", "female", "1975-08-30", "Mannil", "മണ്ണിൽ"),
              ("Vishnu Prasad", "വിഷ്ണു പ്രസാദ്", "9847012349", "O-", "8", "male", "2001-01-15", "Kallumpuram", "കല്ലുംപുറം")]
    with db.tx() as c:
        committees.seed_defaults(c)
        ids = []
        for i, (en, ml, ph, bg, ward, g, dob, hen, hml) in enumerate(people):
            seq = db.next_counter(c, "member_no")
            mid = db.insert(c, "members", {"member_no": f"ASC/{year}/{seq:04d}", "status": "active", "name_en": en, "name_ml": ml, "gender": g, "dob": dob, "blood_group": bg, "phone": ph, "whatsapp": ph,
                                           "house_en": hen, "house_ml": hml, "ward": ward, "membership_type": "life" if i == 0 else "ordinary", "applied_at": now, "approved_at": now,
                                           "joined_on": dt.date.today().isoformat(), "created": now, "updated": now, "lang": "ml"})
            db.insert(c, "users", {"login": ph, "name": en, "role": "member", "pw_hash": auth.hash_pw("member-pass-1"), "active": 1, "member_id": mid, "created": now, "lang": "ml"})
            ids.append(mid)
        db.insert(c, "family", {"member_id": ids[0], "name_en": "Sita R", "name_ml": "സീത ആർ", "relation": "spouse", "dob": "1984-01-02", "blood_group": "B+", "created": now, "updated": now, "verified": 1})
        db.insert(c, "family", {"member_id": ids[0], "name_en": "Arjun R", "name_ml": "അർജുൻ ആർ", "relation": "son", "dob": "2010-07-07", "education": "Class 10", "created": now, "updated": now, "verified": 1})
        execc = db.one("SELECT id FROM committees WHERE kind='executive'")["id"]; sports = db.one("SELECT id FROM committees WHERE name_en LIKE 'Sports%'")["id"]
        for mid, den, dml, role in [(ids[0], "President", "പ്രസിഡന്റ്", "chair"), (ids[1], "Secretary", "സെക്രട്ടറി", "secretary"), (ids[3], "Treasurer", "ട്രഷറർ", "member")]:
            db.insert(c, "committee_members", {"committee_id": execc, "member_id": mid, "designation_en": den, "designation_ml": dml, "role": role, "created": now})
        db.insert(c, "committee_members", {"committee_id": sports, "member_id": ids[2], "designation_en": "Convener", "designation_ml": "കൺവീനർ", "role": "convener", "created": now})
        db.insert(c, "committee_members", {"committee_id": sports, "member_id": ids[4], "designation_en": "Member", "designation_ml": "അംഗം", "role": "member", "created": now})
        soon = (dt.date.today() + dt.timedelta(days=12)).isoformat()
        p1 = db.insert(c, "posts", {"kind": "competition", "status": "published", "title_en": "Onam Sports Meet", "title_ml": "ഓണം കായികമേള", "body_en": "Annual sports meet for members and families. Events for all age groups.", "body_ml": "അംഗങ്ങൾക്കും കുടുംബങ്ങൾക്കുമായുള്ള വാർഷിക കായികമേള. എല്ലാ പ്രായക്കാർക്കും ഇനങ്ങൾ.",
                                    "level": "panchayat", "starts_at": soon + "T09:00", "venue_en": "Govt. HSS ground", "venue_ml": "ഗവ. എച്ച്.എസ്.എസ്. ഗ്രൗണ്ട്", "audience": "public", "reg_open": 1, "created_by": 1, "created": now, "updated": now, "published_at": now})
        for i, (en, ml, ag) in enumerate([("100 m run", "100 മീറ്റർ ഓട്ടം", "senior"), ("Tug of war", "വടംവലി", "open"), ("Musical chair", "മ്യൂസിക്കൽ ചെയർ", "women")]):
            db.insert(c, "comp_items", {"post_id": p1, "idx": i, "name_en": en, "name_ml": ml, "age_group": ag, "kind": "team" if i == 1 else "individual"})
        db.insert(c, "posts", {"kind": "camp", "status": "published", "title_en": "Free medical camp", "title_ml": "സൗജന്യ മെഡിക്കൽ ക്യാമ്പ്", "body_en": "With the Taluk hospital. Blood pressure, sugar and eye check-up.", "body_ml": "താലൂക്ക് ആശുപത്രിയുമായി ചേർന്ന്. രക്തസമ്മർദ്ദം, പ്രമേഹം, നേത്ര പരിശോധന.",
                               "starts_at": (dt.date.today() + dt.timedelta(days=20)).isoformat() + "T08:00", "venue_en": "Club hall", "venue_ml": "ക്ലബ്ബ് ഹാൾ", "audience": "public", "reg_open": 1, "created_by": 1, "created": now, "updated": now, "published_at": now})
        db.insert(c, "posts", {"kind": "news", "status": "published", "title_en": "Library gets 120 new books", "title_ml": "ലൈബ്രറിയിലേക്ക് 120 പുതിയ പുസ്തകങ്ങൾ", "body_en": "Thanks to the Panchayat grant, 120 new Malayalam and English titles are on the shelves.", "body_ml": "പഞ്ചായത്ത് ഗ്രാന്റിന്റെ സഹായത്തോടെ 120 പുതിയ മലയാളം, ഇംഗ്ലീഷ് പുസ്തകങ്ങൾ ഷെൽഫിൽ.",
                               "audience": "members", "pinned": 1, "created_by": 1, "created": now, "updated": now, "published_at": now})
        for en, ml, aen, aml, cat in [("Randamoozham", "രണ്ടാമൂഴം", "M. T. Vasudevan Nair", "എം.ടി. വാസുദേവൻ നായർ", "novel"), ("Khasakkinte Ithihasam", "ഖസാക്കിന്റെ ഇതിഹാസം", "O. V. Vijayan", "ഒ.വി. വിജയൻ", "novel"),
                                      ("Aadujeevitham", "ആടുജീവിതം", "Benyamin", "ബെന്യാമിൻ", "novel"), ("Chemmeen", "ചെമ്മീൻ", "Thakazhi", "തകഴി", "novel"), ("Wings of Fire", "", "A. P. J. Abdul Kalam", "", "biography")]:
            bid = db.insert(c, "books", {"title_en": en, "title_ml": ml, "author_en": aen, "author_ml": aml, "language": "en" if not ml else "ml", "category": cat, "price": 300, "rack": "A1", "created": now, "updated": now})
            for _ in range(2):
                seq = db.next_counter(c, "accession"); db.insert(c, "copies", {"book_id": bid, "accession_no": f"{seq:05d}", "status": "available", "rack": "A1", "added": now})
        for i, (en, ml) in enumerate([("Mathrubhumi", "മാതൃഭൂമി"), ("Malayala Manorama", "മലയാള മനോരമ"), ("The Hindu", ""), ("Bhashaposhini", "ഭാഷാപോഷിണി")]):
            db.insert(c, "periodicals", {"title_en": en, "title_ml": ml, "kind": "monthly" if i == 3 else "newspaper", "language": "en" if not ml else "ml", "created": now})
        m = db.insert(c, "meetings", {"committee_id": execc, "title_en": "Executive committee - monthly", "title_ml": "എക്സിക്യൂട്ടീവ് കമ്മിറ്റി - പ്രതിമാസ യോഗം", "scheduled_at": (dt.date.today() + dt.timedelta(days=5)).isoformat() + "T18:30",
                                      "venue_en": "Club hall", "venue_ml": "ക്ലബ്ബ് ഹാൾ", "quorum": 3, "created_by": 1, "created": now, "updated": now})
        for i, (en, ml, k) in enumerate([("Confirmation of previous minutes", "മുൻ മിനിറ്റ്സ് സ്ഥിരീകരണം", "info"), ("Onam sports meet - budget", "ഓണം കായികമേള - ബജറ്റ്", "resolution"), ("Library subscription renewals", "ലൈബ്രറി വരിസംഖ്യ പുതുക്കൽ", "discussion")]):
            db.insert(c, "agenda_items", {"meeting_id": m, "idx": i, "kind": k, "title_en": en, "title_ml": ml})
        db.insert(c, "actions", {"committee_id": execc, "meeting_id": m, "title_en": "Collect quotations for the stage and sound", "title_ml": "സ്റ്റേജ്, സൗണ്ട് ക്വട്ടേഷനുകൾ ശേഖരിക്കുക", "owner_member_id": ids[2], "due": soon, "status": "open", "created_by": 1, "created": now, "updated": now})
        for mid in ids[1:]:
            c.execute("INSERT OR IGNORE INTO subscriptions(member_id, year, amount, status, due_on, created) VALUES(?,?,?,?,?,?)", (mid, year, 120, "due", f"{year}-04-30", now))
    print("demo data seeded: members sign in with their phone number and password member-pass-1")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create-admin" and len(sys.argv) >= 4:
        create_admin(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Administrator")
    elif cmd == "seed-demo":
        seed_demo()
    elif cmd == "daily":
        from . import scheduler
        db.init(); print(scheduler.run_daily(force=True))
    else:
        print(__doc__)
