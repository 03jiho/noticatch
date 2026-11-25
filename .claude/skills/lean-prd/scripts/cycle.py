#!/usr/bin/env python3
"""`/lean-prd cycle`: BML 사이클 1회의 결과를 PRD 에 반영한다.

Learn 단계에서 내린 결정(Pivot/Persevere)과 측정값을 받아 아래 파일을 한꺼번에 고친 뒤 검증한다.
  02-hypotheses   '검증 상태' 절에 해당 가설의 결과를 기록
  11-cycle-log    '### Cycle N' 블록을 추가하고 회고를 덧붙임
  09-pivot-safeguards  Pivot 이면 '실행된 Pivot' 절에 기록
  00-overview     '최근 결정' 줄을 갱신

  python cycle.py --hypothesis H2 --experiment E2 --measured "12/19 = 63%" \\
      --decision pivot --pivot P1 --learned "..." --retro-good "..." --retro-bad "..." --retro-next "..."
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def replace_or_append_section(text: str, heading: str, body: str, append: bool = False) -> str:
    """'## heading' 절의 본문을 바꾼다(append=True 면 덧붙인다). 절이 없으면 파일 끝에 만든다."""
    pattern = re.compile(rf"(^##\s+{re.escape(heading)}\s*\n)(.*?)(?=^##\s|\Z)", re.S | re.M)
    m = pattern.search(text)
    if not m:
        return text.rstrip("\n") + f"\n\n## {heading}\n\n{body.strip()}\n"
    new_body = (m.group(2).rstrip("\n") + "\n\n" + body.strip() + "\n\n") if append else ("\n" + body.strip() + "\n\n")
    return re.sub(r"\n{3,}", "\n\n", text[: m.start()] + m.group(1) + new_body + text[m.end():])


def next_cycle_number(log: str) -> int:
    nums = [int(n) for n in re.findall(r"^###\s+Cycle\s+(\d+)", log, flags=re.M)]
    return max(nums, default=0) + 1


def apply(root: Path, a: argparse.Namespace) -> int:
    decision = "Pivot" if a.decision == "pivot" else "Persevere"
    today = a.date or date.today().isoformat()
    if decision == "Pivot" and not a.pivot:
        raise SystemExit("--decision pivot 이면 --pivot P# 가 필요하다")

    log_path = root / "11-cycle-log.md"
    log = log_path.read_text(encoding="utf-8")
    n = next_cycle_number(log)
    if "아직 실행한 사이클이 없습니다." in log:
        log = log.replace("아직 실행한 사이클이 없습니다.\n", "")
    block = (
        f"### Cycle {n} — {today}\n\n"
        f"- 가설: {a.hypothesis}\n- 실험: {a.experiment}\n- 측정: {a.measured}\n"
        f"- 결정: **{decision}**{(' → ' + a.pivot) if a.pivot else ''} — {a.reason}\n- 배운 것: {a.learned}\n"
    )
    log = replace_or_append_section(log, "BML 사이클 기록", block, append=True)
    retro = f"**Cycle {n}**\n\n- 잘된 점: {a.retro_good}\n- 안 된 점: {a.retro_bad}\n- 다음 사이클: {a.retro_next}"
    if "아직 없음." in log:
        log = log.replace("아직 없음.\n", "")
    log = replace_or_append_section(log, "회고", retro, append=True)
    log_path.write_text(log, encoding="utf-8")

    hyp_path = root / "02-hypotheses.md"
    hyp = hyp_path.read_text(encoding="utf-8")
    status = {"pivot": "기각 또는 수정 필요", "persevere": "지지됨"}[a.decision]
    line = f"- {a.hypothesis}: {status} (Cycle {n}, {today}) — {a.measured}"
    sec = re.search(r"^##\s+검증 상태\s*\n(.*?)(?=^##\s|\Z)", hyp, re.S | re.M)
    existing = sec.group(1) if sec else ""
    kept = [ln for ln in existing.splitlines() if ln.strip() and not ln.startswith(f"- {a.hypothesis}:")]
    hyp = replace_or_append_section(hyp, "검증 상태", "\n".join([*kept, line]))
    hyp_path.write_text(hyp, encoding="utf-8")

    if a.pivot:
        piv_path = root / "09-pivot-safeguards.md"
        piv = piv_path.read_text(encoding="utf-8")
        piv = replace_or_append_section(piv, "실행된 Pivot", f"- Cycle {n} ({today}): {a.pivot} 실행 — {a.reason}", append=True)
        piv_path.write_text(piv, encoding="utf-8")

    ov_path = root / "00-overview.md"
    ov = ov_path.read_text(encoding="utf-8")
    recent = f"- 최근 결정: **{decision}**{(' (' + a.pivot + ')') if a.pivot else ''} — Cycle {n}, {a.hypothesis}, {a.measured}. {a.reason}"
    if re.search(r"^- 최근 결정:.*$", ov, flags=re.M):
        ov = re.sub(r"^- 최근 결정:.*$", lambda _: recent, ov, flags=re.M)
    else:
        ov = replace_or_append_section(ov, "현재 결정 상태", recent)
    ov_path.write_text(ov, encoding="utf-8")

    print(f"Cycle {n} 반영 완료: {decision}")
    return subprocess.call([sys.executable, str(HERE / "validate_prd.py"), str(root), "--stage", "final"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("docs/prd"))
    ap.add_argument("--hypothesis", required=True)
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--measured", required=True, help="측정값(숫자 포함). 예: '12/19 = 63%%'")
    ap.add_argument("--decision", required=True, choices=["pivot", "persevere"])
    ap.add_argument("--pivot", help="Pivot 일 때 실행할 옵션 ID (P#)")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--learned", required=True)
    ap.add_argument("--retro-good", required=True)
    ap.add_argument("--retro-bad", required=True)
    ap.add_argument("--retro-next", required=True)
    ap.add_argument("--date")
    args = ap.parse_args()
    return apply(args.root, args)


if __name__ == "__main__":
    sys.exit(main())
