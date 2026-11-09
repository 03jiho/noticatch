"""scripts/sprint_metrics.py 단위 테스트. 오늘 날짜(TODAY)와 API 호출을 가짜로 바꿔 검증한다."""

from datetime import UTC, date, datetime, timedelta

import pytest
import sprint_metrics as sm

UTC = UTC


def issue(number, points, state="open", closed_at=None, **extra):
    base = {
        "number": number, "title": f"issue {number}", "points": points, "state": state,
        "created_at": "2026-11-01T00:00:00Z", "closed_at": closed_at,
    }
    if state == "closed":
        base.update(cycle_time_h=10.0, lead_time_h=20.0)
    return {**base, **extra}


@pytest.mark.parametrize(
    ("labels", "expected"),
    [(["size: 3"], 3), (["bug", "size:5"], 5), ([], 0), (["size: x"], 0), (["resize: 8"], 0)],
)
def test_points(labels, expected):
    assert sm.points({"labels": [{"name": n} for n in labels]}) == expected


def test_hours_and_med_round_to_one_decimal():
    assert sm.hours(timedelta(minutes=100)) == 1.7
    assert sm.med([]) is None
    assert sm.med([1, 2, 4]) == 2.0


def test_work_started_uses_first_assignment_or_creation(monkeypatch):
    target = {"number": 1, "created_at": "2026-11-01T00:00:00Z"}
    events = [
        {"event": "labeled", "created_at": "2026-11-01T01:00:00Z"},
        {"event": "assigned", "created_at": "2026-11-03T00:00:00Z"},
        {"event": "assigned", "created_at": "2026-11-02T00:00:00Z"},
    ]
    monkeypatch.setattr(sm, "all_pages", lambda path, params=None: events)
    assert sm.work_started(target) == datetime(2026, 11, 2, tzinfo=UTC)
    monkeypatch.setattr(sm, "all_pages", lambda path, params=None: [])
    assert sm.work_started(target) == datetime(2026, 11, 1, tzinfo=UTC)


def test_build_sprint_active_burndown(monkeypatch):
    monkeypatch.setattr(sm, "TODAY", date(2026, 11, 3))
    # 2026-11-02 03:00 UTC = 한국 시간 11-02 12:00 에 3포인트 이슈가 닫혔다.
    items = [issue(2, 2), issue(1, 3, "closed", "2026-11-02T03:00:00Z")]
    s = sm.build_sprint("Sprint X", date(2026, 11, 1), date(2026, 11, 5), items)
    assert s["status"] == "active"
    assert (s["committed_points"], s["completed_points"]) == (5, 3)
    assert (s["issues_total"], s["issues_done"]) == (2, 1)
    assert s["cycle_time_median_h"] == 10.0
    assert [b["remaining"] for b in s["burndown"]] == [5, 2, 2, None, None]
    assert [b["ideal"] for b in s["burndown"]] == [5.0, 3.75, 2.5, 1.25, 0.0]
    assert [i["number"] for i in s["issues"]] == [1, 2]


@pytest.mark.parametrize(
    ("today", "status"),
    [(date(2026, 10, 31), "planned"), (date(2026, 11, 5), "active"), (date(2026, 11, 6), "closed")],
)
def test_sprint_status_by_date(monkeypatch, today, status):
    monkeypatch.setattr(sm, "TODAY", today)
    s = sm.build_sprint("S", date(2026, 11, 1), date(2026, 11, 5), [])
    assert s["status"] == status


def test_one_day_sprint_does_not_divide_by_zero(monkeypatch):
    monkeypatch.setattr(sm, "TODAY", date(2026, 11, 1))
    s = sm.build_sprint("S", date(2026, 11, 1), date(2026, 11, 1), [issue(1, 2)])
    assert s["burndown"] == [{"date": "2026-11-01", "ideal": 0, "remaining": 2}]


def sprint(title, status, completed, cycles=()):
    return {
        "title": title, "start": "2026-11-01", "end": "2026-11-14", "status": status,
        "committed_points": 8, "completed_points": completed, "issues_total": 1, "issues_done": 1,
        "cycle_time_median_h": None, "lead_time_median_h": None, "burndown": [],
        "issues": [{"number": n, "title": "t", "points": 1, "state": "closed",
                    "closed_at": "2026-11-02T00:00:00Z", "cycle_time_h": c, "lead_time_h": c}
                   for n, c in enumerate(cycles, 1)],
    }


def test_summarize_prefers_closed_sprints():
    r = sm.summarize([sprint("A", "closed", 4), sprint("B", "closed", 6, [2.0, 4.0]), sprint("C", "active", 1)])
    assert r["average_velocity"] == 5.0
    assert r["velocity_basis"] == "완료된 스프린트 평균"
    assert r["current_sprint"] == "C"
    assert (r["cycle_time_median_h"], r["cycle_time_samples"]) == (3.0, 2)


def test_summarize_falls_back_to_active_then_empty():
    r = sm.summarize([sprint("C", "active", 3)])
    assert r["average_velocity"] == 3.0
    assert "진행 중" in r["velocity_basis"]
    empty = sm.summarize([])
    assert empty["average_velocity"] is None
    assert empty["current_sprint"] is None


def test_fmt_h():
    assert sm.fmt_h(None) == "-"
    assert sm.fmt_h(5) == "5.0시간"
    assert sm.fmt_h(72) == "3.0일"


def result(sprints):
    return {
        "generated_at": "2026-11-09T03:00:00+00:00", "repo": "o/r", "sprints": sprints,
        "summary": sm.summarize(sprints),
    }


def test_report_and_table_render():
    r = result([sprint("Sprint 1", "closed", 6, [2.0]), sprint("Sprint 2", "planned", 0)])
    table = sm.sprint_table(r)
    assert "| Sprint 1 | 2026-11-01 ~ 2026-11-14 | 종료 | 1/1 | 6/8 | - |" in table
    assert "예정" in table
    text = sm.report(r)
    assert "# 스프린트 분석 보고서" in text
    assert "#1 t" in text
    assert "아직 완료된 이슈 없음" in sm.report(result([]))


def test_update_readme_replaces_only_marked_block(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "ROOT", tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("A\n<!-- SPRINT:START -->\n옛날\n<!-- SPRINT:END -->\nB\n", encoding="utf-8")
    sm.update_readme(result([sprint("Sprint 1", "closed", 6)]))
    text = readme.read_text(encoding="utf-8")
    assert text.startswith("A\n<!-- SPRINT:START -->") and text.endswith("<!-- SPRINT:END -->\nB\n")
    assert "옛날" not in text and "Sprint 1" in text


def test_collect_skips_prs_and_milestones_without_period(monkeypatch):
    monkeypatch.setattr(sm, "TODAY", date(2026, 11, 20))
    milestones = [
        {"number": 1, "title": "Sprint 1", "description": "설명\n\n기간: 2026-11-01 ~ 2026-11-14"},
        {"number": 2, "title": "기간 없음", "description": "그냥 마일스톤"},
    ]
    issues = [
        {"number": 1, "title": "done", "labels": [{"name": "size: 3"}], "state": "closed",
         "created_at": "2026-11-01T00:00:00Z", "closed_at": "2026-11-02T00:00:00Z"},
        {"number": 2, "title": "a pr", "labels": [], "state": "open", "pull_request": {},
         "created_at": "2026-11-01T00:00:00Z", "closed_at": None},
    ]

    def fake_all_pages(path, params=None):
        return milestones if path.endswith("/milestones") else issues

    monkeypatch.setattr(sm, "all_pages", fake_all_pages)
    monkeypatch.setattr(sm, "work_started", lambda i: datetime(2026, 11, 1, 12, tzinfo=UTC))
    r = sm.collect()
    assert [s["title"] for s in r["sprints"]] == ["Sprint 1"]
    only = r["sprints"][0]
    assert only["status"] == "closed"
    assert (only["committed_points"], only["completed_points"], only["issues_total"]) == (3, 3, 1)
    assert only["issues"][0]["cycle_time_h"] == 12.0  # 11-01 12:00 → 11-02 00:00
    assert only["issues"][0]["lead_time_h"] == 24.0
