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
