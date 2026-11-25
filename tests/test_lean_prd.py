"""lean-prd 스킬(검증기와 템플릿), docs/prd, BML Cycle 1 증빙의 규격과 일관성 테스트."""
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
SCRIPT = SKILL / "scripts" / "validate_prd.py"
PRD = ROOT / "docs" / "prd"
CYCLE = ROOT / "experiments" / "cycle-1"
sys.path.insert(0, str(SKILL / "scripts"))

import validate_prd as vp  # noqa: E402

UTF8 = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def check(prd: Path) -> vp.Report:
    r = vp.Report()
    for rule in vp.BASE_RULES + vp.CUSTOM_RULES:
        rule(prd, r)
    return r


@pytest.fixture
def prd(tmp_path):
    dst = tmp_path / "prd"
    shutil.copytree(PRD, dst)
    return dst


def edit(prd: Path, name: str, old: str, new: str) -> None:
    path = prd / name
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{name} 에 '{old}' 가 없다"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# --- 스킬 구조 ---

def test_skill_frontmatter_and_size():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("---")[1]
    assert "name: lean-prd" in head and "description:" in head
    description = head.split("description:", 1)[1]
    for trigger in ("PRD", "기획서", "MVP", "린 캔버스", "아이디어 검증", "cycle"):
        assert trigger in description
    assert len(text.splitlines()) <= 500
    assert "TODO" not in text
    for needed in ("00-overview를 마지막에 쓰는 이유", "validate_prd.py", "cycle 모드", "하지 말 것"):
        assert needed in text


def test_skill_does_not_hardcode_the_product():
    assert "NotiCatch" not in (SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_reference_has_change_history():
    text = (SKILL / "references" / "team-and-tech-stack-guide.md").read_text(encoding="utf-8")
    assert text.startswith("<!--\n변경 이력") and "공개 웹 데이터 수집·파싱" in text


def test_templates_are_twelve_and_skeleton_fails_validation(tmp_path):
    templates = SKILL / "assets" / "prd-templates"
    assert sorted(p.name for p in templates.glob("*.md")) == vp.FILES
    skeleton = tmp_path / "skeleton"
    shutil.copytree(templates, skeleton)
    fails = check(skeleton).fails
    assert any("자리표시자" in f for f in fails)


# --- PRD ---

def test_repo_prd_passes_validation_and_report_is_fresh():
    r = check(PRD)
    assert r.fails == []
    out = subprocess.run([sys.executable, str(SCRIPT), str(PRD)], capture_output=True, text=True, encoding="utf-8", env=UTF8)
    assert out.returncode == 0
    body = lambda t: t.strip().splitlines()[1:]  # noqa: E731 — 첫 줄은 실행한 경로라 제외
    assert body((PRD / "VALIDATION.txt").read_text(encoding="utf-8")) == body(out.stdout)


def test_prd_has_the_official_twelve_files():
    assert sorted(p.name for p in PRD.glob("*.md") if p.name != "README.md") == vp.FILES


@pytest.mark.parametrize(
    "name, filename, old, new, expected",
    [
        ("06 임계값만 변경", "06-experiment-plan.md", "| E1 | M3 | 90% | 90% |", "| E1 | M3 | 85% | 90% |", "[threshold]"),
        ("05 이벤트 이름 변경", "05-metrics.md", "| `ics_added` | M2 |", "| `calendar_added` | M2 |", "[events]"),
        ("07 FTE 숫자 제거", "07-team.md", "| 0.4 (주 10시간) |", "| 많이 |", "[team]"),
        ("10 없는 지표 참조", "10-risks-and-pivot.md", "| T2 | M1 < 40%", "| T2 | M9 < 40%", "[trigger]"),
        ("03 구축 기간 초과", "03-solution-and-mvp.md", "추정 (1인): 8일", "추정 (1인): 12일", "[mvp-time]"),
        ("09 종료 조건만 변경", "09-milestones.md", "| 정답 코퍼스 15건 이상, 평가 스크립트 | M3 ≥ 90% | P1 |",
         "| 정답 코퍼스 15건 이상, 평가 스크립트 | M3 ≥ 85% | P1 |", "[exit]"),
    ],
)
def test_custom_rules_catch_injected_errors(prd, name, filename, old, new, expected):
    edit(prd, filename, old, new)
    assert any(f.startswith(expected) for f in check(prd).fails), name


def test_base_rules_catch_missing_file_heading_and_orphan_hypothesis(prd):
    edit(prd, "05-metrics.md", "## 3. Actionable vs Vanity", "## 3. 기타")
    edit(prd, "01-problem-and-hypotheses.md", "| H5 | 가치 |", "| H9 | 가치 |")
    (prd / "08-tech-stack.md").unlink()
    fails = " ".join(check(prd).fails)
    assert "08-tech-stack.md" in fails and "Actionable vs Vanity" in fails and "H9" in fails


def test_milestones_must_point_at_existing_pivots(prd):
    edit(prd, "09-milestones.md", "- No-Go: M1 < 40% 또는 M2 < 15% → P2", "- No-Go: M1 < 40% 또는 M2 < 15% → P9")
    assert any("P9" in f for f in check(prd).fails)


def test_ids_chain_from_hypotheses_to_milestones():
    """H# → M# → E# → MS# → P# 가 실제 문서에서 끊기지 않는다."""
    def text(name):
        return (PRD / name).read_text(encoding="utf-8")

    hyp = set(re.findall(r"^\| (H\d+) \|", text("01-problem-and-hypotheses.md"), flags=re.M))
    assert hyp == {"H1", "H2", "H3", "H4", "H5"}
    for h in hyp:
        assert h in text("05-metrics.md") and h in text("06-experiment-plan.md") and h in text("09-milestones.md")
    assert set(re.findall(r"### (MS\d)", text("09-milestones.md"))) == {"MS0", "MS1", "MS2", "MS3"}


# --- BML Cycle 1 ---

def test_cycle1_corpus_is_well_formed():
    cases = json.loads((CYCLE / "corpus.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 15 and len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["source"].startswith("https://")
        assert c["expected"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["expected"])
        assert len(c["snippet"]) < 200  # 원문 전체가 아니라 마감일 줄만 발췌


def test_cycle1_result_matches_log_and_decision_follows_preregistered_threshold():
    result = json.loads((CYCLE / "results.json").read_text(encoding="utf-8"))
    ok = sum(r["ok"] for r in result["rows"])
    log = (PRD / "11-bml-log.md").read_text(encoding="utf-8")
    assert f"{ok}/{result['n']}" in log
    assert result["threshold"] == 0.9
    # 06 의 E1 통과 기준과 측정값을 비교한 결정이 로그의 결정과 같아야 한다
    decision_is_pivot = "**Pivot (Zoom-in, P1)**" in log
    assert (result["accuracy"] < result["threshold"]) == decision_is_pivot
    assert "| E1 | M3 | 90% | 90% |" in (PRD / "06-experiment-plan.md").read_text(encoding="utf-8")


def test_cycle1_eval_runs_and_reports(tmp_path):
    out = subprocess.run([sys.executable, str(CYCLE / "run_eval.py"), "--out", str(tmp_path)],
                         capture_output=True, text=True, encoding="utf-8", env=UTF8, check=True)
    assert "/19 =" in out.stdout and (tmp_path / "results.md").is_file()


# --- 제출물 목록 ---

@pytest.mark.parametrize("rel", [
    "RETROSPECTIVE.md", "docs/skill-session.md", "docs/prd/VALIDATION.txt", "experiments/cycle-1/README.md",
    ".github/ISSUE_TEMPLATE/experiment.md", ".github/workflows/validate-prd.yml",
])
def test_deliverables_exist(rel):
    assert (ROOT / rel).is_file()
