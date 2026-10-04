"""스프린트 분석: Cycle Time, Velocity, Burndown.

데이터 규칙
- 스프린트 = 마일스톤. 설명에 "기간: YYYY-MM-DD ~ YYYY-MM-DD" 가 있어야 한다.
- 스토리 포인트 = "size: N" 라벨.
- 작업 시작 = 이슈에 담당자가 처음 지정된 시각 (assigned 이벤트). 없으면 이슈 생성 시각.
- Cycle Time = 작업 시작 → 이슈 종료, Lead Time = 이슈 생성 → 종료.

출력
- metrics/sprint-latest.json
- reports/sprint/LATEST.md
- docs/images/burndown.png (진행 중이거나 가장 최근 스프린트), docs/images/velocity.png
- README.md 의 <!-- SPRINT:START --> ~ <!-- SPRINT:END --> 구간
"""

from __future__ import annotations

import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent
REPO = os.environ.get("GITHUB_REPOSITORY", "03jiho/noticatch")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
KST = timezone(timedelta(hours=9))
NOW = datetime.now(timezone.utc)
TODAY = NOW.astimezone(KST).date()


def gh(path: str, params: dict | None = None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "noticatch-sprint",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def all_pages(path: str, params: dict | None = None) -> list:
    out, page = [], 1
    while True:
        items = gh(path, {**(params or {}), "per_page": 100, "page": page}) or []
        out += items
        if len(items) < 100:
            return out
        page += 1


def ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def points(issue: dict) -> int:
    for l in issue["labels"]:
        m = re.fullmatch(r"size:\s*(\d+)", l["name"])
        if m:
            return int(m.group(1))
    return 0


def work_started(issue: dict) -> datetime:
    events = all_pages(f"/repos/{REPO}/issues/{issue['number']}/events")
    assigned = [ts(e["created_at"]) for e in events if e["event"] == "assigned"]
    return min(assigned) if assigned else ts(issue["created_at"])


def hours(td: timedelta) -> float:
    return round(td.total_seconds() / 3600, 1)


def med(xs):
    return round(statistics.median(xs), 1) if xs else None


# ------------------------------------------------------------------ collect

def collect() -> dict:
    sprints = []
    for m in all_pages(f"/repos/{REPO}/milestones", {"state": "all", "sort": "due_on"}):
        period = re.search(r"기간:\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})", m.get("description") or "")
        if not period:
            continue
        start, end = date.fromisoformat(period.group(1)), date.fromisoformat(period.group(2))
        issues = [i for i in all_pages(f"/repos/{REPO}/issues", {"milestone": m["number"], "state": "all"})
                  if "pull_request" not in i]
        items = []
        for i in issues:
            item = {
                "number": i["number"], "title": i["title"], "points": points(i),
                "state": i["state"], "created_at": i["created_at"], "closed_at": i["closed_at"],
            }
            if i["state"] == "closed":
                started = work_started(i)
                item["cycle_time_h"] = hours(ts(i["closed_at"]) - started)
                item["lead_time_h"] = hours(ts(i["closed_at"]) - ts(i["created_at"]))
            items.append(item)
        sprints.append(build_sprint(m["title"], start, end, items))
    sprints.sort(key=lambda s: s["start"])
    return {
        "generated_at": NOW.isoformat(timespec="seconds"),
        "repo": REPO,
        "sprints": sprints,
        "summary": summarize(sprints),
    }


def build_sprint(title: str, start: date, end: date, items: list[dict]) -> dict:
    total = sum(i["points"] for i in items)
    done = [i for i in items if i["state"] == "closed"]
    days = [start + timedelta(days=k) for k in range((end - start).days + 1)]
    burndown = []
    for k, d in enumerate(days):
        ideal = round(total * (1 - k / (len(days) - 1)), 2) if len(days) > 1 else 0
        if d <= TODAY:
            closed_pts = sum(i["points"] for i in done
                             if ts(i["closed_at"]).astimezone(KST).date() <= d)
            remaining = total - closed_pts
        else:
            remaining = None
        burndown.append({"date": d.isoformat(), "ideal": ideal, "remaining": remaining})
    status = "planned" if TODAY < start else "active" if TODAY <= end else "closed"
    cycles = [i["cycle_time_h"] for i in done]
    return {
        "title": title, "start": start.isoformat(), "end": end.isoformat(), "status": status,
        "committed_points": total,
        "completed_points": sum(i["points"] for i in done),
        "issues_total": len(items), "issues_done": len(done),
        "cycle_time_median_h": med(cycles),
        "lead_time_median_h": med([i["lead_time_h"] for i in done]),
        "burndown": burndown,
        "issues": sorted(items, key=lambda i: i["number"]),
    }


def summarize(sprints: list[dict]) -> dict:
    finished = [s for s in sprints if s["status"] == "closed"]
    basis = finished or [s for s in sprints if s["status"] == "active"]
    all_cycles = [i["cycle_time_h"] for s in sprints for i in s["issues"] if "cycle_time_h" in i]
    current = next((s["title"] for s in sprints if s["status"] == "active"), None)
    return {
        "current_sprint": current,
        "average_velocity": round(statistics.mean([s["completed_points"] for s in basis]), 1) if basis else None,
        "velocity_basis": "완료된 스프린트 평균" if finished else "진행 중 스프린트의 현재까지 완료분",
        "cycle_time_median_h": med(all_cycles),
        "cycle_time_samples": len(all_cycles),
    }


# ------------------------------------------------------------------ charts

def charts(r: dict) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib 없음: 차트 생략")
        return []

    blue, gray, ink, muted, grid = "#2a78d6", "#898781", "#0b0b0b", "#52514e", "#e1e0d9"
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#c3c2b7",
        "axes.labelcolor": muted, "xtick.color": muted, "ytick.color": muted,
        "axes.spines.top": False, "axes.spines.right": False,
    })
    out_dir = ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []

    sprints = r["sprints"]
    target = next((s for s in sprints if s["status"] == "active"), None) \
        or next((s for s in reversed(sprints) if s["status"] == "closed"), None) \
        or (sprints[0] if sprints else None)
    if target:
        bd = target["burndown"]
        x = [date.fromisoformat(b["date"]).strftime("%m/%d") for b in bd]
        fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
        ax.plot(x, [b["ideal"] for b in bd], color=gray, linestyle="--", linewidth=1.5, label="Ideal")
        actual = [(xi, b["remaining"]) for xi, b in zip(x, bd) if b["remaining"] is not None]
        if actual:
            ax.plot([a[0] for a in actual], [a[1] for a in actual], color=blue, linewidth=2,
                    marker="o", markersize=4, label="Remaining")
            ax.annotate(f"{actual[-1][1]} pts", actual[-1], textcoords="offset points",
                        xytext=(6, 6), color=ink, fontsize=9)
        ax.set_ylim(0, max([b["ideal"] for b in bd] + [1]) * 1.1)
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.set_ylabel("Story points")
        ax.grid(axis="y", color=grid, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=8, rotation=45)
        title = target["title"].split("·")[0].strip()
        ax.set_title(f"Burndown · {title} ({target['start']} ~ {target['end']})", loc="left", color=ink, fontsize=11)
        ax.legend(frameon=False, loc="upper right")
        fig.tight_layout()
        fig.savefig(out_dir / "burndown.png")
        plt.close(fig)
        made.append("docs/images/burndown.png")

    if sprints:
        names = [s["title"].split("·")[0].strip() for s in sprints]
        xs = range(len(sprints))
        w = 0.36
        fig, ax = plt.subplots(figsize=(8, 3.2), dpi=150)
        b1 = ax.bar([i - w / 2 for i in xs], [s["committed_points"] for s in sprints], w,
                    color="#c3c2b7", label="Committed")
        b2 = ax.bar([i + w / 2 for i in xs], [s["completed_points"] for s in sprints], w,
                    color=blue, label="Completed")
        for bars in (b1, b2):
            for b in bars:
                ax.annotate(f"{int(b.get_height())}", (b.get_x() + b.get_width() / 2, b.get_height()),
                            ha="center", va="bottom", fontsize=9, color=ink, xytext=(0, 2), textcoords="offset points")
        ax.set_xticks(list(xs), [f"{n}\n({s['status']})" for n, s in zip(names, sprints)])
        top = max([s["committed_points"] for s in sprints] + [1])
        ax.set_ylim(0, top * 1.2)
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.set_ylabel("Story points")
        ax.grid(axis="y", color=grid, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_title("Velocity · committed vs completed", loc="left", color=ink, fontsize=11)
        ax.legend(frameon=False, loc="upper right")
        fig.tight_layout()
        fig.savefig(out_dir / "velocity.png")
        plt.close(fig)
        made.append("docs/images/velocity.png")
    return made


# ------------------------------------------------------------------ report

def fmt_h(v):
    if v is None:
        return "-"
    return f"{v:.1f}시간" if v < 48 else f"{v / 24:.1f}일"


def sprint_table(r: dict) -> str:
    rows = ["| 스프린트 | 기간 | 상태 | 이슈 (완료/전체) | 포인트 (완료/계획) | Cycle Time 중앙값 |",
            "|---|---|---|---|---|---|"]
    ko = {"planned": "예정", "active": "진행 중", "closed": "종료"}
    for s in r["sprints"]:
        rows.append(f"| {s['title']} | {s['start']} ~ {s['end']} | {ko[s['status']]} | "
                    f"{s['issues_done']}/{s['issues_total']} | {s['completed_points']}/{s['committed_points']} | "
                    f"{fmt_h(s['cycle_time_median_h'])} |")
    return "\n".join(rows)


def report(r: dict) -> str:
    sm = r["summary"]
    gen = datetime.fromisoformat(r["generated_at"]).astimezone(KST)
    lines = [
        "# 스프린트 분석 보고서", "",
        f"- 생성: {gen:%Y-%m-%d %H:%M} KST (GitHub Actions 자동 생성)",
        f"- 현재 스프린트: {sm['current_sprint'] or '없음'}",
        f"- Velocity: {sm['average_velocity'] if sm['average_velocity'] is not None else '-'} pts ({sm['velocity_basis']})",
        f"- Cycle Time 중앙값: {fmt_h(sm['cycle_time_median_h'])} (완료 이슈 {sm['cycle_time_samples']}개)",
        "", "## 스프린트별", "", sprint_table(r), "",
        "![Burndown](../../docs/images/burndown.png)", "",
        "![Velocity](../../docs/images/velocity.png)", "",
        "## 완료된 이슈의 Cycle Time", "",
        "| 이슈 | 포인트 | Cycle Time | Lead Time | 종료 (KST) |", "|---|---|---|---|---|",
    ]
    done = [(s, i) for s in r["sprints"] for i in s["issues"] if i["state"] == "closed"]
    for s, i in sorted(done, key=lambda x: x[1]["closed_at"]):
        closed = ts(i["closed_at"]).astimezone(KST)
        lines.append(f"| #{i['number']} {i['title']} | {i['points']} | {fmt_h(i['cycle_time_h'])} | "
                     f"{fmt_h(i['lead_time_h'])} | {closed:%m-%d %H:%M} |")
    if not done:
        lines.append("| 아직 완료된 이슈 없음 | | | | |")
    lines += ["", "## 정의", "",
              "- **Velocity**: 스프린트(마일스톤) 안에서 닫힌 이슈의 스토리 포인트(`size: N` 라벨) 합",
              "- **Burndown**: 스프린트 시작일부터 날짜별 남은 포인트. 점선은 이상적인 감소선",
              "- **Cycle Time**: 담당자 지정(작업 시작) → 이슈 종료. 담당자가 없으면 생성 시각부터",
              "- **Lead Time**: 이슈 생성 → 종료", ""]
    return "\n".join(lines)


def update_readme(r: dict) -> None:
    p = ROOT / "README.md"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    a, b = "<!-- SPRINT:START -->", "<!-- SPRINT:END -->"
    if a not in t or b not in t:
        return
    sm = r["summary"]
    gen = datetime.fromisoformat(r["generated_at"]).astimezone(KST)
    block = "\n".join([
        a,
        f"_마지막 자동 갱신: {gen:%Y-%m-%d %H:%M} KST · [분석 보고서](reports/sprint/LATEST.md) · [JSON](metrics/sprint-latest.json)_",
        "",
        sprint_table(r),
        "",
        f"Velocity **{sm['average_velocity'] if sm['average_velocity'] is not None else '-'} pts** ({sm['velocity_basis']}) · "
        f"Cycle Time 중앙값 **{fmt_h(sm['cycle_time_median_h'])}** (n={sm['cycle_time_samples']})",
        "",
        "![Burndown](docs/images/burndown.png)",
        "",
        "![Velocity](docs/images/velocity.png)",
        b,
    ])
    head, rest = t.split(a, 1)
    _, tail = rest.split(b, 1)
    p.write_text(head + block + tail, encoding="utf-8")


def main() -> int:
    r = collect()
    (ROOT / "metrics").mkdir(exist_ok=True)
    (ROOT / "metrics" / "sprint-latest.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    charts(r)
    (ROOT / "reports" / "sprint").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "sprint" / "LATEST.md").write_text(report(r), encoding="utf-8")
    update_readme(r)
    print(sprint_table(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
