"""Zuweisen, Abhaken und Backlog (R-1, R-5 bis R-8)."""
from dataclasses import replace
from datetime import date, datetime
from typing import Iterable

from .models import Entry, Scope, Status, Tier
from .periods import normalize_period_start, week_start


def assign_task(task_id: int, scope: Scope, period_start: date, tier: Tier) -> Entry:
    """R-5: Aufgabe einem Tag oder einer Woche zuweisen; es entsteht ein Eintrag."""
    return Entry(
        id=None,  # vergibt die Datenbank
        task_id=task_id,
        scope=scope,
        period_start=normalize_period_start(scope, period_start),
        tier=tier,
    )


def assign_to_day(entry: Entry, day: date, tier: Tier | None = None) -> Entry:
    """R-6: Wochen-Eintrag wird zum Tages-Eintrag (keine Kopie).

    Die Stufe bleibt, ausser es wird eine neue angegeben.
    """
    if entry.scope != Scope.WEEK:
        raise ValueError("Nur Wochen-Einträge können einem Tag zugewiesen werden.")
    if week_start(day) != entry.period_start:
        raise ValueError("Der Tag muss in der Woche des Eintrags liegen.")
    return replace(entry, scope=Scope.DAY, period_start=day, tier=tier or entry.tier)


def mark_done(entry: Entry, now: datetime) -> Entry:
    """R-7: abhaken."""
    return replace(entry, status=Status.DONE, done_at=now)


def mark_open(entry: Entry) -> Entry:
    """R-7: Abhaken rückgängig machen."""
    return replace(entry, status=Status.OPEN, done_at=None)


def is_in_backlog(task_entries: Iterable[Entry]) -> bool:
    """Gehört eine Aufgabe in den Backlog? (Abschnitt 3, v0.2)

    Ja, wenn sie keinen offenen und keinen erledigten Eintrag hat.
    """
    return all(e.status not in (Status.OPEN, Status.DONE) for e in task_entries)
