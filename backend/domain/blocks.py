"""Blöcke: eingeplante Uhrzeit für einen Tages-Eintrag (R-19 bis R-21, R-23).

Zeiten rechnen wir in Minuten seit Mitternacht in Ortszeit (Europe/Zurich),
z.B. 9:15 Uhr = 555. Das Frontend arbeitet mit denselben Zahlen; so spielen
Zeitzone und Sommerzeit nur an einer Stelle eine Rolle (local_time).
"""
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Iterable

from ..config import TIMEZONE
from .entries import move_entry_to_day
from .models import Entry, Scope

DEFAULT_MINUTES = 30        # R-21
MINUTES_PER_DAY = 24 * 60


@dataclass(frozen=True)
class Block:
    id: int | None
    entry_id: int
    start: datetime                       # mit Zeitzone
    end: datetime
    google_event_id: str | None = None    # ab M5 (Google)
    local_updated_at: datetime | None = None
    last_synced_at: datetime | None = None


def default_duration(estimated_minutes: int | None) -> int:
    """R-21: Dauer aus der Schätzung, sonst 30 Minuten."""
    return estimated_minutes or DEFAULT_MINUTES


def local_time(day: date, minute: int) -> datetime:
    """Tag + Minuten seit Mitternacht -> Zeitpunkt in Ortszeit.

    Python rechnet bei einer Zeit mit Zeitzone "Mitternacht + n Minuten" in
    Wanduhrzeit. 9 Uhr bleibt also auch am Tag der Zeitumstellung 9 Uhr.
    """
    return datetime.combine(day, time(0), TIMEZONE) + timedelta(minutes=minute)


def local_minutes(moment: datetime) -> tuple[date, int]:
    """Zeitpunkt -> (Tag, Minuten seit Mitternacht) in Ortszeit."""
    local = moment.astimezone(TIMEZONE)
    return local.date(), local.hour * 60 + local.minute


def minutes_on_day(day: date, moment: datetime) -> int:
    """Minuten seit Mitternacht des Tages; das Ende 0 Uhr am Folgetag ergibt 1440."""
    d, m = local_minutes(moment)
    return m + (d - day).days * MINUTES_PER_DAY


def _check_times(start_minute: int, end_minute: int) -> None:
    """R-19: Ein Block liegt innerhalb eines Tages und hat eine Dauer."""
    if not 0 <= start_minute < end_minute <= MINUTES_PER_DAY:
        raise ValueError("Ein Block muss innerhalb eines Tages liegen und darf nicht leer sein.")


def create_block(entry: Entry, day: date, start_minute: int, end_minute: int | None,
                 estimated_minutes: int | None, now: datetime) -> Block:
    """Neuen Block für einen Tages-Eintrag anlegen (R-19, R-21).

    Ohne end_minute gilt die Standarddauer, höchstens bis Mitternacht.
    """
    if entry.scope != Scope.DAY:
        raise ValueError("Ein Wochen-Eintrag muss erst einem Tag zugewiesen werden.")
    if day != entry.period_start:
        raise ValueError("Der Block muss am Tag des Eintrags liegen.")
    if end_minute is None:
        end_minute = min(start_minute + default_duration(estimated_minutes), MINUTES_PER_DAY)
    _check_times(start_minute, end_minute)
    return Block(
        id=None,
        entry_id=entry.id,
        start=local_time(day, start_minute),
        end=local_time(day, end_minute),
        local_updated_at=now,
    )


def move_block(block: Block, entry: Entry, day: date, start_minute: int, end_minute: int,
               today: date, now: datetime) -> tuple[Block, Entry]:
    """Block verschieben oder in der Länge ändern.

    R-23: Liegt der neue Tag woanders, wandert der Eintrag mit.
    Gibt den geänderten Block und den (evtl. geänderten) Eintrag zurück.
    """
    _check_times(start_minute, end_minute)
    if day != entry.period_start:
        entry = move_entry_to_day(entry, day, today)
    moved = replace(block, start=local_time(day, start_minute),
                    end=local_time(day, end_minute), local_updated_at=now)
    return moved, entry


def overlaps_any(block: Block, events: Iterable[tuple[datetime, datetime]]) -> bool:
    """R-20: Überschneidet sich der Block mit einem der Termine (Start, Ende)?

    Termine, die genau am Blockende beginnen, zählen nicht.
    """
    return any(start < block.end and block.start < end for start, end in events)
