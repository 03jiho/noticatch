#!/usr/bin/env python3
"""docs/prd/ 의 PRD 12개 파일이 lean-prd 규격을 지키는지 검사한다.

  python validate_prd.py [PRD 폴더] [--stage generate|final]

stage
  generate  PRD 를 처음 만든 직후. 11-cycle-log 가 '아직 사이클 없음' 이어도 통과.
  final     BML 사이클을 1회 이상 돌린 뒤. 사이클 기록·결정·회고가 있어야 통과. (기본값)

종료 코드 0 = 통과, 1 = 위반 있음. 위반은 한 줄에 하나씩 출력한다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # Windows 콘솔(cp949/cp1252)에서도 한글이 깨지거나 죽지 않게
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REQUIRED = {
    "00-overview.md": ["한 줄 아이디어", "현재 결정 상태", "핵심 가설 요약", "문서 지도"],
    "01-problem-customer.md": ["고객 세그먼트", "문제", "기존 대안과 한계", "첫 고객(Early adopter) 정의"],
    "02-hypotheses.md": ["가설 목록", "위험도 평가", "가장 위험한 가설"],
    "03-metrics.md": ["지표 정의", "북극성 지표", "가드레일"],
    "04-mvp.md": ["MVP 유형", "In / Out", "성공 기준"],
    "05-experiments.md": ["실험 목록", "실험 순서"],
    "06-team.md": ["역할별 구성", "채용 우선순위", "Pivot 의사결정 규칙"],
    "07-tech-stack.md": ["계층별 스택", "비용 요약"],
    "08-milestones.md": ["마일스톤"],
    "09-pivot-safeguards.md": ["Pivot 옵션", "트리거", "예산·시간 상한"],
    "10-risks.md": ["리스크 등록부"],
    "11-cycle-log.md": ["BML 사이클 기록", "회고"],
}
MVP_TYPES = ("Wizard of Oz", "Concierge", "Landing page", "Single-feature", "Piecemeal")
PLACEHOLDER = re.compile(r"\bTODO\b|\bTBD\b|<[^<>\n]{1,40}에 맞게[^<>\n]*>|\(작성\)")


def sections(text: str) -> dict[str, str]:
    """'## 제목' 별로 본문을 나눈다."""
    out: dict[str, str] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1)
            out[current] = ""
        elif current is not None:
            out[current] += line + "\n"
    return out


def table_rows(body: str) -> list[list[str]]:
    """마크다운 표의 데이터 행(머리글과 구분선 제외)을 셀 목록으로 돌려준다."""
    rows = []
    lines = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("|")]
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        rows.append(cells)
    return rows


def has_digit(s: str) -> bool:
    """숫자가 있는가. 'MS2', 'H1' 같은 ID 속 숫자는 세지 않는다."""
    return bool(re.search(r"\d", re.sub(r"\b(?:MS|H|M|E|P|R)\d+\b", "", s)))


class Checker:
    def __init__(self, root: Path, stage: str):
        self.root, self.stage = root, stage
        self.errors: list[str] = []
        self.texts: dict[str, str] = {}
        self.secs: dict[str, dict[str, str]] = {}

    def err(self, file: str, msg: str) -> None:
        self.errors.append(f"{file}: {msg}")

    # ------------------------------------------------------------ 구조
    def load(self) -> None:
        extra = sorted(p.name for p in self.root.glob("*.md") if p.name not in REQUIRED)
        for name in REQUIRED:
            path = self.root / name
            if not path.is_file():
                self.err(name, "파일이 없다")
                continue
            self.texts[name] = path.read_text(encoding="utf-8")
            self.secs[name] = sections(self.texts[name])
        if extra:
            self.err("docs/prd", f"규격에 없는 파일: {', '.join(extra)} (정확히 12개여야 한다)")
        for name, text in self.texts.items():
            for heading in REQUIRED[name]:
                if heading not in self.secs[name]:
                    self.err(name, f"필수 헤딩 '## {heading}' 이 없다")
                elif not self.secs[name][heading].strip():
                    self.err(name, f"'## {heading}' 내용이 비어 있다")
            hit = PLACEHOLDER.search(text)
            if hit:
                self.err(name, f"자리표시자가 남아 있다: '{hit.group(0)}'")

    def rows(self, name: str, heading: str, ncols: int, prefix: str) -> list[list[str]]:
        body = self.secs.get(name, {}).get(heading, "")
        out = []
        for cells in table_rows(body):
            if not cells or not re.fullmatch(prefix + r"\d+", cells[0]):
                continue
            if len(cells) != ncols:
                self.err(name, f"{cells[0]} 행의 열이 {len(cells)}개다 (필요 {ncols}개)")
                continue
            out.append(cells)
        return out

    # ------------------------------------------------------------ 파일별
    def check(self) -> list[str]:
        self.load()
        H = self.hypotheses()
        M = self.metrics(H)
        self.mvp(H)
        self.experiments(H, M)
        self.team()
        self.tech()
        P = self.pivots(H)
        self.milestones(H, P)
        self.risks(H)
        self.overview(H)
        self.cycle_log(H)
        return self.errors

    def hypotheses(self) -> dict[str, int]:
        f = "02-hypotheses.md"
        rows = self.rows(f, "가설 목록", 7, "H")
        if not rows:
            self.err(f, "H# 행이 하나도 없다")
        ids, risk = [], {}
        for c in rows:
            ids.append(c[0])
            try:
                impact, unc, score = int(c[3]), int(c[4]), int(c[5])
            except ValueError:
                self.err(f, f"{c[0]}: 영향·불확실성·위험도는 정수여야 한다")
                continue
            if not (1 <= impact <= 5 and 1 <= unc <= 5):
                self.err(f, f"{c[0]}: 영향·불확실성은 1~5")
            if score != impact * unc:
                self.err(f, f"{c[0]}: 위험도 {score} != 영향 {impact} x 불확실성 {unc}")
            risk[c[0]] = score
            if not has_digit(c[6]) and len(c[6]) < 10:
                self.err(f, f"{c[0]}: 반증 조건이 구체적이지 않다")
            if len(c[1]) < 20:
                self.err(f, f"{c[0]}: 가설 문장이 너무 짧다 (누가/왜/무엇을 20자 이상)")
        if len(set(ids)) != len(ids):
            self.err(f, "H# 가 중복되었다")
        body = self.secs.get(f, {}).get("가장 위험한 가설", "")
        picked = re.findall(r"H\d+", body)
        if risk and body:
            if not picked:
                self.err(f, "'가장 위험한 가설' 에 H# 가 없다")
            elif picked[0] not in risk:
                self.err(f, f"'가장 위험한 가설' 의 {picked[0]} 가 가설 목록에 없다")
            elif risk[picked[0]] < max(risk.values()):
                self.err(f, f"{picked[0]} 의 위험도 {risk[picked[0]]} 는 최고점 {max(risk.values())} 보다 낮다")
            if "선정 이유" not in body:
                self.err(f, "'가장 위험한 가설' 에 '선정 이유' 가 없다")
        return risk

    def metrics(self, H: dict[str, int]) -> set[str]:
        f = "03-metrics.md"
        rows = self.rows(f, "지표 정의", 6, "M")
        seen_h = set()
        for c in rows:
            if c[1] not in H:
                self.err(f, f"{c[0]}: 가설 {c[1]} 이 02-hypotheses 에 없다")
            seen_h.add(c[1])
            if not has_digit(c[4]):
                self.err(f, f"{c[0]}: 기준값에 숫자가 없다")
        for h in H:
            if h not in seen_h:
                self.err(f, f"{h} 를 재는 지표(M#)가 없다")
        return {c[0] for c in rows}

    def mvp(self, H: dict[str, int]) -> None:
        f = "04-mvp.md"
        kind = self.secs.get(f, {}).get("MVP 유형", "")
        if kind and not any(t.lower() in kind.lower() for t in MVP_TYPES):
            self.err(f, f"MVP 유형은 {', '.join(MVP_TYPES)} 중 하나를 써야 한다")
        body = self.secs.get(f, {}).get("In / Out", "")
        ins = outs = 0
        for c in table_rows(body):
            if len(c) != 4:
                self.err(f, f"In/Out 표의 열은 4개여야 한다: {c[0] if c else ''}")
                continue
            if c[1] == "In":
                ins += 1
                if c[2] not in H:
                    self.err(f, f"In 항목 '{c[0]}' 에 검증 가설(H#)이 없다")
            elif c[1] == "Out":
                outs += 1
            else:
                self.err(f, f"구분은 In 또는 Out: '{c[0]}'")
        if not ins or not outs:
            self.err(f, "In 과 Out 이 모두 있어야 한다")
        if not has_digit(self.secs.get(f, {}).get("성공 기준", "")):
            self.err(f, "성공 기준에 숫자가 없다")

    def experiments(self, H: dict[str, int], M: set[str]) -> set[str]:
        f = "05-experiments.md"
        rows = self.rows(f, "실험 목록", 7, "E")
        seen = set()
        for c in rows:
            if c[1] not in H:
                self.err(f, f"{c[0]}: 가설 {c[1]} 없음")
            if c[2] not in M:
                self.err(f, f"{c[0]}: 지표 {c[2]} 없음")
            seen.add(c[1])
            if not has_digit(c[5]):
                self.err(f, f"{c[0]}: 통과 기준에 숫자가 없다")
        for h in H:
            if h not in seen:
                self.err(f, f"{h} 를 검증하는 실험(E#)이 없다")
        return {c[0] for c in rows}

    def team(self) -> None:
        f = "06-team.md"
        data = table_rows(self.secs.get(f, {}).get("역할별 구성", ""))  # 첫 칸이 역할 이름이라 H#/M# 식 접두어 검사는 하지 않는다
        if len(data) < 2:
            self.err(f, "역할이 2개 이상 있어야 한다")
        for c in data:
            if len(c) != 5:
                self.err(f, f"역할 표의 열은 5개여야 한다: {c[0] if c else ''}")
                continue
            try:
                float(c[1])
            except ValueError:
                self.err(f, f"{c[0]}: FTE 는 숫자(예: 0.5)")
            if not re.search(r"MS\d", c[2]):
                self.err(f, f"{c[0]}: 담당 마일스톤(MS#)이 없다")
            if not (c[3].isdigit() or c[3] == "보유"):
                self.err(f, f"{c[0]}: 채용 우선순위는 숫자 또는 '보유'")
        rule = self.secs.get(f, {}).get("Pivot 의사결정 규칙", "")
        if rule.strip() and (len(rule.strip()) < 60 or not re.search(r"P\d", rule)):
            self.err(f, "Pivot 의사결정 규칙은 60자 이상이고 P# 를 인용해야 한다")

    def tech(self) -> None:
        f = "07-tech-stack.md"
        data = table_rows(self.secs.get(f, {}).get("계층별 스택", ""))
        if len(data) < 3:
            self.err(f, "계층이 3개 이상 있어야 한다 (예: 프런트, 백엔드, 데이터, 배포)")
        for c in data:
            if len(c) != 6:
                self.err(f, f"스택 표의 열은 6개여야 한다 (계층·선택·근거·대안·월 비용·전환 조건): {c[0] if c else ''}")
                continue
            for name, cell in zip(("계층", "선택", "근거", "대안", "월 비용", "전환 조건"), c, strict=True):
                if not cell or cell in ("-", "없음"):
                    self.err(f, f"{c[0]}: '{name}' 이 비어 있다")
            if not has_digit(c[4]):
                self.err(f, f"{c[0]}: 월 비용에 숫자가 없다 (무료면 0원)")
            if not has_digit(c[5]):
                self.err(f, f"{c[0]}: 전환 조건에 숫자가 없다 (언제 바꿀지 기준)")

    def pivots(self, H: dict[str, int]) -> set[str]:
        f = "09-pivot-safeguards.md"
        rows = self.rows(f, "Pivot 옵션", 6, "P")
        if len(rows) < 2:
            self.err(f, "Pivot 옵션(P#)이 2개 이상 있어야 한다")
        for c in rows:
            if not has_digit(c[2]):
                self.err(f, f"{c[0]}: 트리거에 숫자가 없다")
            if c[3] not in H:
                self.err(f, f"{c[0]}: 가설 {c[3]} 없음")
        if not has_digit(self.secs.get(f, {}).get("예산·시간 상한", "")):
            self.err(f, "예산·시간 상한에 숫자가 없다")
        return {c[0] for c in rows}

    def milestones(self, H: dict[str, int], P: set[str]) -> None:
        f = "08-milestones.md"
        rows = self.rows(f, "마일스톤", 6, "MS")
        ids = [c[0] for c in rows]
        for need in ("MS0", "MS1", "MS2", "MS3"):
            if need not in ids:
                self.err(f, f"{need} 가 없다 (MS0~MS3 필수)")
        for c in rows:
            if c[1] not in H:
                self.err(f, f"{c[0]}: 검증 가설 {c[1]} 없음")
            if not has_digit(c[2]):
                self.err(f, f"{c[0]}: 종료 조건에 숫자가 없다")
            if c[4] not in P:
                self.err(f, f"{c[0]}: No-Go 시 Pivot 옵션 {c[4]} 이 09-pivot-safeguards 에 없다")

    def risks(self, H: dict[str, int]) -> None:
        f = "10-risks.md"
        rows = self.rows(f, "리스크 등록부", 6, "R")
        if not rows:
            self.err(f, "R# 행이 없다")
        for c in rows:
            if c[1] not in H:
                self.err(f, f"{c[0]}: 가설 {c[1]} 없음")

    def overview(self, H: dict[str, int]) -> None:
        f = "00-overview.md"
        text = self.texts.get(f, "")
        for h in H:
            if h not in text:
                self.err(f, f"핵심 가설 요약에 {h} 가 없다")
        if H:
            top = max(H, key=lambda k: H[k])
            if "★" not in text:
                self.err(f, f"가장 위험한 가설({top})에 ★ 표시가 없다")
        if self.stage == "final" and not re.search(r"Pivot|Persevere", self.secs.get(f, {}).get("현재 결정 상태", "")):
            self.err(f, "현재 결정 상태에 Pivot/Persevere 결정이 반영되지 않았다")

    def cycle_log(self, H: dict[str, int]) -> None:
        f = "11-cycle-log.md"
        text = self.texts.get(f, "")
        cycles = re.findall(r"^###\s+Cycle\s+\d+", text, flags=re.M)
        if self.stage == "generate":
            return
        if not cycles:
            self.err(f, "BML 사이클 기록(### Cycle N)이 없다")
            return
        for block in re.split(r"^###\s+Cycle", text, flags=re.M)[1:]:
            for key in ("가설", "실험", "측정", "결정", "배운 것"):
                if key not in block:
                    self.err(f, f"사이클 기록에 '{key}' 가 없다")
            if not re.search(r"Pivot|Persevere", block):
                self.err(f, "사이클 기록에 Pivot/Persevere 결정이 없다")
            if not has_digit(block):
                self.err(f, "사이클 기록에 측정한 숫자가 없다")
        retro = self.secs.get(f, {}).get("회고", "")
        if len(retro.strip()) < 80:
            self.err(f, "회고가 너무 짧다 (80자 이상: 잘된 점, 안 된 점, 다음 사이클)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default="docs/prd")
    ap.add_argument("--stage", choices=["generate", "final"], default="final")
    args = ap.parse_args()
    errors = Checker(Path(args.root), args.stage).check()
    if errors:
        print(f"PRD 검증 실패 ({len(errors)}건)")
        for e in errors:
            print(" -", e)
        return 1
    print(f"PRD 검증 통과 (stage={args.stage})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
