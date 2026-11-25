#!/usr/bin/env python3
"""A/B 실험 하루치 합성 세션을 만들어 metrics/*.jsonl 에 한 줄로 기록한다.

세션의 주인은 experiments/personas.json 의 가상 페르소나다. 비중대로 뽑고, variant 는 dashboard/flags.js 와
같은 해시(scripts/ab_simulation.py)로 정하고, 클릭 여부는 그 페르소나의 variant 별 클릭 성향으로 뽑는다.
같은 날짜는 항상 같은 결과가 나오며(날짜를 seed 로 씀), 같은 날짜를 다시 실행하면 그 줄을 덮어쓴다.

주의: 실제 방문자 데이터가 아니라 가정(페르소나의 성향)을 돌린 시뮬레이션이다.

  python scripts/experiment_run.py --date 2026-11-26
  python scripts/experiment_run.py --dry-run-days 14 --out metrics/experiment-dryrun.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path

import ab_simulation as ab

ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT = ROOT / "experiments" / "cta-style.json"
PERSONAS = ROOT / "experiments" / "personas.json"
DEFAULT_OUT = ROOT / "metrics" / "experiment-daily.jsonl"


def load_experiment() -> dict:
    return json.loads(EXPERIMENT.read_text(encoding="utf-8"))


def load_personas() -> list[dict]:
    return json.loads(PERSONAS.read_text(encoding="utf-8"))["personas"]


def flag_experiment() -> dict:
    """dashboard/flags.config.json 의 같은 키 실험(할당 규칙)."""
    config = json.loads(ab.CONFIG.read_text(encoding="utf-8"))
    return next(e for e in config["experiments"] if e["key"] == "cta-style")


def simulate_day(label: str, sessions: int, personas: list[dict]) -> dict:
    """label(날짜 또는 dry-run 일차)을 seed 로 하루치 세션을 만든다."""
    exp = flag_experiment()
    rng = random.Random(f"cta-style:{label}")
    weights = [p["ab"]["weight"] for p in personas]
    variants = {v["key"]: {"exposed": 0, "clicks": 0} for v in exp["variants"]}
    by_persona = {p["id"]: {v: {"exposed": 0, "clicks": 0} for v in variants} for p in personas}
    for i in range(sessions):
        persona = rng.choices(personas, weights)[0]
        variant = ab.assign(exp, f"sim-{label}-{i}")
        clicked = rng.random() < persona["ab"][variant]
        for bucket in (variants[variant], by_persona[persona["id"]][variant]):
            bucket["exposed"] += 1
            bucket["clicks"] += int(clicked)
    return {"date": label, "sessions": sessions, "synthetic": True, "variants": variants, "personas": by_persona}


def upsert(path: Path, row: dict) -> None:
    """같은 date 의 줄이 있으면 바꾸고, 없으면 덧붙인다. 날짜순으로 정렬해 저장한다."""
    rows = []
    if path.exists():
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r["date"] != row["date"]] + [row]
    rows.sort(key=lambda r: str(r["date"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", help="기록할 날짜(YYYY-MM-DD). 기본은 오늘")
    ap.add_argument("--dry-run-days", type=int, help="실험 기간 전체를 일차(day-01...)로 미리 시뮬레이션")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    exp, personas = load_experiment(), load_personas()
    if args.dry_run_days:
        args.out.unlink(missing_ok=True)
        for day in range(1, args.dry_run_days + 1):
            upsert(args.out, simulate_day(f"day-{day:02d}", exp["sessions_per_day"], personas))
        print(f"dry-run {args.dry_run_days}일 → {args.out}")
        return 0

    today = date.fromisoformat(args.date) if args.date else date.today()
    start, end = date.fromisoformat(exp["start"]), date.fromisoformat(exp["end"])
    if not start <= today <= end:
        print(f"{today} 은 실험 기간({start} ~ {end}) 밖이라 기록하지 않습니다.")
        return 0
    upsert(args.out, simulate_day(today.isoformat(), exp["sessions_per_day"], personas))
    print(f"{today} 기록 완료 ({(today - start).days + 1}/{(end - start).days + 1}일차) → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
