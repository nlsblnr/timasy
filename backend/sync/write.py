"""Blöcke mit dem Kalender "Timasy" abgleichen, in beide Richtungen (M5).

Ablauf bei jedem Abgleich:
1. pull: Änderungen aus Google holen (am Handy verschoben, gelöscht …) und
   nach den Regeln in domain/two_way.py anwenden (S-7, S-8, S-13, S-14).
2. push: was in Timasy anders ist als in Google, hochladen: neue Blöcke
   anlegen (S-5, S-15), geänderte ersetzen (S-6), gelöschte aus der
   Warteschlange löschen (S-8, S-10).
Nach jedem Schreibzugriff auf Google wird sofort gespeichert (commit), damit
bei einem Abbruch nichts doppelt angelegt wird.
"""
from dataclasses import replace
from datetime import date, datetime

from ..db import repository as repo
from ..domain.blocks import move_block
from ..domain.two_way import Incoming, decide_incoming, event_body, parse_incoming, signature
from .errors import GoogleGone, GoogleNotFound, SyncTokenInvalid
from .read import CalendarClient, _fetch


class CalendarGone(Exception):
    """Der Kalender "Timasy" existiert in Google nicht mehr."""


def sync_blocks(conn, client: CalendarClient, calendar_id: str, today: date, now: datetime) -> None:
    pull(conn, client, calendar_id, today, now)
    push(conn, client, calendar_id, now)


# --- 1. Änderungen aus Google -----------------------------------------------------

def pull(conn, client: CalendarClient, calendar_id: str, today: date, now: datetime) -> None:
    state = repo.get_sync_state(conn, calendar_id)
    token = state["sync_token"] if state else None
    try:
        try:
            items, new_token = _fetch(client, calendar_id, sync_token=token) if token \
                else _fetch(client, calendar_id)
        except SyncTokenInvalid:
            items, new_token = _fetch(client, calendar_id)
    except GoogleNotFound as e:
        raise CalendarGone() from e

    for item in items:
        _apply(conn, parse_incoming(item), today, now)
    repo.save_sync_state(conn, calendar_id, new_token, today, now)
    conn.commit()


def _find_block(conn, inc: Incoming):
    block = repo.block_by_event(conn, inc.google_event_id)
    if block is None and inc.block_id is not None:
        # Ereignis wurde angelegt, die ID aber nicht gespeichert (Abbruch): übernehmen
        candidate = repo.get_block(conn, inc.block_id)
        if candidate and candidate.google_event_id is None and not inc.cancelled:
            block = replace(candidate, google_event_id=inc.google_event_id)
            repo.update_block(conn, block)
    return block


def _apply(conn, inc: Incoming, today: date, now: datetime) -> None:
    block = _find_block(conn, inc)
    entry = repo.get_entry(conn, block.entry_id) if block else None
    decision = decide_incoming(inc, block, entry, today)

    if decision.kind == "ignore":
        return
    if decision.kind == "delete_event":
        conn.execute("INSERT OR IGNORE INTO google_deletion VALUES (?)", (inc.google_event_id,))
        return
    if decision.kind == "delete_block":
        # S-8 / A-2: Block weg, Eintrag bleibt mit Tag und Stufe ("nicht eingeplant")
        repo.delete_block(conn, block.id)
        repo.clear_deletion(conn, inc.google_event_id)   # in Google ist es schon gelöscht
        _mark_exception(conn, entry)
        return
    if decision.kind == "recreate":
        repo.update_block(conn, replace(block, google_event_id=None, synced_signature=None))
        return
    if decision.kind == "apply_time":
        moved, moved_entry = move_block(block, entry, decision.day, decision.start_minute,
                                        decision.end_minute, today, now)
        # Die Änderung kommt aus Google: nicht als Timasy-Änderung zählen
        repo.update_block(conn, replace(moved, local_updated_at=block.local_updated_at,
                                        last_synced_at=now, synced_signature=inc.signature))
        repo.update_entry(conn, moved_entry)
        _mark_exception(conn, moved_entry)
        return
    # "none" oder "push": merken, was jetzt in Google steht. Weicht es von
    # Timasy ab (Titel geändert, S-13), lädt push() die Timasy-Fassung hoch.
    repo.update_block(conn, replace(block, synced_signature=inc.signature))


def _mark_exception(conn, entry) -> None:
    """Serien-Vorkommen, die in Google geändert wurden, werden zur Ausnahme (R-27)."""
    if entry is not None and entry.series_id is not None and not entry.is_exception:
        repo.update_entry(conn, replace(entry, is_exception=True))


# --- 2. Änderungen nach Google ------------------------------------------------------

def push(conn, client: CalendarClient, calendar_id: str, now: datetime) -> None:
    for event_id in repo.pending_deletions(conn):
        try:
            client.delete_event(calendar_id, event_id)
        except (GoogleNotFound, GoogleGone):
            pass                              # schon weg
        repo.clear_deletion(conn, event_id)
        conn.commit()

    for block, tier, title in repo.blocks_with_titles(conn):
        body = event_body(block, title, tier)
        wanted = signature(body["summary"], body["description"], block.start, block.end)
        if block.google_event_id and block.synced_signature == wanted:
            continue
        event_id = block.google_event_id
        if event_id:
            try:
                client.update_event(calendar_id, event_id, body)
            except (GoogleNotFound, GoogleGone):
                event_id = None               # in Google verschwunden: neu anlegen
        if not event_id:
            event_id = client.insert_event(calendar_id, body)
        repo.update_block(conn, replace(block, google_event_id=event_id, last_synced_at=now,
                                        synced_signature=wanted))
        conn.commit()
