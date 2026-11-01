"""Tests für Serien (R-13 bis R-18, R-24, R-26, R-29) – Meilenstein M3."""
from dataclasses import replace
from datetime import date

import pytest

from backend.domain.models import Entry, Scope, Status, Tier
from backend.domain.rollover import carry_over
from backend.domain.series import (
    EndType, Freq, MonthlyBy, Pattern, Series,
    end_series, from_rrule, make_entry, missing_occurrences, occurrences,
    preview, split_series, to_rrule, validate,
)

MO, TU, WE, TH, FR, SA, SU = range(7)


def series(**kw) -> Series:
    base = dict(id=1, task_id=1, pattern=Pattern(Freq.DAILY), starts_on=date(2026, 11, 2),
                end_type=EndType.NEVER, tier=Tier.MUST, scope=Scope.DAY)
    base.update(kw)
    return Series(**base)


def all_occ(s, last=date(2027, 12, 31)):
    return occurrences(s, s.starts_on, last)


# --- Abnahme M3 --------------------------------------------------------------

def test_weekly_until_29_december():
    # "jede Woche bis am 29. Dezember" – Start Dienstag, 3.11.2026
    s = series(pattern=Pattern(Freq.WEEKLY), starts_on=date(2026, 11, 3),
               end_type=EndType.UNTIL, until_date=date(2026, 12, 29))
    occ = all_occ(s)
    assert occ[0] == date(2026, 11, 3)
    assert occ[-1] == date(2026, 12, 29)  # Enddatum einschliesslich (R-15)
    assert len(occ) == 9
    assert all(d.weekday() == TU for d in occ)


def test_daily_14_times():
    # "täglich, 14 Mal"
    s = series(starts_on=date(2026, 11, 2), end_type=EndType.COUNT, count=14)
    occ = all_occ(s)
    assert len(occ) == 14
    assert occ[0] == date(2026, 11, 2) and occ[-1] == date(2026, 11, 15)


# --- R-14: Muster -------------------------------------------------------------

def test_every_second_day():
    s = series(pattern=Pattern(Freq.DAILY, interval=2), end_type=EndType.COUNT, count=3)
    assert all_occ(s) == [date(2026, 11, 2), date(2026, 11, 4), date(2026, 11, 6)]


def test_weekly_on_selected_weekdays():
    s = series(pattern=Pattern(Freq.WEEKLY, weekdays=(MO, WE, FR)))
    assert occurrences(s, date(2026, 11, 2), date(2026, 11, 8)) == [
        date(2026, 11, 2), date(2026, 11, 4), date(2026, 11, 6)]


def test_every_two_weeks():
    s = series(pattern=Pattern(Freq.WEEKLY, interval=2), end_type=EndType.COUNT, count=3)
    assert all_occ(s) == [date(2026, 11, 2), date(2026, 11, 16), date(2026, 11, 30)]


def test_monthly_on_day_of_month():
    s = series(pattern=Pattern(Freq.MONTHLY), starts_on=date(2026, 11, 15),
               end_type=EndType.COUNT, count=3)
    assert all_occ(s) == [date(2026, 11, 15), date(2026, 12, 15), date(2027, 1, 15)]


def test_monthly_on_nth_weekday():
    # R-29: Start Montag, 2.11.2026 = erster Montag -> jeweils erster Montag
    s = series(pattern=Pattern(Freq.MONTHLY, monthly_by=MonthlyBy.WEEKDAY),
               end_type=EndType.COUNT, count=3)
    assert all_occ(s) == [date(2026, 11, 2), date(2026, 12, 7), date(2027, 1, 4)]


def test_monthly_31st_skips_short_months():
    # R-18
    s = series(pattern=Pattern(Freq.MONTHLY), starts_on=date(2026, 12, 31),
               end_type=EndType.COUNT, count=3)
    assert all_occ(s) == [date(2026, 12, 31), date(2027, 1, 31), date(2027, 3, 31)]


def test_yearly():
    s = series(pattern=Pattern(Freq.YEARLY), starts_on=date(2026, 11, 20),
               end_type=EndType.COUNT, count=2)
    assert all_occ(s, date(2030, 1, 1)) == [date(2026, 11, 20), date(2027, 11, 20)]


def test_never_ending_series_is_limited_by_window():
    s = series()
    assert len(occurrences(s, date(2026, 11, 2), date(2026, 11, 11))) == 10


def test_exdates_are_skipped():
    s = series(exdates=frozenset({date(2026, 11, 3)}), end_type=EndType.COUNT, count=3)
    assert all_occ(s) == [date(2026, 11, 2), date(2026, 11, 4)]


# --- rrule speichern und lesen -----------------------------------------------

@pytest.mark.parametrize("pattern", [
    Pattern(Freq.DAILY, interval=3),
    Pattern(Freq.WEEKLY, weekdays=(MO, FR)),
    Pattern(Freq.MONTHLY, interval=2, monthly_by=MonthlyBy.WEEKDAY),
    Pattern(Freq.MONTHLY),
    Pattern(Freq.YEARLY),
])
def test_rrule_roundtrip(pattern):
    start = date(2026, 11, 2)
    text = to_rrule(pattern, start)
    assert text.startswith("FREQ=")
    assert from_rrule(text) == pattern


def test_rrule_text():
    assert to_rrule(Pattern(Freq.WEEKLY, 2, (MO, WE)), date(2026, 11, 2)) == \
        "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE"
    assert to_rrule(Pattern(Freq.MONTHLY, monthly_by=MonthlyBy.WEEKDAY), date(2026, 11, 2)) == \
        "FREQ=MONTHLY;INTERVAL=1;BYDAY=+1MO"


# --- R-24 und weitere Prüfungen ----------------------------------------------

def test_week_series_only_weekly():
    validate(series(scope=Scope.WEEK, pattern=Pattern(Freq.WEEKLY, interval=2)))
    with pytest.raises(ValueError):
        validate(series(scope=Scope.WEEK, pattern=Pattern(Freq.DAILY)))
    with pytest.raises(ValueError):
        validate(series(scope=Scope.WEEK, pattern=Pattern(Freq.WEEKLY, weekdays=(MO,))))
    with pytest.raises(ValueError):
        validate(series(scope=Scope.WEEK, pattern=Pattern(Freq.WEEKLY), start_minute=600))


@pytest.mark.parametrize("kw", [
    dict(pattern=Pattern(Freq.DAILY, interval=0)),
    dict(end_type=EndType.COUNT, count=0),
    dict(end_type=EndType.UNTIL, until_date=date(2026, 11, 1)),
    dict(end_type=EndType.UNTIL, until_date=None),
    dict(start_minute=23 * 60 + 45, duration_minutes=30),   # über Mitternacht (R-19)
])
def test_invalid_series(kw):
    with pytest.raises(ValueError):
        validate(series(**kw))


def test_week_series_occurrences_are_mondays():
    s = series(scope=Scope.WEEK, pattern=Pattern(Freq.WEEKLY), starts_on=date(2026, 11, 4),
               end_type=EndType.COUNT, count=2)
    assert occurrences(s, date(2026, 11, 1), date(2026, 12, 31)) == [date(2026, 11, 2), date(2026, 11, 9)]


# --- R-16: Einträge für die nächsten 90 Tage ---------------------------------

def test_missing_occurrences_within_90_days():
    s = series()  # täglich ab 2.11.2026, endlos
    today = date(2026, 11, 4)
    missing = missing_occurrences(s, today, existing=set())
    assert missing[0] == today          # vergangene werden nicht nachträglich erzeugt
    assert missing[-1] == date(2027, 2, 2)  # heute + 90 Tage
    assert len(missing) == 91


def test_missing_skips_existing():
    s = series(end_type=EndType.COUNT, count=5)
    today = date(2026, 11, 2)
    existing = {date(2026, 11, 2), date(2026, 11, 3)}
    assert missing_occurrences(s, today, existing) == [
        date(2026, 11, 4), date(2026, 11, 5), date(2026, 11, 6)]


def test_week_series_includes_current_week():
    s = series(scope=Scope.WEEK, pattern=Pattern(Freq.WEEKLY), starts_on=date(2026, 11, 2),
               end_type=EndType.COUNT, count=2)
    # Mittwoch: das Vorkommen dieser Woche (Montag) wird noch erzeugt
    assert missing_occurrences(s, date(2026, 11, 4), set()) == [date(2026, 11, 2), date(2026, 11, 9)]


def test_make_entry():
    s = series(tier=Tier.BONUS)
    e = make_entry(s, date(2026, 11, 5))
    assert (e.task_id, e.scope, e.period_start, e.tier) == (1, Scope.DAY, date(2026, 11, 5), Tier.BONUS)
    assert e.series_id == 1 and e.occurrence_date == date(2026, 11, 5)
    assert e.is_exception is False


def test_make_week_entry():
    s = series(scope=Scope.WEEK, pattern=Pattern(Freq.WEEKLY))
    e = make_entry(s, date(2026, 11, 9))
    assert (e.scope, e.period_start) == (Scope.WEEK, date(2026, 11, 9))


def test_preview_next_occurrences():
    s = series(pattern=Pattern(Freq.WEEKLY, weekdays=(TU, TH)))
    assert preview(s, 3) == [date(2026, 11, 3), date(2026, 11, 5), date(2026, 11, 10)]


# --- R-17: Serie teilen (dieses und alle folgenden) ---------------------------

def test_split_series_with_until():
    s = series(end_type=EndType.UNTIL, until_date=date(2026, 11, 30))
    old, new = split_series(s, date(2026, 11, 10))
    assert (old.end_type, old.until_date) == (EndType.UNTIL, date(2026, 11, 9))
    assert new.starts_on == date(2026, 11, 10)
    assert (new.end_type, new.until_date) == (EndType.UNTIL, date(2026, 11, 30))
    assert new.id is None


def test_split_series_with_count_keeps_total():
    s = series(end_type=EndType.COUNT, count=14)  # 2.11. bis 15.11.
    old, new = split_series(s, date(2026, 11, 6))
    assert len(all_occ(old)) == 4
    assert len(all_occ(new)) == 10


def test_split_series_drops_old_exdates():
    s = series(exdates=frozenset({date(2026, 11, 3), date(2026, 11, 12)}))
    old, new = split_series(s, date(2026, 11, 10))
    assert old.exdates == frozenset({date(2026, 11, 3)})
    assert new.exdates == frozenset({date(2026, 11, 12)})


def test_split_at_first_occurrence_rejected():
    with pytest.raises(ValueError):
        split_series(series(), date(2026, 11, 2))


# --- R-26: Serie beenden -------------------------------------------------------

def test_end_series_today():
    s = end_series(series(), date(2026, 11, 20))
    assert (s.end_type, s.until_date) == (EndType.UNTIL, date(2026, 11, 20))


def test_end_series_keeps_earlier_end():
    s = series(end_type=EndType.UNTIL, until_date=date(2026, 11, 10))
    assert end_series(s, date(2026, 11, 20)).until_date == date(2026, 11, 10)


def test_end_series_with_count():
    s = end_series(series(end_type=EndType.COUNT, count=100), date(2026, 11, 5))
    assert (s.end_type, s.until_date) == (EndType.UNTIL, date(2026, 11, 5))


# --- R-13: Vorkommen werden standardmässig nicht übertragen -------------------

TODAY = date(2026, 11, 4)


def occ_entry(id, day, series_id=1, scope=Scope.DAY, status=Status.OPEN):
    return Entry(id=id, task_id=1, scope=scope, period_start=day, tier=Tier.MUST,
                 status=status, series_id=series_id, occurrence_date=day)


def test_past_open_occurrence_becomes_missed():
    [e] = carry_over([occ_entry(1, date(2026, 11, 3))], TODAY)
    assert e.status == Status.MISSED
    assert e.period_start == date(2026, 11, 3)  # bleibt am Tag
    assert e.overdue is False


def test_past_week_occurrence_becomes_missed():
    [e] = carry_over([occ_entry(1, date(2026, 10, 26), scope=Scope.WEEK)], TODAY)
    assert e.status == Status.MISSED


def test_occurrence_with_carry_over_is_carried():
    [e] = carry_over([occ_entry(1, date(2026, 11, 3))], TODAY, carry_series={1})
    assert e.status == Status.OPEN
    assert e.period_start == TODAY
    assert e.overdue is True


def test_done_and_today_occurrences_untouched():
    entries = [occ_entry(1, date(2026, 11, 3), status=Status.DONE), occ_entry(2, TODAY)]
    assert carry_over(entries, TODAY) == []
