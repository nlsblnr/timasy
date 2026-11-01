"""Lesen und Schreiben in der Datenbank.

Hier steht nur SQL, keine Fachlogik. Einträge werden als domain.Entry
zurückgegeben, damit die Fachlogik direkt damit arbeiten kann.
"""
import sqlite3
from datetime import date, datetime, timedelta
from typing import Iterable

from ..domain.blocks import Block
from ..domain.external import ExternalEvent, Key
from ..domain.models import Entry, Scope, Status, Tier
from ..domain.series import EndType, Series, from_rrule, to_rrule
from ..domain.tags import normalize_tag


# --- Umwandlung Zeile <-> Entry ----------------------------------------------

def _to_entry(row: sqlite3.Row) -> Entry:
    return Entry(
        id=row["id"],
        task_id=row["task_id"],
        scope=Scope(row["scope"]),
        period_start=date.fromisoformat(row["period_start"]),
        tier=Tier(row["tier"]),
        status=Status(row["status"]),
        done_at=datetime.fromisoformat(row["done_at"]) if row["done_at"] else None,
        overdue=bool(row["overdue"]),
        overdue_since=date.fromisoformat(row["overdue_since"]) if row["overdue_since"] else None,
        series_id=row["series_id"],
        occurrence_date=date.fromisoformat(row["occurrence_date"]) if row["occurrence_date"] else None,
        is_exception=bool(row["is_exception"]),
    )


def _entry_values(e: Entry) -> dict:
    return {
        "task_id": e.task_id,
        "scope": e.scope.value,
        "period_start": e.period_start.isoformat(),
        "tier": e.tier.value,
        "status": e.status.value,
        "done_at": e.done_at.isoformat() if e.done_at else None,
        "overdue": int(e.overdue),
        "overdue_since": e.overdue_since.isoformat() if e.overdue_since else None,
        "series_id": e.series_id,
        "occurrence_date": e.occurrence_date.isoformat() if e.occurrence_date else None,
        "is_exception": int(e.is_exception),
    }


# --- Aufgaben ----------------------------------------------------------------

def create_task(conn, title: str, notes: str, estimated_minutes: int | None,
                created_at: datetime) -> int:
    cur = conn.execute(
        "INSERT INTO task (title, notes, estimated_minutes, created_at) VALUES (?, ?, ?, ?)",
        (title, notes, estimated_minutes, created_at.isoformat()),
    )
    return cur.lastrowid


def get_task(conn, task_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()


def update_task(conn, task_id: int, title: str, notes: str,
                estimated_minutes: int | None) -> None:
    conn.execute(
        "UPDATE task SET title = ?, notes = ?, estimated_minutes = ? WHERE id = ?",
        (title, notes, estimated_minutes, task_id),
    )


def delete_task(conn, task_id: int) -> None:
    # Einträge und Tag-Verknüpfungen werden per ON DELETE CASCADE mitgelöscht.
    conn.execute("DELETE FROM task WHERE id = ?", (task_id,))
    _delete_unused_tags(conn)


def tasks_by_ids(conn, ids: Iterable[int]) -> dict[int, sqlite3.Row]:
    ids = list(set(ids))
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT * FROM task WHERE id IN ({marks})", ids).fetchall()
    return {r["id"]: r for r in rows}


def backlog_task_ids(conn) -> list[int]:
    """Aufgaben ohne offenen und ohne erledigten Eintrag (Backlog, v0.2).

    Entspricht domain.entries.is_in_backlog, aber direkt in SQL, damit es auch
    bei tausenden Einträgen schnell bleibt. Vorlagen von Serien gehören nie
    in den Backlog.
    """
    rows = conn.execute(
        """
        SELECT id FROM task
        WHERE NOT EXISTS (
            SELECT 1 FROM entry
            WHERE entry.task_id = task.id AND entry.status IN ('open', 'done')
        )
        AND NOT EXISTS (SELECT 1 FROM series WHERE series.task_id = task.id)
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return [r["id"] for r in rows]


# --- Tags --------------------------------------------------------------------

def set_task_tags(conn, task_id: int, names: Iterable[str]) -> None:
    conn.execute("DELETE FROM task_tag WHERE task_id = ?", (task_id,))
    for name in {normalize_tag(n) for n in names} - {""}:
        conn.execute("INSERT OR IGNORE INTO tag (name) VALUES (?)", (name,))
        tag_id = conn.execute("SELECT id FROM tag WHERE name = ?", (name,)).fetchone()["id"]
        conn.execute("INSERT INTO task_tag (task_id, tag_id) VALUES (?, ?)", (task_id, tag_id))
    _delete_unused_tags(conn)


def tags_for_tasks(conn, task_ids: Iterable[int]) -> dict[int, list[str]]:
    ids = list(set(task_ids))
    result: dict[int, list[str]] = {i: [] for i in ids}
    if not ids:
        return result
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"""
        SELECT task_tag.task_id, tag.name FROM task_tag
        JOIN tag ON tag.id = task_tag.tag_id
        WHERE task_tag.task_id IN ({marks})
        ORDER BY tag.name
        """,
        ids,
    ).fetchall()
    for r in rows:
        result[r["task_id"]].append(r["name"])
    return result


def all_tags(conn) -> list[str]:
    return [r["name"] for r in conn.execute("SELECT name FROM tag ORDER BY name")]


def _delete_unused_tags(conn) -> None:
    """Tags ohne Aufgabe werden entfernt, damit sie nicht mehr vorgeschlagen werden."""
    conn.execute("DELETE FROM tag WHERE id NOT IN (SELECT tag_id FROM task_tag)")


# --- Einträge ----------------------------------------------------------------

def insert_entry(conn, e: Entry) -> int:
    v = _entry_values(e)
    cols = ", ".join(v)
    marks = ", ".join(f":{k}" for k in v)
    return conn.execute(f"INSERT INTO entry ({cols}) VALUES ({marks})", v).lastrowid


def update_entry(conn, e: Entry) -> None:
    v = _entry_values(e)
    sets = ", ".join(f"{k} = :{k}" for k in v)
    conn.execute(f"UPDATE entry SET {sets} WHERE id = :id", {**v, "id": e.id})


def get_entry(conn, entry_id: int) -> Entry | None:
    row = conn.execute("SELECT * FROM entry WHERE id = ?", (entry_id,)).fetchone()
    return _to_entry(row) if row else None


def delete_entry(conn, entry_id: int) -> None:
    conn.execute("DELETE FROM entry WHERE id = ?", (entry_id,))


def entries_for_task(conn, task_id: int) -> list[Entry]:
    rows = conn.execute("SELECT * FROM entry WHERE task_id = ?", (task_id,)).fetchall()
    return [_to_entry(r) for r in rows]


def entries_between(conn, first: date, last: date) -> list[Entry]:
    """Alle Einträge, deren period_start im Bereich liegt (beide einschliesslich)."""
    rows = conn.execute(
        "SELECT * FROM entry WHERE period_start BETWEEN ? AND ? ORDER BY id",
        (first.isoformat(), last.isoformat()),
    ).fetchall()
    return [_to_entry(r) for r in rows]


def open_entries_before(conn, day: date) -> list[Entry]:
    """Kandidaten für die Übertragung (R-9, R-11)."""
    rows = conn.execute(
        "SELECT * FROM entry WHERE status = 'open' AND period_start < ?",
        (day.isoformat(),),
    ).fetchall()
    return [_to_entry(r) for r in rows]


# --- Blöcke ------------------------------------------------------------------

def _to_block(row) -> Block:
    def dt(v):
        return datetime.fromisoformat(v) if v else None
    return Block(
        id=row["id"],
        entry_id=row["entry_id"],
        start=dt(row["start"]),
        end=dt(row["end"]),
        google_event_id=row["google_event_id"],
        local_updated_at=dt(row["local_updated_at"]),
        last_synced_at=dt(row["last_synced_at"]),
    )


def _block_values(b: Block) -> dict:
    def iso(v):
        return v.isoformat() if v else None
    return {
        "entry_id": b.entry_id,
        "start": iso(b.start),
        "end": iso(b.end),
        "google_event_id": b.google_event_id,
        "local_updated_at": iso(b.local_updated_at),
        "last_synced_at": iso(b.last_synced_at),
    }


def insert_block(conn, b: Block) -> int:
    v = _block_values(b)
    return conn.execute(
        'INSERT INTO block (entry_id, start, "end", google_event_id, local_updated_at, '
        "last_synced_at) VALUES (:entry_id, :start, :end, :google_event_id, "
        ":local_updated_at, :last_synced_at)", v).lastrowid


def update_block(conn, b: Block) -> None:
    conn.execute(
        'UPDATE block SET entry_id = :entry_id, start = :start, "end" = :end, '
        "google_event_id = :google_event_id, local_updated_at = :local_updated_at, "
        "last_synced_at = :last_synced_at WHERE id = :id", {**_block_values(b), "id": b.id})


def get_block(conn, block_id: int) -> Block | None:
    row = conn.execute("SELECT * FROM block WHERE id = ?", (block_id,)).fetchone()
    return _to_block(row) if row else None


def delete_block(conn, block_id: int) -> None:
    conn.execute("DELETE FROM block WHERE id = ?", (block_id,))


def blocks_for_entries(conn, entry_ids: Iterable[int]) -> dict[int, Block]:
    """Blöcke nach entry_id; Einträge ohne Block fehlen im Ergebnis."""
    ids = list(set(entry_ids))
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT * FROM block WHERE entry_id IN ({marks})", ids).fetchall()
    return {r["entry_id"]: _to_block(r) for r in rows}


def task_is_unused(conn, task_id: int) -> bool:
    """Keine Einträge und keine Serie verweisen mehr auf die Aufgabe."""
    return conn.execute(
        "SELECT NOT EXISTS (SELECT 1 FROM entry WHERE task_id = ?) "
        "AND NOT EXISTS (SELECT 1 FROM series WHERE task_id = ?)",
        (task_id, task_id)).fetchone()[0] == 1


def entries_for_series(conn, series_id: int) -> list[Entry]:
    rows = conn.execute("SELECT * FROM entry WHERE series_id = ? ORDER BY occurrence_date",
                        (series_id,)).fetchall()
    return [_to_entry(r) for r in rows]


# --- Serien --------------------------------------------------------------------

def _to_series(row) -> Series:
    def d(v):
        return date.fromisoformat(v) if v else None
    return Series(
        id=row["id"],
        task_id=row["task_id"],
        pattern=from_rrule(row["rrule"]),
        starts_on=d(row["starts_on"]),
        end_type=EndType(row["end_type"]),
        tier=Tier(row["tier"]),
        scope=Scope(row["scope"]),
        until_date=d(row["until_date"]),
        count=row["count"],
        start_minute=row["start_minute"],
        duration_minutes=row["duration_minutes"],
        carry_over=bool(row["carry_over"]),
        exdates=frozenset(date.fromisoformat(x) for x in row["exdates"].split(",") if x),
    )


def _series_values(s: Series) -> dict:
    return {
        "task_id": s.task_id,
        "rrule": to_rrule(s.pattern, s.starts_on),
        "starts_on": s.starts_on.isoformat(),
        "end_type": s.end_type.value,
        "until_date": s.until_date.isoformat() if s.until_date else None,
        "count": s.count,
        "tier": s.tier.value,
        "scope": s.scope.value,
        "start_minute": s.start_minute,
        "duration_minutes": s.duration_minutes,
        "carry_over": int(s.carry_over),
        "exdates": ",".join(sorted(d.isoformat() for d in s.exdates)),
    }


def insert_series(conn, s: Series) -> int:
    v = _series_values(s)
    cols = ", ".join(v)
    marks = ", ".join(f":{k}" for k in v)
    return conn.execute(f"INSERT INTO series ({cols}) VALUES ({marks})", v).lastrowid


def update_series(conn, s: Series) -> None:
    v = _series_values(s)
    sets = ", ".join(f"{k} = :{k}" for k in v)
    conn.execute(f"UPDATE series SET {sets} WHERE id = :id", {**v, "id": s.id})


def get_series(conn, series_id: int) -> Series | None:
    row = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    return _to_series(row) if row else None


def all_series(conn) -> list[Series]:
    return [_to_series(r) for r in conn.execute("SELECT * FROM series ORDER BY id")]


def delete_series(conn, series_id: int) -> None:
    conn.execute("DELETE FROM series WHERE id = ?", (series_id,))


# --- Einstellungen -------------------------------------------------------------

def get_setting(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn, key: str, value: str | None) -> None:
    conn.execute("INSERT INTO setting (key, value) VALUES (?, ?) "
                 "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, value))


# --- Google-Kalender und Sync-Stand -------------------------------------------

def save_calendars(conn, calendars: list[dict]) -> None:
    """Kalenderliste von Google übernehmen; die Auswahl bleibt erhalten."""
    ids = [c["id"] for c in calendars]
    for c in calendars:
        conn.execute(
            "INSERT INTO google_calendar (id, summary, color) VALUES (?, ?, ?) "
            "ON CONFLICT (id) DO UPDATE SET summary = excluded.summary, color = excluded.color",
            (c["id"], c["summary"], c.get("color")))
    marks = ",".join("?" * len(ids)) or "''"
    gone = [r["id"] for r in conn.execute(
        f"SELECT id FROM google_calendar WHERE id NOT IN ({marks})", ids)]
    for cal_id in gone:  # in Google entfernte Kalender
        forget_calendar(conn, cal_id)
        conn.execute("DELETE FROM google_calendar WHERE id = ?", (cal_id,))


def calendars(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM google_calendar ORDER BY summary COLLATE NOCASE")
    return [dict(r) | {"selected": bool(r["selected"])} for r in rows]


def set_calendar_selected(conn, calendar_id: str, selected: bool) -> bool:
    cur = conn.execute("UPDATE google_calendar SET selected = ? WHERE id = ?",
                       (int(selected), calendar_id))
    if not selected:
        forget_calendar(conn, calendar_id)
    return cur.rowcount == 1


def selected_calendar_ids(conn) -> list[str]:
    return [r["id"] for r in conn.execute("SELECT id FROM google_calendar WHERE selected = 1")]


def forget_calendar(conn, calendar_id: str) -> None:
    """Zwischenspeicher und Sync-Stand eines Kalenders löschen."""
    conn.execute("DELETE FROM external_event WHERE calendar_id = ?", (calendar_id,))
    conn.execute("DELETE FROM sync_state WHERE calendar_id = ?", (calendar_id,))


def get_sync_state(conn, calendar_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM sync_state WHERE calendar_id = ?", (calendar_id,)).fetchone()


def save_sync_state(conn, calendar_id: str, sync_token: str | None, window_start: date,
                    synced_at: datetime) -> None:
    conn.execute(
        "INSERT INTO sync_state (calendar_id, sync_token, window_start, last_synced_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT (calendar_id) DO UPDATE SET "
        "sync_token = excluded.sync_token, window_start = excluded.window_start, "
        "last_synced_at = excluded.last_synced_at",
        (calendar_id, sync_token, window_start.isoformat(), synced_at.isoformat()))


def last_synced_at(conn) -> str | None:
    return conn.execute("SELECT MAX(last_synced_at) FROM sync_state").fetchone()[0]


# --- Fremdtermine --------------------------------------------------------------

def _to_external(row) -> ExternalEvent:
    return ExternalEvent(
        calendar_id=row["calendar_id"],
        google_event_id=row["google_event_id"],
        title=row["title"],
        start=datetime.fromisoformat(row["start"]),
        end=datetime.fromisoformat(row["end"]),
        all_day=bool(row["all_day"]),
        updated=datetime.fromisoformat(row["updated"]) if row["updated"] else None,
    )


def external_events_for_calendar(conn, calendar_id: str) -> dict[Key, ExternalEvent]:
    rows = conn.execute("SELECT * FROM external_event WHERE calendar_id = ?", (calendar_id,))
    return {(r["calendar_id"], r["google_event_id"]): _to_external(r) for r in rows}


def save_external_events(conn, upserts: list[ExternalEvent], deletes: set[Key]) -> None:
    for key in deletes:
        conn.execute("DELETE FROM external_event WHERE calendar_id = ? AND google_event_id = ?", key)
    for e in upserts:
        conn.execute(
            'INSERT INTO external_event (calendar_id, google_event_id, title, start, "end", '
            "all_day, updated) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (calendar_id, google_event_id) DO UPDATE SET title = excluded.title, "
            'start = excluded.start, "end" = excluded."end", all_day = excluded.all_day, '
            "updated = excluded.updated",
            (e.calendar_id, e.google_event_id, e.title, e.start.isoformat(), e.end.isoformat(),
             int(e.all_day), e.updated.isoformat() if e.updated else None))


def external_events_between(conn, first: date, last: date) -> list[ExternalEvent]:
    """Termine aus gewählten Kalendern, die Tage von first bis last berühren.

    Gespeichert wird mit Zeitzonen-Versatz; für den groben Vergleich als Text
    nehmen wir je einen Tag Reserve und filtern danach genau (events_on_day).
    """
    lo = (first - timedelta(days=1)).isoformat()
    hi = (last + timedelta(days=2)).isoformat()
    rows = conn.execute(
        'SELECT e.* FROM external_event e JOIN google_calendar c ON c.id = e.calendar_id '
        'WHERE c.selected = 1 AND e."end" > ? AND e.start < ? ORDER BY e.start', (lo, hi))
    return [_to_external(r) for r in rows]
