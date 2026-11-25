"""A/B 실험 일일 수집과 분석 로직 테스트."""
import json
import sys
from datetime import date

import ab_simulation as ab
import experiment_report as report
import experiment_run as run
import pytest

EXP = run.load_experiment()
PERSONAS = run.load_personas()


def test_personas_weights_sum_to_one():
    assert sum(p["ab"]["weight"] for p in PERSONAS) == pytest.approx(1.0)


def test_simulate_day_is_deterministic_and_complete():
    a = run.simulate_day("2026-11-26", 500, PERSONAS)
    b = run.simulate_day("2026-11-26", 500, PERSONAS)
    assert a == b
    assert sum(v["exposed"] for v in a["variants"].values()) == 500
    assert sum(v["exposed"] for p in a["personas"].values() for v in p.values()) == 500
    assert a["synthetic"] is True


def test_different_days_differ():
    assert run.simulate_day("2026-11-26", 500, PERSONAS) != run.simulate_day("2026-11-27", 500, PERSONAS)


def test_assignment_uses_the_same_rule_as_the_browser():
    row = run.simulate_day("x", 300, PERSONAS)
    exp = run.flag_experiment()
    expected_control = sum(1 for i in range(300) if ab.assign(exp, f"sim-x-{i}") == "control")
    assert row["variants"]["control"]["exposed"] == expected_control


def test_upsert_replaces_same_date_and_sorts(tmp_path):
    path = tmp_path / "m.jsonl"
    run.upsert(path, {"date": "2026-11-27", "v": 1})
    run.upsert(path, {"date": "2026-11-26", "v": 1})
    run.upsert(path, {"date": "2026-11-27", "v": 2})
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert [(r["date"], r["v"]) for r in rows] == [("2026-11-26", 1), ("2026-11-27", 2)]


def test_main_records_inside_window_and_skips_outside(tmp_path, monkeypatch, capsys):
    out = tmp_path / "d.jsonl"
    monkeypatch.setattr(sys, "argv", ["x", "--date", EXP["start"], "--out", str(out)])
    assert run.main() == 0 and len(out.read_text(encoding="utf-8").splitlines()) == 1
    monkeypatch.setattr(sys, "argv", ["x", "--date", "2030-01-01", "--out", str(out)])
    assert run.main() == 0
    assert "밖이라 기록하지 않습니다" in capsys.readouterr().out
    assert len(out.read_text(encoding="utf-8").splitlines()) == 1


def test_main_dry_run_writes_all_days(tmp_path, monkeypatch):
    out = tmp_path / "dry.jsonl"
    monkeypatch.setattr(sys, "argv", ["x", "--dry-run-days", "3", "--out", str(out)])
    run.main()
    assert [json.loads(x)["date"] for x in out.read_text(encoding="utf-8").splitlines()] == ["day-01", "day-02", "day-03"]


def test_required_sample_size_matches_textbook_value():
    # 기준 10%, 상대 +20%(12%), 양측 5%, 검정력 80% 의 교과서 값은 그룹당 약 3,800명
    assert 3700 <= report.required_per_arm(0.10, 0.20, 0.05, 0.80) <= 3900


def rows_with(control, treatment, days=5):
    row = {"variants": {"control": {"exposed": control[0], "clicks": control[1]}, "treatment": {"exposed": treatment[0], "clicks": treatment[1]}},
           "personas": {p["id"]: {"control": {"exposed": 400, "clicks": 40}, "treatment": {"exposed": 400, "clicks": 40}} for p in PERSONAS}}
    return [row] * days


def test_decision_persevere_on_big_significant_lift():
    a = report.analyze(rows_with((5000, 500), (5000, 650)), EXP, PERSONAS)
    assert a["decision"] == "persevere" and a["lift"] == pytest.approx(0.30)


def test_decision_pivot_when_lift_is_small_even_if_significant():
    a = report.analyze(rows_with((50000, 5000), (50000, 5300)), EXP, PERSONAS)
    assert a["p"] < 0.05 and a["lift"] < 0.10 and a["decision"] == "pivot"
    assert "못 미침" in a["reason"]


def test_decision_pivot_when_not_significant():
    a = report.analyze(rows_with((100, 10), (100, 14), days=1), EXP, PERSONAS)
    assert a["decision"] == "pivot" and "유의하지 않음" in a["reason"]


def test_guardrail_violation_makes_persevere_conditional():
    rows = rows_with((5000, 500), (5000, 650))
    for r in rows:
        r["personas"]["p08"] = {"control": {"exposed": 400, "clicks": 80}, "treatment": {"exposed": 400, "clicks": 40}}
    a = report.analyze(rows, EXP, PERSONAS)
    assert a["decision"] == "persevere-conditional" and a["violations"] == ["윤채원"]


def test_small_segments_are_not_judged():
    rows = rows_with((5000, 500), (5000, 650), days=1)  # 세그먼트당 400노출 → 기준 300 이상이라 판정됨
    for r in rows:
        r["personas"]["p09"] = {"control": {"exposed": 100, "clicks": 50}, "treatment": {"exposed": 100, "clicks": 1}}
    a = report.analyze(rows, EXP, PERSONAS)
    seg = next(s for s in a["segments"] if s["id"] == "p09")
    assert seg["enough"] is False and seg["violation"] is False


def test_render_labels_data_as_synthetic_and_final_vs_weekly():
    a = report.analyze(rows_with((5000, 500), (5000, 650)), EXP, PERSONAS)
    weekly = report.render(a, EXP, "2026-12-01", False, "m.jsonl")
    final = report.render(a, EXP, "2026-12-10", True, "m.jsonl")
    assert "합성 데이터입니다" in weekly and "중간 값이라 확정이 아닙니다" in weekly
    assert "최종 결정" in final and "중간 값" not in final


def test_report_main_writes_file(tmp_path, monkeypatch):
    data = tmp_path / "d.jsonl"
    for day in ("day-01", "day-02"):
        run.upsert(data, run.simulate_day(day, 400, PERSONAS))
    out = tmp_path / "r" / "x.md"
    monkeypatch.setattr(sys, "argv", ["x", "--input", str(data), "--out", str(out), "--final"])
    assert report.main() == 0 and "최종 결정" in out.read_text(encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["x", "--input", str(tmp_path / "none.jsonl"), "--out", str(out)])
    assert report.main() == 1


def test_experiment_window_is_two_weeks():
    assert (date.fromisoformat(EXP["end"]) - date.fromisoformat(EXP["start"])).days + 1 == 14


def test_dry_run_render_is_marked_as_rehearsal():
    a = report.analyze(rows_with((5000, 500), (5000, 650)), EXP, PERSONAS)
    text = report.render(a, EXP, "dry", True, "m.jsonl", dryrun=True)
    assert "사전 시뮬레이션(dry-run) 결과" in text and "리허설 결과라 실제 운영 결정이 아닙니다" in text
    assert "## 현재 기준으로 내리면" in text
