"""Tests für den Zwei-Wege-Abgleich der Blöcke (S-5 bis S-8, S-13, S-14) – reine Logik."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from backend.domain.blocks import Block
from backend.domain.models import Entry, Scope, Status, Tier
from backend.domain.two_way import (
    Incoming, decide_incoming, event_body, parse_incoming, signature,
)

ZH = ZoneInfo("Europe/Zurich")
D = date(2026, 11, 10)
TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=ZH)


def at(d, h, m=0):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ZH)


def entry(**kw):
    base = dict(id=5, task_id=3, scope=Scope.DAY, period_start=D, tier=Tier.MUST)
    base.update(kw)
    return Entry(**base)


def block(**kw):
    base = dict(id=7, entry_id=5, start=at(D, 9), end=at(D, 10), google_event_id="g7",
                local_updated_at=at(TODAY, 8), last_synced_at=at(TODAY, 9))
    base.update(kw)
    return Block(**base)


def google_item(start=None, end=None, updated=None, summary="Bericht", **kw):
    item = {"id": "g7", "status": "confirmed", "summary": summary, "description": "Pflicht",
            "start": {"dateTime": (start or at(D, 9)).isoformat(), "timeZone": "Europe/Zurich"},
            "end": {"dateTime": (end or at(D, 10)).isoformat(), "timeZone": "Europe/Zurich"},
            "updated": (updated or at(TODAY, 11)).isoformat(),
            "extendedProperties": {"private": {"timasyBlockId": "7", "timasyEntryId": "5"}}}
    item.update(kw)
    return item


# --- S-5, S-6: was nach Google geht ------------------------------------------

def test_event_body():
    body = event_body(block(), "Bericht", Tier.MUST)
    assert body["summary"] == "Bericht"
    assert "Pflicht" in body["description"]
    assert body["start"] == {"dateTime": "2026-11-10T09:00:00+01:00", "timeZone": "Europe/Zurich"}
    assert body["end"]["dateTime"] == "2026-11-10T10:00:00+01:00"
    # S-5: private Zusatzfelder mit Block-ID und Eintrags-ID
    assert body["extendedProperties"]["private"] == {"timasyBlockId": "7", "timasyEntryId": "5"}


def test_bonus_description():
    assert "Bonus" in event_body(block(), "X", Tier.BONUS)["description"]


def test_signature_ignores_time_format():
    a = signature("T", "Pflicht", at(D, 9), at(D, 10))
    b = signature("T", "Pflicht", at(D, 9).astimezone(ZoneInfo("UTC")), at(D, 10))
    assert a == b
    assert a != signature("T", "Bonus", at(D, 9), at(D, 10))


# --- Google-Ereignis lesen -----------------------------------------------------

def test_parse_incoming():
    inc = parse_incoming(google_item())
    assert inc.block_id == 7 and inc.google_event_id == "g7"
    assert (inc.start, inc.end) == (at(D, 9), at(D, 10))
    assert inc.cancelled is False and inc.all_day is False


def test_parse_incoming_without_timasy_fields():
    item = google_item()
    del item["extendedProperties"]
    assert parse_incoming(item).block_id is None


def test_parse_cancelled():
    inc = parse_incoming({"id": "g7", "status": "cancelled"})
    assert inc.cancelled is True


# --- Entscheidungen bei Änderungen aus Google -------------------------------

def decide(item, b=None, e=None):
    return decide_incoming(parse_incoming(item), b if b is not None else block(),
                           e if e is not None else entry(), TODAY)


def test_handmade_event_is_ignored():
    # S-14
    item = google_item()
    del item["extendedProperties"]
    assert decide_incoming(parse_incoming(item), None, None, TODAY).kind == "ignore"


def test_unchanged_time_needs_nothing():
    assert decide(google_item()).kind == "none"


def test_moved_in_google_is_taken_over():
    # S-7: Verschieben in Google -> Timasy übernimmt die Zeit
    d = decide(google_item(start=at(D, 14), end=at(D, 15, 30)))
    assert d.kind == "apply_time"
    assert (d.day, d.start_minute, d.end_minute) == (D, 14 * 60, 15 * 60 + 30)


def test_moved_to_other_day_in_google():
    other = D + timedelta(days=2)
    d = decide(google_item(start=at(other, 8), end=at(other, 9)))
    assert d.kind == "apply_time" and d.day == other


def test_both_changed_latest_wins_google():
    # S-7: beide geändert; Google später -> Google gewinnt
    b = block(local_updated_at=at(TODAY, 10), last_synced_at=at(TODAY, 9))
    d = decide(google_item(start=at(D, 14), end=at(D, 15), updated=at(TODAY, 11)), b=b)
    assert d.kind == "apply_time"


def test_both_changed_latest_wins_timasy():
    b = block(local_updated_at=at(TODAY, 11, 30), last_synced_at=at(TODAY, 9))
    d = decide(google_item(start=at(D, 14), end=at(D, 15), updated=at(TODAY, 11)), b=b)
    assert d.kind == "push"


def test_deleted_in_google_deletes_block():
    # S-8 / A-2: Block weg, Eintrag bleibt (das macht die Service-Schicht)
    d = decide({"id": "g7", "status": "cancelled", "updated": at(TODAY, 11).isoformat()})
    assert d.kind == "delete_block"


def test_deleted_in_google_but_moved_later_in_timasy():
    b = block(local_updated_at=at(TODAY, 12), last_synced_at=at(TODAY, 9))
    d = decide({"id": "g7", "status": "cancelled", "updated": at(TODAY, 11).isoformat()}, b=b)
    assert d.kind == "recreate"


def test_all_day_in_google_is_reset():
    # S-13
    item = google_item()
    item["start"] = {"date": "2026-11-10"}
    item["end"] = {"date": "2026-11-11"}
    assert decide(item).kind == "push"


def test_over_midnight_in_google_is_reset():
    assert decide(google_item(start=at(D, 23), end=at(D + timedelta(days=1), 1))).kind == "push"


def test_open_entry_to_past_day_is_reset():
    past = TODAY - timedelta(days=2)
    assert decide(google_item(start=at(past, 9), end=at(past, 10))).kind == "push"


def test_done_entry_may_move_to_past_day():
    past = TODAY - timedelta(days=2)
    d = decide(google_item(start=at(past, 9), end=at(past, 10)), e=entry(status=Status.DONE))
    assert d.kind == "apply_time"


def test_ending_at_midnight_is_fine():
    d = decide(google_item(start=at(D, 23), end=at(D + timedelta(days=1), 0)))
    assert (d.kind, d.end_minute) == ("apply_time", 24 * 60)


def test_title_changed_in_google_only_needs_push():
    # S-6: Titel geht nur von Timasy nach Google -> überschreiben
    assert decide(google_item(summary="Anders")).kind == "none"   # Zeit gleich; Titel per Signatur


def test_echo_of_own_upload_is_ignored():
    # Google meldet unseren eigenen Upload zurück; Timasy wurde inzwischen geändert
    item = google_item()
    sig = parse_incoming(item).signature
    moved = block(start=at(D, 14), end=at(D, 15), synced_signature=sig,
                  local_updated_at=at(TODAY, 8), last_synced_at=at(TODAY, 9))
    assert decide(item, b=moved).kind == "none"
