"""End-to-end workflows against a throwaway database: self-registration -> approval -> membership number, family
updates, publishing with push, meetings with members-only minutes, library circulation with fines, accounts,
broadcasts and the daily jobs. Messages go to a fake transport so nothing leaves the machine."""
import datetime as dt
import os
import tempfile

os.environ["CLUB_DATA"] = tempfile.mkdtemp(prefix="club-test-")
os.environ["CLUB_DEV"] = "1"
os.environ["CLUB_NO_WORKER"] = "1"
os.environ["CLUB_ADMIN_LOGIN"] = "admin@club.test"
os.environ["CLUB_ADMIN_PASSWORD"] = "admin-password-1"
os.environ["CLUB_PUBLIC_URL"] = "https://club.example.org"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import comms, db, i18n, scheduler  # noqa: E402
from app.main import app  # noqa: E402

H = {"X-Club": "1"}
SENT = []
comms.set_sender(lambda ch, to, subject, body: SENT.append((ch, to, subject, body)) or f"id-{len(SENT)}")


@pytest.fixture(scope="module")
def admin():
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"login": "admin@club.test", "password": "admin-password-1"}, headers=H)
        assert r.status_code == 200, r.text
        yield c


def login(login_, pw):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"login": login_, "password": pw}, headers=H)
    assert r.status_code == 200, r.text
    return c


def flush():
    comms.process_outbox(500)


def fresh():
    """Deliver whatever earlier steps queued, then start counting afresh."""
    flush()
    SENT.clear()


def test_public_info_and_registration_flow(admin):
    info = admin.get("/api/public/info").json()
    assert info["club_short"] == "ASC" and any(t["key"] == "life" for t in info["membership_types"])

    # self registration with family, in Malayalam
    r = admin.post("/api/public/apply", json={"name_en": "Ramesh Kumar", "name_ml": "രമേശ് കുമാർ", "phone": "98470 12345", "email": "ramesh@example.org",
                                              "dob": "1980-05-14", "blood_group": "O+", "ward": "7", "lang": "ml", "password": "ramesh-pass-1",
                                              "family": [{"name_en": "Sita", "name_ml": "സീത", "relation": "spouse", "dob": "1984-01-02"}]}, headers=H)
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    # the applicant is told, in Malayalam, on WhatsApp / SMS / e-mail
    flush()
    kinds = {(ch, to) for ch, to, *_ in SENT}
    assert ("whatsapp", "919847012345") in kinds and ("sms", "919847012345") in kinds and ("email", "ramesh@example.org") in kinds
    assert any("അപേക്ഷ" in body for *_, body in SENT)
    # cannot sign in before approval
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"login": "9847012345", "password": "ramesh-pass-1"}, headers=H).status_code == 403
    # duplicate phone is refused
    assert admin.post("/api/public/apply", json={"name_en": "Dup", "phone": "9847012345", "password": "whatever-123"}, headers=H).status_code == 409

    apps = admin.get("/api/members/applications").json()
    assert [a["id"] for a in apps] == [mid] and apps[0]["family"][0]["relation"] == "spouse"

    fresh()
    r = admin.post(f"/api/members/{mid}/decide", json={"decision": "approve"}, headers=H)
    assert r.status_code == 200, r.text
    no = r.json()["member_no"]
    assert no == f"ASC/{dt.date.today().year}/0001"
    flush()
    assert any(no in body and "സ്വാഗതം" in subj for ch, to, subj, body in SENT if ch == "whatsapp")
    m = admin.get(f"/api/members/{mid}").json()
    assert m["status"] == "active" and m["member_no"] == no
    # admission fee + annual subscription are now due (ordinary: 100 + 120)
    assert sorted(s["amount"] for s in m["subscriptions"]) == [100, 120]

    # the member signs in with the phone and updates the family
    mc = login("9847012345", "ramesh-pass-1")
    me = mc.get("/api/auth/me").json()
    assert me["user"]["role"] == "member" and me["member"]["member_no"] == no and "members.manage" not in me["user"]["perms"]
    r = mc.post(f"/api/members/{mid}/family", json={"name_en": "Arjun", "relation": "son", "dob": "2010-07-07", "blood_group": "O+"}, headers=H)
    assert r.status_code == 200
    fam = mc.get(f"/api/members/{mid}/family").json()
    assert len(fam) == 2 and fam[1]["verified"] == 0
    # but may not touch another member's record or the office lists
    assert mc.get("/api/members").status_code == 403
    assert mc.put("/api/members/999", json={"name_en": "x"}, headers=H).status_code == 403
    # directory shows them, blood group search works
    d = mc.get("/api/members/directory?blood=O%2B").json()
    assert d and d[0]["member_no"] == no
    # a second applicant gets the next number
    admin.post("/api/public/apply", json={"name_en": "Second", "phone": "9000000002", "password": "second-pass-1"}, headers=H)
    mid2 = admin.get("/api/members/applications").json()[0]["id"]
    assert admin.post(f"/api/members/{mid2}/decide", json={"decision": "approve"}, headers=H).json()["member_no"].endswith("/0002")
    # rejection notifies and blocks sign-in
    admin.post("/api/public/apply", json={"name_en": "Third", "phone": "9000000003", "password": "third-pass-1"}, headers=H)
    mid3 = admin.get("/api/members/applications").json()[0]["id"]
    fresh()
    admin.post(f"/api/members/{mid3}/decide", json={"decision": "reject", "note": "outside the ward"}, headers=H)
    flush()
    assert any("outside the ward" in body for *_, body in SENT)
    assert TestClient(app).post("/api/auth/login", json={"login": "9000000003", "password": "third-pass-1"}, headers=H).status_code == 403
    # office entry with a given number and the printable card
    r = admin.post("/api/members", json={"name_en": "Old Member", "phone": "9000000004", "member_no": "ASC/OLD/17", "membership_type": "life"}, headers=H)
    assert r.status_code == 200 and r.json()["member_no"] == "ASC/OLD/17"
    card = admin.get(f"/api/members/{mid}/card?lang=ml")
    assert card.status_code == 200 and no in card.text and "data:image/svg" in card.text
    csv_ = admin.get("/api/members/export/csv")
    assert csv_.status_code == 200 and no in csv_.text


def test_news_event_publish_register_results(admin):
    fresh()
    r = admin.post("/api/posts", json={"kind": "competition", "title_en": "Onam Sports Meet", "title_ml": "ഓണം കായികമേള", "body_en": "Annual sports meet", "body_ml": "വാർഷിക കായികമേള",
                                       "level": "panchayat", "starts_at": "2030-09-05T09:00", "venue_en": "School ground", "venue_ml": "സ്കൂൾ ഗ്രൗണ്ട്", "audience": "public",
                                       "reg_open": 1, "reg_family": 1, "items": [{"name_en": "100 m", "name_ml": "100 മീറ്റർ", "age_group": "senior", "max_entries": 1},
                                                                                 {"name_en": "Tug of war", "kind": "team"}]}, headers=H)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    # drafts are invisible to members
    mc = login("9847012345", "ramesh-pass-1")
    assert mc.get(f"/api/posts/{pid}").status_code == 404
    r = admin.post(f"/api/posts/{pid}/publish", json={"channels": ["app", "whatsapp", "sms"]}, headers=H)
    assert r.status_code == 200 and r.json()["queued"] > 0
    flush()
    wa = [body for ch, to, s, body in SENT if ch == "whatsapp" and to == "919847012345"]
    assert wa and "ഓണം കായികമേള" in wa[0] and "/p/" in wa[0]          # member's language is Malayalam; public link
    assert mc.get("/api/notifications").json()[0]["link"] == f"#/posts/{pid}"
    # public page, bilingual
    pub = TestClient(app).get(f"/p/{pid}?lang=en")
    assert pub.status_code == 200 and "Onam Sports Meet" in pub.text and "School ground" in pub.text
    assert "ഓണം കായികമേള" in TestClient(app).get(f"/p/{pid}").text
    # member registers self and a family member for an item; the item's limit puts the second on the wait list
    post = mc.get(f"/api/posts/{pid}").json()
    item = next(i for i in post["items"] if i["name_en"] == "100 m")
    fam = mc.get("/api/auth/me").json()["member"]["id"]
    fam_rows = mc.get(f"/api/members/{fam}/family").json()
    r1 = mc.post(f"/api/posts/{pid}/register", json={"item_id": item["id"]}, headers=H).json()
    r2 = mc.post(f"/api/posts/{pid}/register", json={"item_id": item["id"], "family_id": fam_rows[0]["id"]}, headers=H).json()
    assert r1["status"] == "registered" and r2["status"] == "waitlisted"
    assert mc.post(f"/api/posts/{pid}/register", json={"item_id": item["id"]}, headers=H).status_code == 409
    regs = admin.get(f"/api/posts/{pid}").json()["registrations"]
    assert {x["participant_name"] for x in regs} == {"Ramesh Kumar", "Sita"}
    # member may cancel their own, not promote it
    assert mc.post(f"/api/registrations/{r2['id']}/status", json={"status": "registered"}, headers=H).status_code == 403
    assert mc.post(f"/api/registrations/{r2['id']}/status", json={"status": "cancelled"}, headers=H).status_code == 200
    # results
    fresh()
    r = admin.post(f"/api/posts/{pid}/results", json={"results": [{"item_id": item["id"], "position": 1, "registration_id": r1["id"], "points": 5}],
                                                      "results_en": "100 m: 1. Ramesh Kumar", "notify": True, "channels": ["whatsapp"]}, headers=H)
    assert r.status_code == 200 and r.json()["queued"] >= 1
    assert mc.get(f"/api/posts/{pid}").json()["results"][0]["participant_name"] == "Ramesh Kumar"
    # committee-only post is hidden from a non-member of that committee
    cid = admin.get("/api/committees").json()[1]["id"]
    r = admin.post("/api/posts", json={"kind": "notice", "title_en": "Exec only", "audience": "committee", "committee_id": cid}, headers=H).json()
    admin.post(f"/api/posts/{r['id']}/publish", json={"notify": False}, headers=H)
    assert mc.get(f"/api/posts/{r['id']}").status_code == 404
    assert all(p["id"] != r["id"] for p in mc.get("/api/posts").json())


def test_committees_meetings_minutes_actions(admin):
    coms = admin.get("/api/committees").json()
    general = next(c for c in coms if c["kind"] == "general")
    execc = next(c for c in coms if c["kind"] == "executive")
    sports = next(c for c in coms if c["name_en"].startswith("Sports"))
    members = admin.get("/api/members?status=active").json()
    ramesh = next(m for m in members if m["name_en"] == "Ramesh Kumar")
    second = next(m for m in members if m["name_en"] == "Second")
    # Ramesh convenes the sports committee; Second is not on it
    assert admin.post(f"/api/committees/{sports['id']}/members", json={"member_id": ramesh["id"], "designation_en": "Convener", "designation_ml": "കൺവീനർ", "role": "convener"}, headers=H).status_code == 200
    admin.post(f"/api/committees/{execc['id']}/members", json={"member_id": ramesh["id"], "designation_en": "Member"}, headers=H)
    mc = login("9847012345", "ramesh-pass-1")
    sc = login("9000000002", "second-pass-1")
    # the convener schedules a meeting with an agenda and sends the notice
    r = mc.post("/api/meetings", json={"committee_id": sports["id"], "title_en": "Sports committee - September", "title_ml": "കായിക സമിതി - സെപ്റ്റംബർ", "scheduled_at": "2030-09-01T18:00",
                                       "venue_en": "Club hall", "quorum": 1, "agenda": [{"title_en": "Onam meet budget", "title_ml": "ഓണം മേള ബജറ്റ്", "kind": "resolution"},
                                                                                       {"title_en": "Ground maintenance"}]}, headers=H)
    assert r.status_code == 200, r.text
    meeting = r.json()["id"]
    fresh()
    assert mc.post(f"/api/meetings/{meeting}/notice", json={"channels": ["whatsapp"]}, headers=H).json()["queued"] == 1
    flush()
    assert "1. ഓണം മേള ബജറ്റ്" in SENT[0][3]
    # a non-member of that committee cannot see it, nor schedule one
    assert sc.get(f"/api/meetings/{meeting}").status_code == 403
    assert sc.post("/api/meetings", json={"committee_id": sports["id"], "title_en": "x", "scheduled_at": "2030-01-01"}, headers=H).status_code == 403
    assert all(m["id"] != meeting for m in sc.get("/api/meetings").json())
    # attendance and minutes
    mc.post(f"/api/meetings/{meeting}/attendance", json={"attendance": [{"member_id": ramesh["id"], "status": "present"}]}, headers=H)
    mt = mc.get(f"/api/meetings/{meeting}").json()
    agenda = mt["agenda"]
    agenda[0].update({"decision_en": "Rs 25,000 sanctioned", "decision_ml": "25,000 രൂപ അനുവദിച്ചു", "resolution_no": "SC/2030/01", "proposed_by": ramesh["id"]})
    r = mc.post("/api/meetings", json={"id": meeting, "committee_id": sports["id"], "agenda": agenda, "chaired_by": ramesh["id"], "recorded_by": ramesh["id"]}, headers=H)
    assert r.status_code == 200
    # an action item for Second (who is told) - the committee manager may assign to any member
    fresh()
    r = mc.post("/api/actions", json={"meeting_id": meeting, "agenda_item_id": agenda[1]["id"], "title_en": "Get three quotes for ground levelling", "owner_member_id": second["id"], "due": "2030-09-20"}, headers=H)
    assert r.status_code == 200, r.text
    action = r.json()["id"]
    flush()
    assert any("ground levelling" in body for *_, body in SENT)
    mine = sc.get("/api/actions?mine=1").json()
    assert [a["id"] for a in mine] == [action]
    # owner can progress it but not re-title it
    sc.post("/api/actions", json={"id": action, "status": "in_progress", "progress_note": "two quotes in", "title_en": "hacked"}, headers=H)
    a = sc.get("/api/actions?mine=1").json()[0]
    assert a["status"] == "in_progress" and a["title_en"].startswith("Get three")
    # add Second to the committee: they now see the notice and agenda but not the draft decisions
    admin.post(f"/api/committees/{sports['id']}/members", json={"member_id": second["id"]}, headers=H)
    sc = login("9000000002", "second-pass-1")
    mt = sc.get(f"/api/meetings/{meeting}").json()
    assert mt["draft_hidden"] and "decision_en" not in mt["agenda"][0]
    assert sc.get(f"/api/meetings/{meeting}/print").status_code == 403
    # publish the minutes: members are told and can now read and print them
    fresh()
    r = mc.post(f"/api/meetings/{meeting}/mom", json={"status": "published", "channels": ["whatsapp"]}, headers=H)
    assert r.status_code == 200 and r.json()["queued"] == 2
    mt = sc.get(f"/api/meetings/{meeting}").json()
    assert mt["agenda"][0]["decision_en"] == "Rs 25,000 sanctioned" and mt["status"] == "held"
    pr = sc.get(f"/api/meetings/{meeting}/print?lang=ml")
    assert pr.status_code == 200 and "25,000 രൂപ അനുവദിച്ചു" in pr.text and "SC/2030/01" in pr.text
    # only an officer signs off; afterwards it is approved
    assert mc.post(f"/api/meetings/{meeting}/mom", json={"status": "approved"}, headers=H).status_code == 403
    assert admin.post(f"/api/meetings/{meeting}/mom", json={"status": "approved"}, headers=H).status_code == 200
    assert admin.get(f"/api/meetings/{meeting}").json()["mom_status"] == "approved"
    # general body: every member sees it
    r = admin.post("/api/meetings", json={"committee_id": general["id"], "title_en": "Annual General Body", "scheduled_at": "2030-10-02T10:00"}, headers=H)
    assert sc.get(f"/api/meetings/{r.json()['id']}").status_code == 200
    # plans
    r = mc.post("/api/plans", json={"committee_id": sports["id"], "title_en": "Build a badminton court", "period": "2030-31", "budget": 150000, "owner_member_id": ramesh["id"]}, headers=H)
    assert r.status_code == 200 and mc.get("/api/plans").json()[0]["budget"] == 150000


def test_library_circulation(admin):
    r = admin.post("/api/library/books", json={"title_en": "Randamoozham", "title_ml": "രണ്ടാമൂഴം", "author_en": "M. T. Vasudevan Nair", "author_ml": "എം.ടി. വാസുദേവൻ നായർ",
                                               "language": "ml", "category": "novel", "price": 350, "add_copies": 2}, headers=H)
    assert r.status_code == 200, r.text
    book = r.json()["id"]
    accs = r.json()["accession_nos"]
    assert accs == ["00001", "00002"]
    members = admin.get("/api/members?status=active").json()
    ramesh = next(m for m in members if m["name_en"] == "Ramesh Kumar")
    second = next(m for m in members if m["name_en"] == "Second")
    fresh()
    r = admin.post("/api/library/issue", json={"member_id": ramesh["id"], "accession_no": "00001"}, headers=H)
    assert r.status_code == 200, r.text
    issue = r.json()["id"]
    assert r.json()["due_on"] == (dt.date.today() + dt.timedelta(days=14)).isoformat()
    flush()
    assert any("രണ്ടാമൂഴം" in body for *_, body in SENT)
    # same copy cannot go out twice; the book now shows one available
    assert admin.post("/api/library/issue", json={"member_id": second["id"], "accession_no": "00001"}, headers=H).status_code == 400
    b = admin.get(f"/api/library/books/{book}").json()
    assert sum(1 for c in b["copies"] if c["status"] == "available") == 1
    # the member sees their own loan and can renew once online
    mc = login("9847012345", "ramesh-pass-1")
    mine = mc.get("/api/library/issues").json()
    assert len(mine) == 1 and mine[0]["accession_no"] == "00001"
    assert mc.post("/api/library/renew", json={"issue_id": issue}, headers=H).status_code == 200
    assert mc.post("/api/library/renew", json={"issue_id": issue}, headers=H).status_code == 400
    # Second reserves the title; after the second copy goes out, a return makes it 'ready' and tells them
    admin.post("/api/library/issue", json={"member_id": second["id"], "accession_no": "00002"}, headers=H)
    sc = login("9000000002", "second-pass-1")
    assert sc.post("/api/library/reserve", json={"book_id": book}, headers=H).status_code == 200
    # overdue return with fine: back-date the due date
    with db.tx() as c:
        c.execute("UPDATE issues SET due_on=? WHERE id=?", ((dt.date.today() - dt.timedelta(days=5)).isoformat(), issue))
    assert admin.get("/api/library/issues?overdue=1").json()[0]["fine_now"] == 5
    fresh()
    r = admin.post("/api/library/return", json={"accession_no": "00001"}, headers=H)
    assert r.status_code == 200 and r.json()["fine"] == 5 and r.json()["receipt"]["head"] == "library_fine"
    flush()
    assert any("ലഭ്യമാണ്" in body or "available" in body for *_, body in SENT)   # reservation ready
    assert admin.get(f"/api/library/books/{book}").json()["reservations"][0]["status"] == "ready"
    # the fine receipt sits in accounts
    tx = admin.get("/api/finance/transactions?head=library_fine").json()
    assert tx["totals"]["receipt"] == 5 and tx["rows"][0]["no"].startswith("R/")
    # reading room and periodicals
    assert admin.post("/api/library/reading-room", json={"member_id": ramesh["id"], "purpose": "newspapers"}, headers=H).status_code == 200
    assert len(admin.get("/api/library/reading-room").json()["rows"]) == 1
    r = admin.post("/api/library/periodicals", json={"title_en": "Mathrubhumi", "title_ml": "മാതൃഭൂമി", "kind": "newspaper"}, headers=H)
    admin.post(f"/api/library/periodicals/{r.json()['id']}/received", json={}, headers=H)
    assert admin.get("/api/library/periodicals").json()[0]["last_received"] == dt.date.today().isoformat()
    assert "00001" in admin.get("/api/library/export/catalogue.csv").text
    # members cannot manage
    assert mc.post("/api/library/books", json={"title_en": "x"}, headers=H).status_code == 403


def test_finance_dues_and_broadcast(admin):
    members = admin.get("/api/members?status=active").json()
    ramesh = next(m for m in members if m["name_en"] == "Ramesh Kumar")
    year = dt.date.today().year
    fresh()
    r = admin.post("/api/finance/transactions", json={"kind": "receipt", "head": "subscription", "member_id": ramesh["id"], "amount": 120, "mode": "upi", "ref": "UPI123"}, headers=H)
    assert r.status_code == 200, r.text
    flush()
    assert any("രസീത്" in subj for ch, to, subj, body in SENT if ch == "whatsapp")
    m = admin.get(f"/api/members/{ramesh['id']}").json()
    sub = next(s for s in m["subscriptions"] if s["year"] == year)
    assert sub["status"] == "paid" and sub["paid"] == 120
    # admission fee still due; defaulters list shows it; reminders go out
    dues = admin.get("/api/finance/dues").json()
    assert any(d["member_id"] == ramesh["id"] and d["year"] == 0 for d in dues)
    assert admin.post("/api/finance/dues/generate", json={"year": year + 1}, headers=H).json()["created"] >= 2
    assert admin.post("/api/finance/dues/remind", json={"channels": ["whatsapp"]}, headers=H).json()["members"] >= 2
    # a payment voucher and the summary
    admin.post("/api/finance/transactions", json={"kind": "payment", "head": "books", "party": "DC Books", "amount": 1500, "mode": "bank"}, headers=H)
    s = admin.get("/api/finance/summary").json()
    assert s["receipts"] == 125 and s["payments"] == 1500 and s["balance"] == -1375
    # voiding a subscription receipt reopens the due
    tid = admin.get("/api/finance/transactions?head=subscription").json()["rows"][0]["id"]
    admin.post(f"/api/finance/transactions/{tid}/void", json={"note": "entered twice"}, headers=H)
    m = admin.get(f"/api/members/{ramesh['id']}").json()
    assert next(s for s in m["subscriptions"] if s["year"] == year)["status"] == "due"
    # a treasurer-only screen is closed to members; member sees their own dues
    mc = login("9847012345", "ramesh-pass-1")
    assert mc.get("/api/finance/transactions").status_code == 403
    assert len(mc.get("/api/finance/mine").json()["dues"]) >= 2
    # broadcast to a ward, bilingual, respecting channel consent
    mc.put(f"/api/members/{ramesh['id']}", json={"notify_sms": 0}, headers=H)
    assert admin.post("/api/broadcast/preview", json={"audience": {"kind": "ward", "value": "7"}}, headers=H).json()["recipients"] == 1
    fresh()
    r = admin.post("/api/broadcast", json={"audience": {"kind": "ward", "value": "7"}, "channels": ["whatsapp", "sms", "email"], "subject": "Cleaning drive",
                                           "body_en": "Cleaning drive on Sunday 7 am", "body_ml": "ഞായറാഴ്ച രാവിലെ 7-ന് ശുചീകരണം"}, headers=H)
    assert r.status_code == 200 and r.json()["recipients"] == 1
    flush()
    chans = {ch for ch, *_ in SENT}
    assert chans == {"whatsapp", "email"} and all("ശുചീകരണം" in body for *_, body in SENT)
    bl = admin.get("/api/broadcasts").json()
    assert bl[0]["delivery"].get("sent") == 2
    ob = admin.get("/api/outbox").json()
    assert ob["counts"]["sent"] >= 2 and ob["channels"]["app"] is True


def test_daily_jobs_and_dashboard(admin):
    members = admin.get("/api/members?status=active").json()
    ramesh = next(m for m in members if m["name_en"] == "Ramesh Kumar")
    today = dt.date.today()
    admin.put(f"/api/members/{ramesh['id']}", json={"dob": f"1980-{today.month:02d}-{today.day:02d}"}, headers=H)
    r = admin.post("/api/posts", json={"kind": "camp", "title_en": "Blood donation camp", "starts_at": (today + dt.timedelta(days=1)).isoformat() + "T09:00", "audience": "members"}, headers=H)
    admin.post(f"/api/posts/{r.json()['id']}/publish", json={"notify": False}, headers=H)
    fresh()
    out = scheduler.run_daily(force=True)
    assert out["birthdays"] >= 1 and out["event_reminders"] >= 1
    flush()
    assert any("ജന്മദിനാശംസകൾ" in subj for ch, to, subj, body in SENT if ch == "whatsapp")
    assert any("Blood donation camp" in body for *_, body in SENT)
    assert scheduler.run_daily().get("skipped") is True
    d = admin.get("/api/dashboard").json()
    assert d["office"]["members_active"] >= 3 and d["birthdays"][0]["id"] == ramesh["id"]
    ov = admin.get("/api/reports/overview").json()
    assert ov["by_type"] and ov["library_popular"][0]["title_en"] == "Randamoozham"
    # users & settings are admin-only
    mc = login("9847012345", "ramesh-pass-1")
    assert mc.get("/api/settings").status_code == 403 and mc.get("/api/users").status_code == 403
    assert admin.post("/api/settings", json={"club_short": "KASC", "member_no_prefix": "KASC"}, headers=H).status_code == 200
    assert admin.get("/api/public/info").json()["club_short"] == "KASC"
    # state-changing calls without the app header are refused (CSRF)
    assert admin.post("/api/settings", json={"club_short": "X"}).status_code == 403
    # a treasurer login
    assert admin.post("/api/users", json={"login": "treasurer@club.test", "name": "Treasurer", "role": "treasurer", "password": "treasurer-pass-1"}, headers=H).status_code == 200
    tc = login("treasurer@club.test", "treasurer-pass-1")
    assert tc.get("/api/finance/summary").status_code == 200 and tc.get("/api/members/applications").status_code == 403


def test_templates_render_in_both_languages():
    for key in i18n.TEMPLATES:
        for lang in ("en", "ml"):
            subj, body = i18n.render(key, lang, {"name": "X", "club": "C", "club_short": "S", "title": "T", "subject": "Sub", "body": "B", "no": "R1"})
            assert subj and body
    assert comms.normalise_phone("0 98470-12345") == "919847012345" and comms.normalise_phone("+91 98470 12345") == "919847012345"
    assert comms.wa_link("9847012345", "hi there").startswith("https://wa.me/919847012345?text=hi%20there")
