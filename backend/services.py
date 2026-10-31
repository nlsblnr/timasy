"""Anwendungsfälle: verbindet Fachlogik (domain) und Datenbank (db).

Jede Funktion bekommt die Datenbankverbindung und, falls nötig, die aktuelle
Zeit übergeben. Die Regeln selbst stehen in backend/domain.
"""
import sqlite3
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta

from .db import repository as repo
from .domain.entries import assign_task, assign_to_day, mark_done, mark_open
from .domain.models import Entry, Scope, Status, Tier
from .domain.periods import week_start
from .domain.progress import Progress, day_progress, week_progress
from .domain.quick_capture import parse_quick_input
from .domain.rollover import carry_over, overdue_days


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


# --- Übertragung (R-9 bis R-11) ----------------------------------------------

def roll_over(conn: sqlite3.Connection, today: date) -> int:
    """Überträgt offene Einträge vergangener Zeiträume. Gibt die Anzahl zurück.

    Wird vor jeder Ansicht aufgerufen. So greift die Übertragung beim ersten
    Start an einem neuen Tag und beim Tageswechsel, solange die App läuft.
    Läuft sie mehrfach, passiert nichts Neues (es gibt dann nichts zu tun).
    """
    changed = carry_over(repo.open_entries_before(conn, today), today)
    for e in changed:
        repo.update_entry(conn, e)
    return len(changed)


# --- Aufgaben ----------------------------------------------------------------

def task_payload(conn, task_id: int) -> dict:
    row = repo.get_task(conn, task_id)
    if row is None:
        raise NotFound
    return _task_dict(row, repo.tags_for_tasks(conn, [task_id])[task_id])


def _task_dict(row, tags: list[str]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "notes": row["notes"],
        "estimated_minutes": row["estimated_minutes"],
        "created_at": row["created_at"],
        "tags": tags,
    }


def create_task(conn, title: str, now: datetime, notes: str = "",
                estimated_minutes: int | None = None, tags: list[str] = ()) -> int:
    title = title.strip()
    if not title:
        raise ValueError("Der Titel darf nicht leer sein.")
    task_id = repo.create_task(conn, title, notes, estimated_minutes, now)
    repo.set_task_tags(conn, task_id, tags)
    return task_id


def update_task(conn, task_id: int, title: str, notes: str,
                estimated_minutes: int | None, tags: list[str]) -> None:
    if repo.get_task(conn, task_id) is None:
        raise NotFound
    title = title.strip()
    if not title:
        raise ValueError("Der Titel darf nicht leer sein.")
    repo.update_task(conn, task_id, title, notes, estimated_minutes)
    repo.set_task_tags(conn, task_id, tags)


def delete_task(conn, task_id: int) -> None:
    """R-8: Aufgabe endgültig löschen (mit allen Einträgen)."""
    if repo.get_task(conn, task_id) is None:
        raise NotFound
    repo.delete_task(conn, task_id)


def backlog(conn) -> list[dict]:
    ids = repo.backlog_task_ids(conn)
    rows = repo.tasks_by_ids(conn, ids)
    tags = repo.tags_for_tasks(conn, ids)
    return [_task_dict(rows[i], tags[i]) for i in ids]


# --- Einträge ----------------------------------------------------------------

def entry_payloads(conn, entries: list[Entry], today: date) -> list[dict]:
    """Einträge mit den Angaben ihrer Aufgabe, so wie das Frontend sie braucht."""
    ids = [e.task_id for e in entries]
    tasks = repo.tasks_by_ids(conn, ids)
    tags = repo.tags_for_tasks(conn, ids)
    result = []
    for e in entries:
        d = asdict(e)
        d.update(
            scope=e.scope.value,
            tier=e.tier.value,
            status=e.status.value,
            period_start=e.period_start.isoformat(),
            done_at=e.done_at.isoformat() if e.done_at else None,
            overdue_since=e.overdue_since.isoformat() if e.overdue_since else None,
            overdue_days=overdue_days(e, today),
            task=_task_dict(tasks[e.task_id], tags[e.task_id]),
            title=tasks[e.task_id]["title"],
        )
        result.append(d)
    return result


def create_entry(conn, task_id: int, scope: Scope, period_start: date, tier: Tier) -> Entry:
    """R-5: Aufgabe einem Zeitraum zuweisen."""
    if repo.get_task(conn, task_id) is None:
        raise NotFound
    if any(e.status == Status.OPEN for e in repo.entries_for_task(conn, task_id)):
        # Eine Aufgabe ist zugewiesen, solange sie einen offenen Eintrag hat.
        raise Conflict("Die Aufgabe ist bereits einem Zeitraum zugewiesen.")
    e = assign_task(task_id, scope, period_start, tier)
    return replace(e, id=repo.insert_entry(conn, e))


def change_entry(conn, entry_id: int, now: datetime, done: bool | None = None,
                 tier: Tier | None = None, day: date | None = None) -> Entry:
    e = repo.get_entry(conn, entry_id)
    if e is None:
        raise NotFound
    if day is not None:
        e = assign_to_day(e, day, tier)  # R-6
    elif tier is not None:
        e = replace(e, tier=tier)
    if done is True and e.status != Status.DONE:
        e = mark_done(e, now)            # R-7
    elif done is False:
        e = mark_open(e)
    repo.update_entry(conn, e)
    return e


def remove_entry(conn, entry_id: int) -> None:
    """R-8: aus Zeitraum entfernen; die Aufgabe geht zurück in den Backlog."""
    if repo.get_entry(conn, entry_id) is None:
        raise NotFound
    repo.delete_entry(conn, entry_id)


def quick_capture(conn, text: str, now: datetime, tier: Tier = Tier.MUST,
                  scope: Scope = Scope.DAY, day: date | None = None, notes: str = "",
                  estimated_minutes: int | None = None,
                  extra_tags: list[str] = ()) -> tuple[int, Entry | None]:
    """V-7: Mit Datum entsteht ein Eintrag, ohne Datum eine Aufgabe im Backlog.

    notes, estimated_minutes und extra_tags kommen aus dem erweiterten Dialog.
    """
    title, tags = parse_quick_input(text)
    task_id = create_task(conn, title, now, notes, estimated_minutes, [*tags, *extra_tags])
    entry = create_entry(conn, task_id, scope, day, tier) if day else None
    return task_id, entry


# --- Ansichten ---------------------------------------------------------------

def _progress_dict(p: Progress) -> dict:
    return {
        "must_done": p.must_done,
        "must_total": p.must_total,
        "all_done": p.all_done,
        "all_total": p.all_total,
        "must_ratio": p.must_ratio,
        "all_ratio": p.all_ratio,
        "minimum_reached": p.minimum_reached,
    }


def day_view(conn, day: date, today: date) -> dict:
    """Daten für die Heute-Ansicht (V-1) eines beliebigen Tages."""
    monday = week_start(day)
    week_entries = repo.entries_between(conn, monday, monday + timedelta(days=6))
    day_entries = [e for e in week_entries if e.scope == Scope.DAY and e.period_start == day]
    open_week = [e for e in week_entries if e.scope == Scope.WEEK and e.status == Status.OPEN]
    return {
        "today": today.isoformat(),
        "date": day.isoformat(),
        "week_start": monday.isoformat(),
        "progress": _progress_dict(day_progress(week_entries, day)),
        "week_progress": _progress_dict(week_progress(week_entries, day)),
        "entries": entry_payloads(conn, day_entries, today),
        "week_entries": entry_payloads(conn, open_week, today),
    }
