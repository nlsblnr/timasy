"""Tests für Blöcke (R-19 bis R-21, R-23) und das Verschieben von Einträgen (V-2)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from backend.domain.blocks import (
    Block,
    create_block,
    default_duration,
    local_minutes,
    move_block,
    overlaps_any,
)
from backend.domain.entries import move_entry_to_day
from backend.domain.models import Entry, Scope, Status, Tier

ZH = ZoneInfo("Europe/Zurich")
TODAY = date(2026, 11, 4)  # Mittwoch
NOW = datetime(2026, 11, 4, 8, 0, tzinfo=ZH)


def entry(**kw):
    base = dict(id=1, task_id=1, scope=Scope.DAY, period_start=TODAY, tier=Tier.MUST)
    base.update(kw)
    return Entry(**base)


def at(day, h, m=0):
    return datetime(day.year, day.month, day.day, h, m, tzinfo=ZH)


# --- R-21: Standarddauer -----------------------------------------------------

def test_default_duration_uses_estimate_or_30():
    assert default_duration(45) == 45
    assert default_duration(None) == 30


def test_new_block_takes_estimated_duration():
    b = create_block(entry(), TODAY, 9 * 60, None, estimated_minutes=90, now=NOW)
    assert (b.start, b.end) == (at(TODAY, 9), at(TODAY, 10, 30))
    assert b.entry_id == 1
    assert b.local_updated_at == NOW


def test_new_block_without_estimate_is_30_minutes():
    b = create_block(entry(), TODAY, 14 * 60, None, estimated_minutes=None, now=NOW)
    assert b.end == at(TODAY, 14, 30)


def test_new_block_with_explicit_end():
    b = create_block(entry(), TODAY, 9 * 60, 9 * 60 + 15, estimated_minutes=90, now=NOW)
    assert b.end == at(TODAY, 9, 15)


def test_default_end_is_cut_at_midnight():
    # R-19: keine Blöcke über Mitternacht
    b = create_block(entry(), TODAY, 23 * 60 + 45, None, estimated_minutes=60, now=NOW)
    assert b.end == datetime(2026, 11, 5, 0, 0, tzinfo=ZH)


# --- R-19: Block innerhalb eines Tages, nur für Tages-Einträge ----------------

def test_block_only_for_day_entries():
    week = entry(scope=Scope.WEEK, period_start=date(2026, 11, 2))
    with pytest.raises(ValueError):
        create_block(week, TODAY, 9 * 60, None, None, NOW)


def test_block_must_be_on_entry_day():
    with pytest.raises(ValueError):
        create_block(entry(), date(2026, 11, 5), 9 * 60, None, None, NOW)


@pytest.mark.parametrize("start,end", [(-15, 30), (600, 600), (600, 540), (1380, 1500)])
def test_invalid_times_rejected(start, end):
    with pytest.raises(ValueError):
        create_block(entry(), TODAY, start, end, None, NOW)


def test_local_minutes():
    assert local_minutes(at(TODAY, 9, 15)) == (TODAY, 555)


def test_times_are_local_across_dst_change():
    # 25.10.2026: Umstellung auf Winterzeit. 9 Uhr bleibt 9 Uhr Ortszeit.
    day = date(2026, 10, 25)
    b = create_block(entry(period_start=day), day, 9 * 60, None, None, NOW)
    assert b.start.hour == 9
    assert b.start.utcoffset().total_seconds() == 3600  # +01:00 nach der Umstellung


# --- R-23: Block verschieben, Eintrag wandert mit ----------------------------

def block():
    return Block(id=7, entry_id=1, start=at(TODAY, 9), end=at(TODAY, 10))


def test_move_block_same_day():
    b, e = move_block(block(), entry(), TODAY, 11 * 60, 12 * 60 + 30, today=TODAY, now=NOW)
    assert (b.start, b.end) == (at(TODAY, 11), at(TODAY, 12, 30))
    assert e.period_start == TODAY
    assert b.local_updated_at == NOW


def test_move_block_to_other_day_moves_entry():
    tomorrow = date(2026, 11, 5)
    b, e = move_block(block(), entry(), tomorrow, 9 * 60, 10 * 60, today=TODAY, now=NOW)
    assert b.start == at(tomorrow, 9)
    assert e.period_start == tomorrow
    assert e.scope == Scope.DAY


def test_move_block_keeps_overdue_note():
    overdue = entry(overdue=True, overdue_since=date(2026, 11, 1))
    _, e = move_block(block(), overdue, date(2026, 11, 5), 540, 600, today=TODAY, now=NOW)
    assert e.overdue is True and e.overdue_since == date(2026, 11, 1)


def test_move_block_rejects_invalid_times():
    with pytest.raises(ValueError):
        move_block(block(), entry(), TODAY, 600, 590, today=TODAY, now=NOW)


# --- Eintrag auf einen anderen Tag (V-2) --------------------------------------

def test_move_day_entry_to_other_day():
    assert move_entry_to_day(entry(), date(2026, 11, 6), TODAY).period_start == date(2026, 11, 6)


def test_move_week_entry_to_day_is_r6():
    week = entry(scope=Scope.WEEK, period_start=date(2026, 11, 2), tier=Tier.BONUS)
    e = move_entry_to_day(week, date(2026, 11, 6), TODAY)
    assert (e.scope, e.period_start, e.tier) == (Scope.DAY, date(2026, 11, 6), Tier.BONUS)


def test_open_entry_cannot_move_to_past_day():
    # Sonst würde ihn die Übertragung (R-9) sofort als überfällig zurückholen.
    with pytest.raises(ValueError):
        move_entry_to_day(entry(), date(2026, 11, 3), TODAY)


def test_done_entry_may_move_to_past_day():
    done = entry(status=Status.DONE)
    assert move_entry_to_day(done, date(2026, 11, 3), TODAY).period_start == date(2026, 11, 3)


# --- R-20: Überschneidung mit Fremdterminen -----------------------------------

def test_overlaps_any():
    b = block()  # 9–10 Uhr
    assert overlaps_any(b, [(at(TODAY, 9, 30), at(TODAY, 11))]) is True
    assert overlaps_any(b, [(at(TODAY, 10), at(TODAY, 11))]) is False  # angrenzend
    assert overlaps_any(b, [(at(TODAY, 7), at(TODAY, 9))]) is False
    assert overlaps_any(b, []) is False
