"""Zwei-Wege-Abgleich der Blöcke mit simuliertem Google (M5: S-5 bis S-11, S-13 bis S-15).

Deckt das Abnahmekriterium von M5 ab: Ein Block erscheint im Timasy-Kalender;
Verschieben und Löschen funktionieren in beide Richtungen (S-7, S-8).
"""
import itertools
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend import clock, services
from backend.db import repository as repo
from backend.db.connection import connect, init_db
from backend.sync.errors import GoogleGone, GoogleNotFound, SyncTokenInvalid
from backend.sync.service import SyncService

ZH = ZoneInfo("Europe/Zurich")
TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 8, 0, tzinfo=ZH)


class FakeGoogleCalendar:
    """Simulierter Google Calendar mit Lesen und Schreiben."""

    def __init__(self):
        self.calendars = {"privat": {"summary": "Privat"}}
        self.events = {"privat": {}}
        self.changes = {"privat": []}
        self.ids = itertools.count(1)
        self.clock = NOW   # "updated"-Zeit für Änderungen in Google
        self.writes = []

    # --- Hilfen für die Tests: Änderungen "am Handy" ---------------------------
    def _touch(self, cal, item):
        self.clock += timedelta(minutes=1)
        item["updated"] = self.clock.isoformat()
        self.changes[cal].append(dict(item))

    def user_move(self, cal, gid, start, end):
        item = self.events[cal][gid]
        item["start"] = {"dateTime": start.isoformat()}
        item["end"] = {"dateTime": end.isoformat()}
        self._touch(cal, item)

    def user_delete(self, cal, gid):
        item = self.events[cal].pop(gid)
        self._touch(cal, {"id": gid, "status": "cancelled", "extendedProperties": item.get("extendedProperties", {})})

    def user_edit(self, cal, gid, **fields):
        self.events[cal][gid].update(fields)
        self._touch(cal, self.events[cal][gid])

    def user_add(self, cal, item):
        self.events[cal][item["id"]] = item
        self._touch(cal, item)

    # --- API, wie GoogleClient --------------------------------------------------
    def list_calendars(self):
        return [{"id": cid, "summary": c["summary"]} for cid, c in self.calendars.items()]

    def create_calendar(self, summary, time_zone):
        cid = f"cal{next(self.ids)}"
        self.calendars[cid] = {"summary": summary}
        self.events[cid] = {}
        self.changes[cid] = []
        return cid

    def list_events(self, calendar_id, time_min=None, time_max=None, sync_token=None, page_token=None):
        if calendar_id not in self.calendars:
            raise GoogleNotFound()
        if sync_token:
            items, self.changes[calendar_id] = self.changes[calendar_id], []
        else:
            items = [dict(e) for e in self.events[calendar_id].values()]
            self.changes[calendar_id] = []
        return {"items": items, "nextSyncToken": "t"}

    def insert_event(self, calendar_id, body):
        gid = f"ev{next(self.ids)}"
        item = dict(body, id=gid, status="confirmed")
        self.events[calendar_id][gid] = item
        self._touch(calendar_id, item)
        self.writes.append(("insert", gid))
        return gid

    def update_event(self, calendar_id, gid, body):
        if gid not in self.events[calendar_id]:
            raise GoogleGone()
        item = dict(body, id=gid, status="confirmed")
        self.events[calendar_id][gid] = item
        self._touch(calendar_id, item)
        self.writes.append(("update", gid))

    def delete_event(self, calendar_id, gid):
        if gid not in self.events[calendar_id]:
            raise GoogleGone()
        self.events[calendar_id].pop(gid)
        self._touch(calendar_id, {"id": gid, "status": "cancelled"})
        self.writes.append(("delete", gid))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMASY_TODAY", TODAY.isoformat())
    path = tmp_path / "t.db"
    init_db(path)
    google = FakeGoogleCalendar()
    service = SyncService(path, client_factory=lambda: google)
    return path, google, service


def db(path):
    return connect(path)


def plan(path, title="Bericht", day=TODAY, start=9 * 60, **kw):
    """Eintrag mit Block anlegen, wie über die Oberfläche."""
    conn = db(path)
    _, e = services.quick_capture(conn, title, NOW, day=day, start_minute=start, today=TODAY, **kw)
    conn.commit()
    conn.close()
    return e.id


def block_of(path, entry_id):
    return repo.blocks_for_entries(db(path), [entry_id]).get(entry_id)


def entry_of(path, entry_id):
    return repo.get_entry(db(path), entry_id)


def timasy_cal(path):
    return repo.get_setting(db(path), "timasy_calendar_id")


def at(d, h, m=0):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ZH)


# --- Timasy -> Google ------------------------------------------------------------

def test_block_appears_in_timasy_calendar(env):
    path, google, service = env
    eid = plan(path, tier=services.Tier.MUST)
    service.run_once()
    cal = timasy_cal(path)
    [event] = google.events[cal].values()
    assert event["summary"] == "Bericht"
    assert "Pflicht" in event["description"]
    assert event["start"]["dateTime"] == "2026-11-09T09:00:00+01:00"
    assert block_of(path, eid).google_event_id == event["id"]
    assert service.status()["state"] == "ok"


def test_second_run_changes_nothing(env):
    path, google, service = env
    plan(path)
    service.run_once()
    google.writes.clear()
    service.run_once()
    assert google.writes == []


def test_move_in_timasy_updates_google(env):
    path, google, service = env
    eid = plan(path)
    service.run_once()
    conn = db(path)
    b = repo.blocks_for_entries(conn, [eid])[eid]
    services.change_block(conn, b.id, TODAY, 14 * 60, 15 * 60, TODAY, clock.now())
    conn.commit()
    service.run_once()
    [event] = google.events[timasy_cal(path)].values()
    assert event["start"]["dateTime"] == "2026-11-09T14:00:00+01:00"


def test_title_and_tier_changes_are_pushed(env):
    path, google, service = env
    eid = plan(path)
    service.run_once()
    conn = db(path)
    e = repo.get_entry(conn, eid)
    services.update_task(conn, e.task_id, "Bericht fertig", "", None, [])
    services.change_entry(conn, eid, NOW, TODAY, tier=services.Tier.BONUS)
    conn.commit()
    service.run_once()
    [event] = google.events[timasy_cal(path)].values()
    assert event["summary"] == "Bericht fertig" and "Bonus" in event["description"]


def test_delete_in_timasy_deletes_in_google(env):
    # S-8
    path, google, service = env
    eid = plan(path)
    service.run_once()
    conn = db(path)
    services.remove_block(conn, block_of(path, eid).id)
    conn.commit()
    service.run_once()
    assert google.events[timasy_cal(path)] == {}


def test_carry_over_deletes_event(env, monkeypatch):
    # R-12: alter Block wird gelöscht, auch der Kalendereintrag in Google
    path, google, service = env
    plan(path)
    service.run_once()
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-10")
    conn = db(path)
    services.refresh(conn, date(2026, 11, 10), NOW)
    conn.commit()
    service.run_once()
    assert google.events[timasy_cal(path)] == {}


def test_removing_entry_deletes_event(env):
    path, google, service = env
    eid = plan(path)
    service.run_once()
    conn = db(path)
    services.remove_entry(conn, eid)
    conn.commit()
    service.run_once()
    assert google.events[timasy_cal(path)] == {}


def test_offline_changes_wait_in_queue(env):
    # S-10: Warteschlange, App bleibt nutzbar
    path, google, service = env
    eid = plan(path)
    service.run_once()
    conn = db(path)
    services.remove_block(conn, block_of(path, eid).id)
    conn.commit()
    working = service.client_factory
    service.client_factory = lambda: (_ for _ in ()).throw(OSError("offline"))
    service.run_once()
    assert service.status()["state"] == "error"
    assert repo.pending_deletions(db(path)) != []
    service.client_factory = working
    service.run_once()
    assert google.events[timasy_cal(path)] == {}
    assert repo.pending_deletions(db(path)) == []


def test_existing_blocks_uploaded_once(env):
    # S-15
    path, google, service = env
    for i in range(3):
        plan(path, title=f"T{i}", start=(8 + i) * 60)
    service.run_once()
    assert len(google.events[timasy_cal(path)]) == 3


def test_series_occurrences_become_single_events(env):
    # S-11
    path, google, service = env
    conn = db(path)
    services.create_series(conn, {"text": "Joggen", "starts_on": TODAY, "freq": "daily",
                                  "end_type": "count", "count": 3, "start_minute": 420,
                                  "duration_minutes": 30}, TODAY, NOW)
    conn.commit()
    service.run_once()
    starts = sorted(e["start"]["dateTime"] for e in google.events[timasy_cal(path)].values())
    assert starts == ["2026-11-09T07:00:00+01:00", "2026-11-10T07:00:00+01:00",
                      "2026-11-11T07:00:00+01:00"]


# --- Google -> Timasy ----------------------------------------------------------------

def test_move_in_google_is_taken_over(env):
    # S-7
    path, google, service = env
    eid = plan(path)
    service.run_once()
    gid = block_of(path, eid).google_event_id
    google.user_move(timasy_cal(path), gid, at(TODAY, 16), at(TODAY, 17, 30))
    service.run_once()
    b = block_of(path, eid)
    assert (b.start, b.end) == (at(TODAY, 16), at(TODAY, 17, 30))
    google.writes.clear()
    service.run_once()
    assert google.writes == []          # nicht hin und her


def test_move_to_other_day_in_google_moves_entry(env):
    path, google, service = env
    eid = plan(path)
    service.run_once()
    tomorrow = TODAY + timedelta(days=1)
    google.user_move(timasy_cal(path), block_of(path, eid).google_event_id, at(tomorrow, 9), at(tomorrow, 10))
    service.run_once()
    assert entry_of(path, eid).period_start == tomorrow       # R-23


def test_delete_in_google_keeps_entry(env):
    # S-8 / A-2: Eintrag verliert nur die Uhrzeit
    path, google, service = env
    eid = plan(path, tier=services.Tier.BONUS)
    service.run_once()
    google.user_delete(timasy_cal(path), block_of(path, eid).google_event_id)
    service.run_once()
    e = entry_of(path, eid)
    assert block_of(path, eid) is None
    assert (e.period_start, e.tier) == (TODAY, services.Tier.BONUS)
    assert repo.pending_deletions(db(path)) == []


def test_conflict_latest_change_wins(env):
    # S-7: beide geändert; Timasy später -> Timasy gewinnt
    path, google, service = env
    eid = plan(path)
    service.run_once()
    cal = timasy_cal(path)
    gid = block_of(path, eid).google_event_id
    google.clock = clock.now()
    google.user_move(cal, gid, at(TODAY, 16), at(TODAY, 17))          # Google: zuerst
    conn = db(path)
    services.change_block(conn, block_of(path, eid).id, TODAY, 11 * 60, 12 * 60, TODAY,
                          clock.now() + timedelta(minutes=5))           # Timasy: später
    conn.commit()
    service.run_once()
    assert block_of(path, eid).start == at(TODAY, 11)
    assert google.events[cal][gid]["start"]["dateTime"] == "2026-11-09T11:00:00+01:00"


def test_title_changed_in_google_is_overwritten(env):
    # S-6
    path, google, service = env
    eid = plan(path)
    service.run_once()
    cal = timasy_cal(path)
    gid = block_of(path, eid).google_event_id
    google.user_edit(cal, gid, summary="Am Handy umbenannt")
    service.run_once()
    assert google.events[cal][gid]["summary"] == "Bericht"


def test_all_day_in_google_is_reset(env):
    # S-13
    path, google, service = env
    eid = plan(path)
    service.run_once()
    cal = timasy_cal(path)
    gid = block_of(path, eid).google_event_id
    google.user_edit(cal, gid, start={"date": "2026-11-09"}, end={"date": "2026-11-10"})
    service.run_once()
    assert google.events[cal][gid]["start"]["dateTime"] == "2026-11-09T09:00:00+01:00"
    assert block_of(path, eid).start == at(TODAY, 9)


def test_handmade_event_in_timasy_calendar_ignored(env):
    # S-14
    path, google, service = env
    service.run_once()
    cal = timasy_cal(path)
    google.user_add(cal, {"id": "hand", "status": "confirmed", "summary": "Von Hand",
                          "start": {"dateTime": at(TODAY, 9).isoformat()},
                          "end": {"dateTime": at(TODAY, 10).isoformat()}})
    service.run_once()
    assert "hand" in google.events[cal]
    assert repo.all_blocks(db(path)) == []


def test_series_occurrence_moved_in_google_becomes_exception(env):
    path, google, service = env
    conn = db(path)
    s = services.create_series(conn, {"text": "Joggen", "starts_on": TODAY, "freq": "daily",
                                      "end_type": "count", "count": 2, "start_minute": 420},
                               TODAY, NOW)
    conn.commit()
    service.run_once()
    first = [e for e in repo.entries_for_series(db(path), s.id) if e.period_start == TODAY][0]
    google.user_move(timasy_cal(path), block_of(path, first.id).google_event_id,
                     at(TODAY, 18), at(TODAY, 18, 30))
    service.run_once()
    assert entry_of(path, first.id).is_exception is True


def test_timasy_calendar_deleted_in_google_is_recreated(env):
    path, google, service = env
    plan(path)
    service.run_once()
    old = timasy_cal(path)
    del google.calendars[old]
    service.run_once()
    service.run_once()
    new = timasy_cal(path)
    assert new != old and len(google.events[new]) == 1


def test_conflict_google_later_wins(env):
    path, google, service = env
    eid = plan(path)
    service.run_once()
    cal = timasy_cal(path)
    gid = block_of(path, eid).google_event_id
    conn = db(path)
    services.change_block(conn, block_of(path, eid).id, TODAY, 11 * 60, 12 * 60, TODAY,
                          clock.now())                                  # Timasy: zuerst
    conn.commit()
    google.clock = clock.now() + timedelta(minutes=5)
    google.user_move(cal, gid, at(TODAY, 16), at(TODAY, 17))          # Google: später
    service.run_once()
    assert block_of(path, eid).start == at(TODAY, 16)
