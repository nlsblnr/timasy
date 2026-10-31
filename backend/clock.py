"""Die aktuelle Zeit an einer Stelle (T-5).

Die Fachlogik bekommt die Zeit immer übergeben. Woher sie kommt, entscheidet
nur diese Datei. Zum Ausprobieren eines Tageswechsels lässt sich das Datum
mit der Umgebungsvariable TIMASY_TODAY verstellen, z.B. TIMASY_TODAY=2026-11-05.
"""
import os
from datetime import date, datetime

from .config import TIMEZONE


def now() -> datetime:
    real = datetime.now(TIMEZONE)
    fake_day = os.environ.get("TIMASY_TODAY")
    if fake_day:
        d = date.fromisoformat(fake_day)
        return real.replace(year=d.year, month=d.month, day=d.day)
    return real


def today() -> date:
    return now().date()
