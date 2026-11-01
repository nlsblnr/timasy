"""Tests für das Lesen aus Google (S-4, S-8, S-10) mit einem simulierten Google."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from backend.db import repository as repo
from backend.db.connection import connect, init_db
from backend.sync.errors import SyncTokenInvalid
from backend.sync.read import sync_calendar_list, sync_external

ZH = ZoneInfo("Europe/Zurich")
TODAY = date(2026, 11, 4)
NOW = datetime(2026, 11, 4, 8, 0, tzinfo=ZH)


def item(id, day="2026-11-04", h=9, title="Termin", status="confirmed"):
    return {"id": id, "status": status, "summary": title,
            "start": {"dateTime": f"{day}T{h:02d}:00:00+01:00"},
            "end": {"dateTime": f"{day}T{h + 1:02d}:00:00+01:00"}}


class FakeGoogle:
    """Verhält sich wie die Google-Calendar-API, soweit wir sie brauchen."""

    def __init__(self):
        self.calendars = [{"id": "privat", "summary": "Privat"}, {"id": "arbeit", "summary": "Arbeit"},
                          {"id": "timasy", "summary": "Timasy"}]
        self.events = {"privat": {}, "arbeit": {}}
        self.changes = {"privat": [], "arbeit": []}   # seit dem letzten Token
        self.calls = []
        self.token_invalid = False
        self.page_size = 2

    def add(self, cal, it):
        self.events[cal][it["id"]] = it
        self.changes[cal].append(it)

    def delete(self, cal, id):
        self.events[cal].pop(id)
        self.changes[cal].append({"id": id, "status": "cancelled"})

    def list_calendars(self):
        return self.calendars

    def list_events(self, calendar_id, time_min=None, time_max=None, sync_token=None, page_token=None):
        self.calls.append((calendar_id, "incremental" if sync_token else "full"))
        if sync_token and self.token_invalid:
            raise SyncTokenInvalid()
        if sync_token:
            items = list(self.changes[calendar_id])
        else:
            items = [e for e in self.events[calendar_id].values()
                     if time_min <= e["start"]["dateTime"] < time_max]
        start = int(page_token or 0)
        page = items[start:start + self.page_size]
        result = {"items": page}
        if start + self.page_size < len(items):
            result["nextPageToken"] = str(start + self.page_size)
        else:
            result["nextSyncToken"] = "token"
            self.changes[calendar_id] = []
        return result


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "t.db"
    init_db(path)
    c = connect(path)
    yield c
    c.close()


@pytest.fixture
def google():
    return FakeGoogle()


def titles(conn):
    return sorted(e.title for e in repo.external_events_between(conn, TODAY, date(2027, 3, 1)))


def setup(conn, google, select=("privat",)):
    repo.set_setting(conn, "timasy_calendar_id", "timasy")
    sync_calendar_list(conn, google)
    for cal in select:
        repo.set_calendar_selected(conn, cal, True)


def test_calendar_list_without_timasy(conn, google):
    setup(conn, google, select=())
    assert [c["id"] for c in repo.calendars(conn)] == ["arbeit", "privat"]
    assert all(not c["selected"] for c in repo.calendars(conn))   # Standard: keiner (v0.5)


def test_nothing_read_without_selection(conn, google):
    setup(conn, google, select=())
    google.add("privat", item("a"))
    sync_external(conn, google, TODAY, NOW)
    assert google.calls == []
    assert titles(conn) == []


def test_full_sync_reads_selected_calendar_with_pages(conn, google):
    setup(conn, google)
    for i in range(5):
        google.add("privat", item(f"p{i}", title=f"P{i}"))
    google.add("arbeit", item("w", title="Arbeit"))
    sync_external(conn, google, TODAY, NOW)
    assert titles(conn) == ["P0", "P1", "P2", "P3", "P4"]
    assert ("arbeit", "full") not in google.calls


def test_incremental_sync_update_and_delete(conn, google):
    # Änderung am Handy erscheint beim nächsten Abgleich (M4 "Fertig, wenn")
    setup(conn, google)
    google.add("privat", item("a", title="Zahnarzt"))
    google.add("privat", item("b", title="Coiffeur"))
    sync_external(conn, google, TODAY, NOW)
    google.add("privat", item("a", h=14, title="Zahnarzt verschoben"))
    google.delete("privat", "b")
    google.add("privat", item("c", title="Neu"))
    sync_external(conn, google, TODAY, NOW)
    assert google.calls[-1] == ("privat", "incremental")
    assert titles(conn) == ["Neu", "Zahnarzt verschoben"]


def test_invalid_token_triggers_full_sync(conn, google):
    # S-4: ist der Token ungültig, wird neu abgeglichen
    setup(conn, google)
    google.add("privat", item("a", title="A"))
    sync_external(conn, google, TODAY, NOW)
    google.token_invalid = True
    google.events["privat"].pop("a")          # gelöscht, ohne dass wir es inkrementell erfahren
    google.add("privat", item("b", title="B"))
    sync_external(conn, google, TODAY, NOW)
    assert google.calls[-1] == ("privat", "full")
    assert titles(conn) == ["B"]


def test_new_day_means_full_sync_and_window_moves(conn, google):
    setup(conn, google)
    google.add("privat", item("old", day="2026-11-04", title="Heute"))
    google.add("privat", item("far", day="2027-02-03", title="Tag 91"))  # ausserhalb des Fensters
    sync_external(conn, google, TODAY, NOW)
    assert titles(conn) == ["Heute"]
    sync_external(conn, google, date(2026, 11, 5), NOW)          # nächster Tag
    assert google.calls[-1] == ("privat", "full")
    assert titles(conn) == ["Tag 91"]    # gestern fällt raus, Tag 91 kommt dazu


def test_deselect_removes_cached_events(conn, google):
    setup(conn, google)
    google.add("privat", item("a"))
    sync_external(conn, google, TODAY, NOW)
    repo.set_calendar_selected(conn, "privat", False)
    assert titles(conn) == []
    assert repo.get_sync_state(conn, "privat") is None


def test_calendar_removed_in_google(conn, google):
    setup(conn, google)
    google.add("privat", item("a"))
    sync_external(conn, google, TODAY, NOW)
    google.calendars = [c for c in google.calendars if c["id"] != "privat"]
    sync_calendar_list(conn, google)
    assert [c["id"] for c in repo.calendars(conn)] == ["arbeit"]
    assert titles(conn) == []
