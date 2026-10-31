"""Hilfsfunktionen für Zeiträume (Tag und Woche)."""
from datetime import date, timedelta

from .models import Scope


def week_start(d: date) -> date:
    """Montag der Woche, zu der das Datum gehört."""
    return d - timedelta(days=d.weekday())  # weekday(): Montag = 0


def normalize_period_start(scope: Scope, d: date) -> date:
    """Bei Wochen wird jedes Datum auf den Montag gelegt."""
    return week_start(d) if scope == Scope.WEEK else d


def week_days(monday: date) -> list[date]:
    """Die sieben Tage einer Woche, Montag bis Sonntag."""
    return [monday + timedelta(days=i) for i in range(7)]
