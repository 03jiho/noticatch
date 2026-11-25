"""GitHub Pages 에 올릴 사이트 폴더를 만든다: main 의 대시보드 + 열려 있는 PR 의 프리뷰. 표준 라이브러리만 쓴다.

    _site/
      index.html ...                  main 의 dashboard/
      pr-preview/
        index.html                    프리뷰 목록
        pr-12/index.html ...          PR #12 브랜치의 dashboard/ (맨 위에 프리뷰 안내 띠를 붙인다)

왜 이렇게 하나: GitHub Pages 는 배포 하나가 사이트 전체를 바꾼다. PR 프리뷰만 따로 올리면 main 사이트와 다른 PR 프리뷰가
사라진다. 그래서 main 배포와 PR 배포가 모두 "main + 열린 PR 프리뷰 전부"를 새로 만들어 올린다. PR 이 닫히면 다음 배포에서
그 프리뷰는 저절로 사라진다.

프리뷰 대상: 같은 저장소의 브랜치에서 연 PR 중 dashboard/ 를 바꾼 것. 포크 PR 은 제외한다.
(프리뷰는 main 과 같은 도메인에서 서비스되므로, 쓰기 권한이 있는 사람이 올린 브랜치만 올린다.)

사용 예 (Actions)
  python3 scripts/build_pages_site.py --repo "$GITHUB_REPOSITORY" --out _site --previews
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PREVIEW_DIR = "pr-preview"
MAX_PREVIEWS = 10
FRONTEND_PREFIX = "dashboard/"


def select_previews(prs: list[dict], files_by_pr: dict[int, list[str]], repo: str, limit: int = MAX_PREVIEWS) -> list[dict]:
    """프리뷰를 만들 PR 을 고른다: 열림, 초안 아님, 같은 저장소, dashboard/ 변경. 최근 PR 부터 limit 개."""
    chosen = []
    for pr in sorted(prs, key=lambda p: -p["number"]):
        head_repo = (pr.get("head", {}).get("repo") or {}).get("full_name")
        if pr.get("state") != "open" or pr.get("draft"):
            continue
        if head_repo != repo:
            continue
        if not any(f.startswith(FRONTEND_PREFIX) for f in files_by_pr.get(pr["number"], [])):
            continue
        chosen.append({"number": pr["number"], "title": pr["title"], "sha": pr["head"]["sha"]})
        if len(chosen) >= limit:
            break
    return chosen


def inject_banner(page: str, number: int, sha: str, title: str) -> str:
    """프리뷰 페이지 맨 위에 '이건 프리뷰'라는 안내 띠를 붙인다. <body> 가 없으면 그대로 둔다."""
    banner = (
        '<div style="position:sticky;top:0;z-index:99999;padding:6px 12px;background:#fff4dc;color:#3a2f14;'
        'font:13px/1.4 system-ui,sans-serif;border-bottom:1px solid #e6cf9a">'
        f"PR #{number} 프리뷰 · 커밋 {html.escape(sha[:7])} · {html.escape(title)} "
        '· <a href="../" style="color:inherit">프리뷰 목록</a></div>'
    )
    return re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + banner, page, count=1, flags=re.IGNORECASE)


def render_index(previews: list[dict]) -> str:
    items = "\n".join(
        f'<li><a href="pr-{p["number"]}/">PR #{p["number"]}</a> — {html.escape(p["title"])} <code>{html.escape(p["sha"][:7])}</code></li>'
        for p in previews
    ) or "<li>열려 있는 프리뷰가 없습니다.</li>"
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>PR 프리뷰 목록</title></head><body style=\"font-family:system-ui,sans-serif;max-width:40rem;margin:2rem auto;padding:0 1rem\">"
        f"<h1>PR 프리뷰</h1><p>열려 있는 PR 중 대시보드를 바꾼 것만 보여 줍니다. PR 이 닫히면 사라집니다.</p><ul>{items}</ul>"
        '<p><a href="../">← 대시보드로</a></p></body></html>\n'
    )


def check_relative_links(page: str) -> list[str]:
    """프리뷰는 하위 경로(/pr-preview/pr-N/)에서 서비스되므로, '/' 로 시작하는 링크는 깨진다."""
    return re.findall(r'(?:href|src)="(/(?!/)[^"]*)"', page)


def run(*cmd: str, cwd: str | None = None) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", cwd=cwd).stdout


def gh_json(path: str) -> list[dict]:
    out = run("gh", "api", path, "--paginate", "--jq", ".[]")
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def export_dashboard(sha: str, dest: Path) -> None:
    """PR 의 dashboard/ 를 git 에서 꺼내 dest 에 둔다. 작업 폴더는 건드리지 않는다."""
    with tempfile.TemporaryDirectory() as tmp:
        tar = Path(tmp) / "d.tar"
        subprocess.run(["git", "archive", "--format=tar", "-o", str(tar), sha, "dashboard"], check=True)
        run("tar", "-xf", str(tar), "-C", tmp)
        shutil.copytree(Path(tmp) / "dashboard", dest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", default="_site")
    ap.add_argument("--previews", action="store_true", help="열린 PR 프리뷰를 함께 만든다")
    ap.add_argument("--manifest", help="만든 프리뷰 목록을 JSON 으로 저장할 경로")
    args = ap.parse_args()

    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree("dashboard", out)

    previews: list[dict] = []
    if args.previews:
        prs = gh_json(f"repos/{args.repo}/pulls?state=open&per_page=100")
        files = {pr["number"]: [f["filename"] for f in gh_json(f"repos/{args.repo}/pulls/{pr['number']}/files?per_page=100")]
                 for pr in prs if (pr.get("head", {}).get("repo") or {}).get("full_name") == args.repo and not pr.get("draft")}
        for p in select_previews(prs, files, args.repo):
            try:
                run("git", "fetch", "--depth=1", "origin", f"refs/pull/{p['number']}/head")
                dest = out / PREVIEW_DIR / f"pr-{p['number']}"
                export_dashboard(run("git", "rev-parse", "FETCH_HEAD").strip(), dest)
            except subprocess.CalledProcessError as e:
                print(f"PR #{p['number']} 프리뷰를 만들지 못해 건너뜁니다: {e}", file=sys.stderr)
                continue
            index = dest / "index.html"
            if not index.is_file():
                print(f"PR #{p['number']}: dashboard/index.html 이 없어 건너뜁니다.", file=sys.stderr)
                shutil.rmtree(dest)
                continue
            page = index.read_text(encoding="utf-8")
            bad = check_relative_links(page)
            if bad:
                print(f"PR #{p['number']}: 하위 경로에서 깨질 절대 경로 링크 {bad[:3]} — 건너뜁니다.", file=sys.stderr)
                shutil.rmtree(dest)
                continue
            index.write_text(inject_banner(page, p["number"], p["sha"], p["title"]), encoding="utf-8")
            previews.append(p)
        (out / PREVIEW_DIR).mkdir(exist_ok=True)
        (out / PREVIEW_DIR / "index.html").write_text(render_index(previews), encoding="utf-8")

    (out / ".nojekyll").write_text("", encoding="utf-8")
    if args.manifest:
        Path(args.manifest).write_text(json.dumps(previews, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"사이트 폴더 {out}: main 대시보드 + 프리뷰 {len(previews)}개 ({', '.join('#' + str(p['number']) for p in previews) or '없음'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
