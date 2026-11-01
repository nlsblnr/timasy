"""Tests für den Abgleich im Hintergrund (S-3, S-9, S-10) mit simuliertem Google."""
from datetime import date, datetime

import pytest

from backend.db import repository as repo
from backend.db.connection import connect, init_db
from backend.sync.errors import AuthExpired, NotConfigured, NotConnected
from backend.sync.service import SyncService
from tests.test_sync_read import FakeGoogle, item


class FakeWithCreate(FakeGoogle):
    def __init__(self):
        super().__init__()
        self.calendars = [c for c in self.calendars if c["id"] != "timasy"]
        self.created = []

    def create_calendar(self, summary, time_zone):
        self.created.append(summary)
        self.calendars.append({"id": "neu-timasy", "summary": summary})
        return "neu-timasy"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMASY_TODAY", "2026-11-04")
    path = tmp_path / "t.db"
    init_db(path)
    return path


def test_first_sync_creates_timasy_calendar_once(db):
    # S-3: beim ersten Abgleich Kalender "Timasy" anlegen und ID merken
    google = FakeWithCreate()
    service = SyncService(db, client_factory=lambda: google)
    service.run_once()
    service.run_once()
    assert google.created == ["Timasy"]
    conn = connect(db)
    assert repo.get_setting(conn, "timasy_calendar_id") == "neu-timasy"
    assert [c["id"] for c in repo.calendars(conn)] == ["arbeit", "privat"]   # Timasy nicht wählbar
    assert service.status()["state"] == "ok"
    assert service.status()["last_synced_at"] is not None


def test_sync_reads_selected_calendar(db):
    google = FakeWithCreate()
    google.add("privat", item("a", title="Zahnarzt"))
    service = SyncService(db, client_factory=lambda: google)
    service.run_once()
    conn = connect(db)
    repo.set_calendar_selected(conn, "privat", True)
    conn.commit()
    service.run_once()
    titles = [e.title for e in repo.external_events_between(connect(db), date(2026, 11, 4), date(2026, 11, 5))]
    assert titles == ["Zahnarzt"]


@pytest.mark.parametrize("error,state", [
    (NotConfigured(), "not_configured"),   # credentials.json fehlt
    (NotConnected(), "disconnected"),      # noch nie angemeldet
    (AuthExpired(), "reconnect"),          # S-10: "Neu verbinden"
])
def test_states_without_working_access(db, error, state):
    def factory():
        raise error
    service = SyncService(db, client_factory=factory)
    service.run_once()
    assert service.status()["state"] == state


def test_errors_retry_with_growing_wait(db):
    # S-10: erneut versuchen mit wachsenden Wartezeiten, höchstens bis zum Intervall
    def factory():
        raise OSError("offline")
    service = SyncService(db, client_factory=factory, interval_minutes=5)
    waits = []
    for _ in range(5):
        service.run_once()
        waits.append(service.next_wait_seconds())
    assert service.status()["state"] == "error"
    assert "offline" in service.status()["last_error"]
    assert waits == [60, 120, 240, 300, 300]


def test_success_resets_wait(db):
    calls = {"n": 0}
    google = FakeWithCreate()

    def factory():
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("offline")
        return google
    service = SyncService(db, client_factory=factory, interval_minutes=5)
    service.run_once()
    service.run_once()
    assert service.status()["state"] == "ok"
    assert service.next_wait_seconds() == 300
