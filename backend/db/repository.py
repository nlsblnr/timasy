"""Lesen und Schreiben in der Datenbank.

Hier steht nur SQL, keine Fachlogik. Einträge werden als domain.Entry
zurückgegeben, damit die Fachlogik direkt damit arbeiten kann.
"""
import sqlite3
from datetime import date, datetime
from typing import Iterable

from ..domain.blocks import Block
from ..domain.models import Entry, Scope, Status, Tier
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
    bei tausenden Einträgen schnell bleibt.
    """
    rows = conn.execute(
        """
        SELECT id FROM task
        WHERE NOT EXISTS (
            SELECT 1 FROM entry
            WHERE entry.task_id = task.id AND entry.status IN ('open', 'done')
        )
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
