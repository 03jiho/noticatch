"""공지 본문에서 마감일을 뽑는다.

규칙: 기간(`A ~ B`)이면 끝나는 날, 날짜가 여럿이면 가장 늦은 날을 마감일로 본다.
연도가 없는 날짜(`12월 13일`, `12/13`)는 오늘 이후 가장 가까운 해로 채운다.
"""
from __future__ import annotations

import re
from datetime import date

_SEP = r"\s*[.\-]\s*"
# (정규식, 연도가 글 안에 있는가). 앞에서부터 차례로 적용하고, 같은 위치의 날짜는 한 번만 센다.
_PATTERNS: tuple[tuple[re.Pattern[str], bool], ...] = (
    (re.compile(rf"(\d{{4}}){_SEP}(\d{{1,2}}){_SEP}(\d{{1,2}})"), True),
    (re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"), True),
    (re.compile(r"(?<![\d.\-/])(\d{1,2})\s*월\s*(\d{1,2})\s*일"), False),
    (re.compile(r"(?<![\d.\-/])(\d{1,2})/(\d{1,2})(?![\d/])"), False),
)
_YEAR_BEFORE = re.compile(r"\d{4}\s*년\s*$")


def _build(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _fill_year(month: int, day: int, today: date) -> date | None:
    """연도가 없는 날짜: 오늘 이후로 가장 가까운 날짜."""
    for year in (today.year, today.year + 1):
        found = _build(year, month, day)
        if found is None:
            return None
        if found >= today:
            return found
    return None


def _find_dates(text: str, today: date) -> list[tuple[int, date]]:
    found: list[tuple[int, date]] = []
    for pattern, has_year in _PATTERNS:
        for m in pattern.finditer(text):
            if has_year:
                parsed = _build(*(int(g) for g in m.groups()))
            elif _YEAR_BEFORE.search(text[max(0, m.start() - 8) : m.start()]):
                continue  # "2026년 12월 13일" 의 뒷부분을 연도 없는 날짜로 또 세지 않는다
            else:
                parsed = _fill_year(int(m.group(1)), int(m.group(2)), today)
            if parsed is not None:
                found.append((m.start(), parsed))
    return sorted(found)


def extract_deadline(text: str, today: date) -> date | None:
    """마감일을 돌려준다. 찾지 못하면 None."""
    found = _find_dates(text, today)
    if not found:
        return None
    tilde = text.rfind("~")
    after_range = [d for pos, d in found if tilde >= 0 and pos > tilde]
    return after_range[0] if after_range else max(d for _, d in found)
