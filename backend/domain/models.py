"""Fachliche Datentypen (Glossar: Abschnitt 3 der SPEC)."""
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class Scope(str, Enum):
    """Zeitraum eines Eintrags."""
    DAY = "day"    # Tag
    WEEK = "week"  # Woche (Start Montag)


class Tier(str, Enum):
    """Stufe eines Eintrags."""
    MUST = "must"    # Pflicht (Minimalziel)
    BONUS = "bonus"  # Bonus (Maximalziel)


class Status(str, Enum):
    OPEN = "open"      # offen
    DONE = "done"      # erledigt
    MISSED = "missed"  # verpasst (nur Serien-Vorkommen, R-13)


# frozen=True: Ein Entry wird nie verändert. Funktionen geben stattdessen eine
# geänderte Kopie zurück (mit dataclasses.replace). So bleibt nachvollziehbar,
# was eine Funktion bewirkt.
@dataclass(frozen=True)
class Entry:
    """Eintrag: eine Aufgabe, zugewiesen an einen Zeitraum mit einer Stufe."""
    id: int | None
    task_id: int
    scope: Scope
    period_start: date            # Tag bzw. Montag der Woche
    tier: Tier
    status: Status = Status.OPEN
    done_at: datetime | None = None
    overdue: bool = False
    overdue_since: date | None = None  # Datum des ursprünglichen Zeitraums
    series_id: int | None = None       # erst ab M3 (Serien) benutzt
