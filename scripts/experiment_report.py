#!/usr/bin/env python3
"""A/B 실험 지표를 분석해 주간 리포트 또는 Pivot/Persevere 결정 문서를 만든다.

결정 규칙은 실험 시작 전에 experiments/cta-style.json 에 적어 둔 것을 그대로 쓴다. (결과를 보고 기준을 바꾸지 않기 위해서)

  python scripts/experiment_report.py --input metrics/experiment-daily.jsonl --out docs/lean/reports/latest.md
  python scripts/experiment_report.py --input metrics/experiment-daily.jsonl --final --out docs/lean/decision-final.md
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path
from statistics import NormalDist

import ab_simulation as ab
import experiment_run as run

ROOT = run.ROOT


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def required_per_arm(base: float, lift: float, alpha: float, power: float) -> int:
    """기준 클릭률 base 에서 상대 증가 lift 를 검출하는 데 필요한 그룹당 표본 수(양측 z 검정)."""
    p1, p2 = base, base * (1 + lift)
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    return math.ceil(z**2 * (p1 * (1 - p1) + p2 * (1 - p2)) / (p2 - p1) ** 2)


def _sum(rows: list[dict], variant: str) -> tuple[int, int]:
    return (sum(r["variants"][variant]["exposed"] for r in rows), sum(r["variants"][variant]["clicks"] for r in rows))


def analyze(rows: list[dict], exp: dict, personas: list[dict]) -> dict:
    n_c, x_c = _sum(rows, "control")
    n_t, x_t = _sum(rows, "treatment")
    ctr_c, ctr_t = (x_c / n_c if n_c else 0.0), (x_t / n_t if n_t else 0.0)
    z, p = ab.two_proportion_z(x_c, n_c, x_t, n_t)
    lift = (ctr_t - ctr_c) / ctr_c if ctr_c else 0.0
    se = math.sqrt(ctr_c * (1 - ctr_c) / n_c + ctr_t * (1 - ctr_t) / n_t) if n_c and n_t else 0.0
    ci = (ctr_t - ctr_c - 1.96 * se, ctr_t - ctr_c + 1.96 * se)

    guard = exp["guardrail"]
    segments, violations = [], []
    for persona in personas:
        pid = persona["id"]
        sc = [r["personas"][pid]["control"] for r in rows]
        st = [r["personas"][pid]["treatment"] for r in rows]
        nc, xc = sum(s["exposed"] for s in sc), sum(s["clicks"] for s in sc)
        nt, xt = sum(s["exposed"] for s in st), sum(s["clicks"] for s in st)
        rc, rt = (xc / nc if nc else 0.0), (xt / nt if nt else 0.0)
        rel = (rt - rc) / rc if rc else 0.0
        enough = min(nc, nt) >= guard["min_segment_exposures_per_variant"]
        bad = enough and rel <= -guard["max_segment_relative_drop"]
        segments.append({"id": pid, "name": persona["name"], "role": persona["role"], "n_control": nc, "n_treatment": nt,
                         "ctr_control": rc, "ctr_treatment": rt, "relative": rel, "enough": enough, "violation": bad})
        if bad:
            violations.append(persona["name"])

    planned = (date.fromisoformat(exp["end"]) - date.fromisoformat(exp["start"])).days + 1
    significant = p < exp["alpha"]
    wins = significant and lift >= exp["minimum_detectable_lift"]
    if wins and violations:
        decision = "persevere-conditional"
    elif wins:
        decision = "persevere"
    else:
        decision = "pivot"
    if wins:
        reason = f"유의하고(p={p:.4f}) 증가율 {lift:+.1%} ≥ +{exp['minimum_detectable_lift']:.0%}"
    elif significant:
        reason = f"유의하지만(p={p:.4f}) 증가율 {lift:+.1%} 이 기준 +{exp['minimum_detectable_lift']:.0%} 에 못 미침"
    else:
        reason = f"통계적으로 유의하지 않음(p={p:.4f})"
    return {"reason": reason, "days": len(rows), "planned_days": planned, "n_control": n_c, "n_treatment": n_t, "x_control": x_c, "x_treatment": x_t,
            "ctr_control": ctr_c, "ctr_treatment": ctr_t, "lift": lift, "z": z, "p": p, "ci": ci, "segments": segments,
            "violations": violations, "decision": decision,
            "required_per_arm": required_per_arm(ctr_c or 0.1, exp["minimum_detectable_lift"], exp["alpha"], exp["power"])}


DECISION_TEXT = {
    "persevere": "**Persevere (유지·확대)**: 새 문구를 모든 사용자에게 적용한다.",
    "persevere-conditional": "**조건부 Persevere**: 새 문구를 적용하되, 가드레일을 위반한 세그먼트는 원본 문구를 유지한다.",
    "pivot": "**Pivot (방향 전환)**: 버튼 문구 가설은 기준을 넘지 못했다. 다른 가설로 옮긴다.",
}


def render(a: dict, exp: dict, label: str, final: bool, source: str, dryrun: bool = False) -> str:
    seg_rows = "\n".join(
        f"| {s['name']} ({s['role']}) | {s['n_control']:,} / {s['n_treatment']:,} | {s['ctr_control']:.1%} | {s['ctr_treatment']:.1%} | "
        f"{s['relative']:+.0%} | {'⚠ 위반' if s['violation'] else ('표본 부족' if not s['enough'] else '정상')} |"
        for s in a["segments"]
    )
    enough_n = min(a["n_control"], a["n_treatment"]) >= a["required_per_arm"]
    verdict = "p < 0.05: 통계적으로 유의" if a["p"] < exp["alpha"] else "p ≥ 0.05: 유의하지 않음"
    status = ("**사전 시뮬레이션 결과 (실제 운영 전 리허설)**" if dryrun else "**최종 결과**" if final else f"**중간 결과 ({a['days']}/{a['planned_days']}일차)**")
    kind = "사전 시뮬레이션(dry-run) 결과" if dryrun else "최종 결정" if final else "주간 리포트"
    return f"""# 실험 {kind}: `{exp['key']}` — {label}

> **합성 데이터입니다.** 실제 방문자가 아니라 가상 페르소나 10명의 성향을 돌린 시뮬레이션이며, 데이터 출처는 `{source}` 입니다.
> 이 결과는 실험 파이프라인(할당 → 수집 → 분석 → 결정)이 동작함을 보이는 것이고, 실제 사용자 반응의 증거가 아닙니다.

## 가설과 규칙 (실험 전에 고정)

- 가설: {exp['hypothesis']}
- 1차 지표: {exp['primary_metric']}
- 기간: {exp['start']} ~ {exp['end']} ({a['planned_days']}일), 하루 {exp['sessions_per_day']:,}세션
- Persevere 규칙: {exp['decision_rule']['persevere']}
- Pivot 규칙: {exp['decision_rule']['pivot']}

## {status}

| variant | 노출 | 클릭 | CTR |
|---|---|---|---|
| `control` ({exp['variants']['control']}) | {a['n_control']:,} | {a['x_control']:,} | {a['ctr_control']:.2%} |
| `treatment` ({exp['variants']['treatment']}) | {a['n_treatment']:,} | {a['x_treatment']:,} | {a['ctr_treatment']:.2%} |

- 상대 증가율 **{a['lift']:+.1%}**, 차이의 95% 신뢰구간 [{a['ci'][0]:+.2%}p, {a['ci'][1]:+.2%}p]
- z = {a['z']:.2f}, p = {a['p']:.4f} → {verdict}
- 표본: 그룹당 {min(a['n_control'], a['n_treatment']):,}명 / 필요 {a['required_per_arm']:,}명 (최소 검출 +{exp['minimum_detectable_lift']:.0%}, 검정력 {exp['power']:.0%}) → {'충족' if enough_n else '아직 부족'}

### 세그먼트(페르소나)별 가드레일

| 페르소나 | 노출(원본/신규) | 원본 CTR | 신규 CTR | 상대 변화 | 판정 |
|---|---|---|---|---|---|
{seg_rows}

가드레일: 세그먼트 CTR 이 {exp['guardrail']['max_segment_relative_drop']:.0%} 이상 떨어지면 위반(그룹당 {exp['guardrail']['min_segment_exposures_per_variant']}노출 이상일 때만 판정).
{'위반 세그먼트: ' + ', '.join(a['violations']) if a['violations'] else '위반 세그먼트 없음.'}

## {'결정' if final and not dryrun else '현재 기준으로 내리면'}

{DECISION_TEXT[a['decision']]}
이유: {a['reason']}.
{(chr(10) + '리허설 결과라 실제 운영 결정이 아닙니다. 실제 결정은 `decision-final.md` 로 자동 생성됩니다.' + chr(10)) if dryrun else '' if final else chr(10) + '실험이 끝나기 전의 중간 값이라 확정이 아닙니다. 최종 결정은 마지막 날 이후 자동으로 만들어집니다.' + chr(10)}"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=run.DEFAULT_OUT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--final", action="store_true", help="최종 결정 문서로 만든다")
    ap.add_argument("--dry-run", action="store_true", help="사전 시뮬레이션(리허설) 결과로 표시한다")
    ap.add_argument("--label", help="제목에 넣을 날짜나 이름. 기본은 마지막 기록 날짜")
    args = ap.parse_args()

    exp, personas = run.load_experiment(), run.load_personas()
    rows = load_rows(args.input)
    if not rows:
        print("기록된 지표가 없습니다.")
        return 1
    analysis = analyze(rows, exp, personas)
    source = str(args.input.relative_to(ROOT)) if args.input.is_absolute() and ROOT in args.input.parents else str(args.input)
    text = render(analysis, exp, args.label or rows[-1]["date"], args.final or args.dry_run, source, dryrun=args.dry_run)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"{analysis['decision']} lift={analysis['lift']:+.1%} p={analysis['p']:.4f} → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
