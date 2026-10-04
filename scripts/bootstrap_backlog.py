"""project/labels.yml, project/backlog.yml 을 읽어 라벨·마일스톤·이슈를 만든다.

- 라벨: 없으면 만들고, 있으면 색·설명을 맞춘다. remove 목록은 삭제한다.
- 마일스톤/이슈: 같은 제목이 이미 있으면 건너뛴다 (여러 번 실행해도 안전).
- DRY_RUN=1 이면 실제로 만들지 않고 계획만 출력한다.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("GITHUB_REPOSITORY", "03jiho/noticatch")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DRY = os.environ.get("DRY_RUN") == "1"


def gh(method: str, path: str, body: dict | None = None, params: dict | None = None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "noticatch-bootstrap",
        "Authorization": f"Bearer {TOKEN}",
        **({"Content-Type": "application/json"} if data else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"!! {method} {path} -> {e.code} {e.read().decode()[:300]}")
        raise


def all_pages(path: str, params: dict | None = None) -> list:
    out, page = [], 1
    while True:
        items = gh("GET", path, params={**(params or {}), "per_page": 100, "page": page}) or []
        out += items
        if len(items) < 100:
            return out
        page += 1


def do(method: str, path: str, body: dict | None = None):
    print(f"{'[dry] ' if DRY else ''}{method} {path} {json.dumps(body, ensure_ascii=False)[:120] if body else ''}")
    return None if DRY else gh(method, path, body)


def sync_labels(cfg: dict) -> None:
    existing = {l["name"]: l for l in all_pages(f"/repos/{REPO}/labels")}
    for l in cfg["labels"]:
        want = {"name": l["name"], "color": l["color"], "description": l.get("description", "")}
        cur = existing.get(l["name"])
        if cur is None:
            do("POST", f"/repos/{REPO}/labels", want)
        elif cur["color"].lower() != want["color"].lower() or (cur.get("description") or "") != want["description"]:
            do("PATCH", f"/repos/{REPO}/labels/{urllib.parse.quote(l['name'])}", want)
    for name in cfg.get("remove", []):
        if name in existing:
            do("DELETE", f"/repos/{REPO}/labels/{urllib.parse.quote(name)}")


def sync_milestones(cfg: dict) -> dict[str, int]:
    existing = {m["title"]: m["number"] for m in all_pages(f"/repos/{REPO}/milestones", {"state": "all"})}
    for m in cfg["milestones"]:
        if m["title"] in existing:
            continue
        body = {
            "title": m["title"],
            # 마감일은 KST 23:59 로 맞춘다
            "due_on": f"{m['due']}T14:59:59Z",
            "description": f"{m['description']}\n\n기간: {m['start']} ~ {m['due']}",
        }
        res = do("POST", f"/repos/{REPO}/milestones", body)
        existing[m["title"]] = res["number"] if res else -1
    return existing


def create_issues(cfg: dict, milestones: dict[str, int]) -> None:
    titles = {i["title"] for i in all_pages(f"/repos/{REPO}/issues", {"state": "all"})}
    for issue in cfg["issues"]:
        if issue["title"] in titles:
            print(f"skip (exists): {issue['title']}")
            continue
        body = {"title": issue["title"], "body": issue.get("body", ""), "labels": issue.get("labels", [])}
        if issue.get("milestone"):
            body["milestone"] = milestones[issue["milestone"]]
        do("POST", f"/repos/{REPO}/issues", body)


def main() -> int:
    labels = yaml.safe_load((ROOT / "project/labels.yml").read_text(encoding="utf-8"))
    backlog = yaml.safe_load((ROOT / "project/backlog.yml").read_text(encoding="utf-8"))
    sync_labels(labels)
    ms = sync_milestones(backlog)
    create_issues(backlog, ms)
    print(f"done: {len(backlog['issues'])} issues in backlog file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
