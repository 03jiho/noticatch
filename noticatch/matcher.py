"""키워드 구독 매칭. 프런트 쪽 `packages/noticatch-keywords` 와 같은 규칙을 서버(파이썬)에서도 쓴다.

- 제외 키워드가 하나라도 있으면 포함 키워드와 상관없이 제외
- 포함 키워드가 비어 있으면 (제외되지 않은) 모든 공지가 대상
- 구독 게시판이 있으면 그 게시판의 공지만 대상
- 비교는 NFC 정규화 + 앞뒤 공백 제거 + 소문자로 한다 (분해형 한글 대응)
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Subscription:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    boards: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    hits: list[str] = field(default_factory=list)
    excluded_by: list[str] = field(default_factory=list)


NO_MATCH = MatchResult(False)


def _norm(value: str | None) -> str:
    return unicodedata.normalize("NFC", value or "").strip().lower()


def _keywords(values: Iterable[str]) -> list[str]:
    return [k for k in (_norm(v) for v in values) if k]


def match_notice(notice: dict, sub: Subscription) -> MatchResult:
    if sub.boards and notice.get("board") not in sub.boards:
        return NO_MATCH
    text = f"{_norm(notice.get('title'))}\n{_norm(notice.get('body'))}"
    excluded_by = [k for k in _keywords(sub.exclude) if k in text]
    if excluded_by:
        return MatchResult(False, excluded_by=excluded_by)
    include = _keywords(sub.include)
    if not include:
        return MatchResult(True)
    hits = [k for k in include if k in text]
    return MatchResult(bool(hits), hits=hits)
