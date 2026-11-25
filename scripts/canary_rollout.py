#!/usr/bin/env python3
"""카나리 롤아웃 1% → 10% → 50% → 100% 와 헬스체크 기반 자동 롤백.

각 단계마다 트래픽 비율을 올린 뒤 헬스체크를 여러 번 하고, 오류율이나 지연이 기준을 넘으면
그 즉시 안정 리비전으로 100% 되돌린다(롤백). 설정은 rollout/canary.json.

두 가지 방식으로 돌린다.
  --scenario healthy|error-spike|slow    가상의 헬스체크 결과(시뮬레이션). 롤아웃 로직 검증용.
  --url https://...                      실제 URL 에 요청을 보내 오류율과 p95 지연을 잰다.

트래픽 전환 자체는 실제로 하지 않는다. 대신 Cloud Run 이라면 어떤 명령을 실행할지를 계획으로 출력한다.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "rollout" / "canary.json"

Probe = Callable[[int, int], dict]  # (단계 %, 몇 번째 검사) -> {"error_rate": float, "p95_ms": float}


def scenario_probe(name: str) -> Probe:
    """가상 시나리오. 같은 입력에는 항상 같은 값이 나온다."""
    def probe(stage: int, check: int) -> dict:
        base = {"error_rate": 0.002 + 0.0005 * check, "p95_ms": 180 + 10 * check}
        if name == "error-spike" and stage >= 50:
            base["error_rate"] = 0.06          # 50% 로 늘리자 오류가 튄다
        if name == "slow" and stage >= 10:
            base["p95_ms"] = 1400               # 10% 부터 느려진다
        return base
    return probe


def http_probe(url: str, requests: int = 10, timeout: float = 5.0) -> Probe:
    """실제 URL 로 요청해 오류율과 p95 를 잰다. (단계와 무관하게 같은 곳을 본다)"""
    def probe(stage: int, check: int) -> dict:
        times, errors = [], 0
        for _ in range(requests):
            start = time.perf_counter()
            try:
                with urllib.request.urlopen(url, timeout=timeout) as resp:
                    if resp.status >= 400:
                        errors += 1
                    resp.read(1)
            except Exception:
                errors += 1
            times.append((time.perf_counter() - start) * 1000)
        times.sort()
        p95 = times[max(0, math.ceil(0.95 * len(times)) - 1)]
        return {"error_rate": errors / requests, "p95_ms": p95}
    return probe


def run_rollout(probe: Probe, stages: list[int], checks: int, max_error_rate: float, max_p95_ms: float) -> dict:
    steps = []
    for stage in stages:
        for n in range(1, checks + 1):
            m = probe(stage, n)
            ok = m["error_rate"] <= max_error_rate and m["p95_ms"] <= max_p95_ms
            reason = ""
            if m["error_rate"] > max_error_rate:
                reason = f"오류율 {m['error_rate']:.1%} > {max_error_rate:.1%}"
            elif m["p95_ms"] > max_p95_ms:
                reason = f"p95 {m['p95_ms']:.0f}ms > {max_p95_ms:.0f}ms"
            steps.append({"stage": stage, "check": n, "error_rate": m["error_rate"], "p95_ms": m["p95_ms"], "ok": ok, "reason": reason})
            if not ok:
                return {"outcome": "rolled_back", "failed_stage": stage, "reason": reason, "steps": steps}
    return {"outcome": "promoted", "failed_stage": None, "reason": "", "steps": steps}


def gcloud_plan(service: str, result: dict, stages: list[int]) -> list[str]:
    """실제 Cloud Run 에서라면 실행할 명령 (출력만 하고 실행하지 않는다)."""
    cmds = []
    for stage in stages:
        if result["failed_stage"] is not None and stage > result["failed_stage"]:
            break
        cmds.append(f"gcloud run services update-traffic {service} --to-revisions=CANARY={stage},STABLE={100 - stage}"
                    if stage < 100 else f"gcloud run services update-traffic {service} --to-latest")
    if result["outcome"] == "rolled_back":
        cmds.append(f"gcloud run services update-traffic {service} --to-revisions=STABLE=100   # 자동 롤백")
    return cmds


def render(result: dict, label: str, cfg: dict, plan: list[str], simulated: bool) -> str:
    th = cfg["thresholds"]
    head = "롤백됨" if result["outcome"] == "rolled_back" else "100% 승격 완료"
    lines = [f"### {label}: {head}", ""]
    if simulated:
        lines += ["> 가상 헬스체크 값을 쓰는 시뮬레이션입니다. 실제 트래픽을 옮기지는 않습니다.", ""]
    lines += [f"기준: 오류율 ≤ {th['maxErrorRate']:.1%}, p95 ≤ {th['maxP95Ms']}ms", "",
              "| 트래픽 | 검사 | 오류율 | p95 | 판정 |", "|---|---|---|---|---|"]
    for s in result["steps"]:
        verdict = "통과" if s["ok"] else f"실패 ({s['reason']})"
        lines.append(f"| {s['stage']}% | {s['check']} | {s['error_rate']:.1%} | {s['p95_ms']:.0f}ms | {verdict} |")
    if result["outcome"] == "rolled_back":
        lines += ["", f"→ {result['failed_stage']}% 단계에서 실패해 안정 리비전으로 100% 되돌렸습니다."]
    lines += ["", "실행했다면 쓸 명령:", "", "```bash", *plan, "```", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", choices=["healthy", "error-spike", "slow", "all"], default="all")
    ap.add_argument("--url", help="지정하면 시뮬레이션 대신 이 URL 을 실제로 검사한다")
    ap.add_argument("--out", type=Path, help="결과를 마크다운으로 저장할 경로")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    th = cfg["thresholds"]
    stages, checks = cfg["stages"], cfg["checksPerStage"]
    runs: list[tuple[str, dict, bool]] = []
    if args.url:
        runs.append((f"실제 URL ({args.url})", run_rollout(http_probe(args.url), stages, checks, th["maxErrorRate"], th["maxP95Ms"]), False))
    else:
        names = ["healthy", "error-spike", "slow"] if args.scenario == "all" else [args.scenario]
        for n in names:
            runs.append((f"시나리오 {n}", run_rollout(scenario_probe(n), stages, checks, th["maxErrorRate"], th["maxP95Ms"]), True))

    parts = ["# 카나리 롤아웃 검증 로그", "", f"단계: {' → '.join(f'{s}%' for s in stages)} · 단계마다 {checks}회 검사", ""]
    for label, result, simulated in runs:
        parts.append(render(result, label, cfg, gcloud_plan(cfg["service"], result, stages), simulated))
    text = "\n".join(parts)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    # 실제 URL 검사에서 롤백이 났다면 종료 코드로 알린다
    return 1 if args.url and runs[0][1]["outcome"] == "rolled_back" else 0


if __name__ == "__main__":
    raise SystemExit(main())
