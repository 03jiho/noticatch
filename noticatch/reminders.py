"""마감 리마인드(D-3, D-1)와 D-day 표시."""
from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date

DEFAULT_OFFSETS = (3, 1)


def dday_label(deadline: date | None, today: date) -> str:
    if deadline is None:
        return "마감일 미정"
    days = (deadline - today).days
    if days > 0:
        return f"D-{days}"
    if days == 0:
        return "D-day"
    return f"마감 (D+{-days})"


@dataclass(frozen=True)
class Reminder:
    url: str
    title: str
    deadline: date
    days_left: int
    label: str


def due_reminders(
    notices: Iterable[dict],
    today: date,
    offsets: tuple[int, ...] = DEFAULT_OFFSETS,
    sent: Collection[tuple[str, int]] = (),
) -> list[Reminder]:
    """오늘 보내야 할 리마인드. `sent` 는 이미 보낸 (공지 URL, 며칠 전) 쌍이라 중복 발송을 막는다."""
    reminders = []
    for notice in notices:
        deadline = notice["deadline"]
        if deadline is None:
            continue
        days_left = (deadline - today).days
        if days_left in offsets and (notice["url"], days_left) not in sent:
            reminders.append(Reminder(notice["url"], notice["title"], deadline, days_left, dday_label(deadline, today)))
    return reminders
