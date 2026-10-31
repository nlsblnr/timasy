"""Fortschritt eines Tages oder einer Woche (R-2 bis R-4)."""
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .models import Entry, Scope, Status, Tier
from .periods import week_start


@dataclass(frozen=True)
class Progress:
    must_done: int
    must_total: int
    all_done: int
    all_total: int

    @property
    def must_ratio(self) -> float:
        """Anteil erledigter Pflicht-Einträge, 0 bis 1."""
        return self.must_done / self.must_total if self.must_total else 0.0

    @property
    def all_ratio(self) -> float:
        """Anteil aller erledigten Einträge, 0 bis 1."""
        return self.all_done / self.all_total if self.all_total else 0.0

    @property
    def minimum_reached(self) -> bool:
        """R-3: mindestens ein Pflicht-Eintrag und alle erledigt."""
        return self.must_total > 0 and self.must_done == self.must_total


def _count(entries: list[Entry]) -> Progress:
    """R-2: gezählt wird nach Anzahl, nicht nach Dauer."""
    must = [e for e in entries if e.tier == Tier.MUST]
    return Progress(
        must_done=sum(e.status == Status.DONE for e in must),
        must_total=len(must),
        all_done=sum(e.status == Status.DONE for e in entries),
        all_total=len(entries),
    )


def day_progress(entries: Iterable[Entry], day: date) -> Progress:
    """Fortschritt eines Tages: nur die Tages-Einträge dieses Tages."""
    return _count([e for e in entries if e.scope == Scope.DAY and e.period_start == day])


def week_progress(entries: Iterable[Entry], any_day: date) -> Progress:
    """R-4: Wochen-Einträge plus alle Tages-Einträge der Woche."""
    monday = week_start(any_day)
    return _count([e for e in entries if week_start(e.period_start) == monday])
