"""DORA 4대 지표 수집 스크립트.

GitHub REST API로 배포 워크플로우 실행 기록, 커밋, incident 이슈를 읽어서
Deployment Frequency / Lead Time for Changes / Change Failure Rate / MTTR 를 계산한다.

출력
- metrics/dora-latest.json           최신 결과 (대시보드가 읽음)
- metrics/history/YYYY-MM-DD.json    날짜별 스냅샷
- reports/weekly/YYYY-Www.md         주간 보고서
- README.md 의 <!-- DORA:START --> ~ <!-- DORA:END --> 구간

환경변수
- GITHUB_TOKEN       (Actions에서 자동 제공, 로컬 테스트 땐 없어도 됨)
- GITHUB_REPOSITORY  owner/repo
- DEPLOY_WORKFLOW    배포 워크플로우 파일명 (기본 deploy-pages.yml)
- WINDOW_DAYS        집계 기간 (기본 30)
- WEEKS              주간 추이 개수 (기본 8)
- INCIDENT_LABEL     장애 이슈 라벨 (기본 incident)
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent

REPO = os.environ.get("GITHUB_REPOSITORY", "03jiho/noticatch")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
DEPLOY_WORKFLOW = os.environ.get("DEPLOY_WORKFLOW", "deploy-pages.yml")
WINDOW_DAYS = int(os.environ.get("WINDOW_DAYS", "30"))
WEEKS = int(os.environ.get("WEEKS", "8"))
INCIDENT_LABEL = os.environ.get("INCIDENT_LABEL", "incident")

NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------- API helpers

def gh(path: str, params: dict | None = None):
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "noticatch-dora",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def paged(path: str, params: dict, key: str | None = None, limit_pages: int = 10):
    out = []
    for page in range(1, limit_pages + 1):
        data = gh(path, {**params, "per_page": 100, "page": page})
        if data is None:
            break
        items = data.get(key, []) if key else data
        out.extend(items)
        if len(items) < 100:
            break
    return out


def ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def hours(td: timedelta) -> float:
    return round(td.total_seconds() / 3600, 2)


def median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 2) if xs else None


def iso_week(d: datetime) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


# ---------------------------------------------------------------- collection

def deploy_runs(since: datetime) -> list[dict]:
    runs = paged(
        f"/repos/{REPO}/actions/workflows/{DEPLOY_WORKFLOW}/runs",
        {"branch": "main", "created": f">={since.date().isoformat()}"},
        key="workflow_runs",
    )
    done = [r for r in runs if r["status"] == "completed"
            and r["conclusion"] in ("success", "failure")]
    done.sort(key=lambda r: r["created_at"])
    return done


def commits_between(base: str | None, head: str) -> list[dict]:
    """head 배포에 새로 포함된 커밋들. 이전 배포가 없으면 head 커밋 하나만 본다."""
    if base and base != head:
        data = gh(f"/repos/{REPO}/compare/{base}...{head}")
        if data and data.get("commits"):
            return data["commits"]
    if base == head:
        return []
    c = gh(f"/repos/{REPO}/commits/{head}")
    return [c] if c else []


def incident_issues(since: datetime) -> list[dict]:
    issues = paged(f"/repos/{REPO}/issues",
                   {"labels": INCIDENT_LABEL, "state": "all", "since": since.isoformat()})
    return [i for i in issues if "pull_request" not in i]


# ---------------------------------------------------------------- metrics

def compute() -> dict:
    lookback = max(WINDOW_DAYS, WEEKS * 7)
    since = NOW - timedelta(days=lookback)
    window_start = NOW - timedelta(days=WINDOW_DAYS)

    runs = deploy_runs(since)

    # Lead time: 배포 완료 시각 - 그 배포에 포함된 각 커밋 시각
    deployments = []
    last_ok_sha = None
    for r in runs:
        finished = ts(r["updated_at"])
        lead = []
        if r["conclusion"] == "success":
            for c in commits_between(last_ok_sha, r["head_sha"]):
                if "[skip ci]" in c["commit"].get("message", ""):
                    continue  # 지표 자동 갱신 커밋은 제외
                committed = ts(c["commit"]["committer"]["date"])
                if committed and committed <= finished:
                    lead.append(hours(finished - committed))
            last_ok_sha = r["head_sha"]
        deployments.append({
            "run_id": r["id"],
            "sha": r["head_sha"][:7],
            "conclusion": r["conclusion"],
            "created_at": r["created_at"],
            "finished_at": r["updated_at"],
            "lead_times_h": lead,
            "url": r["html_url"],
        })

    # MTTR 1) 배포 실패 → 다음 성공 배포까지
    recoveries = []
    fail_start = None
    for d in deployments:
        if d["conclusion"] == "failure" and fail_start is None:
            fail_start = ts(d["created_at"])
        elif d["conclusion"] == "success" and fail_start is not None:
            recoveries.append({"source": "failed_deploy",
                               "opened": fail_start.isoformat(),
                               "hours": hours(ts(d["finished_at"]) - fail_start)})
            fail_start = None
    # MTTR 2) incident 라벨 이슈 open → close
    for i in incident_issues(since):
        if i.get("closed_at"):
            recoveries.append({"source": f"issue#{i['number']}",
                               "opened": i["created_at"],
                               "hours": hours(ts(i["closed_at"]) - ts(i["created_at"]))})

    in_win = [d for d in deployments if ts(d["created_at"]) >= window_start]
    ok = [d for d in in_win if d["conclusion"] == "success"]
    failed = [d for d in in_win if d["conclusion"] == "failure"]
    leads = [x for d in ok for x in d["lead_times_h"]]
    rec_win = [r["hours"] for r in recoveries if ts(r["opened"]) >= window_start]

    per_week = round(len(ok) / (WINDOW_DAYS / 7), 2)
    cfr = round(len(failed) / len(in_win), 3) if in_win else None

    # 주간 추이
    weekly = []
    for k in range(WEEKS - 1, -1, -1):
        start = (NOW - timedelta(days=NOW.weekday(), weeks=k)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        wk = [d for d in deployments if start <= ts(d["created_at"]) < end]
        wk_ok = [d for d in wk if d["conclusion"] == "success"]
        wk_fail = [d for d in wk if d["conclusion"] == "failure"]
        wk_rec = [r["hours"] for r in recoveries if start <= ts(r["opened"]) < end]
        weekly.append({
            "week": iso_week(start),
            "start": start.date().isoformat(),
            "deploys": len(wk_ok),
            "failed": len(wk_fail),
            "lead_time_median_h": median([x for d in wk_ok for x in d["lead_times_h"]]),
            "change_failure_rate": round(len(wk_fail) / len(wk), 3) if wk else None,
            "mttr_median_h": median(wk_rec),
        })

    metrics = {
        "deployment_frequency": {"successful_deploys": len(ok), "per_week": per_week},
        "lead_time_for_changes": {"median_h": median(leads), "samples": len(leads)},
        "change_failure_rate": {"rate": cfr, "failed": len(failed), "total": len(in_win)},
        "mttr": {"median_h": median(rec_win), "samples": len(rec_win)},
    }
    return {
        "generated_at": NOW.isoformat(timespec="seconds"),
        "repo": REPO,
        "window_days": WINDOW_DAYS,
        "deploy_workflow": DEPLOY_WORKFLOW,
        "metrics": metrics,
        "levels": classify(metrics),
        "weekly": weekly,
        "deployments": deployments[-30:],
        "recoveries": recoveries[-30:],
    }


def classify(m: dict) -> dict:
    """DORA State of DevOps 보고서의 성과 구간을 단순화한 참고용 등급."""
    def band(v, cuts, reverse=False):
        if v is None:
            return "N/A"
        names = ["Elite", "High", "Medium", "Low"]
        for name, cut in zip(names, cuts):
            if (v >= cut) if reverse else (v <= cut):
                return name
        return "Low"

    return {
        # 주당 배포 횟수: 7회 이상(하루 1회 이상) / 1회 이상 / 월 1회(0.25) 이상
        "deployment_frequency": band(m["deployment_frequency"]["per_week"], [7, 1, 0.25], reverse=True),
        # 리드타임(시간): 하루 / 일주일 / 한 달
        "lead_time_for_changes": band(m["lead_time_for_changes"]["median_h"], [24, 168, 720]),
        # 변경 실패율: 15% / 20% / 30%
        "change_failure_rate": band(m["change_failure_rate"]["rate"], [0.15, 0.20, 0.30]),
        # 복구 시간(시간): 1시간 / 하루 / 일주일
        "mttr": band(m["mttr"]["median_h"], [1, 24, 168]),
    }


# ---------------------------------------------------------------- outputs

def fmt_h(v):
    if v is None:
        return "데이터 없음"
    if v < 1:
        return f"{round(v * 60)}분"
    if v < 48:
        return f"{v:.1f}시간"
    return f"{v / 24:.1f}일"


def fmt_rate(v):
    return "데이터 없음" if v is None else f"{v * 100:.0f}%"


def summary_table(r: dict) -> str:
    m, lv = r["metrics"], r["levels"]
    df = m["deployment_frequency"]
    rows = [
        ("Deployment Frequency", f"{df['successful_deploys']}회 (주 {df['per_week']}회)", lv["deployment_frequency"]),
        ("Lead Time for Changes", f"{fmt_h(m['lead_time_for_changes']['median_h'])} (중앙값, n={m['lead_time_for_changes']['samples']})", lv["lead_time_for_changes"]),
        ("Change Failure Rate", f"{fmt_rate(m['change_failure_rate']['rate'])} ({m['change_failure_rate']['failed']}/{m['change_failure_rate']['total']})", lv["change_failure_rate"]),
        ("MTTR", f"{fmt_h(m['mttr']['median_h'])} (중앙값, n={m['mttr']['samples']})", lv["mttr"]),
    ]
    out = ["| 지표 | 최근 %d일 | 등급(참고) |" % r["window_days"], "|---|---|---|"]
    out += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(out)


def weekly_report(r: dict) -> str:
    kst = datetime.fromisoformat(r["generated_at"]).astimezone(timezone(timedelta(hours=9)))
    lines = [
        f"# DORA 주간 보고서 {iso_week(NOW)}",
        "",
        f"- 저장소: `{r['repo']}`",
        f"- 생성 시각: {kst:%Y-%m-%d %H:%M} (KST), GitHub Actions 자동 생성",
        f"- 집계 기간: 최근 {r['window_days']}일 / 배포 기준 워크플로우: `{r['deploy_workflow']}`",
        "",
        "## 요약",
        "",
        summary_table(r),
        "",
        "## 주간 추이",
        "",
        "| 주차 | 성공 배포 | 실패 배포 | 리드타임 중앙값 | 변경 실패율 | MTTR 중앙값 |",
        "|---|---|---|---|---|---|",
    ]
    for w in r["weekly"]:
        lines.append(f"| {w['week']} ({w['start']}~) | {w['deploys']} | {w['failed']} | "
                     f"{fmt_h(w['lead_time_median_h'])} | {fmt_rate(w['change_failure_rate'])} | "
                     f"{fmt_h(w['mttr_median_h'])} |")
    lines += ["", "## 최근 배포", "", "| 시각(UTC) | 커밋 | 결과 | 실행 |", "|---|---|---|---|"]
    for d in reversed(r["deployments"][-10:]):
        lines.append(f"| {d['created_at'][:16].replace('T', ' ')} | `{d['sha']}` | {d['conclusion']} | [run]({d['url']}) |")
    if not r["deployments"]:
        lines.append("| - | - | 배포 기록 없음 | - |")
    lines += ["", "> 원본 데이터: [`metrics/dora-latest.json`](../../metrics/dora-latest.json)", ""]
    return "\n".join(lines)


def update_readme(r: dict, report_path: str) -> None:
    readme = ROOT / "README.md"
    if not readme.exists():
        return
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- DORA:START -->", "<!-- DORA:END -->"
    if start not in text or end not in text:
        return
    kst = datetime.fromisoformat(r["generated_at"]).astimezone(timezone(timedelta(hours=9)))
    block = "\n".join([
        start,
        f"_마지막 자동 갱신: {kst:%Y-%m-%d %H:%M} KST · [주간 보고서]({report_path}) · [JSON](metrics/dora-latest.json)_",
        "",
        summary_table(r),
        end,
    ])
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    readme.write_text(head + block + tail, encoding="utf-8")


def main() -> int:
    result = compute()
    out = ROOT / "metrics"
    (out / "history").mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    (out / "dora-latest.json").write_text(payload, encoding="utf-8")
    (out / "history" / f"{NOW.date().isoformat()}.json").write_text(payload, encoding="utf-8")

    rep_dir = ROOT / "reports" / "weekly"
    rep_dir.mkdir(parents=True, exist_ok=True)
    rep_name = f"{iso_week(NOW)}.md"
    (rep_dir / rep_name).write_text(weekly_report(result), encoding="utf-8")
    (ROOT / "reports" / "LATEST.md").write_text(weekly_report(result).replace("../../", "../"), encoding="utf-8")

    update_readme(result, f"reports/weekly/{rep_name}")
    print(summary_table(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
