"""변경된 파일 목록으로 CI 에서 어떤 단계를 실행할지 결정한다. 표준 라이브러리만 쓴다.

판단 기준
- test  : 코드·테스트·의존성·CI 설정이 바뀌었다 → lint 와 pytest 가 필요하다.
- build : test 가 필요하거나, 배포 번들에 들어가는 파일(dashboard, project, LICENSE, README.md)이 바뀌었다.
- 그 밖의 파일(docs/, reports/, metrics/ 등)만 바뀌면 둘 다 false 라서 무거운 단계를 건너뛴다.

안전한 쪽으로 판단하는 경우(둘 다 true): --force, 비교 기준 커밋이 없을 때(새 브랜치·태그 push),
git diff 가 실패했을 때.

사용 예 (Actions)
  python3 scripts/changed_paths.py --base "$BASE" --head "$HEAD" \\
      --github-output "$GITHUB_OUTPUT" --summary "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TEST_PREFIXES = ("scripts/", "tests/", ".github/workflows/", ".github/actions/")
TEST_EXACT = {"pyproject.toml"}
TEST_REGEX = re.compile(r"requirements[^/]*\.txt")
BUNDLE_PREFIXES = ("dashboard/", "project/")
BUNDLE_EXACT = {"LICENSE", "README.md"}
ZERO_SHA = "0" * 40


def needs_test(path: str) -> bool:
    return path.startswith(TEST_PREFIXES) or path in TEST_EXACT or bool(TEST_REGEX.fullmatch(path))


def in_bundle(path: str) -> bool:
    return path.startswith(BUNDLE_PREFIXES) or path in BUNDLE_EXACT


def decide(files: list[str], force: bool = False, reason: str = "") -> dict:
    """변경 파일 목록에서 실행 여부를 결정한다. 반환값은 GITHUB_OUTPUT 에 그대로 쓸 수 있다."""
    if force:
        return {"test": True, "build": True, "changed": len(files), "reason": reason or "전체 실행 지정"}
    test = any(needs_test(f) for f in files)
    build = test or any(in_bundle(f) for f in files)
    if not files:
        why = "변경된 파일 없음"
    elif test:
        why = "코드·테스트·의존성·CI 설정 변경"
    elif build:
        why = "배포 번들에 들어가는 파일만 변경"
    else:
        why = "문서·자동 생성 파일만 변경"
    return {"test": test, "build": build, "changed": len(files), "reason": why}


def git_changed_files(base: str, head: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    return [line for line in out.splitlines() if line]


def summary_markdown(result: dict, files: list[str]) -> str:
    def mark(v: bool) -> str:
        return "실행" if v else "건너뜀"

    lines = [
        "### 변경 파일 감지",
        "",
        f"- 판단: **{result['reason']}** (변경 {result['changed']}개)",
        f"- lint·test: **{mark(result['test'])}**, build: **{mark(result['build'])}**",
    ]
    if files:
        shown = files[:15]
        lines += ["", "<details><summary>변경 파일</summary>", ""]
        lines += [f"- `{f}`" for f in shown]
        if len(files) > len(shown):
            lines.append(f"- … 외 {len(files) - len(shown)}개")
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="", help="비교 기준 커밋(없거나 0000… 이면 전체 실행)")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--force", action="store_true", help="항상 전체 실행")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args(argv)

    files: list[str] = []
    if args.force:
        result = decide(files, force=True, reason="수동 실행 또는 태그: 전체 실행")
    elif not args.base or args.base == ZERO_SHA:
        result = decide(files, force=True, reason="비교 기준 커밋이 없어 전체 실행")
    else:
        try:
            files = git_changed_files(args.base, args.head)
            result = decide(files)
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"git diff 실패: {e}", file=sys.stderr)
            result = decide(files, force=True, reason="변경 파일을 확인하지 못해 전체 실행")

    lines = [f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in result.items()]
    print("\n".join(lines))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as f:
            f.write(summary_markdown(result, files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
