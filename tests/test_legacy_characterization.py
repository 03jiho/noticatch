"""레거시 스크립트의 main() 흐름을 고정하는 특성화(characterization) 테스트.

리팩토링 전에 '지금 동작'을 테스트로 먼저 못 박아 두고, 외부 호출(gh, git, 네트워크)은 가짜로 바꿔 끼운다.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import build_pages_site as bps
import canary_rollout as canary
import dependabot_automerge as dm
import pytest

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------ build_pages_site.main
@pytest.fixture
def site_workdir(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "dashboard", tmp_path / "dashboard")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["build_pages_site.py", *argv])
    return bps.main()


def test_main_without_previews_copies_dashboard_and_writes_nojekyll(site_workdir, monkeypatch, capsys):
    assert run_main(monkeypatch, "--repo", "o/r") == 0
    assert (site_workdir / "_site" / "index.html").is_file()
    assert (site_workdir / "_site" / ".nojekyll").is_file()
    assert "프리뷰 0개" in capsys.readouterr().out


def fake_pr(number, title="t", draft=False, repo="o/r"):
    return {"number": number, "title": title, "state": "open", "draft": draft, "head": {"sha": f"{number}" * 40, "repo": {"full_name": repo}}}


def patch_github(monkeypatch, prs, page, fail_fetch=()):
    files = {pr["number"]: [{"filename": "dashboard/index.html"}] for pr in prs}

    def gh_json(path):
        if path.endswith("per_page=100") and "/files" not in path:
            return prs
        return files[int(path.split("/pulls/")[1].split("/")[0])]

    def run(*cmd, cwd=None):
        if cmd[:2] == ("git", "fetch"):
            number = int(cmd[-1].split("/")[2])
            if number in fail_fetch:
                raise subprocess.CalledProcessError(1, cmd, stderr="boom")
            return ""
        if cmd[:2] == ("git", "rev-parse"):
            return "abc123\n"
        raise AssertionError(cmd)

    def export(sha, dest):
        dest.mkdir(parents=True)
        if page is not None:
            (dest / "index.html").write_text(page, encoding="utf-8")

    monkeypatch.setattr(bps, "gh_json", gh_json)
    monkeypatch.setattr(bps, "run", run)
    monkeypatch.setattr(bps, "export_dashboard", export)


GOOD_PAGE = "<html><body><h1>PR</h1></body></html>"


def test_main_builds_preview_with_banner_and_manifest(site_workdir, monkeypatch, capsys):
    patch_github(monkeypatch, [fake_pr(7, "새 차트")], GOOD_PAGE)
    assert run_main(monkeypatch, "--repo", "o/r", "--previews", "--manifest", "m.json") == 0
    page = (site_workdir / "_site" / "pr-preview" / "pr-7" / "index.html").read_text(encoding="utf-8")
    assert "PR #7 프리뷰" in page
    assert json.loads((site_workdir / "m.json").read_text(encoding="utf-8"))[0]["number"] == 7
    assert "PR #7" in (site_workdir / "_site" / "pr-preview" / "index.html").read_text(encoding="utf-8")
    assert "프리뷰 1개" in capsys.readouterr().out


def test_main_skips_preview_when_fetch_fails(site_workdir, monkeypatch, capsys):
    patch_github(monkeypatch, [fake_pr(8)], GOOD_PAGE, fail_fetch={8})
    run_main(monkeypatch, "--repo", "o/r", "--previews")
    assert "건너뜁니다" in capsys.readouterr().err
    assert not (site_workdir / "_site" / "pr-preview" / "pr-8").exists()


def test_main_skips_preview_without_index(site_workdir, monkeypatch, capsys):
    patch_github(monkeypatch, [fake_pr(9)], None)
    run_main(monkeypatch, "--repo", "o/r", "--previews")
    assert "index.html 이 없어" in capsys.readouterr().err
    assert not (site_workdir / "_site" / "pr-preview" / "pr-9").exists()


def test_main_skips_preview_with_absolute_links(site_workdir, monkeypatch, capsys):
    patch_github(monkeypatch, [fake_pr(10)], '<html><body><a href="/x">x</a></body></html>')
    run_main(monkeypatch, "--repo", "o/r", "--previews")
    assert "깨질 절대 경로" in capsys.readouterr().err


def test_gh_json_parses_one_object_per_line(monkeypatch):
    monkeypatch.setattr(bps, "run", lambda *a, **k: '{"a": 1}\n\n{"a": 2}\n')
    assert bps.gh_json("x") == [{"a": 1}, {"a": 2}]


def test_run_returns_stdout():
    assert bps.run(sys.executable, "-c", "print('hi')").strip() == "hi"


# ------------------------------------------------------------ dependabot_automerge.main
BOT_PR = {"title": "Bump eslint", "state": "open", "draft": False, "merged": False, "user": {"login": "dependabot[bot]"},
          "head": {"ref": "dependabot/npm_and_yarn/packages/noticatch-keywords/eslint-9", "sha": "deadbeef"}}
COMMIT_MSG = "Bump\n\n---\nupdated-dependencies:\n- dependency-name: eslint\n  dependency-type: direct:development\n  update-type: version-update:semver-patch\n...\n"


def patch_gh_api(monkeypatch, pr, runs, merge_error=False):
    calls = []

    def gh_api(path, *extra):
        calls.append((path, extra))
        if path.endswith("/commits"):
            return json.dumps([{"commit": {"message": COMMIT_MSG}}])
        if "/check-runs" in path:
            return "\n".join(json.dumps(r) for r in runs)
        if path.endswith("/merge"):
            if merge_error:
                raise subprocess.CalledProcessError(1, "gh", stderr="not mergeable")
            return "{}"
        return json.dumps(pr)

    monkeypatch.setattr(dm, "gh_api", gh_api)
    return calls


def run_dm(monkeypatch, *extra):
    monkeypatch.setattr(sys, "argv", ["dependabot_automerge.py", "--pr", "5", "--repo", "o/r", *extra])
    return dm.main()


GREEN = [{"name": "test", "status": "completed", "conclusion": "success"}]


def test_dependabot_merges_when_rules_and_checks_pass(monkeypatch, capsys, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    calls = patch_gh_api(monkeypatch, BOT_PR, GREEN)
    assert run_dm(monkeypatch) == 0
    assert any(c[0].endswith("/merge") for c in calls)
    assert "머지함" in summary.read_text(encoding="utf-8")


def test_dependabot_dry_run_does_not_merge(monkeypatch):
    calls = patch_gh_api(monkeypatch, BOT_PR, GREEN)
    run_dm(monkeypatch, "--dry-run")
    assert not any(c[0].endswith("/merge") for c in calls)


def test_dependabot_waits_for_pending_checks(monkeypatch, capsys):
    patch_gh_api(monkeypatch, BOT_PR, [{"name": "test", "status": "in_progress"}])
    run_dm(monkeypatch)
    assert "진행 중" in capsys.readouterr().out


def test_dependabot_ignores_closed_pr(monkeypatch, capsys):
    patch_gh_api(monkeypatch, {**BOT_PR, "state": "closed"}, GREEN)
    run_dm(monkeypatch)
    assert "일반 PR 이 아님" in capsys.readouterr().out


def test_dependabot_reports_rejected_merge(monkeypatch, capsys):
    patch_gh_api(monkeypatch, BOT_PR, GREEN, merge_error=True)
    run_dm(monkeypatch)
    assert "거절됨" in capsys.readouterr().out


def test_dependabot_holds_major_updates(monkeypatch, capsys):
    monkeypatch.setattr(dm, "parse_metadata", lambda m: [{"name": "x", "type": "direct:production", "update": "version-update:semver-major"}])
    patch_gh_api(monkeypatch, BOT_PR, GREEN)
    run_dm(monkeypatch)
    assert "메이저" in capsys.readouterr().out


def test_dependabot_gh_api_wraps_subprocess(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, stdout="ok"))
    assert dm.gh_api("repos/x") == "ok"


# ------------------------------------------------------------ canary_rollout
def test_http_probe_counts_errors_and_measures_latency(monkeypatch):
    class Resp:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b""

    answers = iter([Resp(200), Resp(500), OSError("down"), Resp(200)])

    def fake_urlopen(url, timeout):
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(canary.urllib.request, "urlopen", fake_urlopen)
    m = canary.http_probe("http://x", requests=4)(1, 1)
    assert m["error_rate"] == 0.5
    assert m["p95_ms"] >= 0


def test_canary_main_writes_log_for_all_scenarios(monkeypatch, tmp_path, capsys):
    out = tmp_path / "log.md"
    monkeypatch.setattr(sys, "argv", ["canary_rollout.py", "--out", str(out)])
    assert canary.main() == 0
    text = out.read_text(encoding="utf-8")
    assert "healthy: 100% 승격 완료" in text and "error-spike: 롤백됨" in text and "slow: 롤백됨" in text


def test_canary_main_with_url_fails_when_rolled_back(monkeypatch):
    monkeypatch.setattr(canary, "http_probe", lambda url: (lambda stage, check: {"error_rate": 1.0, "p95_ms": 10}))
    monkeypatch.setattr(sys, "argv", ["canary_rollout.py", "--url", "http://x"])
    assert canary.main() == 1


def test_canary_main_with_healthy_url_succeeds(monkeypatch):
    monkeypatch.setattr(canary, "http_probe", lambda url: (lambda stage, check: {"error_rate": 0.0, "p95_ms": 10}))
    monkeypatch.setattr(sys, "argv", ["canary_rollout.py", "--url", "http://x"])
    assert canary.main() == 0
