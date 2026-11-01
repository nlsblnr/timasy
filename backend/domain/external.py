"""Fremdtermine aus Google Calendar: nur lesen (D-4, S-4, S-8, R-20).

Reine Logik: Google-Antworten (als dict) in ExternalEvent umwandeln, Änderungen
auf den Zwischenspeicher anwenden, Zeitfenster und Überschneidungen. Der
eigentliche Abruf bei Google steht in backend/sync.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Iterable

from ..config import TIMEZONE
from .blocks import Block

WINDOW_DAYS = 90          # S-4 (v0.5): ab heute bis 90 Tage voraus
NO_TITLE = "(ohne Titel)"

Key = tuple[str, str]     # (calendar_id, google_event_id)


@dataclass(frozen=True)
class ExternalEvent:
    calendar_id: str
    google_event_id: str
    title: str
    start: datetime          # mit Zeitzone; ganztägig: 0 Uhr Ortszeit
    end: datetime            # exklusiv; ganztägig: 0 Uhr des Folgetags
    all_day: bool = False
    updated: datetime | None = None

    @property
    def key(self) -> Key:
        return (self.calendar_id, self.google_event_id)


def _midnight(d: date) -> datetime:
    return datetime.combine(d, time(0), TIMEZONE)


def _parse_time(value: dict) -> tuple[datetime, bool]:
    """Google liefert entweder {"dateTime": ...} oder {"date": ...} (ganztägig)."""
    if "dateTime" in value:
        moment = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
        return moment.astimezone(TIMEZONE), False
    return _midnight(date.fromisoformat(value["date"])), True


def parse_event(calendar_id: str, item: dict) -> tuple[Key, ExternalEvent | None]:
    """Ein Ereignis aus der Google-Antwort lesen.

    Gibt (Schlüssel, Termin) zurück; Termin None heisst "in Google gelöscht" (S-8).
    """
    key = (calendar_id, item["id"])
    if item.get("status") == "cancelled":
        return key, None
    start, all_day = _parse_time(item["start"])
    end, _ = _parse_time(item["end"])
    updated = None
    if item.get("updated"):
        updated = datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
    return key, ExternalEvent(calendar_id, item["id"], item.get("summary") or NO_TITLE,
                              start, end, all_day, updated)


def sync_window(today: date) -> tuple[datetime, datetime]:
    """S-4 (v0.5): von heute 0 Uhr bis und mit Tag 90 (Ende exklusiv)."""
    return _midnight(today), _midnight(today + timedelta(days=WINDOW_DAYS + 1))


def _overlaps(start: datetime, end: datetime, other_start: datetime, other_end: datetime) -> bool:
    return start < other_end and other_start < end


def apply_changes(cached: dict[Key, ExternalEvent],
                  changes: Iterable[tuple[Key, ExternalEvent | None]],
                  window: tuple[datetime, datetime] | None = None,
                  ) -> tuple[list[ExternalEvent], set[Key]]:
    """Änderungen von Google auf den Zwischenspeicher anwenden.

    Gibt zurück, was gespeichert (neu/geändert) und was entfernt werden muss.
    Termine ausserhalb des Zeitfensters werden nicht gespeichert.
    """
    upserts: dict[Key, ExternalEvent] = {}
    deletes: set[Key] = set()
    for key, event in changes:
        outside = event is not None and window is not None and \
            not _overlaps(event.start, event.end, *window)
        if event is None or outside:
            upserts.pop(key, None)
            if key in cached:
                deletes.add(key)
        else:
            upserts[key] = event
            deletes.discard(key)
    return list(upserts.values()), deletes


def events_on_day(events: Iterable[ExternalEvent], day: date) -> list[ExternalEvent]:
    """Termine, die einen Tag berühren (auch über Mitternacht oder mehrtägig)."""
    start, end = _midnight(day), _midnight(day + timedelta(days=1))
    return [e for e in events if _overlaps(e.start, e.end, start, end)]


def conflicting_entries(blocks: Iterable[Block], events: Iterable[ExternalEvent]) -> set[int]:
    """R-20: Einträge, deren Block sich mit einem Fremdtermin überschneidet.

    Ganztägige Termine (z.B. Geburtstage, Ferien) zählen nicht als Überschneidung.
    """
    timed = [e for e in events if not e.all_day]
    return {b.entry_id for b in blocks
            if any(_overlaps(b.start, b.end, e.start, e.end) for e in timed)}


def selectable_calendars(calendars: Iterable[dict], timasy_calendar_id: str | None) -> list[dict]:
    """Kalender, die man zum Lesen wählen kann; der Timasy-Kalender nie (S-4)."""
    return [c for c in calendars if c["id"] != timasy_calendar_id]
