"""저장소 자체가 약속한 구조를 지키는지 검사한다: 백로그 데이터, 필수 문서, 워크플로우, README 마커."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


def load(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def labels():
    return load("project/labels.yml")


@pytest.fixture(scope="module")
def backlog():
    return load("project/backlog.yml")


def test_labels_are_unique_and_have_hex_colors(labels):
    names = [lb["name"] for lb in labels["labels"]]
    assert len(names) == len(set(names))
    for lb in labels["labels"]:
        assert len(lb["color"]) == 6
        int(lb["color"], 16)


def test_backlog_issues_use_defined_labels_and_milestones(labels, backlog):
    defined = {lb["name"] for lb in labels["labels"]}
    milestones = {m["title"] for m in backlog["milestones"]}
    titles = [i["title"] for i in backlog["issues"]]
    assert len(titles) == len(set(titles)), "이슈 제목이 중복됨"
    for i in backlog["issues"]:
        assert set(i.get("labels", [])) <= defined, f"정의되지 않은 라벨: {i['title']}"
        if i.get("milestone"):
            assert i["milestone"] in milestones, f"없는 마일스톤: {i['title']}"


def test_every_backlog_issue_has_one_size_and_done_criteria(backlog):
    for i in backlog["issues"]:
        sizes = [x for x in i.get("labels", []) if x.startswith("size:")]
        assert len(sizes) == 1, f"size 라벨은 정확히 1개: {i['title']}"
        assert "완료 조건" in i["body"], f"완료 조건 누락: {i['title']}"


def test_milestones_have_ordered_periods(backlog):
    for m in backlog["milestones"]:
        assert str(m["start"]) < str(m["due"]), m["title"]


@pytest.mark.parametrize("name", ["LICENSE", "README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"])
def test_oss_basics_exist_and_are_not_empty(name):
    assert (ROOT / name).read_text(encoding="utf-8").strip()


def test_license_is_mit():
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")


@pytest.mark.parametrize("tag", ["DORA", "SPRINT"])
def test_readme_has_balanced_auto_update_markers(tag):
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert text.count(f"<!-- {tag}:START -->") == 1
    assert text.count(f"<!-- {tag}:END -->") == 1
    assert text.index(f"<!-- {tag}:START -->") < text.index(f"<!-- {tag}:END -->")


def test_workflows_exist():
    assert WORKFLOWS, ".github/workflows 에 워크플로우가 있어야 한다"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_workflow_is_valid_and_least_privilege(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc.get("name"), "name 이 필요하다"
    # YAML 1.1 에서는 키 on 이 True 로 읽힌다.
    assert "on" in doc or True in doc, "트리거(on)가 필요하다"
    assert doc.get("jobs"), "jobs 가 필요하다"
    assert "permissions" in doc or all("permissions" in j for j in doc["jobs"].values()), \
        "권한은 최소로 명시해야 한다(permissions)"
    triggers = doc.get("on", doc.get(True))
    names = triggers if isinstance(triggers, list | dict) else [triggers]
    assert "pull_request_target" not in names, "포크 PR 에 비밀값이 노출될 수 있어 쓰지 않는다"


def local_uses(doc) -> list[str]:
    """워크플로우 안의 `uses: ./...` 참조(Composite Action, Reusable Workflow)를 모은다."""
    found = []
    for job in doc["jobs"].values():
        if str(job.get("uses", "")).startswith("./"):
            found.append(job["uses"])
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("./"):
                found.append(step["uses"])
    return found


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_local_action_and_workflow_references_exist(path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for ref in local_uses(doc):
        target = ROOT / ref.removeprefix("./")
        assert target.exists() and (target.is_file() or (target / "action.yml").is_file()), f"{path.name}: {ref}"


def test_composite_actions_are_valid():
    actions = sorted((ROOT / ".github" / "actions").glob("*/action.yml"))
    assert actions, "Composite Action 이 있어야 한다"
    for a in actions:
        doc = yaml.safe_load(a.read_text(encoding="utf-8"))
        assert doc["runs"]["using"] == "composite", a
        assert doc.get("name") and doc.get("description"), a
        for step in doc["runs"]["steps"]:
            if "run" in step:
                assert step.get("shell"), f"composite 의 run 단계에는 shell 이 필요하다: {a}"


def test_reusable_workflow_is_callable_and_used():
    reusable = yaml.safe_load((ROOT / ".github/workflows/python-tests.yml").read_text(encoding="utf-8"))
    triggers = reusable.get("on", reusable.get(True))
    assert "workflow_call" in triggers and "matrix" in triggers["workflow_call"]["inputs"]
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    callers = [name for name, j in ci["jobs"].items() if j.get("uses") == "./.github/workflows/python-tests.yml"]
    assert len(callers) >= 2, "PR 용과 전체 matrix 용으로 재사용되어야 한다"


def test_setup_steps_are_not_duplicated_in_workflows():
    """setup-python 을 직접 쓰는 곳은 Composite Action 과 벤치마크(캐시 없는 기준 측정이 목적)뿐이어야 한다."""
    allowed = {"cache-benchmark.yml"}
    for path in WORKFLOWS:
        if path.name in allowed:
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        used = [s.get("uses", "") for j in doc["jobs"].values() for s in j.get("steps", [])]
        assert not any(u.startswith("actions/setup-python") for u in used), f"{path.name} 이 setup-python 을 직접 쓴다"


def test_deploy_is_limited_to_push_or_manual_runs():
    ci = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    condition = ci["jobs"]["deploy"]["if"]
    assert "github.event_name == 'push'" in condition and "pull_request" not in condition
    assert ci["jobs"]["deploy"]["needs"] == "build"


def test_benchmark_job_name_matches_the_timing_parser():
    """잡 이름의 ` #` 이 YAML 주석으로 읽혀 이름이 잘리면 ci_timing 이 샘플을 하나도 못 찾는다."""
    import re

    import ci_timing

    doc = yaml.safe_load((ROOT / ".github/workflows/cache-benchmark.yml").read_text(encoding="utf-8"))
    template = doc["jobs"]["bench"]["name"]
    name = re.sub(r"\$\{\{\s*matrix\.(\w+)\s*\}\}", lambda m: {"os": "ubuntu-latest", "case": "dev", "n": "2"}[m[1]], template)
    match = ci_timing.BENCH_JOB.fullmatch(name)
    assert match, f"집계 정규식과 맞지 않는 잡 이름: {name!r}"
    assert (match["os"], match["case"], match["n"]) == ("ubuntu-latest", "dev", "2")


def test_benchmark_step_names_match_the_timing_parser():
    doc = yaml.safe_load((ROOT / ".github/workflows/cache-benchmark.yml").read_text(encoding="utf-8"))
    names = {s.get("name") for s in doc["jobs"]["bench"]["steps"]}
    assert {"Install without cache", "Restore pip cache", "Install with restored cache"} <= names
