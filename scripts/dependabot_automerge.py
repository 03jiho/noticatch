"""Dependabot PR 을 자동으로 머지해도 되는지 판단하고, 조건을 만족하면 머지한다. 표준 라이브러리만 쓴다.

자동 머지 조건 (모두 만족해야 한다)
1. PR 작성자가 dependabot[bot] 이고 브랜치 이름이 dependabot/ 으로 시작한다.
2. 변경에 메이저 업데이트가 없다. (메이저는 항상 사람이 확인한다)
3. 패치 업데이트이거나, 마이너 업데이트인데 개발용(dev) 의존성 또는 GitHub Actions 이다.
   (배포되는 코드에 들어가는 마이너 업데이트는 사람이 확인한다)
4. 그 커밋의 검사(check run)가 모두 끝났고 실패가 없다.
5. 초안(draft)이 아니고, 열려 있다.

업데이트 종류는 Dependabot 이 커밋 메시지에 남기는 메타데이터에서 읽는다.
(dependabot/fetch-metadata 액션과 같은 정보다. 외부 액션 없이 직접 읽는다.)

사용 예 (Actions)
  python3 scripts/dependabot_automerge.py --pr 123            # 조건을 만족하면 머지
  python3 scripts/dependabot_automerge.py --pr 123 --dry-run  # 판단만 출력
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

BOT = "dependabot[bot]"
PASSING = {"success", "skipped", "neutral"}

_DEP_RE = re.compile(r"^- dependency-name:\s*(?P<name>.+?)\s*$")
_FIELD_RE = re.compile(r"^\s+(?P<key>dependency-type|update-type):\s*(?P<value>\S+)\s*$")


def parse_metadata(commit_message: str) -> list[dict]:
    """커밋 메시지의 `updated-dependencies:` 블록을 읽어 [{name, type, update}] 로 돌려준다."""
    deps: list[dict] = []
    in_block = False
    for line in commit_message.splitlines():
        if line.strip() == "updated-dependencies:":
            in_block = True
            continue
        if not in_block:
            continue
        if line.strip() in ("...", "---") and deps:
            break
        m = _DEP_RE.match(line)
        if m:
            deps.append({"name": m["name"], "type": "", "update": ""})
            continue
        m = _FIELD_RE.match(line)
        if m and deps:
            deps[-1]["type" if m["key"] == "dependency-type" else "update"] = m["value"]
    return deps


def ecosystem_of(head_ref: str) -> str:
    """dependabot/<생태계>/<경로>/<패키지> 브랜치 이름에서 생태계를 읽는다. (예: npm_and_yarn, github_actions)"""
    parts = head_ref.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == "dependabot" else ""


def decide(author: str, head_ref: str, deps: list[dict]) -> tuple[bool, str]:
    """(머지 여부, 이유)."""
    if author != BOT or not head_ref.startswith("dependabot/"):
        return False, f"Dependabot PR 이 아님 (작성자 {author})"
    if not deps:
        return False, "업데이트 메타데이터를 읽지 못해 사람이 확인해야 함"
    eco = ecosystem_of(head_ref)
    for d in deps:
        kind = d["update"].removeprefix("version-update:")
        if kind == "semver-major":
            return False, f"메이저 업데이트({d['name']})는 사람이 확인해야 함"
        if kind == "semver-patch":
            continue
        if kind == "semver-minor":
            if d["type"] == "direct:development" or eco == "github_actions":
                continue
            return False, f"배포 코드에 들어가는 마이너 업데이트({d['name']})는 사람이 확인해야 함"
        return False, f"업데이트 종류를 알 수 없음({d['name']}: {d['update'] or '없음'})"
    return True, f"패치/허용된 마이너 업데이트 {len(deps)}건"


def checks_ok(check_runs: list[dict]) -> tuple[bool, str]:
    """모든 검사가 끝났고 실패가 없는지 본다."""
    if not check_runs:
        return False, "검사 결과가 아직 없음"
    pending = [c["name"] for c in check_runs if c.get("status") != "completed"]
    if pending:
        return False, f"아직 진행 중인 검사: {', '.join(sorted(pending))}"
    failed = [c["name"] for c in check_runs if c.get("conclusion") not in PASSING]
    if failed:
        return False, f"통과하지 못한 검사: {', '.join(sorted(failed))}"
    return True, f"검사 {len(check_runs)}개 모두 통과"


def gh_api(path: str, *extra: str) -> str:
    return subprocess.run(
        ["gh", "api", path, *extra], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pr", type=int, required=True)
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = args.repo
    pr = json.loads(gh_api(f"repos/{repo}/pulls/{args.pr}"))
    summary: list[str] = [f"### Dependabot 자동 머지 판단 — #{args.pr}", "", f"- 제목: {pr['title']}"]

    def finish(merged: bool, reason: str) -> int:
        summary.append(f"- 결과: **{'머지함' if merged else '머지하지 않음'}** — {reason}")
        text = "\n".join(summary)
        print(text)
        path = os.environ.get("GITHUB_STEP_SUMMARY")
        if path:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
        return 0

    if pr["state"] != "open" or pr.get("draft") or pr.get("merged"):
        return finish(False, "열려 있는 일반 PR 이 아님")

    commits = json.loads(gh_api(f"repos/{repo}/pulls/{args.pr}/commits"))
    message = commits[0]["commit"]["message"] if commits else ""
    deps = parse_metadata(message)
    ok, why = decide(pr["user"]["login"], pr["head"]["ref"], deps)
    listed = ", ".join(f"{d['name']}({d['update'].removeprefix('version-update:semver-')})" for d in deps)
    summary.append(f"- 업데이트: {listed or '확인 불가'}")
    if not ok:
        return finish(False, why)

    sha = pr["head"]["sha"]
    raw = gh_api(f"repos/{repo}/commits/{sha}/check-runs", "--paginate", "--jq", ".check_runs[]")
    runs = [json.loads(line) for line in raw.splitlines() if line.strip()]
    ok, why2 = checks_ok(runs)
    if not ok:
        return finish(False, why2)

    if args.dry_run:
        return finish(False, f"{why}; {why2} (dry-run 이라 머지하지 않음)")

    try:
        # sha 를 함께 보내면 판단한 뒤에 커밋이 바뀐 경우 GitHub 이 머지를 거절한다.
        gh_api(
            f"repos/{repo}/pulls/{args.pr}/merge", "-X", "PUT",
            "-f", "merge_method=squash", "-f", f"sha={sha}", "-f", f"commit_title={pr['title']} (#{args.pr})",
        )
    except subprocess.CalledProcessError as e:
        # 다른 검사 완료 이벤트가 먼저 머지했을 수 있다.
        return finish(False, f"머지 요청이 거절됨(이미 머지되었을 수 있음): {(e.stderr or '').strip()[:200]}")
    return finish(True, f"{why}; {why2}")


if __name__ == "__main__":
    sys.exit(main())
