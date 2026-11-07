"""Tests für Backups (V-6, v0.9): Knopf und täglich automatisch, 14 behalten."""
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from backend.backup import AUTO_KEEP, create_backup, daily_backup, list_backups
from backend.db.connection import connect, init_db

ZH = ZoneInfo("Europe/Zurich")
NOW = datetime(2026, 11, 9, 8, 30, 15, tzinfo=ZH)


def make_db(tmp_path):
    path = tmp_path / "timasy.db"
    init_db(path)
    conn = connect(path)
    conn.execute("INSERT INTO task (title, created_at) VALUES ('Probe', '2026-11-09T08:00:00+01:00')")
    conn.commit()
    conn.close()
    return path


def test_manual_backup_is_full_copy(tmp_path):
    db = make_db(tmp_path)
    target = create_backup(db, tmp_path / "backups", NOW)
    assert target.name == "timasy-2026-11-09-083015.db"
    rows = sqlite3.connect(target).execute("SELECT title FROM task").fetchall()
    assert rows == [("Probe",)]


def test_daily_backup_once_per_day(tmp_path):
    db = make_db(tmp_path)
    folder = tmp_path / "backups"
    first = daily_backup(db, folder, NOW)
    assert first.name == "timasy-auto-2026-11-09.db"
    assert daily_backup(db, folder, NOW + timedelta(hours=3)) is None
    assert daily_backup(db, folder, NOW + timedelta(days=1)).name == "timasy-auto-2026-11-10.db"


def test_only_14_automatic_backups_kept(tmp_path):
    db = make_db(tmp_path)
    folder = tmp_path / "backups"
    create_backup(db, folder, NOW)                    # manuelles bleibt immer
    for i in range(20):
        daily_backup(db, folder, NOW + timedelta(days=i))
    names = [b["name"] for b in list_backups(folder)]
    autos = [n for n in names if "-auto-" in n]
    assert len(autos) == AUTO_KEEP == 14
    assert "timasy-auto-2026-11-28.db" in autos       # die neusten bleiben
    assert "timasy-auto-2026-11-09.db" not in autos
    assert "timasy-2026-11-09-083015.db" in names


def test_list_backups_newest_first(tmp_path):
    db = make_db(tmp_path)
    folder = tmp_path / "backups"
    create_backup(db, folder, NOW)
    create_backup(db, folder, NOW + timedelta(minutes=5))
    listed = list_backups(folder)
    assert [b["name"] for b in listed] == ["timasy-2026-11-09-083515.db", "timasy-2026-11-09-083015.db"]
    assert listed[0]["size"] > 0 and listed[0]["automatic"] is False
    assert list_backups(tmp_path / "gibtsnicht") == []
