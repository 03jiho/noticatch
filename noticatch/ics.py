"""마감일을 .ics(iCalendar) 구독 피드로 만든다. Google·Apple 캘린더가 이 주소를 구독하면 마감일이 자동으로 들어간다.

RFC 5545 에서 필요한 부분만 구현한다.
- 줄바꿈은 CRLF, 한 줄은 75옥텟을 넘으면 접는다(다음 줄은 공백으로 시작). 한글 글자 중간에서는 자르지 않는다.
- 마감일은 종일 일정이다. 종일 일정의 DTEND 는 배타적이라 다음 날을 쓴다.
- UID 는 공지 URL 에서 만들어 피드를 다시 만들어도 같은 일정이 중복되지 않는다.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import datetime, timedelta

CRLF = "\r\n"
MAX_OCTETS = 75


def escape_text(text: str) -> str:
    """TEXT 값 이스케이프: 역슬래시, 세미콜론, 쉼표, 줄바꿈."""
    return text.replace("\\", "\\\\").replace(";", r"\;").replace(",", "\\,").replace("\n", "\\n")


def fold_line(line: str) -> str:
    chunks: list[str] = []
    current = ""
    for ch in line:
        if len((current + ch).encode("utf-8")) > MAX_OCTETS:
            chunks.append(current)
            current = " " + ch  # 이어지는 줄의 맨 앞 공백도 길이에 포함된다
        else:
            current += ch
    chunks.append(current)
    return CRLF.join(chunks)


def _uid(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16] + "@noticatch"


def _event_lines(event: dict, stamp: str) -> list[str]:
    day = event["deadline"]
    return [
        "BEGIN:VEVENT",
        f"UID:{_uid(event['url'])}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
        f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{escape_text(event['title'])}",
        f"URL:{event['url']}",
        "END:VEVENT",
    ]


def build_ics(events: Iterable[dict], now: datetime, name: str = "NotiCatch 마감일") -> str:
    """마감일이 있는 공지만 일정으로 만든다."""
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//NotiCatch//Deadlines//KO", f"X-WR-CALNAME:{escape_text(name)}"]
    for event in events:
        if event.get("deadline"):
            lines += _event_lines(event, stamp)
    lines.append("END:VCALENDAR")
    return "".join(fold_line(line) + CRLF for line in lines)
