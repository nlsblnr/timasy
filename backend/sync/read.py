"""Fremdtermine aus Google lesen (S-4, S-8).

Ablauf pro gewähltem Kalender:
- Vollabgleich (alle Termine im Zeitfenster), wenn es noch keinen Sync-Token
  gibt, der Token ungültig ist oder ein neuer Tag begonnen hat (das Fenster
  "heute bis +90 Tage" verschiebt sich täglich).
- Sonst inkrementell: Google liefert nur, was sich seit dem letzten Abgleich
  geändert hat (neue, geänderte, gelöschte Termine).
"""
from datetime import date, datetime
from typing import Protocol

from ..db import repository as repo
from ..domain.external import apply_changes, parse_event, selectable_calendars, sync_window


class SyncTokenInvalid(Exception):
    """Google meldet: Sync-Token ungültig (HTTP 410) -> neu abgleichen."""


class CalendarClient(Protocol):
    """Was der Abgleich von Google braucht (echt: google_client.GoogleClient)."""

    def list_calendars(self) -> list[dict]:
        """[{"id": ..., "summary": ..., "color": ...}, ...]"""

    def list_events(self, calendar_id: str, time_min: str | None = None,
                    time_max: str | None = None, sync_token: str | None = None,
                    page_token: str | None = None) -> dict:
        """Eine Seite: {"items": [...], "nextPageToken" | "nextSyncToken": ...}"""


def sync_calendar_list(conn, client: CalendarClient) -> None:
    """Kalenderliste aktualisieren (für die Auswahl in den Einstellungen)."""
    timasy_id = repo.get_setting(conn, "timasy_calendar_id")
    repo.save_calendars(conn, selectable_calendars(client.list_calendars(), timasy_id))


def _fetch(client: CalendarClient, calendar_id: str, **params) -> tuple[list[dict], str | None]:
    """Alle Seiten abholen; gibt (Ereignisse, neuer Sync-Token) zurück."""
    items: list[dict] = []
    page_token = None
    while True:
        result = client.list_events(calendar_id, page_token=page_token, **params)
        items += result.get("items", [])
        page_token = result.get("nextPageToken")
        if not page_token:
            return items, result.get("nextSyncToken")


def sync_external(conn, client: CalendarClient, today: date, now: datetime) -> None:
    """Alle gewählten Kalender abgleichen."""
    window = sync_window(today)
    for calendar_id in repo.selected_calendar_ids(conn):
        state = repo.get_sync_state(conn, calendar_id)
        cached = repo.external_events_for_calendar(conn, calendar_id)
        full = (state is None or not state["sync_token"]
                or state["window_start"] != today.isoformat())
        items, token = [], None
        if not full:
            try:
                items, token = _fetch(client, calendar_id, sync_token=state["sync_token"])
            except SyncTokenInvalid:
                full = True
        if full:
            items, token = _fetch(client, calendar_id, time_min=window[0].isoformat(),
                                  time_max=window[1].isoformat())

        changes = [parse_event(calendar_id, it) for it in items]
        upserts, deletes = apply_changes(cached, changes, window)
        if full:
            # Was beim Vollabgleich nicht mehr kommt, gibt es nicht mehr (S-8)
            seen = {key for key, _ in changes}
            deletes |= {key for key in cached if key not in seen}
        repo.save_external_events(conn, upserts, deletes)
        repo.save_sync_state(conn, calendar_id, token, today, now)
