"""Anwendungsfälle: verbindet Fachlogik (domain) und Datenbank (db).

Jede Funktion bekommt die Datenbankverbindung und, falls nötig, die aktuelle
Zeit übergeben. Die Regeln selbst stehen in backend/domain.
"""
import sqlite3
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta

from .db import repository as repo
from .domain.blocks import (
    Block, create_block, default_duration, local_minutes, minutes_on_day, move_block,
)
from .domain.entries import assign_task, mark_done, mark_open, move_entry_to_day
from .domain.models import Entry, Scope, Status, Tier
from .domain.periods import month_weeks, week_days, week_start
from .domain.progress import Progress, day_progress, week_progress
from .domain.quick_capture import parse_quick_input
from .domain.rollover import carry_over, overdue_days
from .domain.series import (
    EndType, Freq, MonthlyBy, Pattern, Series, end_series, make_entry, missing_occurrences,
    occurrences, preview, split_series, validate,
)


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


# --- Übertragung und Serien nachziehen (R-9 bis R-13, R-16) ----------------

def refresh(conn: sqlite3.Connection, today: date, now: datetime) -> None:
    """Wird vor jeder Ansicht aufgerufen.

    So greifen Übertragung und Serien beim ersten Start an einem neuen Tag und
    beim Tageswechsel, solange die App läuft. Läuft es mehrfach, passiert
    nichts Neues (es gibt dann nichts zu tun).
    """
    all_series = repo.all_series(conn)
    roll_over(conn, today, {s.id for s in all_series if s.carry_over})
    for series in all_series:
        generate(conn, series, today, now)


def roll_over(conn, today: date, carry_series: set[int] = frozenset()) -> int:
    """Überträgt offene Einträge vergangener Zeiträume (R-9 bis R-11) bzw.
    setzt Serien-Vorkommen auf "verpasst" (R-13). Gibt die Anzahl zurück."""
    changed = carry_over(repo.open_entries_before(conn, today), today, carry_series)
    blocks = repo.blocks_for_entries(conn, [e.id for e in changed])
    for e in changed:
        repo.update_entry(conn, e)
        if e.status == Status.OPEN and e.id in blocks:
            # R-12: Der alte Block wird gelöscht; am neuen Tag ist der
            # Eintrag zunächst nicht eingeplant. Verpasste behalten ihren Block.
            repo.delete_block(conn, blocks[e.id].id)
    return len(changed)


def generate(conn, series: Series, today: date, now: datetime) -> None:
    """R-16: Einträge (und Blöcke bei fester Uhrzeit) für die nächsten 90 Tage."""
    existing = {e.occurrence_date for e in repo.entries_for_series(conn, series.id)}
    missing = missing_occurrences(series, today, existing)
    if not missing:
        return
    estimate = repo.get_task(conn, series.task_id)["estimated_minutes"]
    for day in missing:
        e = make_entry(series, day)
        e = replace(e, id=repo.insert_entry(conn, e))
        if series.start_minute is not None:
            duration = series.duration_minutes or default_duration(estimate)
            end = min(series.start_minute + duration, 24 * 60)
            repo.insert_block(conn, create_block(e, day, series.start_minute, end, None, now))


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
    blocks = repo.blocks_for_entries(conn, [e.id for e in entries])
    result = []
    for e in entries:
        d = asdict(e)
        d.update(
            occurrence_date=e.occurrence_date.isoformat() if e.occurrence_date else None,
            scope=e.scope.value,
            tier=e.tier.value,
            status=e.status.value,
            period_start=e.period_start.isoformat(),
            done_at=e.done_at.isoformat() if e.done_at else None,
            overdue_since=e.overdue_since.isoformat() if e.overdue_since else None,
            overdue_days=overdue_days(e, today),
            task=_task_dict(tasks[e.task_id], tags[e.task_id]),
            title=tasks[e.task_id]["title"],
            block=block_payload(blocks[e.id]) if e.id in blocks else None,
        )
        result.append(d)
    return result


def block_payload(b: Block) -> dict:
    """Block fürs Frontend: Tag und Minuten seit Mitternacht in Ortszeit."""
    day, start_minute = local_minutes(b.start)
    return {
        "id": b.id,
        "day": day.isoformat(),
        "start_minute": start_minute,
        "end_minute": minutes_on_day(day, b.end),
        "start": b.start.isoformat(),
        "end": b.end.isoformat(),
    }


def create_entry(conn, task_id: int, scope: Scope, period_start: date, tier: Tier) -> Entry:
    """R-5: Aufgabe einem Zeitraum zuweisen."""
    if repo.get_task(conn, task_id) is None:
        raise NotFound
    if any(e.status == Status.OPEN for e in repo.entries_for_task(conn, task_id)):
        # Eine Aufgabe ist zugewiesen, solange sie einen offenen Eintrag hat.
        raise Conflict("Die Aufgabe ist bereits einem Zeitraum zugewiesen.")
    e = assign_task(task_id, scope, period_start, tier)
    return replace(e, id=repo.insert_entry(conn, e))


def change_entry(conn, entry_id: int, now: datetime, today: date, done: bool | None = None,
                 tier: Tier | None = None, day: date | None = None) -> Entry:
    e = repo.get_entry(conn, entry_id)
    if e is None:
        raise NotFound
    if day is not None and (e.scope == Scope.WEEK or day != e.period_start):
        e = move_entry_to_day(e, day, today)  # bei Wochen-Einträgen R-6
        _move_block_with_entry(conn, e, now)
        e = _as_exception(e)
    if tier is not None and tier != e.tier:
        e = _as_exception(replace(e, tier=tier))
    if done is True and e.status != Status.DONE:
        e = mark_done(e, now)            # R-7
    elif done is False:
        e = mark_open(e)
    repo.update_entry(conn, e)
    return e


def _as_exception(e: Entry) -> Entry:
    """R-27: Ein einzeln geändertes Serien-Vorkommen wird zur Ausnahme (R-17)."""
    return replace(e, is_exception=True) if e.series_id is not None else e


def _move_block_with_entry(conn, e: Entry, now: datetime) -> None:
    """Hat der Eintrag einen Block, kommt er mit gleicher Uhrzeit auf den neuen Tag (R-19)."""
    block = repo.blocks_for_entries(conn, [e.id]).get(e.id)
    if block is None:
        return
    old_day, start = local_minutes(block.start)
    end = minutes_on_day(old_day, block.end)
    moved, _ = move_block(block, e, e.period_start, start, end, e.period_start, now)
    repo.update_block(conn, moved)


def schedule_entry(conn, entry_id: int, day: date, start_minute: int, end_minute: int | None,
                   today: date, now: datetime) -> Entry:
    """Eintrag auf eine Uhrzeit legen (Drag & Drop, V-1/V-2).

    Liegt der Eintrag an einem anderen Tag oder in der Woche, kommt er auf
    diesen Tag (R-6, R-23). Hat er schon einen Block, wird dieser verschoben
    (Dauer bleibt, wenn kein Ende angegeben ist), sonst entsteht ein neuer (R-21).
    """
    e = repo.get_entry(conn, entry_id)
    if e is None:
        raise NotFound
    block = repo.blocks_for_entries(conn, [e.id]).get(e.id)
    if block:
        if end_minute is None:
            duration = round((block.end - block.start).total_seconds() / 60)
            end_minute = min(start_minute + duration, 24 * 60)
        block, e = move_block(block, e, day, start_minute, end_minute, today, now)
        repo.update_block(conn, block)
    else:
        if e.scope == Scope.WEEK or day != e.period_start:
            e = move_entry_to_day(e, day, today)
        task = repo.get_task(conn, e.task_id)
        block = create_block(e, day, start_minute, end_minute, task["estimated_minutes"], now)
        repo.insert_block(conn, block)
    e = _as_exception(e)
    repo.update_entry(conn, e)
    return e


def change_block(conn, block_id: int, day: date, start_minute: int, end_minute: int,
                 today: date, now: datetime) -> Entry:
    """Block verschieben oder Länge ändern; R-23: Eintrag wandert mit."""
    block = repo.get_block(conn, block_id)
    if block is None:
        raise NotFound
    e = repo.get_entry(conn, block.entry_id)
    block, e = move_block(block, e, day, start_minute, end_minute, today, now)
    repo.update_block(conn, block)
    e = _as_exception(e)
    repo.update_entry(conn, e)
    return e


def remove_block(conn, block_id: int) -> None:
    """Block löschen; der Eintrag bleibt, ist aber nicht mehr eingeplant."""
    block = repo.get_block(conn, block_id)
    if block is None:
        raise NotFound
    repo.delete_block(conn, block_id)
    e = repo.get_entry(conn, block.entry_id)
    repo.update_entry(conn, _as_exception(e))


def remove_entry(conn, entry_id: int) -> None:
    """R-8: aus Zeitraum entfernen; die Aufgabe geht zurück in den Backlog.

    Bei Serien-Vorkommen wird nur dieses Vorkommen gelöscht (R-27).
    """
    e = repo.get_entry(conn, entry_id)
    if e is None:
        raise NotFound
    if e.series_id is not None:
        delete_occurrence(conn, entry_id, "this", e.period_start)
        return
    repo.delete_entry(conn, entry_id)


def quick_capture(conn, text: str, now: datetime, tier: Tier = Tier.MUST,
                  scope: Scope = Scope.DAY, day: date | None = None, notes: str = "",
                  estimated_minutes: int | None = None, extra_tags: list[str] = (),
                  start_minute: int | None = None,
                  today: date | None = None) -> tuple[int, Entry | None]:
    """V-7: Mit Datum entsteht ein Eintrag, ohne Datum eine Aufgabe im Backlog.

    notes, estimated_minutes, extra_tags und start_minute (Uhrzeit, ergibt
    einen Block) kommen aus dem erweiterten Dialog.
    """
    title, tags = parse_quick_input(text)
    task_id = create_task(conn, title, now, notes, estimated_minutes, [*tags, *extra_tags])
    entry = create_entry(conn, task_id, scope, day, tier) if day else None
    if entry and start_minute is not None:
        entry = schedule_entry(conn, entry.id, day, start_minute, None, today or day, now)
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


def week_view(conn, any_day: date, today: date) -> dict:
    """Daten für die Wochenansicht (V-2)."""
    monday = week_start(any_day)
    days = week_days(monday)
    entries = repo.entries_between(conn, monday, days[-1])
    return {
        "today": today.isoformat(),
        "week_start": monday.isoformat(),
        "days": [d.isoformat() for d in days],
        "progress": _progress_dict(week_progress(entries, monday)),
        "entries": entry_payloads(conn, [e for e in entries if e.scope == Scope.DAY], today),
        "week_entries": entry_payloads(conn, [e for e in entries if e.scope == Scope.WEEK], today),
    }


def month_view(conn, any_day: date, today: date) -> dict:
    """Daten für die Monatsansicht (V-3): pro Tag offene Pflicht-Einträge und Blöcke."""
    weeks = month_weeks(any_day.year, any_day.month)
    entries = [e for e in repo.entries_between(conn, weeks[0][0], weeks[-1][-1])
               if e.scope == Scope.DAY]
    blocks = repo.blocks_for_entries(conn, [e.id for e in entries])
    open_must: dict[date, int] = {}
    block_count: dict[date, int] = {}
    for e in entries:
        if e.status == Status.OPEN and e.tier == Tier.MUST:
            open_must[e.period_start] = open_must.get(e.period_start, 0) + 1
        if e.id in blocks:
            block_count[e.period_start] = block_count.get(e.period_start, 0) + 1
    return {
        "today": today.isoformat(),
        "month": f"{any_day.year:04d}-{any_day.month:02d}",
        "weeks": [[{
            "date": d.isoformat(),
            "in_month": d.month == any_day.month,
            "open_must": open_must.get(d, 0),
            "blocks": block_count.get(d, 0),
        } for d in week] for week in weeks],
    }


# --- Serien (M3) ----------------------------------------------------------------

def build_series(task_id: int, data: dict, base: Series | None = None) -> Series:
    """Serie aus den Angaben des Formulars bauen (V-8).

    Mit base werden nur die angegebenen Felder geändert, der Rest bleibt.
    """
    def get(key, default=None):
        if key in data:
            return data[key]
        return default

    old = base.pattern if base else Pattern(Freq.DAILY)
    pattern = Pattern(
        freq=Freq(get("freq", old.freq)),
        interval=get("interval", old.interval) or 1,
        weekdays=tuple(sorted(get("weekdays", old.weekdays) or ())),
        monthly_by=MonthlyBy(get("monthly_by", old.monthly_by)),
    )
    if pattern.freq != Freq.WEEKLY:
        pattern = replace(pattern, weekdays=())
    end_type = EndType(get("end_type", base.end_type if base else EndType.NEVER))
    return Series(
        id=base.id if base else None,
        task_id=task_id,
        pattern=pattern,
        starts_on=get("starts_on", base.starts_on if base else None),
        end_type=end_type,
        until_date=get("until_date", base.until_date if base else None) if end_type == EndType.UNTIL else None,
        count=get("count", base.count if base else None) if end_type == EndType.COUNT else None,
        tier=Tier(get("tier", base.tier if base else Tier.MUST)),
        scope=Scope(get("scope", base.scope if base else Scope.DAY)),
        start_minute=get("start_minute", base.start_minute if base else None),
        duration_minutes=get("duration_minutes", base.duration_minutes if base else None),
        carry_over=bool(get("carry_over", base.carry_over if base else False)),
        exdates=base.exdates if base else frozenset(),
    )


def create_series(conn, data: dict, today: date, now: datetime) -> Series:
    """Neue Serie mit Vorlage-Aufgabe anlegen und Einträge erzeugen."""
    series = build_series(0, data)
    validate(series)
    title, tags = parse_quick_input(data["text"])
    task_id = create_task(conn, title, now, data.get("notes", ""),
                          data.get("estimated_minutes"), [*tags, *data.get("tags", [])])
    series = replace(series, task_id=task_id)
    series = replace(series, id=repo.insert_series(conn, series))
    generate(conn, series, today, now)
    return series


def preview_series(data: dict) -> list[date]:
    """V-8: die nächsten Vorkommen ab Start."""
    series = build_series(0, data)
    validate(series)
    return preview(series)


def _horizon_start(series: Series, today: date) -> date:
    """Ab hier gelten Vorkommen als "künftig" (bei Wochen: diese Woche)."""
    return week_start(today) if series.scope == Scope.WEEK else today


def series_payload(conn, series: Series, today: date) -> dict:
    task = task_payload(conn, series.task_id)
    upcoming = occurrences(series, max(_horizon_start(series, today), series.starts_on),
                           today + timedelta(days=366 * 3))
    return {
        "id": series.id,
        "task": task,
        "title": task["title"],
        "freq": series.pattern.freq.value,
        "interval": series.pattern.interval,
        "weekdays": list(series.pattern.weekdays),
        "monthly_by": series.pattern.monthly_by.value,
        "starts_on": series.starts_on.isoformat(),
        "end_type": series.end_type.value,
        "until_date": series.until_date.isoformat() if series.until_date else None,
        "count": series.count,
        "tier": series.tier.value,
        "scope": series.scope.value,
        "start_minute": series.start_minute,
        "duration_minutes": series.duration_minutes,
        "carry_over": series.carry_over,
        "next_occurrence": upcoming[0].isoformat() if upcoming else None,
    }


def list_series(conn, today: date) -> list[dict]:
    return [series_payload(conn, s, today) for s in repo.all_series(conn)]


def get_series(conn, series_id: int) -> Series:
    series = repo.get_series(conn, series_id)
    if series is None:
        raise NotFound
    return series


def set_carry_over(conn, series_id: int, value: bool) -> Series:
    series = replace(get_series(conn, series_id), carry_over=value)
    repo.update_series(conn, series)
    return series


def end_series_now(conn, series_id: int, today: date) -> Series:
    """R-26 / V-5: Serie endet heute; offene Vorkommen ab morgen verschwinden."""
    series = end_series(get_series(conn, series_id), today)
    repo.update_series(conn, series)
    for e in repo.entries_for_series(conn, series.id):
        if e.status == Status.OPEN and e.period_start > _horizon_start(series, today):
            _delete_entry_and_copy(conn, e, series)
    return series


def _delete_entry_and_copy(conn, e: Entry, series: Series | None) -> None:
    """Eintrag löschen; eine eigene Aufgaben-Kopie (R-25) wird mitgelöscht."""
    repo.delete_entry(conn, e.id)
    if (series is None or e.task_id != series.task_id) and repo.task_is_unused(conn, e.task_id):
        repo.delete_task(conn, e.task_id)


def _drop_future(conn, series: Series, first: date, keep_exceptions: bool = True) -> None:
    """Offene Vorkommen ab einem Datum entfernen (Ausnahmen bleiben, R-17)."""
    for e in repo.entries_for_series(conn, series.id):
        if (e.status == Status.OPEN and e.occurrence_date >= first
                and not (keep_exceptions and e.is_exception)):
            _delete_entry_and_copy(conn, e, series)


TEXT_FIELDS = ("title", "notes", "estimated_minutes", "tags")


def _apply_text(conn, task_id: int, data: dict, copy: bool, now: datetime) -> int:
    """Titel, Notiz, Dauer, Tags ändern. Mit copy=True entsteht eine neue Aufgabe
    (R-25), sonst wird die bestehende geändert. Gibt die Aufgaben-ID zurück."""
    if not any(k in data for k in TEXT_FIELDS):
        return task_id
    current = task_payload(conn, task_id)
    new = {k: data.get(k, current[k]) for k in TEXT_FIELDS}
    if all(new[k] == current[k] for k in TEXT_FIELDS if k != "tags") and \
            sorted(new["tags"]) == sorted(current["tags"]):
        return task_id  # nichts geändert
    if copy:
        return create_task(conn, new["title"], now, new["notes"], new["estimated_minutes"],
                           new["tags"])
    update_task(conn, task_id, new["title"], new["notes"], new["estimated_minutes"], new["tags"])
    return task_id


def edit_occurrence(conn, entry_id: int, mode: str, data: dict,
                    today: date, now: datetime) -> Entry:
    """R-17: ein Vorkommen bearbeiten – "this", "following" oder "all".

    data enthält nur die Felder, die das Formular mitschickt.
    """
    e = repo.get_entry(conn, entry_id)
    if e is None:
        raise NotFound
    if e.series_id is None:
        raise ValueError("Der Eintrag gehört zu keiner Serie.")
    series = get_series(conn, e.series_id)

    if mode == "following" and e.occurrence_date <= series.starts_on:
        mode = "all"  # ab dem ersten Vorkommen ist "folgende" dasselbe wie "alle"

    if mode == "this":
        # Text: eigene Kopie, solange das Vorkommen noch die Vorlage teilt (R-25)
        e = replace(e, task_id=_apply_text(conn, e.task_id, data,
                                           copy=e.task_id == series.task_id, now=now))
        if data.get("tier"):
            e = replace(e, tier=Tier(data["tier"]))
        if data.get("day") and data["day"] != e.period_start:
            e = move_entry_to_day(e, data["day"], today)
            _move_block_with_entry(conn, e, now)
        e = replace(e, is_exception=True)
        repo.update_entry(conn, e)
        if "start_minute" in data:
            _set_time(conn, e, data["start_minute"], data.get("duration_minutes"), today, now)
        return repo.get_entry(conn, e.id)

    if mode == "all":
        _apply_text(conn, series.task_id, data, copy=False, now=now)
        updated = build_series(series.task_id, data, base=series)
        validate(updated)
        repo.update_series(conn, updated)
        _drop_future(conn, series, _horizon_start(series, today))
        generate(conn, updated, today, now)
        target_series = updated
    elif mode == "following":
        old, new = split_series(series, e.occurrence_date)
        task_id = _apply_text(conn, series.task_id, data, copy=True, now=now)
        new = build_series(task_id, {k: v for k, v in data.items() if k != "starts_on"}, base=new)
        new = replace(new, id=None)
        validate(new)
        repo.update_series(conn, old)
        new = replace(new, id=repo.insert_series(conn, new))
        _drop_future(conn, series, e.occurrence_date)
        generate(conn, new, today, now)
        target_series = new
    else:
        raise ValueError("Unbekannte Art der Bearbeitung.")

    # Offene Vorkommen wurden neu erzeugt: das bearbeitete wiederfinden
    # (gleiches Datum in der geänderten bzw. neuen Serie).
    current = repo.get_entry(conn, entry_id)
    if current and current.series_id == target_series.id:
        return current
    for x in repo.entries_for_series(conn, target_series.id):
        if x.occurrence_date == e.occurrence_date:
            return x
    return current or e


def _set_time(conn, e: Entry, start_minute: int | None, duration: int | None,
              today: date, now: datetime) -> None:
    """Uhrzeit eines einzelnen Vorkommens setzen oder entfernen."""
    block = repo.blocks_for_entries(conn, [e.id]).get(e.id)
    if start_minute is None:
        if block:
            repo.delete_block(conn, block.id)
        return
    end = None
    if duration:
        end = min(start_minute + duration, 24 * 60)
    schedule_entry(conn, e.id, e.period_start, start_minute, end, today, now)


def delete_occurrence(conn, entry_id: int, mode: str, today: date) -> None:
    """R-17 Löschen: "this", "following" oder "all" (R-28)."""
    e = repo.get_entry(conn, entry_id)
    if e is None:
        raise NotFound
    if e.series_id is None:
        raise ValueError("Der Eintrag gehört zu keiner Serie.")
    series = get_series(conn, e.series_id)
    if mode == "following" and e.occurrence_date <= series.starts_on:
        mode = "all"

    if mode == "this":
        # Datum merken, damit das Vorkommen nicht neu erzeugt wird
        repo.update_series(conn, replace(series, exdates=series.exdates | {e.occurrence_date}))
        _delete_entry_and_copy(conn, e, series)
    elif mode == "following":
        old, _ = split_series(series, e.occurrence_date)
        repo.update_series(conn, old)
        _drop_future(conn, series, e.occurrence_date)
    elif mode == "all":
        delete_series(conn, series.id)
    else:
        raise ValueError("Unbekannte Art des Löschens.")


def delete_series(conn, series_id: int) -> None:
    """R-28: Serie mit allen offenen und verpassten Vorkommen löschen; erledigte bleiben."""
    series = get_series(conn, series_id)
    for e in repo.entries_for_series(conn, series.id):
        if e.status != Status.DONE:
            _delete_entry_and_copy(conn, e, series)
    repo.delete_series(conn, series.id)   # erledigte behalten ihren Eintrag ohne Serie
    if repo.task_is_unused(conn, series.task_id):
        repo.delete_task(conn, series.task_id)
