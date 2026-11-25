"""기능 5: D-day 표시 (TDD)."""
from datetime import date

from noticatch.reminders import dday_label

TODAY = date(2026, 12, 10)


def test_future_dates_are_d_minus_n():
    assert dday_label(date(2026, 12, 13), TODAY) == "D-3"
    assert dday_label(date(2026, 12, 11), TODAY) == "D-1"


def test_today_is_d_day():
    assert dday_label(TODAY, TODAY) == "D-day"


def test_past_dates_are_marked_closed():
    assert dday_label(date(2026, 12, 8), TODAY) == "마감 (D+2)"


def test_no_deadline():
    assert dday_label(None, TODAY) == "마감일 미정"
