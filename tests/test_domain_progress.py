"""Tests für den Fortschritt (R-2 bis R-4)."""
from datetime import date

from backend.domain.models import Entry, Scope, Status, Tier
from backend.domain.progress import day_progress, week_progress

_next_id = iter(range(1, 1000))


def e(tier=Tier.MUST, status=Status.OPEN, scope=Scope.DAY, day=date(2026, 11, 4)):
    return Entry(id=next(_next_id), task_id=1, scope=scope, period_start=day,
                 tier=tier, status=status)


def test_progress_counts_by_number():
    # R-2: 1 von 2 Pflicht erledigt, 2 von 4 insgesamt
    entries = [
        e(Tier.MUST, Status.DONE),
        e(Tier.MUST),
        e(Tier.BONUS, Status.DONE),
        e(Tier.BONUS),
    ]
    p = day_progress(entries, date(2026, 11, 4))
    assert (p.must_done, p.must_total) == (1, 2)
    assert (p.all_done, p.all_total) == (2, 4)
    assert p.must_ratio == 0.5
    assert p.all_ratio == 0.5


def test_progress_only_counts_entries_of_that_day():
    entries = [e(day=date(2026, 11, 4)), e(day=date(2026, 11, 5))]
    assert day_progress(entries, date(2026, 11, 4)).must_total == 1


def test_day_progress_ignores_week_entries():
    entries = [e(), e(scope=Scope.WEEK, day=date(2026, 11, 2))]
    assert day_progress(entries, date(2026, 11, 4)).all_total == 1


def test_empty_progress_has_zero_ratio_and_no_minimum():
    p = day_progress([], date(2026, 11, 4))
    assert p.must_ratio == 0
    assert p.all_ratio == 0
    assert p.minimum_reached is False


def test_minimum_reached_when_all_must_done():
    # R-3
    entries = [e(Tier.MUST, Status.DONE), e(Tier.MUST, Status.DONE), e(Tier.BONUS)]
    assert day_progress(entries, date(2026, 11, 4)).minimum_reached is True


def test_minimum_not_reached_without_must_entries():
    # R-3: mindestens ein Pflicht-Eintrag nötig
    entries = [e(Tier.BONUS, Status.DONE)]
    assert day_progress(entries, date(2026, 11, 4)).minimum_reached is False


def test_minimum_not_reached_with_open_must():
    entries = [e(Tier.MUST, Status.DONE), e(Tier.MUST)]
    assert day_progress(entries, date(2026, 11, 4)).minimum_reached is False


def test_week_progress_includes_week_and_day_entries():
    # R-4: Woche vom 2.11. bis 8.11.2026
    entries = [
        e(Tier.MUST, Status.DONE, Scope.WEEK, date(2026, 11, 2)),
        e(Tier.MUST, Status.OPEN, Scope.DAY, date(2026, 11, 3)),
        e(Tier.BONUS, Status.DONE, Scope.DAY, date(2026, 11, 8)),  # Sonntag
        e(Tier.MUST, Status.OPEN, Scope.DAY, date(2026, 11, 9)),   # nächste Woche
        e(Tier.MUST, Status.OPEN, Scope.WEEK, date(2026, 11, 9)),  # nächste Woche
    ]
    p = week_progress(entries, date(2026, 11, 5))
    assert (p.must_done, p.must_total) == (1, 2)
    assert (p.all_done, p.all_total) == (2, 3)
