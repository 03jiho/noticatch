"""중복 공지 제거. 같은 공지가 재공지·공유 링크로 다시 올라와도 한 번만 남긴다.

같은 공지로 보는 기준 (둘 중 하나):
1. 정규화한 URL 이 같다 (대소문자, 끝의 `/`, `#...`, `utm_*` 추적 파라미터, 쿼리 순서는 무시)
2. 같은 게시판에서 공백만 다른 같은 제목
"""
from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = sorted((k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_"))
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path.rstrip('/')}?{urlencode(query)}"


def _title_key(notice: dict) -> tuple[str, str]:
    return notice.get("board", ""), " ".join(notice["title"].split())


def dedupe_notices(notices: Iterable[dict]) -> list[dict]:
    """먼저 나온 공지를 남기고 순서를 유지한다. 입력은 바꾸지 않는다."""
    seen: set[tuple[str, str]] = set()
    kept: list[dict] = []
    for notice in notices:
        keys = {("url", canonical_url(notice["url"])), ("title", _title_key(notice))}
        if keys & seen:
            continue
        seen |= keys
        kept.append(notice)
    return kept
