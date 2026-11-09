import dependabot_automerge as dm
import pytest


def commit(*deps: tuple[str, str, str]) -> str:
    body = "\n".join(
        f"- dependency-name: {n}\n  dependency-type: {t}\n  update-type: version-update:semver-{u}" for n, t, u in deps
    )
    return f"Bump things\n\nBumps stuff.\n\n---\nupdated-dependencies:\n{body}\n...\n\nSigned-off-by: dependabot[bot] <support@github.com>"


def test_parse_metadata_reads_every_dependency():
    deps = dm.parse_metadata(commit(("eslint", "direct:development", "minor"), ("left-pad", "indirect", "patch")))
    assert deps == [
        {"name": "eslint", "type": "direct:development", "update": "version-update:semver-minor"},
        {"name": "left-pad", "type": "indirect", "update": "version-update:semver-patch"},
    ]


def test_parse_metadata_without_block_is_empty():
    assert dm.parse_metadata("fix: 그냥 커밋") == []


def test_ecosystem_of_branch():
    assert dm.ecosystem_of("dependabot/github_actions/actions/checkout-5") == "github_actions"
    assert dm.ecosystem_of("dependabot/npm_and_yarn/packages/x/eslint-9.1.0") == "npm_and_yarn"
    assert dm.ecosystem_of("feat/something") == ""


NPM = "dependabot/npm_and_yarn/packages/noticatch-keywords/dev-abc"
ACTIONS = "dependabot/github_actions/actions/checkout-5"


@pytest.mark.parametrize(
    ("ref", "deps", "expected"),
    [
        (NPM, [("a", "direct:production", "patch")], True),
        (NPM, [("a", "direct:development", "minor")], True),
        (NPM, [("a", "direct:development", "minor"), ("b", "indirect", "patch")], True),
        (ACTIONS, [("actions/checkout", "direct:production", "minor")], True),
        (NPM, [("a", "direct:production", "minor")], False),   # 배포 코드의 마이너는 사람이 본다
        (NPM, [("a", "direct:development", "major")], False),
        (ACTIONS, [("actions/checkout", "direct:production", "major")], False),
        (NPM, [("a", "direct:development", "patch"), ("b", "direct:production", "major")], False),  # 하나라도 메이저면 전부 보류
        ("dependabot/docker/node-23", [("node", "direct:production", "minor")], False),
    ],
)
def test_decide_by_update_type(ref, deps, expected):
    parsed = dm.parse_metadata(commit(*deps))
    ok, reason = dm.decide("dependabot[bot]", ref, parsed)
    assert ok is expected, reason


def test_decide_rejects_non_dependabot_author_even_with_matching_branch():
    parsed = dm.parse_metadata(commit(("a", "direct:development", "patch")))
    assert dm.decide("03jiho", NPM, parsed)[0] is False
    assert dm.decide("dependabot[bot]", "feat/x", parsed)[0] is False


def test_decide_rejects_missing_or_unknown_metadata():
    assert dm.decide("dependabot[bot]", NPM, [])[0] is False
    unknown = [{"name": "a", "type": "direct:development", "update": ""}]
    assert dm.decide("dependabot[bot]", NPM, unknown)[0] is False


def run(name: str, status: str = "completed", conclusion: str | None = "success") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion}


def test_checks_ok_requires_all_completed_and_passing():
    assert dm.checks_ok([run("a"), run("b", conclusion="skipped")])[0] is True
    assert dm.checks_ok([])[0] is False
    ok, why = dm.checks_ok([run("a"), run("b", status="in_progress", conclusion=None)])
    assert ok is False and "b" in why
    ok, why = dm.checks_ok([run("a"), run("lint", conclusion="failure")])
    assert ok is False and "lint" in why
    assert dm.checks_ok([run("a", conclusion="cancelled")])[0] is False
