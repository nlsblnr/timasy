"""Tests für Zuweisen, Abhaken, Stufen, Zeiträume und Backlog (R-1, R-5 bis R-8)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from backend.domain.entries import (
    assign_task,
    assign_to_day,
    is_in_backlog,
    mark_done,
    mark_open,
)
from backend.domain.models import Entry, Scope, Status, Tier
from backend.domain.periods import normalize_period_start, week_start

ZH = ZoneInfo("Europe/Zurich")


def entry(**kw) -> Entry:
    base = dict(id=1, task_id=10, scope=Scope.DAY, period_start=date(2026, 11, 2),
                tier=Tier.MUST)
    base.update(kw)
    return Entry(**base)


# --- Zeiträume ---------------------------------------------------------------

def test_week_starts_on_monday():
    # Mittwoch, 4.11.2026 -> Montag, 2.11.2026
    assert week_start(date(2026, 11, 4)) == date(2026, 11, 2)
    assert week_start(date(2026, 11, 2)) == date(2026, 11, 2)
    # Sonntag gehört noch zur Woche davor
    assert week_start(date(2026, 11, 8)) == date(2026, 11, 2)


def test_week_period_is_normalized_to_monday():
    assert normalize_period_start(Scope.WEEK, date(2026, 11, 5)) == date(2026, 11, 2)
    assert normalize_period_start(Scope.DAY, date(2026, 11, 5)) == date(2026, 11, 5)


# --- R-1, R-5: Zuweisen -------------------------------------------------------

def test_assign_creates_open_entry_with_tier():
    e = assign_task(task_id=10, scope=Scope.DAY, period_start=date(2026, 11, 3), tier=Tier.BONUS)
    assert e.task_id == 10
    assert e.scope == Scope.DAY
    assert e.period_start == date(2026, 11, 3)
    assert e.tier == Tier.BONUS
    assert e.status == Status.OPEN
    assert e.overdue is False


def test_assign_to_week_uses_monday():
    e = assign_task(task_id=10, scope=Scope.WEEK, period_start=date(2026, 11, 6), tier=Tier.MUST)
    assert e.period_start == date(2026, 11, 2)


def test_tier_belongs_to_entry_not_task():
    # R-1: dieselbe Aufgabe kann diese Woche Pflicht und nächste Woche Bonus sein
    a = assign_task(10, Scope.WEEK, date(2026, 11, 2), Tier.MUST)
    b = assign_task(10, Scope.WEEK, date(2026, 11, 9), Tier.BONUS)
    assert (a.tier, b.tier) == (Tier.MUST, Tier.BONUS)


# --- R-6: Wochen-Eintrag einem Tag zuweisen ----------------------------------

def test_week_entry_becomes_day_entry_keeping_tier():
    week = entry(scope=Scope.WEEK, period_start=date(2026, 11, 2), tier=Tier.BONUS)
    day = assign_to_day(week, date(2026, 11, 4))
    assert day.id == week.id  # derselbe Eintrag, keine Kopie
    assert day.scope == Scope.DAY
    assert day.period_start == date(2026, 11, 4)
    assert day.tier == Tier.BONUS


def test_week_entry_to_day_can_change_tier():
    week = entry(scope=Scope.WEEK, period_start=date(2026, 11, 2), tier=Tier.BONUS)
    assert assign_to_day(week, date(2026, 11, 4), tier=Tier.MUST).tier == Tier.MUST


def test_week_entry_can_only_go_to_day_of_its_week():
    week = entry(scope=Scope.WEEK, period_start=date(2026, 11, 2))
    with pytest.raises(ValueError):
        assign_to_day(week, date(2026, 11, 9))


# --- R-7: Abhaken und rückgängig ---------------------------------------------

def test_mark_done_and_undo():
    now = datetime(2026, 11, 2, 9, 30, tzinfo=ZH)
    done = mark_done(entry(), now)
    assert done.status == Status.DONE
    assert done.done_at == now
    reopened = mark_open(done)
    assert reopened.status == Status.OPEN
    assert reopened.done_at is None


# --- Backlog (Abschnitt 3, v0.2) ---------------------------------------------

def test_task_without_entries_is_in_backlog():
    assert is_in_backlog([]) is True


def test_task_with_open_entry_is_not_in_backlog():
    assert is_in_backlog([entry()]) is False


def test_done_task_is_not_in_backlog():
    assert is_in_backlog([entry(status=Status.DONE)]) is False


def test_task_with_only_missed_entries_is_in_backlog():
    # "verpasst" (Serien, R-13) zählt weder als offen noch als erledigt
    assert is_in_backlog([entry(status=Status.MISSED)]) is True


def test_month_weeks():
    from backend.domain.periods import month_weeks
    weeks = month_weeks(2026, 11)  # 1.11.2026 ist ein Sonntag
    assert weeks[0][0] == date(2026, 10, 26)
    assert weeks[-1][-1] == date(2026, 12, 6)
    assert all(len(w) == 7 for w in weeks)
    assert len(weeks) == 6
