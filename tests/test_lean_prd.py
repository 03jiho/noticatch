"""lean-prd 스킬(검증기, 뼈대 생성, 사이클 반영)과 docs/prd 의 규격 테스트."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "lean-prd"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cycle  # noqa: E402
import scaffold_prd  # noqa: E402
import validate_prd as vp  # noqa: E402

PRD = ROOT / "docs" / "prd"
FILES = sorted(vp.REQUIRED)


def run_validator(root: Path, stage: str = "final"):
    return vp.Checker(root, stage).check()


@pytest.fixture
def prd(tmp_path):
    dst = tmp_path / "prd"
    shutil.copytree(PRD, dst)
    return dst


def edit(root: Path, name: str, old: str, new: str) -> None:
    p = root / name
    text = p.read_text(encoding="utf-8")
    assert old in text, f"{name} 에 '{old}' 가 없다"
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_skill_has_required_files_and_frontmatter():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: lean-prd\n")
    for needed in ("왜 가설을 먼저 세우고", "00-overview", "/lean-prd cycle", "/lean-prd validate"):
        assert needed in text
    for ref in ("bml-cycle.md", "prd-spec.md", "sufficiency-examples.md"):
        assert (SKILL / "references" / ref).is_file()
    assert sorted(p.name for p in (SKILL / "templates").glob("*.md")) == FILES


def test_spec_has_exactly_twelve_files_in_expected_order():
    assert len(FILES) == 12 and FILES[0] == "00-overview.md" and FILES[-1] == "11-cycle-log.md"
    assert sorted(p.name for p in PRD.glob("*.md")) == FILES


def test_repo_prd_passes_final_validation():
    assert run_validator(PRD) == []


def test_empty_skeleton_fails_with_placeholders(tmp_path):
    scaffold_prd.scaffold("테스트 아이디어", tmp_path / "p")
    errors = run_validator(tmp_path / "p", "generate")
    assert any("자리표시자" in e for e in errors)
    assert len(list((tmp_path / "p").glob("*.md"))) == 12


def test_scaffold_refuses_to_overwrite(tmp_path):
    scaffold_prd.scaffold("a", tmp_path)
    with pytest.raises(FileExistsError):
        scaffold_prd.scaffold("b", tmp_path)
    scaffold_prd.scaffold("b", tmp_path, force=True)
    assert "b" in (tmp_path / "00-overview.md").read_text(encoding="utf-8")


def test_missing_file_is_reported(prd):
    (prd / "05-experiments.md").unlink()
    assert any("05-experiments.md" in e and "파일이 없다" in e for e in run_validator(prd))


def test_extra_thirteenth_file_is_rejected(prd):
    (prd / "12-extra.md").write_text("# x\n", encoding="utf-8")
    assert any("12-extra.md" in e for e in run_validator(prd))


def test_missing_required_heading(prd):
    edit(prd, "03-metrics.md", "## 가드레일", "## 기타")
    assert any("가드레일" in e for e in run_validator(prd))


def test_hypothesis_without_metric_or_experiment_is_caught(prd):
    edit(prd, "02-hypotheses.md", "| H5 |", "| H9 |")
    errors = run_validator(prd)
    assert any("H9" in e and "지표" in e for e in errors)
    assert any("H9" in e and "실험" in e for e in errors)


def test_risk_score_must_equal_impact_times_uncertainty(prd):
    edit(prd, "02-hypotheses.md", "| 기술 | 5 | 4 | 20 |", "| 기술 | 5 | 4 | 19 |")
    assert any("위험도 19" in e for e in run_validator(prd))


def test_riskiest_hypothesis_must_have_max_score(prd):
    edit(prd, "02-hypotheses.md", "**H2 (위험도 20, H1 과 동점)**", "**H3 (위험도 12)**")
    assert any("최고점" in e for e in run_validator(prd))


def test_metric_threshold_needs_a_number(prd):
    edit(prd, "03-metrics.md", "90% 이상 | 공개 학교 게시판 공지", "높게 | 공개 학교 게시판 공지")
    assert any("M3" in e and "숫자" in e for e in run_validator(prd))


def test_every_in_feature_needs_a_hypothesis(prd):
    edit(prd, "04-mvp.md", "| 마감일 추출 | In | H2 |", "| 마감일 추출 | In | - |")
    assert any("검증 가설" in e for e in run_validator(prd))


def test_mvp_type_must_be_a_known_type(prd):
    edit(prd, "04-mvp.md", "**Concierge MVP.**", "**그냥 만든다.**")
    assert any("MVP 유형" in e for e in run_validator(prd))


def test_experiment_must_reference_existing_metric(prd):
    edit(prd, "05-experiments.md", "| E1 | H2 | M3 |", "| E1 | H2 | M99 |")
    assert any("M99" in e for e in run_validator(prd))


def test_team_rows_need_fte_milestone_and_priority(prd):
    edit(prd, "06-team.md", "| 0.4 | MS0, MS1 | 보유 |", "| 많이 | - | 나중에 |")
    errors = run_validator(prd)
    assert any("FTE" in e for e in errors) and any("MS#" in e for e in errors) and any("우선순위" in e for e in errors)


def test_pivot_rule_must_cite_an_option(prd):
    edit(prd, "06-team.md", "P# 를 실행한다(MS0 미달이면 P1, MS1 미달이면 P2)", "알아서 한다(상황에 맞게 다시 논의해서 정한다)")
    assert any("Pivot 의사결정 규칙" in e for e in run_validator(prd))


def test_tech_stack_needs_all_six_columns_filled(prd):
    edit(prd, "07-tech-stack.md", "| Playwright | 0원 |", "| | 0원 |")
    assert any("대안" in e and "비어" in e for e in run_validator(prd))


def test_tech_stack_cost_and_switch_condition_need_numbers(prd):
    edit(prd, "07-tech-stack.md", "| 0원 | 사용자가 100명을 넘거나 동시 쓰기 충돌이 월 3회 이상 나면 전환 |", "| 무료 | 사용자가 많아지면 전환 |")
    errors = run_validator(prd)
    assert any("월 비용" in e for e in errors) and any("전환 조건" in e for e in errors)


def test_all_four_milestones_required_with_numeric_exit_and_valid_pivot(prd):
    edit(prd, "08-milestones.md", "| MS3 |", "| MS7 |")
    assert any("MS3" in e for e in run_validator(prd))


def test_milestone_no_go_must_point_to_existing_pivot(prd):
    edit(prd, "08-milestones.md", "| MS1 로 진행 | P1 |", "| MS1 로 진행 | P9 |")
    assert any("P9" in e for e in run_validator(prd))


def test_pivot_budget_section_needs_numbers(prd):
    text = (prd / "09-pivot-safeguards.md").read_text(encoding="utf-8")
    text = re.sub(r"(## 예산·시간 상한\n).*?(?=\n## |\Z)", r"\1\n충분히 쓰고 안 되면 접는다.\n", text, flags=re.S)
    (prd / "09-pivot-safeguards.md").write_text(text, encoding="utf-8")
    assert any("예산·시간 상한" in e for e in run_validator(prd))


def test_overview_must_star_the_riskiest_and_list_all_hypotheses(prd):
    edit(prd, "00-overview.md", "★ ", "")
    assert any("★" in e for e in run_validator(prd))


def test_final_stage_requires_a_cycle_and_decision(prd):
    (prd / "11-cycle-log.md").write_text(
        "# 11\n\n## BML 사이클 기록\n\n아직 실행한 사이클이 없습니다.\n\n## 회고\n\n아직 없음.\n", encoding="utf-8")
    edit(prd, "00-overview.md", "**Pivot** (P1)", "보류")
    final = run_validator(prd, "final")
    assert any("Cycle" in e for e in final) and any("결정" in e for e in final)
    assert run_validator(prd, "generate") == []


def test_cycle_block_needs_numbers_and_decision(prd):
    text = (prd / "11-cycle-log.md").read_text(encoding="utf-8")
    text = re.sub(r"\*\*Pivot\*\*", "보류", text)
    (prd / "11-cycle-log.md").write_text(text, encoding="utf-8")
    assert any("Pivot/Persevere" in e for e in run_validator(prd))


def reset_to_pre_cycle(root: Path) -> None:
    for name, heading in (("09-pivot-safeguards.md", "실행된 Pivot"), ("02-hypotheses.md", "검증 상태")):
        text = (root / name).read_text(encoding="utf-8")
        (root / name).write_text(re.sub(rf"\n## {heading}\n.*?(?=\n## |\Z)", "", text, flags=re.S), encoding="utf-8")
    (root / "11-cycle-log.md").write_text("# 11\n\n## BML 사이클 기록\n\n아직 실행한 사이클이 없습니다.\n\n## 회고\n\n아직 없음.\n", encoding="utf-8")
    text = (root / "00-overview.md").read_text(encoding="utf-8")
    (root / "00-overview.md").write_text(re.sub(r"^- 최근 결정:.*$", "- 최근 결정: 아직 없음", text, flags=re.M), encoding="utf-8")


def cycle_args(decision="persevere", pivot=None):
    argv = ["--hypothesis", "H2", "--experiment", "E1", "--measured", "19건 중 18건 = 94.7%", "--decision", decision,
            "--reason", "기준 90% 를 넘었다", "--learned", "형식 결함 2건만 남았다", "--retro-good", "기준을 먼저 고정했다 " * 3,
            "--retro-bad", "표본이 작았다 " * 3, "--retro-next", "새 공지 20건으로 다시 잰다 " * 3]
    if pivot:
        argv += ["--pivot", pivot]
    return argv


def run_cycle(root: Path, argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    for name in ("hypothesis", "experiment", "measured", "decision", "pivot", "reason", "learned", "retro-good", "retro-bad", "retro-next", "date"):
        ap.add_argument(f"--{name}")
    ns = ap.parse_args(argv)
    ns.retro_good, ns.retro_bad, ns.retro_next = ns.retro_good, ns.retro_bad, ns.retro_next
    return cycle.apply(root, ns)


def test_cycle_persevere_updates_all_files_and_validates(prd):
    reset_to_pre_cycle(prd)
    assert run_cycle(prd, cycle_args("persevere")) == 0
    assert "### Cycle 1" in (prd / "11-cycle-log.md").read_text(encoding="utf-8")
    assert "H2: 지지됨" in (prd / "02-hypotheses.md").read_text(encoding="utf-8")
    assert "**Persevere**" in (prd / "00-overview.md").read_text(encoding="utf-8")
    assert "실행된 Pivot" not in (prd / "09-pivot-safeguards.md").read_text(encoding="utf-8")


def test_cycle_pivot_records_the_option_and_second_cycle_increments(prd):
    reset_to_pre_cycle(prd)
    assert run_cycle(prd, cycle_args("pivot", "P1")) == 0
    assert "실행된 Pivot" in (prd / "09-pivot-safeguards.md").read_text(encoding="utf-8")
    assert run_cycle(prd, cycle_args("persevere")) == 0
    log = (prd / "11-cycle-log.md").read_text(encoding="utf-8")
    assert "### Cycle 1" in log and "### Cycle 2" in log
    hyp = (prd / "02-hypotheses.md").read_text(encoding="utf-8")
    assert hyp.count("- H2:") == 1  # 같은 가설의 상태 줄은 갱신되고 중복되지 않는다


def test_cycle_pivot_requires_option(prd):
    reset_to_pre_cycle(prd)
    with pytest.raises(SystemExit):
        run_cycle(prd, cycle_args("pivot"))


UTF8 = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def test_cli_validator_exit_codes(tmp_path):
    ok = subprocess.run([sys.executable, str(SCRIPTS / "validate_prd.py"), str(PRD)], capture_output=True, text=True, encoding="utf-8", env=UTF8)
    assert ok.returncode == 0 and "통과" in ok.stdout
    scaffold_prd.scaffold("x", tmp_path / "p")
    bad = subprocess.run([sys.executable, str(SCRIPTS / "validate_prd.py"), str(tmp_path / "p")], capture_output=True, text=True, encoding="utf-8", env=UTF8)
    assert bad.returncode == 1 and "검증 실패" in bad.stdout


# --- BML Cycle 1 증거 ---
CYCLE = ROOT / "experiments" / "bml-cycle-1"


def test_cycle1_corpus_is_real_and_well_formed():
    cases = json.loads((CYCLE / "corpus.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 15
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["source"].startswith("https://")
        assert c["expected"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["expected"])
        assert len(c["snippet"]) < 200  # 원문 전체가 아니라 마감일 줄만 발췌


def test_cycle1_recorded_result_matches_the_cycle_log():
    result = json.loads((CYCLE / "results.json").read_text(encoding="utf-8"))
    assert result["n"] == 19 and result["threshold"] == 0.9
    log = (PRD / "11-cycle-log.md").read_text(encoding="utf-8")
    ok = sum(r["ok"] for r in result["rows"])
    assert f"{ok}건 일치" in log or f"{result['n']}건 중 {ok}건" in log
    assert (result["accuracy"] >= result["threshold"]) == ("**Persevere**" in log)


def test_cycle1_eval_is_deterministic_and_runs(tmp_path):
    out = subprocess.run([sys.executable, str(CYCLE / "run_eval.py"), "--out", str(tmp_path)], capture_output=True, text=True, encoding="utf-8", env=UTF8, check=True)
    assert "/19 =" in out.stdout
    assert (tmp_path / "results.md").is_file()
