#!/usr/bin/env python3
"""templates/ 의 12개 파일을 docs/prd/ 로 복사해 빈 PRD 뼈대를 만든다. (TODO 를 채워야 검증을 통과한다)

  python scaffold_prd.py "아이디어 한 줄" [--out docs/prd] [--force]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def scaffold(idea: str, out: Path, force: bool = False) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    existing = [p.name for p in out.glob("*.md")]
    if existing and not force:
        raise FileExistsError(f"{out} 에 이미 파일이 있다 ({len(existing)}개). 덮어쓰려면 --force")
    written = []
    for src in sorted(TEMPLATES.glob("*.md")):
        text = src.read_text(encoding="utf-8")
        if src.name == "00-overview.md":
            text = text.replace("## 한 줄 아이디어\n\nTODO", f"## 한 줄 아이디어\n\n{idea}\n\n(TODO: 아이디어를 한 문장으로 다듬는다. 이 파일은 마지막에 완성한다)")
        (out / src.name).write_text(text, encoding="utf-8")
        written.append(src.name)
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("idea")
    ap.add_argument("--out", type=Path, default=Path("docs/prd"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    try:
        names = scaffold(args.idea.strip(), args.out, args.force)
    except FileExistsError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"{len(names)}개 파일 생성 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
