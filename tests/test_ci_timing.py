"""scripts/ci_timing.py 단위 테스트: 시간 차이, 중앙값, 개선율, 작업 집계. API 는 부르지 않는다."""

import ci_timing as ct
import pytest


def at(sec):
    """기준 시각(12:00:00) + sec 초 의 ISO 문자열."""
    return f"2026-11-09T12:{sec // 60:02d}:{sec % 60:02d}Z"


def step(name, start, end, conclusion="success"):
    return {"name": name, "started_at": at(start), "completed_at": at(end), "conclusion": conclusion}


def bench_job(os_name, case, n, cold, restore, warm, conclusion="success"):
    return {"name": f"Bench ({os_name}, {case}, #{n})", "conclusion": conclusion, "steps": [
        step("Install without cache", 0, cold), step("Restore pip cache", cold, cold + restore),
        step("Install with restored cache", cold + restore, cold + restore + warm)]}


def job(name, start, end, conclusion="success"):
    return {"name": name, "started_at": at(start), "completed_at": at(end), "conclusion": conclusion}


def test_seconds_and_missing_values():
    assert ct.seconds(at(0), at(90)) == 90
    assert ct.seconds(None, at(1)) is None
    assert ct.seconds(at(1), None) is None


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [(10, 6, 40.0), (10, 10, 0.0), (10, 12, -20.0), (0, 5, None), (None, 5, None), (8, None, None), (3, 2, 33.3)],
)
def test_improvement(before, after, expected):
    assert ct.improvement(before, after) == expected


def test_median():
    assert ct.median([]) is None
    assert ct.median([9, 7, 8]) == 8
    assert ct.median([1, 2]) == 1.5


def test_step_seconds_requires_success():
    j = {"steps": [step("a", 0, 5), step("b", 5, 9, conclusion="failure")]}
    assert ct.step_seconds(j, "a") == 5
    assert ct.step_seconds(j, "b") is None
    assert ct.step_seconds(j, "missing") is None


def test_bench_samples_skips_failed_and_unrelated_jobs():
    jobs = [bench_job("ubuntu-latest", "dev", 1, 10, 2, 3), bench_job("ubuntu-latest", "dev", 2, 10, 2, 3, "failure"),
            {"name": "Report", "conclusion": "success", "steps": []}]
    samples = ct.bench_samples(jobs)
    assert len(samples) == 1
    assert samples[0] == {"os": "ubuntu-latest", "case": "dev", "n": 1, "cold": 10, "restore": 2,
                          "warm_install": 3, "warm": 5}


def test_summarize_bench_uses_median_per_group():
    jobs = [bench_job("windows-latest", "scripts", n, cold, 4, 6)
            for n, cold in [(1, 30), (2, 40), (3, 100)]]  # 중앙값 40, 이상치 100 은 영향이 작다
    jobs.append(bench_job("ubuntu-latest", "scripts", 1, 8, 2, 2))
    rows = ct.summarize_bench(ct.bench_samples(jobs))
    assert [(r["os"], r["case"]) for r in rows] == [("ubuntu-latest", "scripts"), ("windows-latest", "scripts")]
    win = rows[1]
    assert (win["cold"], win["warm"], win["saved"], win["improvement_pct"], win["samples"]) == (40, 10, 30, 75.0, 3)
    assert rows[0]["improvement_pct"] == 50.0


def test_render_bench_shows_negative_improvement():
    rows = ct.summarize_bench(ct.bench_samples([bench_job("ubuntu-latest", "dev", 1, 2, 2, 2)]))
    text = ct.render_bench(rows)
    assert "-100.0%" in text
    assert "| ubuntu-latest | dev | 1 | 2.0 | 2.0 | 2.0 | 4.0 | -2.0 | -100.0% |" in text


@pytest.mark.parametrize(("name", "bucket"), [
    ("Lint (ruff)", "ubuntu"), ("Build bundle", "ubuntu"), ("test-pr / Test (windows-latest, py3.12)", "windows"),
    ("Test (macos-latest, py3.13)", "macos"), ("Test (ubuntu-latest, py3.11)", "ubuntu")])
def test_os_bucket(name, bucket):
    assert ct.os_bucket(name) == bucket


def test_run_stats_counts_ran_skipped_and_weights_os():
    jobs = [job("Detect changes", 0, 5), job("Lint (ruff)", 5, 15),
            job("Test (windows-latest, py3.12)", 15, 45), job("Test (macos-latest, py3.12)", 15, 35),
            job("Deploy", 0, 0, "skipped")]
    s = ct.run_stats(jobs)
    assert (s["jobs_total"], s["jobs_ran"], s["jobs_skipped"]) == (5, 4, 1)
    assert s["wall"] == 45  # 0초 → 45초
    assert s["by_os"] == {"ubuntu": 15.0, "windows": 30.0, "macos": 20.0}
    assert s["job_seconds"] == 65.0
    assert s["weighted_seconds"] == 15 * 1 + 30 * 2 + 20 * 10


def test_run_stats_with_nothing_run():
    s = ct.run_stats([job("Lint (ruff)", 0, 0, "skipped")])
    assert (s["jobs_ran"], s["wall"], s["job_seconds"]) == (0, None, 0)


def test_compare_runs_and_render():
    before = ct.run_stats([job("Lint (ruff)", 0, 10), job("Test (macos-latest, py3.12)", 10, 40)])
    after = ct.run_stats([job("Detect changes", 0, 5), job("Lint (ruff)", 0, 0, "skipped"),
                          job("Test (macos-latest, py3.12)", 0, 0, "skipped")])
    c = ct.compare_runs(before, after)
    assert c["wall_pct"] == 87.5      # 40초 → 5초
    assert c["job_seconds_pct"] == 87.5
    assert c["jobs_ran_before"] == 2 and c["jobs_ran_after"] == 1
    text = ct.render_pipeline([{"name": "문서만 바뀐 PR", "before_id": 1, "after_id": 2, "before": before, "after": after}])
    assert "#### 문서만 바뀐 PR" in text and "+87.5%" in text and "run 1" in text and "run 2" in text


def test_cli_markdown_and_json_outputs(tmp_path, monkeypatch):
    jobs = [bench_job("ubuntu-latest", "dev", 1, 10, 2, 3)]
    monkeypatch.setattr(ct, "fetch_jobs", lambda run_id: jobs)
    md, js = tmp_path / "summary.md", tmp_path / "bench.json"
    md.write_text("앞의 내용\n", encoding="utf-8")
    assert ct.main(["bench", "--run", "1", "--markdown", str(md), "--json", str(js)]) == 0
    text = md.read_text(encoding="utf-8")
    assert text.startswith("앞의 내용\n") and "캐시 효과" in text  # 덧붙인다
    assert '"improvement_pct": 50.0' in js.read_text(encoding="utf-8")


def test_cli_pipeline_pairs(tmp_path, monkeypatch):
    by_run = {1: [job("Lint (ruff)", 0, 10)], 2: [job("Lint (ruff)", 0, 5)]}
    monkeypatch.setattr(ct, "fetch_jobs", lambda run_id: by_run[run_id])
    js = tmp_path / "p.json"
    ct.main(["pipeline", "--pair", "코드 변경 PR|1|2", "--json", str(js)])
    assert '"wall_pct": 50.0' in js.read_text(encoding="utf-8")
