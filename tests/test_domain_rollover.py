"""Tests für die Übertragung unerledigter Einträge (R-9 bis R-11)."""
from datetime import date

from backend.domain.models import Entry, Scope, Status, Tier
from backend.domain.rollover import carry_over, overdue_days

TODAY = date(2026, 11, 4)  # Mittwoch; Woche beginnt am 2.11.


def e(id, scope=Scope.DAY, day=date(2026, 11, 3), tier=Tier.MUST, status=Status.OPEN, **kw):
    return Entry(id=id, task_id=id, scope=scope, period_start=day, tier=tier,
                 status=status, **kw)


def by_id(entries):
    return {x.id: x for x in entries}


def test_open_day_entries_of_past_days_move_to_today():
    # R-9
    changed = by_id(carry_over([e(1, day=date(2026, 11, 3))], TODAY))
    assert changed[1].period_start == TODAY
    assert changed[1].scope == Scope.DAY


def test_tier_is_kept():
    # R-9: Pflicht bleibt Pflicht, Bonus bleibt Bonus
    changed = by_id(carry_over([e(1, tier=Tier.MUST), e(2, tier=Tier.BONUS)], TODAY))
    assert changed[1].tier == Tier.MUST
    assert changed[2].tier == Tier.BONUS


def test_several_days_idle_all_land_on_today():
    # R-9: App lag mehrere Tage still
    entries = [e(1, day=date(2026, 10, 28)), e(2, day=date(2026, 11, 1))]
    changed = by_id(carry_over(entries, TODAY))
    assert changed[1].period_start == TODAY
    assert changed[2].period_start == TODAY


def test_done_today_and_future_entries_stay():
    entries = [
        e(1, status=Status.DONE),            # erledigt gestern
        e(2, day=TODAY),                     # heute
        e(3, day=date(2026, 11, 5)),         # morgen
        e(4, status=Status.MISSED),          # verpasst
    ]
    assert carry_over(entries, TODAY) == []


def test_carried_entry_is_overdue_since_original_day():
    # R-10
    changed = by_id(carry_over([e(1, day=date(2026, 11, 1))], TODAY))
    assert changed[1].overdue is True
    assert changed[1].overdue_since == date(2026, 11, 1)


def test_overdue_since_is_kept_on_repeated_carry():
    # R-10: auch bei mehrfacher Übertragung bleibt das ursprüngliche Datum
    first = carry_over([e(1, day=date(2026, 11, 1))], date(2026, 11, 2))[0]
    second = carry_over([first], TODAY)[0]
    assert second.period_start == TODAY
    assert second.overdue_since == date(2026, 11, 1)


def test_overdue_days():
    entry = e(1, day=TODAY, overdue=True, overdue_since=date(2026, 11, 1))
    assert overdue_days(entry, TODAY) == 3
    assert overdue_days(e(2, day=TODAY), TODAY) is None


def test_open_week_entries_of_past_weeks_move_to_current_week():
    # R-11
    entries = [
        e(1, scope=Scope.WEEK, day=date(2026, 10, 26), tier=Tier.BONUS),
        e(2, scope=Scope.WEEK, day=date(2026, 10, 19)),
    ]
    changed = by_id(carry_over(entries, TODAY))
    assert changed[1].period_start == date(2026, 11, 2)
    assert changed[1].scope == Scope.WEEK
    assert changed[1].tier == Tier.BONUS
    assert changed[1].overdue is True
    assert changed[1].overdue_since == date(2026, 10, 26)
    assert changed[2].overdue_since == date(2026, 10, 19)


def test_current_week_entry_stays():
    entries = [e(1, scope=Scope.WEEK, day=date(2026, 11, 2))]
    assert carry_over(entries, TODAY) == []


def test_day_entry_earlier_this_week_moves_to_today_not_week():
    changed = carry_over([e(1, day=date(2026, 11, 2))], TODAY)[0]
    assert changed.scope == Scope.DAY
    assert changed.period_start == TODAY




def test_carry_over_does_not_mutate_input():
    original = e(1)
    carry_over([original], TODAY)
    assert original.period_start == date(2026, 11, 3)
    assert original.overdue is False
