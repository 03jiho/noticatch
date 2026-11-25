#!/usr/bin/env python3
"""BML Cycle 1 의 측정(Measure) 단계: 마감일 추출기를 실제 공지 샘플로 평가한다.

  python experiments/cycle-1/run_eval.py [--out experiments/cycle-1]

결과: results.json(기계용), results.md(사람용). 통과 기준은 docs/prd/05-experiments.md 의 E1 (정확도 90% 이상)로,
실험 전에 이미 커밋되어 있다.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from noticatch.deadlines import extract_deadline  # noqa: E402

for _stream in (sys.stdout, sys.stderr):  # Windows 콘솔(cp949/cp1252)에서도 한글이 깨지거나 죽지 않게
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

THRESHOLD = 0.90


def evaluate(cases: list[dict]) -> list[dict]:
    rows = []
    for c in cases:
        got = extract_deadline(c["snippet"], today=date.fromisoformat(c["ref_date"]))
        got_s = got.isoformat() if got else None
        rows.append({**c, "got": got_s, "ok": got_s == c["expected"]})
    return rows


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
    except Exception:
        return "unknown"


def render(rows: list[dict], accuracy: float, sha: str) -> str:
    ok = sum(r["ok"] for r in rows)
    lines = [
        "# Cycle 1 측정 결과: 마감일 추출 정확도 (E1)",
        "",
        f"- 정확도: **{ok}/{len(rows)} = {accuracy:.1%}** (통과 기준 {THRESHOLD:.0%} 이상) → {'통과' if accuracy >= THRESHOLD else '**미달**'}",
        f"- 추출기 버전: 커밋 `{sha}` (`noticatch/deadlines.py`)",
        "- 데이터: 공개 학교 게시판 공지 19건에서 마감일이 적힌 줄만 발췌 (`corpus.json`). 정답은 사람이 원문을 읽고 붙였다.",
        "",
        "| id | 판정 | 정답 | 추출 | 원문 줄 |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['id']} | {'✅' if r['ok'] else '❌'} | {r['expected'] or '없음'} | {r['got'] or '없음'} | {r['snippet']} |")
    fails = [r for r in rows if not r["ok"]]
    lines += ["", "## 틀린 사례의 원인", ""]
    for r in fails:
        lines.append(f"- **{r['id']}**: 정답 {r['expected'] or '없음'}, 추출 {r['got'] or '없음'} — {r.get('cause', '')}".rstrip(" —"))
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE)
    args = ap.parse_args()
    cases = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))["cases"]
    rows = evaluate(cases)
    accuracy = sum(r["ok"] for r in rows) / len(rows)
    sha = git_sha()
    (args.out / "results.json").write_text(
        json.dumps({"accuracy": accuracy, "n": len(rows), "threshold": THRESHOLD, "extractor_commit": sha, "rows": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out / "results.md").write_text(render(rows, accuracy, sha), encoding="utf-8")
    print(f"{sum(r['ok'] for r in rows)}/{len(rows)} = {accuracy:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
