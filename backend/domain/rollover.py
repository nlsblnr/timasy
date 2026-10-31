"""Übertragung unerledigter Einträge auf heute bzw. diese Woche (R-9 bis R-11)."""
from dataclasses import replace
from datetime import date
from typing import Iterable

from .models import Entry, Scope, Status
from .periods import week_start


def carry_over(entries: Iterable[Entry], today: date) -> list[Entry]:
    """Gibt die Einträge zurück, die übertragen werden müssen, bereits geändert.

    - R-9: offene Tages-Einträge vergangener Tage -> heute
    - R-11: offene Wochen-Einträge vergangener Wochen -> diese Woche
    - R-10: Vermerk "überfällig"; overdue_since behält das ursprüngliche Datum
    Die Stufe bleibt in jedem Fall gleich.
    Nicht betroffene Einträge kommen nicht in der Liste vor.
    """
    this_week = week_start(today)
    changed = []
    for e in entries:
        if e.status != Status.OPEN:
            continue
        if e.series_id is not None:
            # Vorkommen von Serien behandelt R-13 (Meilenstein M3).
            continue
        if e.scope == Scope.DAY and e.period_start < today:
            target = today
        elif e.scope == Scope.WEEK and e.period_start < this_week:
            target = this_week
        else:
            continue
        changed.append(replace(
            e,
            period_start=target,
            overdue=True,
            overdue_since=e.overdue_since or e.period_start,
        ))
    return changed


def overdue_days(entry: Entry, today: date) -> int | None:
    """Für die Anzeige "überfällig seit n Tagen" (R-10); None, wenn nicht überfällig."""
    if not entry.overdue or entry.overdue_since is None:
        return None
    return (today - entry.overdue_since).days
