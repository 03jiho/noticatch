"""기능 3: 키워드·제외 키워드·게시판 구독 매칭 (TDD)."""
import unicodedata

from noticatch.matcher import Subscription, match_notice


def notice(title, body="", board="학사"):
    return {"title": title, "body": body, "board": board}


def test_include_keyword_in_title_matches():
    r = match_notice(notice("2026 국가근로장학생 모집"), Subscription(include=["장학"]))
    assert (r.matched, r.hits, r.excluded_by) == (True, ["장학"], [])


def test_keyword_in_body_matches():
    assert match_notice(notice("공지", "교환학생 지원 안내"), Subscription(include=["교환학생"])).matched


def test_exclude_keyword_wins_over_include():
    r = match_notice(notice("대학원 장학생 모집"), Subscription(include=["장학"], exclude=["대학원"]))
    assert not r.matched and r.excluded_by == ["대학원"]


def test_empty_include_means_everything_except_excluded():
    assert match_notice(notice("수강신청 안내"), Subscription()).matched
    assert not match_notice(notice("대학원 안내"), Subscription(exclude=["대학원"])).matched


def test_case_and_whitespace_are_ignored():
    assert match_notice(notice("Intern Program 2026"), Subscription(include=["  INTERN "])).matched


def test_blank_keywords_are_ignored():
    assert match_notice(notice("아무 공지"), Subscription(include=["", "  "])).matched


def test_decomposed_hangul_matches_composed_keyword():
    nfd_title = unicodedata.normalize("NFD", "장학금 안내")
    assert match_notice(notice(nfd_title), Subscription(include=["장학"])).matched


def test_board_filter_limits_matches_to_subscribed_boards():
    sub = Subscription(include=["장학"], boards=["학사"])
    assert match_notice(notice("장학 안내", board="학사"), sub).matched
    assert not match_notice(notice("장학 안내", board="공과대"), sub).matched


def test_missing_fields_do_not_crash():
    assert not match_notice({}, Subscription(include=["장학"])).matched
