"""npm audit / Snyk 의 JSON 결과를 읽어 사람이 보기 좋은 보고서(Markdown)로 만든다. 표준 라이브러리만 쓴다.

- npm audit : `npm audit --json` 출력 (npm 7 이상 형식)
- Snyk      : `snyk test --json` 출력 (선택)
- 기준 심각도(--threshold) 이상인 항목이 있으면 "조치 필요"로 센다. 이 값은 GITHUB_OUTPUT 으로 내보내
  워크플로우가 이슈를 열거나 닫는 데 쓴다.
- 스캔 자체가 실패한 경우(npm audit 이 오류를 돌려줌, JSON 이 아님)는 "취약점 없음"으로 넘기지 않고 오류로 끝낸다.

사용 예 (Actions)
  python3 scripts/security_report.py --npm audit.json --snyk snyk.json --threshold moderate \\
      --out report.md --github-output "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SEVERITIES = ["info", "low", "moderate", "high", "critical"]
RANK = {s: i for i, s in enumerate(SEVERITIES)}
# Snyk 은 moderate 대신 medium 을 쓴다.
ALIASES = {"medium": "moderate"}


class ScanError(Exception):
    """스캔 결과를 믿을 수 없을 때(스캔 실패)."""


def norm_severity(value: str | None) -> str:
    v = (value or "info").lower()
    v = ALIASES.get(v, v)
    return v if v in RANK else "info"


def parse_npm_audit(data: dict) -> list[dict]:
    """`npm audit --json` 결과를 [{tool, package, severity, title, url, fix}] 로 바꾼다."""
    if "error" in data:
        err = data["error"]
        raise ScanError(f"npm audit 실행 실패: {err.get('summary') or err.get('code') or err}")
    if "vulnerabilities" not in data:
        raise ScanError("npm audit 결과 형식을 알 수 없음 (vulnerabilities 키 없음)")
    out: list[dict] = []
    for name, v in sorted(data["vulnerabilities"].items()):
        advisories = [x for x in v.get("via", []) if isinstance(x, dict)]
        fix = v.get("fixAvailable")
        if isinstance(fix, dict):
            fix_text = f"{fix.get('name')}@{fix.get('version')}" + (" (메이저 업데이트)" if fix.get("isSemVerMajor") else "")
        else:
            fix_text = "업데이트 가능" if fix else "수정 버전 없음"
        if not advisories:
            # 다른 패키지의 취약점이 전파된 항목(via 가 문자열)
            out.append({"tool": "npm audit", "package": name, "severity": norm_severity(v.get("severity")),
                        "title": f"의존하는 패키지({', '.join(map(str, v.get('via', [])))})의 취약점", "url": "", "fix": fix_text})
            continue
        for a in advisories:
            out.append({"tool": "npm audit", "package": name, "severity": norm_severity(a.get("severity") or v.get("severity")),
                        "title": a.get("title", ""), "url": a.get("url", ""), "fix": fix_text})
    return out


def parse_snyk(data: dict) -> list[dict]:
    """`snyk test --json` 결과를 같은 형식으로 바꾼다."""
    if "error" in data and "vulnerabilities" not in data:
        raise ScanError(f"Snyk 실행 실패: {data.get('error')}")
    if "vulnerabilities" not in data:
        raise ScanError("Snyk 결과 형식을 알 수 없음 (vulnerabilities 키 없음)")
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for v in data["vulnerabilities"]:
        key = (v.get("id", ""), v.get("packageName", ""))
        if key in seen:
            continue
        seen.add(key)
        fixed = v.get("fixedIn") or []
        out.append({
            "tool": "Snyk", "package": v.get("packageName", "?"), "severity": norm_severity(v.get("severity")),
            "title": v.get("title", ""), "url": f"https://security.snyk.io/vuln/{v['id']}" if v.get("id") else "",
            "fix": f"{v.get('packageName')}@{fixed[0]} 이상" if fixed else "수정 버전 없음",
        })
    return out


def counts(findings: list[dict]) -> dict[str, int]:
    c = dict.fromkeys(SEVERITIES, 0)
    for f in findings:
        c[f["severity"]] += 1
    return c


def actionable(findings: list[dict], threshold: str) -> list[dict]:
    limit = RANK[norm_severity(threshold)]
    return sorted((f for f in findings if RANK[f["severity"]] >= limit), key=lambda f: -RANK[f["severity"]])


def render(findings: list[dict], threshold: str, tools: list[str], note: str = "") -> str:
    c = counts(findings)
    todo = actionable(findings, threshold)
    lines = ["## 의존성 보안 스캔 결과", ""]
    if note:
        lines += [f"> {note}", ""]
    lines += [f"- 스캔 도구: {', '.join(tools)}", f"- 조치 기준: **{norm_severity(threshold)}** 이상", ""]
    lines += ["| 심각도 | 건수 |", "|---|---|"]
    lines += [f"| {s} | {c[s]} |" for s in reversed(SEVERITIES)]
    lines.append("")
    if not todo:
        lines.append("조치가 필요한 취약점이 없습니다.")
        return "\n".join(lines) + "\n"
    lines += [f"### 조치가 필요한 항목 ({len(todo)}건)", "", "| 심각도 | 패키지 | 내용 | 해결 방법 | 도구 |", "|---|---|---|---|---|"]
    for f in todo:
        title = f"[{f['title']}]({f['url']})" if f["url"] else f["title"]
        lines.append(f"| {f['severity']} | `{f['package']}` | {title} | {f['fix']} | {f['tool']} |")
    lines += ["", "해결 방법: Dependabot 보안 업데이트 PR 이 열려 있는지 확인하고, 없으면 `npm audit fix` 로 올린 뒤 PR 로 보내 주세요."]
    return "\n".join(lines) + "\n"


def load_json(path: str, what: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ScanError(f"{what} 결과 파일을 읽을 수 없음({path}): {e}") from e


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--npm", required=True, help="npm audit --json 결과 파일")
    ap.add_argument("--snyk", help="snyk test --json 결과 파일 (선택)")
    ap.add_argument("--threshold", default="moderate", choices=[*SEVERITIES, "medium"])
    ap.add_argument("--out", required=True, help="Markdown 보고서 경로")
    ap.add_argument("--note", default="", help="보고서 맨 위에 넣을 안내 문구")
    ap.add_argument("--github-output", help="GITHUB_OUTPUT 파일 경로")
    args = ap.parse_args()

    try:
        findings = parse_npm_audit(load_json(args.npm, "npm audit"))
        tools = ["npm audit"]
        if args.snyk:
            findings += parse_snyk(load_json(args.snyk, "Snyk"))
            tools.append("Snyk")
    except ScanError as e:
        print(f"스캔 실패: {e}", file=sys.stderr)
        return 2

    todo = actionable(findings, args.threshold)
    Path(args.out).write_text(render(findings, args.threshold, tools, args.note), encoding="utf-8")
    highest = max((f["severity"] for f in findings), key=lambda s: RANK[s], default="none")
    print(f"전체 {len(findings)}건, 조치 필요 {len(todo)}건, 가장 높은 심각도: {highest}")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as f:
            f.write(f"total={len(findings)}\nactionable={len(todo)}\nhighest={highest}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
