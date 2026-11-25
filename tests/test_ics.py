"""기능 4: .ics 캘린더 피드 생성 (TDD). RFC 5545 의 필요한 부분만 지킨다."""
from datetime import UTC, date, datetime

from noticatch.ics import build_ics, escape_text, fold_line

NOW = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)
EVENT = {"title": "국가근로장학생 신청 마감", "url": "https://x.kr/n/1", "deadline": date(2026, 12, 13)}


def lines(text):
    return text.split("\r\n")


def test_calendar_envelope_and_crlf():
    out = build_ics([EVENT], now=NOW)
    assert out.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n")
    assert out.endswith("END:VCALENDAR\r\n")
    assert "\n" not in out.replace("\r\n", "")


def test_all_day_event_ends_the_next_day():
    out = lines(build_ics([EVENT], now=NOW))
    assert "DTSTART;VALUE=DATE:20261213" in out
    assert "DTEND;VALUE=DATE:20261214" in out  # 종일 일정의 DTEND 는 다음 날(배타적)
    assert "DTSTAMP:20261126T090000Z" in out


def test_month_end_rolls_over():
    ev = {**EVENT, "deadline": date(2026, 12, 31)}
    assert "DTEND;VALUE=DATE:20270101" in lines(build_ics([ev], now=NOW))


def test_uid_is_stable_for_the_same_url():
    a = [x for x in lines(build_ics([EVENT], now=NOW)) if x.startswith("UID:")]
    b = [x for x in lines(build_ics([EVENT], now=datetime(2027, 1, 1, tzinfo=UTC))) if x.startswith("UID:")]
    assert a == b and a[0].endswith("@noticatch")


def test_text_escaping():
    assert escape_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"


def test_summary_is_escaped():
    ev = {**EVENT, "title": "인턴, 모집; 안내"}
    assert "SUMMARY:인턴\\, 모집\\; 안내" in lines(build_ics([ev], now=NOW))


def test_long_lines_are_folded_at_75_octets_without_splitting_characters():
    folded = fold_line("SUMMARY:" + "가" * 60)
    parts = folded.split("\r\n")
    assert all(len(p.encode("utf-8")) <= 75 for p in parts)
    assert all(p.startswith(" ") for p in parts[1:])
    assert "".join([parts[0], *[p[1:] for p in parts[1:]]]) == "SUMMARY:" + "가" * 60


def test_events_without_a_deadline_are_skipped():
    out = build_ics([{"title": "마감 미정", "url": "https://x.kr/n/2", "deadline": None}], now=NOW)
    assert "BEGIN:VEVENT" not in out
