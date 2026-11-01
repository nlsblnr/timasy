"""Serien: Wiederholungsregeln, die laufend Einträge erzeugen (R-13 bis R-18, R-24 bis R-29).

Neues Konzept "RRULE": ein Standard aus Kalender-Apps, der Wiederholungen als
Text beschreibt, z.B. "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE" = alle 2 Wochen am
Montag und Mittwoch. Die Bibliothek dateutil rechnet daraus die Daten aus.
Wir speichern die RRULE ohne Start und Ende; diese stehen in eigenen Feldern.
"""
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import Enum

from dateutil.rrule import rrulestr

from .models import Entry, Scope, Tier
from .periods import normalize_period_start, week_start

HORIZON_DAYS = 90                     # R-16
WEEKDAY_CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]   # 0 = Montag


class Freq(str, Enum):
    DAILY = "daily"        # täglich
    WEEKLY = "weekly"      # wöchentlich
    MONTHLY = "monthly"    # monatlich
    YEARLY = "yearly"      # jährlich


class MonthlyBy(str, Enum):
    DAY = "day"            # am n-ten Tag des Monats (z.B. am 15.)
    WEEKDAY = "weekday"    # am n-ten Wochentag (z.B. erster Montag)


class EndType(str, Enum):
    NEVER = "never"
    UNTIL = "until"        # an einem Datum (einschliesslich)
    COUNT = "count"        # nach n Vorkommen


@dataclass(frozen=True)
class Pattern:
    """Rhythmus einer Serie (R-14)."""
    freq: Freq
    interval: int = 1                       # alle n Einheiten
    weekdays: tuple[int, ...] = ()          # nur wöchentlich; leer = Wochentag des Starts
    monthly_by: MonthlyBy = MonthlyBy.DAY   # nur monatlich (R-29)


@dataclass(frozen=True)
class Series:
    id: int | None
    task_id: int                    # Vorlage für alle Vorkommen
    pattern: Pattern
    starts_on: date
    end_type: EndType
    tier: Tier
    scope: Scope
    until_date: date | None = None
    count: int | None = None
    start_minute: int | None = None     # feste Uhrzeit (Minuten seit Mitternacht)
    duration_minutes: int | None = None
    carry_over: bool = False            # R-13
    exdates: frozenset[date] = frozenset()  # einzeln gelöschte Vorkommen


# --- RRULE-Text ----------------------------------------------------------------

def to_rrule(pattern: Pattern, starts_on: date) -> str:
    parts = [f"FREQ={pattern.freq.name}", f"INTERVAL={pattern.interval}"]
    if pattern.freq == Freq.WEEKLY and pattern.weekdays:
        parts.append("BYDAY=" + ",".join(WEEKDAY_CODES[d] for d in sorted(pattern.weekdays)))
    if pattern.freq == Freq.MONTHLY:
        if pattern.monthly_by == MonthlyBy.WEEKDAY:
            nth = (starts_on.day - 1) // 7 + 1          # 1. bis 5. Wochentag im Monat
            parts.append(f"BYDAY=+{nth}{WEEKDAY_CODES[starts_on.weekday()]}")
        else:
            parts.append(f"BYMONTHDAY={starts_on.day}")
    return ";".join(parts)


def from_rrule(text: str) -> Pattern:
    fields = dict(part.split("=", 1) for part in text.split(";"))
    freq = Freq[fields["FREQ"]]
    weekdays: tuple[int, ...] = ()
    monthly_by = MonthlyBy.DAY
    if freq == Freq.WEEKLY and "BYDAY" in fields:
        weekdays = tuple(WEEKDAY_CODES.index(code) for code in fields["BYDAY"].split(","))
    if freq == Freq.MONTHLY and "BYDAY" in fields:
        monthly_by = MonthlyBy.WEEKDAY
    return Pattern(freq, int(fields.get("INTERVAL", 1)), weekdays, monthly_by)


# --- Prüfen --------------------------------------------------------------------

def validate(s: Series) -> None:
    """Wirft ValueError mit einer verständlichen Meldung, wenn etwas nicht stimmt."""
    if s.pattern.interval < 1:
        raise ValueError("Das Intervall muss mindestens 1 sein.")
    if s.end_type == EndType.COUNT and (s.count is None or s.count < 1):
        raise ValueError("Die Anzahl Wiederholungen muss mindestens 1 sein.")
    if s.end_type == EndType.UNTIL and (s.until_date is None or s.until_date < s.starts_on):
        raise ValueError("Das Enddatum muss nach dem Start liegen.")
    if s.scope == Scope.WEEK:
        # R-24: Wochen-Serien nur alle n Wochen, ohne Wochentage und Uhrzeit
        if s.pattern.freq != Freq.WEEKLY or s.pattern.weekdays:
            raise ValueError("Wochen-Serien wiederholen sich nur wöchentlich oder alle n Wochen.")
        if s.start_minute is not None:
            raise ValueError("Wochen-Einträge haben keine Uhrzeit.")
    if s.start_minute is not None:
        duration = s.duration_minutes or 30
        if not (0 <= s.start_minute and s.start_minute + duration <= 24 * 60 and duration > 0):
            raise ValueError("Die Uhrzeit muss innerhalb eines Tages liegen (R-19).")


# --- Vorkommen berechnen -----------------------------------------------------

def _first_day(s: Series) -> date:
    """Bei Wochen-Serien ist jedes Vorkommen ein Montag."""
    return normalize_period_start(s.scope, s.starts_on)


def occurrences(s: Series, first: date, last: date) -> list[date]:
    """Alle Vorkommen zwischen first und last (beide einschliesslich).

    Ende "an einem Datum" und "nach n Mal" sind berücksichtigt (R-15), ebenso
    einzeln gelöschte Vorkommen (exdates). Fehlende Monatstage entfallen (R-18).
    """
    start = _first_day(s)
    text = "RRULE:" + to_rrule(s.pattern, start)
    if s.end_type == EndType.COUNT:
        text += f";COUNT={s.count}"
    elif s.end_type == EndType.UNTIL:
        text += f";UNTIL={s.until_date:%Y%m%d}T235959"
    rule = rrulestr(text, dtstart=_midnight(start))
    found = rule.between(_midnight(first), _midnight(last), inc=True)
    return [d.date() for d in found if d.date() not in s.exdates]


def _midnight(d: date) -> datetime:
    """dateutil rechnet mit datetime; wir brauchen nur das Datum."""
    return datetime(d.year, d.month, d.day)


def missing_occurrences(s: Series, today: date, existing: set[date]) -> list[date]:
    """R-16: Vorkommen der nächsten 90 Tage, für die es noch keinen Eintrag gibt.

    Vergangene Tage werden nicht nachträglich erzeugt. Bei Wochen-Serien zählt
    die laufende Woche noch dazu.
    """
    first = week_start(today) if s.scope == Scope.WEEK else today
    last = today + timedelta(days=HORIZON_DAYS)
    return [d for d in occurrences(s, max(first, _first_day(s)), last) if d not in existing]


def make_entry(s: Series, occurrence: date) -> Entry:
    return Entry(
        id=None,
        task_id=s.task_id,
        scope=s.scope,
        period_start=normalize_period_start(s.scope, occurrence),
        tier=s.tier,
        series_id=s.id,
        occurrence_date=occurrence,
    )


def preview(s: Series, n: int = 5) -> list[date]:
    """Die ersten n Vorkommen ab Start, für die Vorschau beim Erfassen (V-8)."""
    result: list[date] = []
    first = _first_day(s)
    while len(result) < n:
        last = first + timedelta(days=366 * 2)
        batch = occurrences(s, first, last)
        result += batch
        if not batch or s.end_type != EndType.NEVER and len(batch) < n:
            break
        first = last + timedelta(days=1)
    return result[:n]


# --- Ändern ---------------------------------------------------------------------

def split_series(s: Series, at: date) -> tuple[Series, Series]:
    """R-17 "dieses und alle folgenden": Serie am Datum at teilen.

    Die alte Serie endet am Vortag, die neue beginnt bei at mit dem gleichen
    Ende. Bei "nach n Mal" bleibt die Gesamtzahl gleich.
    """
    if at <= _first_day(s):
        raise ValueError("Ab dem ersten Vorkommen bitte „alle“ ändern.")
    before = occurrences(replace(s, exdates=frozenset()), _first_day(s), at - timedelta(days=1))
    old = replace(s, end_type=EndType.UNTIL, until_date=at - timedelta(days=1), count=None,
                  exdates=frozenset(d for d in s.exdates if d < at))
    new = replace(s, id=None, starts_on=at,
                  exdates=frozenset(d for d in s.exdates if d >= at))
    if s.end_type == EndType.COUNT:
        new = replace(new, count=s.count - len(before))
        if new.count < 1:
            raise ValueError("Nach diesem Datum gibt es keine Vorkommen mehr.")
    return old, new


def end_series(s: Series, today: date) -> Series:
    """R-26: Serie endet heute (ein früheres Ende bleibt)."""
    if s.end_type == EndType.UNTIL and s.until_date <= today:
        return s
    if s.end_type == EndType.COUNT:
        remaining = occurrences(replace(s, exdates=frozenset()), today + timedelta(days=1),
                                today + timedelta(days=366 * 50))
        if not remaining:
            return s
    return replace(s, end_type=EndType.UNTIL, until_date=today, count=None)
