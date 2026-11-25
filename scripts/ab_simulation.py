#!/usr/bin/env python3
"""A/B 테스트 할당·분석 도구.

dashboard/flags.js 와 같은 해시(FNV-1a)·같은 규칙으로 사용자를 variant 에 나누고,
가상 사용자 이벤트(exposure, cta_click)로 실험 로그를 만든다.

주의: 여기서 만드는 이벤트는 **시뮬레이션**이다. 실제 방문자 데이터가 아니라, 할당 일관성과
분석 로직이 동작함을 보이기 위한 합성 데이터다. (--seed 가 같으면 결과도 같다)

  python scripts/ab_simulation.py --users 10000 --out docs/experiments
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "dashboard" / "flags.config.json"


def hash32(text: str) -> int:
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def bucket(key: str, user_id: str) -> int:
    return hash32(f"{key}:{user_id}") % 10000


def assign(experiment: dict, user_id: str) -> str:
    variants = experiment["variants"]
    total = sum(v["weight"] for v in variants)
    point = bucket("exp:" + experiment["key"], user_id) / 10000 * total
    acc = 0
    for v in variants:
        acc += v["weight"]
        if point < acc:
            return v["key"]
    return variants[-1]["key"]


def evaluate(flag: dict, user_id: str, env: str, groups: list[str]) -> tuple[bool, str]:
    """flags.js 의 evaluate 와 같은 규칙."""
    if flag.get("enabled") is False:
        return False, "kill-switch"
    if "environments" in flag and env not in flag["environments"]:
        return False, "environment"
    if user_id in flag.get("allowUsers", []):
        return True, "user"
    if any(g in groups for g in flag.get("allowGroups", [])):
        return True, "group"
    if isinstance(flag.get("percentage"), (int, float)):
        return (bucket(flag["key"], user_id) < flag["percentage"] * 100), "percentage"
    if "allowUsers" in flag or "allowGroups" in flag:
        return False, "not-targeted"
    return True, "default"


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> tuple[float, float]:
    """두 비율 차이의 z 값과 양측 p 값. 표본이 비어 있으면 (0, 1)."""
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    p1, p2 = x1 / n1, x2 / n2
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p2 - p1) / se
    p = math.erfc(abs(z) / math.sqrt(2))
    return z, p


def simulate(experiment: dict, users: int, rates: dict[str, float], seed: int) -> dict:
    rng = random.Random(seed)
    events: list[dict] = []
    exposed = {v["key"]: 0 for v in experiment["variants"]}
    converted = {v["key"]: 0 for v in experiment["variants"]}
    for i in range(users):
        uid = f"sim-{i}"
        v = assign(experiment, uid)
        assert v == assign(experiment, uid)  # 같은 사용자는 다시 물어도 같은 variant
        exposed[v] += 1
        events.append({"name": "exposure", "userId": uid, "experiment": experiment["key"], "variant": v})
        if rng.random() < rates[v]:
            converted[v] += 1
            events.append({"name": experiment["metric"], "userId": uid, "experiment": experiment["key"], "variant": v})
    keys = [v["key"] for v in experiment["variants"]]
    z, p = two_proportion_z(converted[keys[0]], exposed[keys[0]], converted[keys[1]], exposed[keys[1]])
    return {"exposed": exposed, "converted": converted, "z": z, "p": p, "events": events, "keys": keys}


def render_log(experiment: dict, result: dict, users: int, rates: dict[str, float], seed: int) -> str:
    a, b = result["keys"]
    rows = []
    for k in result["keys"]:
        n, x = result["exposed"][k], result["converted"][k]
        rows.append(f"| `{k}` | {n:,} | {n / users:.1%} | {x:,} | {(x / n if n else 0):.2%} |")
    verdict = "p < 0.05: 차이가 통계적으로 유의함" if result["p"] < 0.05 else "p ≥ 0.05: 차이가 유의하지 않음"
    return f"""# 실험 로그: `{experiment['key']}`

> **시뮬레이션 결과입니다.** 가상 사용자 {users:,}명과 가정한 전환율(`{a}` {rates[a]:.0%}, `{b}` {rates[b]:.0%}, seed={seed})으로
> 만든 합성 데이터이며 실제 방문자 데이터가 아닙니다. 할당 일관성과 분석 로직이 동작함을 보이는 용도입니다.
> 재현: `python scripts/ab_simulation.py --users {users} --seed {seed} --out docs/experiments`

## 설정

- 가설: {experiment['description']}
- variant: {', '.join(f"`{v['key']}`({v['weight']}%)" for v in experiment['variants'])}
- 성공 지표: `{experiment['metric']}` / 노출 이벤트: `exposure` (사용자·실험당 1회)

## 할당 일관성

- 같은 사용자 id 를 두 번 할당해 같은 variant 가 나오는지 {users:,}명 모두 확인했습니다. (어긋나면 스크립트가 중단됨)
- 할당은 `FNV-1a("exp:{experiment['key']}:<userId>") mod 10000` 으로 정해지므로 저장소나 서버 없이도 일정합니다.
- 브라우저 구현(`dashboard/flags.js`)과 같은 결과를 내는지는 `tests/test_flags.py` 가 Node 로 비교합니다.

## 결과

| variant | 노출 | 비율 | {experiment['metric']} | 전환율 |
|---|---|---|---|---|
{chr(10).join(rows)}

- z = {result['z']:.2f}, p = {result['p']:.4f} → {verdict}
- 원시 이벤트: [`events-sample.jsonl`](events-sample.jsonl) (앞 200건)
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--users", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--rate-control", type=float, default=0.10)
    ap.add_argument("--rate-treatment", type=float, default=0.12)
    ap.add_argument("--out", type=Path, default=Path("docs/experiments"))
    args = ap.parse_args()

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    exp = config["experiments"][0]
    rates = {exp["variants"][0]["key"]: args.rate_control, exp["variants"][1]["key"]: args.rate_treatment}
    result = simulate(exp, args.users, rates, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ab-log.md").write_text(render_log(exp, result, args.users, rates, args.seed), encoding="utf-8")
    with open(args.out / "events-sample.jsonl", "w", encoding="utf-8") as f:
        for e in result["events"][:200]:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"exposed={result['exposed']} converted={result['converted']} z={result['z']:.2f} p={result['p']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
