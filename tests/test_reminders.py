"""기능 6: D-3, D-1 리마인드 선정 (TDD)."""
from datetime import date

from noticatch.reminders import Reminder, due_reminders

TODAY = date(2026, 12, 10)


def n(url, deadline, title="공지"):
    return {"title": title, "url": url, "deadline": deadline}


def test_notices_three_and_one_day_away_are_due():
    notices = [n("u3", date(2026, 12, 13)), n("u1", date(2026, 12, 11)), n("u7", date(2026, 12, 17))]
    got = due_reminders(notices, TODAY)
    assert [(r.url, r.days_left) for r in got] == [("u3", 3), ("u1", 1)]


def test_reminder_carries_label_and_title():
    (r,) = due_reminders([n("u1", date(2026, 12, 11), "장학 신청")], TODAY)
    assert r == Reminder(url="u1", title="장학 신청", deadline=date(2026, 12, 11), days_left=1, label="D-1")


def test_already_sent_reminders_are_skipped():
    notices = [n("u3", date(2026, 12, 13))]
    assert due_reminders(notices, TODAY, sent={("u3", 3)}) == []


def test_same_notice_can_still_get_the_other_reminder():
    notices = [n("u", date(2026, 12, 11))]
    assert due_reminders(notices, TODAY, sent={("u", 3)})[0].days_left == 1


def test_past_and_undated_notices_are_ignored():
    notices = [n("past", date(2026, 12, 1)), n("none", None)]
    assert due_reminders(notices, TODAY) == []


def test_custom_offsets():
    got = due_reminders([n("u", date(2026, 12, 17))], TODAY, offsets=(7,))
    assert got[0].label == "D-7"
