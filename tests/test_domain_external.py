"""Tests für Fremdtermine (S-4, S-8, R-20) – reine Logik ohne Google-Zugriff."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.domain.blocks import Block
from backend.domain.external import (
    ExternalEvent, apply_changes, conflicting_entries, events_on_day, parse_event,
    selectable_calendars, sync_window,
)

ZH = ZoneInfo("Europe/Zurich")
CAL = "privat@example.com"


def at(d, h, m=0):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ZH)


D = date(2026, 11, 4)


# --- Google-Ereignis lesen ---------------------------------------------------

def test_parse_timed_event():
    item = {"id": "abc", "status": "confirmed", "summary": "Zahnarzt",
            "start": {"dateTime": "2026-11-04T09:00:00+01:00"},
            "end": {"dateTime": "2026-11-04T10:00:00+01:00"},
            "updated": "2026-11-01T10:00:00.000Z"}
    key, ev = parse_event(CAL, item)
    assert key == (CAL, "abc")
    assert ev.title == "Zahnarzt"
    assert (ev.start, ev.end) == (at(D, 9), at(D, 10))
    assert ev.all_day is False


def test_parse_converts_to_local_time():
    item = {"id": "x", "summary": "Call", "start": {"dateTime": "2026-11-04T08:00:00Z"},
            "end": {"dateTime": "2026-11-04T08:30:00Z"}}
    _, ev = parse_event(CAL, item)
    assert ev.start.hour == 9 and ev.start.tzinfo is not None


def test_parse_all_day_event():
    # Google: Ende eines Ganztags-Termins ist exklusiv (der Tag danach)
    item = {"id": "f", "summary": "Ferien", "start": {"date": "2026-11-04"},
            "end": {"date": "2026-11-06"}}
    _, ev = parse_event(CAL, item)
    assert ev.all_day is True
    assert ev.start == at(D, 0)
    assert ev.end == at(date(2026, 11, 6), 0)


def test_parse_without_title():
    _, ev = parse_event(CAL, {"id": "n", "start": {"date": "2026-11-04"}, "end": {"date": "2026-11-05"}})
    assert ev.title == "(ohne Titel)"


def test_cancelled_event_means_delete():
    # S-8: in Google gelöschter Termin verschwindet aus dem Zwischenspeicher
    key, ev = parse_event(CAL, {"id": "abc", "status": "cancelled"})
    assert key == (CAL, "abc") and ev is None


# --- Änderungen anwenden -------------------------------------------------------

def ev(id, start, end, title="T", cal=CAL, all_day=False):
    return ExternalEvent(cal, id, title, start, end, all_day)


def test_apply_changes_upserts_and_deletes():
    old = {(CAL, "a"): ev("a", at(D, 9), at(D, 10)), (CAL, "b"): ev("b", at(D, 11), at(D, 12))}
    changes = [
        ((CAL, "a"), ev("a", at(D, 14), at(D, 15), "neu")),   # geändert
        ((CAL, "b"), None),                                     # gelöscht
        ((CAL, "c"), ev("c", at(D, 8), at(D, 9))),             # neu
        ((CAL, "zz"), None),                                    # unbekannt gelöscht: egal
    ]
    upserts, deletes = apply_changes(old, changes)
    assert {e.google_event_id for e in upserts} == {"a", "c"}
    assert deletes == {(CAL, "b")}


def test_apply_changes_skips_events_outside_window():
    window = sync_window(D)
    far = ev("far", at(date(2027, 6, 1), 9), at(date(2027, 6, 1), 10))
    past = ev("past", at(date(2026, 11, 1), 9), at(date(2026, 11, 1), 10))
    old = {(CAL, "past"): past}
    upserts, deletes = apply_changes(old, [((CAL, "far"), far), ((CAL, "past"), past)], window)
    assert upserts == []
    assert deletes == {(CAL, "past")}   # aus dem Fenster gefallen -> entfernen


# --- Zeitfenster (S-4, v0.5) ----------------------------------------------------

def test_sync_window_today_plus_90_days():
    start, end = sync_window(D)
    assert start == at(D, 0)
    assert end == at(date(2027, 2, 3), 0)  # Ende exklusiv: Tag 90 ist noch drin (2.2.2027)


# --- Anzeige pro Tag -------------------------------------------------------------

def test_events_on_day_includes_overlapping_and_all_day():
    events = [
        ev("a", at(D, 9), at(D, 10)),
        ev("night", at(date(2026, 11, 3), 23), at(D, 1)),          # über Mitternacht
        ev("f", at(date(2026, 11, 3), 0), at(date(2026, 11, 5), 0), all_day=True),
        ev("other", at(date(2026, 11, 5), 9), at(date(2026, 11, 5), 10)),
        ev("ends0", at(date(2026, 11, 3), 22), at(D, 0)),          # endet genau um 0 Uhr
    ]
    assert {e.google_event_id for e in events_on_day(events, D)} == {"a", "night", "f"}


# --- R-20: Überschneidung markieren ---------------------------------------------

def test_conflicting_entries():
    blocks = [Block(1, entry_id=10, start=at(D, 9), end=at(D, 10)),
              Block(2, entry_id=11, start=at(D, 10), end=at(D, 11)),
              Block(3, entry_id=12, start=at(D, 14), end=at(D, 15))]
    events = [ev("a", at(D, 9, 30), at(D, 10)),
              ev("f", at(D, 0), at(date(2026, 11, 5), 0), all_day=True)]  # ganztägig zählt nicht
    assert conflicting_entries(blocks, events) == {10}


# --- Kalenderauswahl --------------------------------------------------------------

def test_timasy_calendar_is_never_selectable():
    cals = [{"id": "a", "summary": "Privat"}, {"id": "t", "summary": "Timasy"},
            {"id": "b", "summary": "Arbeit"}]
    assert [c["id"] for c in selectable_calendars(cals, timasy_calendar_id="t")] == ["a", "b"]
