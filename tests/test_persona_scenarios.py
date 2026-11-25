"""페르소나 시나리오 인수 테스트.

experiments/personas.json 의 가상 사용자 10명 각각의 시나리오를 실행 가능한 코드로 옮겼다.
통과/실패가 곧 그 페르소나에 대한 '제품이 약속을 지키는가' 평가이고, 실패는 백로그가 된다.
"""
import json
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path

from noticatch.deadlines import extract_deadline
from noticatch.dedupe import dedupe_notices
from noticatch.ics import build_ics, fold_line
from noticatch.matcher import Subscription, match_notice
from noticatch.reminders import due_reminders

PERSONAS = {p["id"]: p for p in json.loads((Path(__file__).resolve().parent.parent / "experiments" / "personas.json").read_text(encoding="utf-8"))["personas"]}
TODAY = date(2026, 11, 26)


def test_persona_file_has_ten_distinct_personas():
    assert len(PERSONAS) == 10
    assert len({p["name"] for p in PERSONAS.values()}) == 10
    assert len({p["role"] for p in PERSONAS.values()}) == 10


def test_p01_scholarship_subscriber_sees_match_and_deadline():
    sub = Subscription(include=["장학"], exclude=["대학원"])
    ok = {"title": "2026 국가근로장학생 모집", "body": "접수기간: 2026. 12. 1. ~ 2026. 12. 13."}
    grad = {"title": "대학원 장학생 모집", "body": ""}
    assert match_notice(ok, sub).matched and not match_notice(grad, sub).matched
    assert extract_deadline(ok["body"], TODAY) == date(2026, 12, 13)


def test_p02_keyword_case_and_spaces_do_not_matter():
    assert match_notice({"title": "Summer Intern Program 2026"}, Subscription(include=[" INTERN "])).matched


def test_p03_decomposed_hangul_from_mac_still_matches():
    title = unicodedata.normalize("NFD", "2학기 수강신청 안내")
    assert match_notice({"title": title}, Subscription(include=["수강신청"])).matched


def test_p04_board_filter_blocks_other_boards():
    sub = Subscription(include=["연구"], boards=["대학원"])
    assert match_notice({"title": "연구비 안내", "board": "대학원"}, sub).matched
    assert not match_notice({"title": "연구비 안내", "board": "학부"}, sub).matched


def test_p05_short_date_and_d3_reminder():
    deadline = extract_deadline("교환학생 지원서 12/20까지 제출", TODAY)
    assert deadline == date(2026, 12, 20)
    reminders = due_reminders([{"title": "교환학생", "url": "u", "deadline": deadline}], date(2026, 12, 17))
    assert [r.label for r in reminders] == ["D-3"]


def test_p06_calendar_feed_is_valid_and_idempotent():
    ev = {"title": "복학 신청, 등록금 납부", "url": "https://x.kr/n/9", "deadline": date(2026, 12, 13)}
    a = build_ics([ev], now=datetime(2026, 11, 26, tzinfo=UTC))
    b = build_ics([ev], now=datetime(2026, 11, 27, tzinfo=UTC))
    assert "SUMMARY:복학 신청\\, 등록금 납부" in a
    uid = next(line for line in a.split("\r\n") if line.startswith("UID:"))
    assert uid in b.split("\r\n")


def test_p07_reposted_notice_is_shown_once():
    notices = [
        {"title": "장학 안내", "url": "https://x.kr/n/1", "board": "학사"},
        {"title": "[재공지] 장학 안내", "url": "https://x.kr/n/1?utm_source=push", "board": "학사"},
    ]
    assert len(dedupe_notices(notices)) == 1


def test_p07_deadline_written_as_month_dot_day_with_weekday():
    assert extract_deadline("신청기간 11.30(일)~12.5(금)", TODAY) == date(2026, 12, 5)
    assert extract_deadline("11. 30.(일) ~ 12. 5.(금) 접수", TODAY) == date(2026, 12, 5)


def test_p08_english_keyword_finds_bilingual_notice():
    notice = {"title": "Scholarship / 장학금 신청 안내"}
    assert match_notice(notice, Subscription(include=["scholarship"])).matched


def test_p09_deadline_with_weekday_and_time():
    assert extract_deadline("2026년 12월 13일(토) 17:00까지 납부", TODAY) == date(2026, 12, 13)


def test_p10_many_boards_and_long_titles_fold_correctly():
    sub = Subscription(include=["공모", "장학", "대회"], boards=["학사", "학생회", "공과대"])
    assert match_notice({"title": "공모전 안내", "board": "학생회"}, sub).matched
    long_title = "2026학년도 겨울방학 학생회 주관 전국 대학생 아이디어 공모전 참가팀 모집 및 사전 설명회 개최 안내"
    ev = {"title": long_title, "url": "https://x.kr/n/10", "deadline": date(2026, 12, 13)}
    out = build_ics([ev], now=datetime(2026, 11, 26, tzinfo=UTC))
    assert all(len(line.encode("utf-8")) <= 75 for line in out.split("\r\n"))
    unfolded = out.replace("\r\n ", "")
    assert f"SUMMARY:{long_title}" in unfolded
    assert fold_line("A" * 200).count("\r\n") >= 2
