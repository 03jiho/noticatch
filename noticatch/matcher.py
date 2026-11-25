import unicodedata
from dataclasses import dataclass, field


@dataclass
class Subscription:
    include: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    boards: list = field(default_factory=list)


@dataclass
class MatchResult:
    matched: bool
    hits: list
    excluded_by: list


def norm(s):
    return unicodedata.normalize("NFC", s or "").strip().lower()


def match_notice(notice, sub):
    if sub.boards and notice.get("board") not in sub.boards:
        return MatchResult(False, [], [])
    text = norm(notice.get("title")) + "\n" + norm(notice.get("body"))
    inc = [norm(k) for k in sub.include if norm(k)]
    exc = [norm(k) for k in sub.exclude if norm(k)]
    ex = [k for k in exc if k in text]
    if ex:
        return MatchResult(False, [], ex)
    if not inc:
        return MatchResult(True, [], [])
    hits = [k for k in inc if k in text]
    return MatchResult(bool(hits), hits, [])
