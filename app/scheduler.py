"""The daily tick: birthday wishes, event reminders, book due / overdue reminders. Runs once a day in a thread,
remembering the last run in settings so a restart does not repeat it; `run_daily(force=True)` is the manual button."""
import datetime as dt
import logging
import os
import threading
import time

from . import backup, comms, db, i18n, tenancy

log = logging.getLogger("club.scheduler")


def run_daily(force=False):
    today = dt.date.today()
    t = today.isoformat()
    if not force and db.setting("last_daily_run", "") == t:
        return {"skipped": True}
    out = {"birthdays": 0, "event_reminders": 0, "due_soon": 0, "overdue": 0}
    with db.tx() as c:
        if force or db.setting("last_daily_run", "") != t:
            db.set_setting(c, "last_daily_run", t)
            # birthdays
            ids = [r["id"] for r in db.q("SELECT id FROM members WHERE status='active' AND substr(dob,6,5)=?", (t[5:],))]
            out["birthdays"] = comms.notify_members(c, ids, "birthday", {}, ("app", "whatsapp"), ref_kind="birthday", batch_id=comms.new_batch())
            # event reminders, N days before
            days = int(db.setting("reminder_days_before_event"))
            target = (today + dt.timedelta(days=days)).isoformat()
            from .news import audience_for_post, _when
            for p in db.q("SELECT * FROM posts WHERE status='published' AND deleted=0 AND kind<>'news' AND substr(starts_at,1,10)=? AND reminded_at IS NULL", (target,)):
                link = f"{comms.club_ctx()['link']}/#/posts/{p['id']}"
                out["event_reminders"] += comms.notify_members(c, audience_for_post(p), "event_reminder", {"link": link}, ("app", "whatsapp"), ref_kind="post", ref_id=p["id"],
                                                               batch_id=comms.new_batch(), per_member=lambda m, p=p: {"title": i18n.pick(p, "title", m["lang"]), "when": _when(p, m["lang"]),
                                                                                                                      "venue": i18n.pick(p, "venue", m["lang"])})
                c.execute("UPDATE posts SET reminded_at=? WHERE id=?", (time.time(), p["id"]))
            # books due tomorrow
            tomorrow = (today + dt.timedelta(days=1)).isoformat()
            for i in db.q("SELECT i.*, b.title_en, b.title_ml FROM issues i JOIN books b ON b.id=i.book_id WHERE i.returned_on='' AND i.due_on=? AND i.reminded_at IS NULL", (tomorrow,)):
                out["due_soon"] += comms.notify_members(c, [i["member_id"]], "book_due", {"due": i["due_on"]}, ("app", "whatsapp"), ref_kind="issue", ref_id=i["id"],
                                                        per_member=lambda m, i=i: {"book": i18n.pick(i, "title", m["lang"])})
                c.execute("UPDATE issues SET reminded_at=? WHERE id=?", (time.time(), i["id"]))
            # overdue: once a week per issue
            week_ago = time.time() - 7 * 86400
            fine_per_day = float(db.setting("library_fine_per_day"))
            for i in db.q("SELECT i.*, b.title_en, b.title_ml FROM issues i JOIN books b ON b.id=i.book_id WHERE i.returned_on='' AND i.due_on<? AND (i.reminded_at IS NULL OR i.reminded_at<?)", (t, week_ago)):
                late = (today - dt.date.fromisoformat(i["due_on"])).days
                out["overdue"] += comms.notify_members(c, [i["member_id"]], "book_overdue", {"due": i["due_on"], "days": late, "fine": f"{late * fine_per_day:,.0f}"}, ("app", "whatsapp", "sms"),
                                                       ref_kind="issue", ref_id=i["id"], per_member=lambda m, i=i: {"book": i18n.pick(i, "title", m["lang"])})
                c.execute("UPDATE issues SET reminded_at=? WHERE id=?", (time.time(), i["id"]))
    return out


def nightly_backup(force=False):
    """Once a day after CLUB_BACKUP_HOUR (default 2 am): local backup, Drive upload when configured."""
    today = dt.date.today().isoformat()
    if not force and (db.setting("last_backup_day", "") == today or dt.datetime.now().hour < int(os.environ.get("CLUB_BACKUP_HOUR", "2"))):
        return None
    with db.tx() as c:
        db.set_setting(c, "last_backup_day", today)
    return backup.run("nightly")


_thread = None


def start():
    global _thread
    if _thread or os.environ.get("CLUB_NO_WORKER"):
        return

    def run():
        last_saas = ""
        while True:
            today = dt.date.today().isoformat()
            if last_saas != today:
                try:
                    from . import saas
                    saas.daily()
                    last_saas = today
                except Exception:  # noqa: BLE001
                    log.exception("plan daily job")
            for slug in tenancy.all_slugs():
                try:
                    with tenancy.use(slug):
                        if dt.datetime.now().hour >= int(os.environ.get("CLUB_DAILY_HOUR", "8")):
                            run_daily()
                        nightly_backup()
                except Exception:  # noqa: BLE001
                    log.exception("daily job for %s", slug)
            time.sleep(600)

    _thread = threading.Thread(target=run, name="club-daily", daemon=True)
    _thread.start()
