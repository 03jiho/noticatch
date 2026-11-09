"""scripts/changed_paths.py 단위 테스트: 어떤 파일이 바뀌면 어떤 단계를 실행하는지."""

import subprocess

import changed_paths as cp
import pytest


@pytest.mark.parametrize(
    ("files", "test", "build"),
    [
        (["scripts/dora_metrics.py"], True, True),
        (["tests/test_x.py"], True, True),
        (["requirements-dev.txt"], True, True),
        (["requirements-scripts.txt"], True, True),
        (["pyproject.toml"], True, True),
        ([".github/workflows/ci.yml"], True, True),
        ([".github/actions/setup-python-env/action.yml"], True, True),
        (["dashboard/index.html"], False, True),
        (["project/backlog.yml"], False, True),
        (["README.md"], False, True),
        (["LICENSE"], False, True),
        (["docs/ci/optimization-report.md"], False, False),
        (["CONTRIBUTING.md"], False, False),
        (["reports/LATEST.md", "metrics/dora-latest.json"], False, False),
        ([".github/pull_request_template.md", ".github/CODEOWNERS"], False, False),
        (["docs/a.md", "scripts/x.py"], True, True),  # 하나라도 코드면 전체
        (["docs/a.md", "README.md"], False, True),
    ],
)
def test_decide(files, test, build):
    r = cp.decide(files)
    assert (r["test"], r["build"], r["changed"]) == (test, build, len(files))


def test_decide_without_changes_runs_nothing():
    r = cp.decide([])
    assert (r["test"], r["build"]) == (False, False)
    assert "없음" in r["reason"]


def test_decide_force_runs_everything():
    r = cp.decide(["docs/a.md"], force=True)
    assert (r["test"], r["build"]) == (True, True)


def test_requirements_pattern_does_not_match_other_files():
    assert not cp.needs_test("docs/requirements-notes.txt")  # 하위 폴더는 제외
    assert not cp.needs_test("requirements.md")
    assert cp.needs_test("requirements.txt")


def test_summary_lists_files_and_truncates():
    files = [f"docs/{i}.md" for i in range(20)]
    text = cp.summary_markdown(cp.decide(files), files)
    assert "건너뜀" in text and "외 5개" in text


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("a\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    return tmp_path


def head(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()


def test_main_with_real_git_diff_and_outputs(repo, tmp_path_factory, monkeypatch):
    base = head(repo)
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("x\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs only")
    monkeypatch.chdir(repo)
    out = tmp_path_factory.mktemp("o") / "out.txt"
    summary = out.parent / "summary.md"
    assert cp.main(["--base", base, "--head", head(repo), "--github-output", str(out), "--summary", str(summary)]) == 0
    assert out.read_text(encoding="utf-8").splitlines() == [
        "test=false", "build=false", "changed=1", "reason=문서·자동 생성 파일만 변경",
    ]
    assert "docs/a.md" in summary.read_text(encoding="utf-8")


def test_main_code_change_runs_everything(repo, tmp_path_factory, monkeypatch):
    base = head(repo)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "x.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "code")
    monkeypatch.chdir(repo)
    out = tmp_path_factory.mktemp("o") / "out.txt"
    cp.main(["--base", base, "--head", head(repo), "--github-output", str(out)])
    assert out.read_text(encoding="utf-8").startswith("test=true\nbuild=true")


@pytest.mark.parametrize("base", ["", cp.ZERO_SHA])
def test_main_without_base_runs_everything(base, tmp_path, capsys):
    out = tmp_path / "out.txt"
    cp.main(["--base", base, "--github-output", str(out)])
    assert out.read_text(encoding="utf-8").startswith("test=true\nbuild=true")
    assert "기준 커밋이 없어" in capsys.readouterr().out


def test_main_falls_back_to_full_run_when_git_fails(repo, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = tmp_path / "out.txt"
    cp.main(["--base", "deadbeef" * 5, "--head", "HEAD", "--github-output", str(out)])
    assert out.read_text(encoding="utf-8").startswith("test=true\nbuild=true")
    assert "확인하지 못해" in capsys.readouterr().out


def test_main_force_flag(tmp_path):
    out = tmp_path / "out.txt"
    cp.main(["--force", "--base", "abc", "--github-output", str(out)])
    assert "reason=수동 실행 또는 태그: 전체 실행" in out.read_text(encoding="utf-8")
