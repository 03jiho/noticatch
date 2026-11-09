"""scripts/dora_metrics.py 단위 테스트. 네트워크 없이 GitHub API 호출을 가짜로 바꿔 검증한다."""

from datetime import UTC, datetime, timedelta

import dora_metrics as dm
import pytest

UTC = UTC


def test_ts_parses_z_suffix_and_none():
    assert dm.ts("2026-11-01T00:00:00Z") == datetime(2026, 11, 1, tzinfo=UTC)
    assert dm.ts(None) is None


def test_hours_rounds_to_two_decimals():
    assert dm.hours(timedelta(minutes=90)) == 1.5
    assert dm.hours(timedelta(seconds=1000)) == 0.28


def test_median():
    assert dm.median([]) is None
    assert dm.median([1, 2, 3, 4]) == 2.5


def test_iso_week_uses_iso_year():
    # 2027-01-01(금)은 ISO 기준으로 2026년의 53주차다.
    assert dm.iso_week(datetime(2027, 1, 1)) == "2026-W53"
    assert dm.iso_week(datetime(2026, 11, 9)) == "2026-W46"


def metrics(per_week, lead, cfr, mttr):
    return {
        "deployment_frequency": {"per_week": per_week},
        "lead_time_for_changes": {"median_h": lead},
        "change_failure_rate": {"rate": cfr},
        "mttr": {"median_h": mttr},
    }


def test_classify_elite_at_boundaries():
    levels = dm.classify(metrics(7, 24, 0.15, 1))
    assert set(levels.values()) == {"Elite"}


def test_classify_low():
    levels = dm.classify(metrics(0.1, 1000, 0.5, 200))
    assert set(levels.values()) == {"Low"}


def test_classify_middle_bands():
    levels = dm.classify(metrics(1, 100, 0.2, 24))
    assert levels == {
        "deployment_frequency": "High",
        "lead_time_for_changes": "High",
        "change_failure_rate": "High",
        "mttr": "High",
    }


def test_classify_missing_data_is_na():
    levels = dm.classify(metrics(0, None, None, None))
    assert levels["mttr"] == "N/A"
    assert levels["lead_time_for_changes"] == "N/A"
    assert levels["change_failure_rate"] == "N/A"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "데이터 없음"), (0.5, "30분"), (5, "5.0시간"), (72, "3.0일")],
)
def test_fmt_h(value, expected):
    assert dm.fmt_h(value) == expected


def test_fmt_rate():
    assert dm.fmt_rate(None) == "데이터 없음"
    assert dm.fmt_rate(0.2) == "20%"


@pytest.fixture
def fake_api(monkeypatch):
    """배포 3건(성공·실패·성공)과 커밋을 돌려주는 가짜 API."""
    monkeypatch.setattr(dm, "NOW", datetime(2026, 11, 9, 12, tzinfo=UTC))
    monkeypatch.setattr(dm, "WINDOW_DAYS", 30)
    monkeypatch.setattr(dm, "WEEKS", 2)

    def run(i, conclusion, created, updated, sha):
        return {"id": i, "head_sha": sha * 40, "conclusion": conclusion, "status": "completed",
                "created_at": created, "updated_at": updated, "html_url": f"https://example.test/{i}"}

    runs = [
        run(1, "success", "2026-11-01T00:00:00Z", "2026-11-01T01:00:00Z", "a"),
        run(2, "failure", "2026-11-03T00:00:00Z", "2026-11-03T00:10:00Z", "b"),
        run(3, "success", "2026-11-04T00:00:00Z", "2026-11-04T02:00:00Z", "c"),
    ]

    def commit(date, message="feat: x"):
        return {"commit": {"message": message, "committer": {"date": date}}}

    commits = {
        "a" * 40: [commit("2026-11-01T00:00:00Z")],
        # 두 번째 성공 배포: 일반 커밋 1개 + 지표 자동 갱신 커밋([skip ci]) 1개
        "c" * 40: [commit("2026-11-04T00:00:00Z"), commit("2026-11-04T01:00:00Z", "chore: metrics [skip ci]")],
    }
    monkeypatch.setattr(dm, "deploy_runs", lambda since: runs)
    monkeypatch.setattr(dm, "commits_between", lambda base, head: commits[head])
    monkeypatch.setattr(dm, "incident_issues", lambda since: [])
    return monkeypatch


def test_compute_core_metrics(fake_api):
    r = dm.compute()
    m = r["metrics"]
    assert m["deployment_frequency"] == {"successful_deploys": 2, "per_week": 0.47}
    assert m["change_failure_rate"] == {"rate": 0.333, "failed": 1, "total": 3}
    # 리드타임: 1.0시간, 2.0시간. [skip ci] 커밋은 제외된다.
    assert m["lead_time_for_changes"] == {"median_h": 1.5, "samples": 2}
    # 복구 시간: 실패 배포 시작(11-03 00:00) → 다음 성공 배포 종료(11-04 02:00) = 26시간
    assert m["mttr"] == {"median_h": 26.0, "samples": 1}
    assert r["levels"]["lead_time_for_changes"] == "Elite"
    assert r["levels"]["change_failure_rate"] == "Low"
    assert len(r["weekly"]) == 2


def test_compute_counts_closed_incident_issues_as_recoveries(fake_api):
    issue = {"number": 5, "created_at": "2026-11-05T00:00:00Z", "closed_at": "2026-11-05T00:30:00Z"}
    still_open = {"number": 6, "created_at": "2026-11-06T00:00:00Z", "closed_at": None}
    fake_api.setattr(dm, "incident_issues", lambda since: [issue, still_open])
    m = dm.compute()["metrics"]["mttr"]
    assert m["samples"] == 2
    assert m["median_h"] == 13.25  # (26 + 0.5) / 2


def test_compute_without_deployments(monkeypatch):
    monkeypatch.setattr(dm, "deploy_runs", lambda since: [])
    monkeypatch.setattr(dm, "incident_issues", lambda since: [])
    r = dm.compute()
    assert r["metrics"]["change_failure_rate"]["rate"] is None
    assert r["levels"]["change_failure_rate"] == "N/A"
    assert r["deployments"] == []


def test_reports_render_for_empty_and_filled_data(fake_api):
    filled = dm.compute()
    table = dm.summary_table(filled)
    assert table.splitlines()[0] == "| 지표 | 최근 30일 | 등급(참고) |"
    assert len(table.splitlines()) == 6  # 헤더 2줄 + 지표 4줄
    assert "Deployment Frequency" in table
    assert "[run](https://example.test/3)" in dm.weekly_report(filled)

    filled["deployments"] = []
    assert "배포 기록 없음" in dm.weekly_report(filled)


def test_update_readme_replaces_only_marked_block(tmp_path, monkeypatch, fake_api):
    monkeypatch.setattr(dm, "ROOT", tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("앞부분\n<!-- DORA:START -->\n옛날 내용\n<!-- DORA:END -->\n뒷부분\n", encoding="utf-8")
    dm.update_readme(dm.compute(), "reports/weekly/x.md")
    text = readme.read_text(encoding="utf-8")
    assert text.startswith("앞부분\n<!-- DORA:START -->")
    assert text.endswith("<!-- DORA:END -->\n뒷부분\n")
    assert "옛날 내용" not in text
    assert "Change Failure Rate" in text


def test_update_readme_ignores_missing_markers_and_missing_file(tmp_path, monkeypatch, fake_api):
    monkeypatch.setattr(dm, "ROOT", tmp_path)
    result = dm.compute()
    dm.update_readme(result, "x.md")  # README 없음: 오류 없이 지나간다
    readme = tmp_path / "README.md"
    readme.write_text("마커 없음\n", encoding="utf-8")
    dm.update_readme(result, "x.md")
    assert readme.read_text(encoding="utf-8") == "마커 없음\n"
