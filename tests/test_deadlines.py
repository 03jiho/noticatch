"""기능 1: 공지 본문에서 마감일 추출 (TDD)."""
from datetime import date

import pytest

from noticatch.deadlines import extract_deadline

TODAY = date(2026, 11, 26)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("접수기간: 2026. 12. 1. ~ 2026. 12. 13.", date(2026, 12, 13)),
        ("신청 마감: 2026-12-13", date(2026, 12, 13)),
        ("12월 1일 ~ 12월 13일(토)까지 신청", date(2026, 12, 13)),
        ("12/13까지 제출", date(2026, 12, 13)),
        ("2026년 12월 13일 오후 6시까지", date(2026, 12, 13)),
    ],
)
def test_extracts_deadline_from_common_korean_formats(text, expected):
    assert extract_deadline(text, today=TODAY) == expected


def test_range_uses_the_end_date_not_the_start():
    assert extract_deadline("신청기간 12월 1일 ~ 12월 20일", today=TODAY) == date(2026, 12, 20)


def test_year_rolls_over_when_month_already_passed():
    assert extract_deadline("1월 5일까지 접수", today=date(2026, 12, 20)) == date(2027, 1, 5)


def test_returns_none_when_no_date():
    assert extract_deadline("마감일은 추후 공지합니다", today=TODAY) is None
    assert extract_deadline("", today=TODAY) is None


def test_invalid_calendar_dates_are_ignored():
    assert extract_deadline("2월 30일까지", today=TODAY) is None


def test_without_range_marker_the_latest_date_wins():
    assert extract_deadline("발표 12월 5일, 서류 마감 12월 13일", today=TODAY) == date(2026, 12, 13)
