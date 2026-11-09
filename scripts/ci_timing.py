"""GitHub Actions 실행 시간을 집계해 캐시 효과와 파이프라인 최적화 전후를 수치로 비교한다.

시간은 Actions API 가 알려 주는 작업·단계의 started_at / completed_at 차이(초 단위 해상도)다.
누구나 같은 실행 번호로 다시 계산해 볼 수 있다.

명령
  bench    cache-benchmark.yml 한 번의 실행에서 OS·의존성 묶음별 "캐시 없음 vs 캐시 사용"을 계산한다.
  pipeline 최적화 전/후 CI 실행을 짝지어 전체 시간, 작업 시간 합, 실행된 작업 수를 비교한다.
  history  어떤 워크플로우의 특정 단계가 최근 실행에서 얼마나 걸렸는지 본다(캐시 도입 전 기준값).

환경변수: GITHUB_TOKEN(없어도 되지만 호출 한도가 낮다), GITHUB_REPOSITORY(기본 03jiho/noticatch)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPOSITORY", "03jiho/noticatch")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

BENCH_JOB = re.compile(r"Bench \((?P<os>[^,]+), (?P<case>[^,]+), #(?P<n>\d+)\)")
# 비공개 저장소의 분 단위 과금 배수(Linux 1, Windows 2, macOS 10). 이 저장소는 공개라 실제 과금은 없다.
BILLING_MULTIPLIER = {"ubuntu": 1, "windows": 2, "macos": 10}


# ---------------------------------------------------------------- 계산 (순수 함수)

def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return (parse_ts(end) - parse_ts(start)).total_seconds()


def step_seconds(job: dict, name: str) -> float | None:
    for s in job.get("steps", []):
        if s["name"] == name and s.get("conclusion") == "success":
            return seconds(s.get("started_at"), s.get("completed_at"))
    return None


def median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 2) if xs else None


def improvement(before: float | None, after: float | None) -> float | None:
    """(전 - 후) / 전 × 100. 양수면 빨라진 것, 음수면 느려진 것이다."""
    if before is None or after is None or before <= 0:
        return None
    return round((before - after) / before * 100, 1)


def bench_samples(jobs: list[dict]) -> list[dict]:
    """벤치마크 작업 하나가 샘플 하나다. 캐시 없음 / 캐시 복원 / 복원 후 설치 시간을 읽는다."""
    out = []
    for job in jobs:
        m = BENCH_JOB.fullmatch(job["name"])
        if not m or job.get("conclusion") != "success":
            continue
        cold = step_seconds(job, "Install without cache")
        restore = step_seconds(job, "Restore pip cache")
        warm_install = step_seconds(job, "Install with restored cache")
        if None in (cold, restore, warm_install):
            continue
        out.append({"os": m["os"], "case": m["case"], "n": int(m["n"]), "cold": cold,
                    "restore": restore, "warm_install": warm_install, "warm": restore + warm_install,
                    "venv": step_seconds(job, "Restore venv cache")})  # 가상환경 캐시 측정이 없는 실행이면 None
    return out


def summarize_bench(samples: list[dict]) -> list[dict]:
    """(OS, 의존성 묶음)마다 반복 측정의 중앙값과 개선율을 계산한다."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for s in samples:
        groups.setdefault((s["os"], s["case"]), []).append(s)
    rows = []
    for (os_name, case), items in sorted(groups.items()):
        cold, warm = median([i["cold"] for i in items]), median([i["warm"] for i in items])
        venv = median([i["venv"] for i in items if i.get("venv") is not None])
        rows.append({
            "os": os_name, "case": case, "samples": len(items),
            "cold": cold, "restore": median([i["restore"] for i in items]),
            "warm_install": median([i["warm_install"] for i in items]), "warm": warm,
            "saved": None if cold is None or warm is None else round(cold - warm, 2),
            "improvement_pct": improvement(cold, warm),
            "venv": venv, "venv_improvement_pct": improvement(cold, venv),
        })
    return rows


def pct(v: float | None) -> str:
    return "-" if v is None else f"{v:+.1f}%"


def render_bench(rows: list[dict]) -> str:
    out = [
        "### 캐시 효과 (의존성 설치, 반복 측정 중앙값)",
        "",
        "- **캐시 없음**: `pip install --no-cache-dir` 시간",
        "- **pip 캐시**: 저장해 둔 pip 다운로드 캐시를 복원하는 시간 + 복원 뒤 `pip install` 시간",
        "- **가상환경 캐시**: 설치가 끝난 가상환경(venv) 자체를 복원하는 시간. 설치를 건너뛴다.",
        "- 개선율 = (캐시 없음 − 캐시 사용) / 캐시 없음 × 100. 음수면 캐시가 오히려 느린 것이다. 시간은 1초 단위로만 측정된다.",
        "",
        "| OS | 의존성 | 반복 | 캐시 없음(초) | pip 캐시(초) | 개선율 | 가상환경 캐시(초) | 개선율 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        venv = "-" if r.get("venv") is None else r["venv"]
        out.append(f"| {r['os']} | {r['case']} | {r['samples']} | {r['cold']} | {r['warm']} | "
                   f"{pct(r['improvement_pct'])} | {venv} | {pct(r.get('venv_improvement_pct'))} |")
    return "\n".join(out) + "\n"


def os_bucket(job_name: str) -> str:
    lowered = job_name.lower()
    for key in ("windows", "macos"):
        if key in lowered:
            return key
    return "ubuntu"  # lint, build, deploy 등 이름에 OS 가 없는 작업은 ubuntu-latest 에서 돈다.


def run_stats(jobs: list[dict]) -> dict:
    """한 번의 실행에서 실행 구간 길이, 작업 시간의 합, 실행·건너뜀 작업 수를 센다."""
    ran = [j for j in jobs if j.get("conclusion") != "skipped" and j.get("started_at") and j.get("completed_at")]
    skipped = [j for j in jobs if j.get("conclusion") == "skipped"]
    wall = None
    if ran:
        wall = seconds(min(j["started_at"] for j in ran), max(j["completed_at"] for j in ran))
    by_os = {"ubuntu": 0.0, "windows": 0.0, "macos": 0.0}
    for j in ran:
        by_os[os_bucket(j["name"])] += seconds(j["started_at"], j["completed_at"])
    total = sum(by_os.values())
    weighted = sum(v * BILLING_MULTIPLIER[k] for k, v in by_os.items())
    return {"jobs_total": len(jobs), "jobs_ran": len(ran), "jobs_skipped": len(skipped),
            "wall": wall, "job_seconds": round(total, 1), "weighted_seconds": round(weighted, 1),
            "by_os": {k: round(v, 1) for k, v in by_os.items()}}


def compare_runs(before: dict, after: dict) -> dict:
    return {
        "wall_pct": improvement(before["wall"], after["wall"]),
        "job_seconds_pct": improvement(before["job_seconds"], after["job_seconds"]),
        "weighted_pct": improvement(before["weighted_seconds"], after["weighted_seconds"]),
        "jobs_ran_before": before["jobs_ran"], "jobs_ran_after": after["jobs_ran"],
    }


def render_pipeline(pairs: list[dict]) -> str:
    out = ["### 파이프라인 전후 비교", "",
           "- **실행 구간**: 첫 작업 시작 → 마지막 작업 종료(대기열 시간 제외)",
           "- **작업 시간 합**: 실행된 모든 작업의 소요 시간 합. 병렬로 돌아서 실행 구간보다 길다.",
           "- **과금 환산**: 비공개 저장소 기준 배수(Linux 1, Windows 2, macOS 10)를 곱한 합. 이 저장소는 공개라 참고용이다.",
           "- 개선율 = (전 − 후) / 전 × 100", ""]
    for p in pairs:
        b, a, c = p["before"], p["after"], compare_runs(p["before"], p["after"])
        out += [f"#### {p['name']}", "",
                f"| 항목 | 전 (run {p.get('before_id', '')}) | 후 (run {p.get('after_id', '')}) | 개선율 |",
                "|---|---|---|---|",
                f"| 실행된 작업 수 | {b['jobs_ran']} / {b['jobs_total']} | {a['jobs_ran']} / {a['jobs_total']} | |",
                f"| 건너뛴 작업 수 | {b['jobs_skipped']} | {a['jobs_skipped']} | |",
                f"| 실행 구간(초) | {b['wall']} | {a['wall']} | {pct(c['wall_pct'])} |",
                f"| 작업 시간 합(초) | {b['job_seconds']} | {a['job_seconds']} | {pct(c['job_seconds_pct'])} |",
                f"| 과금 환산(초) | {b['weighted_seconds']} | {a['weighted_seconds']} | {pct(c['weighted_pct'])} |", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- API

def api_get(path: str, params: dict | None = None):
    url = f"{API}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "noticatch-ci-timing", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def fetch_jobs(run_id: int) -> list[dict]:
    jobs, page = [], 1
    while True:
        data = api_get(f"/repos/{REPO}/actions/runs/{run_id}/jobs", {"per_page": 100, "page": page})
        jobs += data["jobs"]
        if len(data["jobs"]) < 100:
            return jobs
        page += 1


def step_history(workflow: str, step: str, limit: int) -> list[float]:
    runs = api_get(f"/repos/{REPO}/actions/workflows/{workflow}/runs",
                   {"per_page": limit, "status": "completed"})["workflow_runs"]
    values = []
    for r in runs:
        for job in fetch_jobs(r["id"]):
            v = step_seconds(job, step)
            if v is not None:
                values.append(v)
    return values


# ---------------------------------------------------------------- CLI

def write(path: Path | None, text: str, append: bool = False) -> None:
    if path:
        with path.open("a" if append else "w", encoding="utf-8") as f:
            f.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bench")
    b.add_argument("--run", type=int, required=True)
    p = sub.add_parser("pipeline")
    p.add_argument("--pair", action="append", required=True, metavar="이름|전RUN|후RUN")
    h = sub.add_parser("history")
    h.add_argument("--workflow", required=True)
    h.add_argument("--step", required=True)
    h.add_argument("--limit", type=int, default=10)
    for sp in (b, p):
        sp.add_argument("--markdown", type=Path, help="마크다운을 이 파일 끝에 덧붙인다(예: $GITHUB_STEP_SUMMARY)")
        sp.add_argument("--json", type=Path, help="계산 결과를 JSON 으로 저장")
    args = parser.parse_args(argv)

    if args.cmd == "bench":
        rows = summarize_bench(bench_samples(fetch_jobs(args.run)))
        text = render_bench(rows)
        data = {"run": args.run, "rows": rows}
    elif args.cmd == "pipeline":
        pairs = []
        for spec in args.pair:
            name, before_id, after_id = spec.split("|")
            pairs.append({"name": name, "before_id": int(before_id), "after_id": int(after_id),
                          "before": run_stats(fetch_jobs(int(before_id))),
                          "after": run_stats(fetch_jobs(int(after_id)))})
        text = render_pipeline(pairs)
        data = {"pairs": [{**x, "compare": compare_runs(x["before"], x["after"])} for x in pairs]}
    else:
        values = step_history(args.workflow, args.step, args.limit)
        print(json.dumps({"step": args.step, "samples": len(values), "values": values, "median": median(values),
                          "min": min(values, default=None), "max": max(values, default=None)}, ensure_ascii=False))
        return 0

    print(text)
    write(args.markdown, text, append=True)
    write(args.json, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
