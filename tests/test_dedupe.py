"""기능 2: 중복 공지 제거 (TDD)."""
from noticatch.dedupe import canonical_url, dedupe_notices


def test_canonical_url_ignores_tracking_fragment_and_trailing_slash():
    a = canonical_url("HTTPS://School.ac.kr/notice/1/?utm_source=kakao&id=7#top")
    b = canonical_url("https://school.ac.kr/notice/1?id=7")
    assert a == b


def test_canonical_url_sorts_query_parameters():
    assert canonical_url("https://x.kr/n?b=2&a=1") == canonical_url("https://x.kr/n?a=1&b=2")


def test_same_url_is_removed_keeping_the_first():
    notices = [
        {"title": "장학생 모집", "url": "https://x.kr/n/1", "board": "학사"},
        {"title": "[재공지] 장학생 모집", "url": "https://x.kr/n/1/?utm_medium=push", "board": "학사"},
    ]
    assert dedupe_notices(notices) == notices[:1]


def test_same_title_on_same_board_is_removed_even_with_different_url():
    notices = [
        {"title": "  수강신청  안내 ", "url": "https://x.kr/n/1", "board": "학사"},
        {"title": "수강신청 안내", "url": "https://x.kr/n/2", "board": "학사"},
    ]
    assert len(dedupe_notices(notices)) == 1


def test_same_title_on_different_boards_is_kept():
    notices = [
        {"title": "수강신청 안내", "url": "https://x.kr/a/1", "board": "학사"},
        {"title": "수강신청 안내", "url": "https://x.kr/b/1", "board": "공과대"},
    ]
    assert len(dedupe_notices(notices)) == 2


def test_order_is_preserved_and_input_is_not_modified():
    notices = [{"title": f"공지{i}", "url": f"https://x.kr/{i}", "board": "b"} for i in (3, 1, 2)]
    snapshot = [dict(n) for n in notices]
    assert dedupe_notices(notices) == snapshot
    assert notices == snapshot


def test_empty_input():
    assert dedupe_notices([]) == []
