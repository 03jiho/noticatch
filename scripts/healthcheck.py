"""배포된 서비스가 살아 있는지 확인한다. 표준 라이브러리만 쓴다.

확인하는 것
1. <url>/healthz 가 200 이고 본문이 ok 이다.
2. (--expect-sha) <url>/version.json 의 sha 가 방금 배포한 커밋과 같다. → 옛 버전이 아니라 새 버전이 응답하는지 본다.
3. (--max-latency-ms) 응답 시간이 기준 이하이다.

실패하면 --retries 번까지 --interval 초 간격으로 다시 시도한다. (막 뜬 서비스·CDN 전파 지연 대응)
모두 통과하면 종료 코드 0, 끝까지 실패하면 1.

사용 예
  python3 scripts/healthcheck.py https://example.run.app --expect-sha "$GITHUB_SHA" --retries 10 --interval 6
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def fetch(url: str, timeout: float) -> tuple[int, str, float]:
    """(상태 코드, 본문, 걸린 시간(ms)). 연결 실패는 상태 코드 0."""
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": "noticatch-healthcheck", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read(65536).decode("utf-8", errors="replace")
            return res.status, body, (time.monotonic() - start) * 1000
    except urllib.error.HTTPError as e:
        return e.code, "", (time.monotonic() - start) * 1000
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, "", (time.monotonic() - start) * 1000


def check_once(base: str, expect_sha: str | None, max_latency_ms: float | None, timeout: float) -> tuple[bool, str]:
    base = base.rstrip("/")
    code, body, ms = fetch(f"{base}/healthz", timeout)
    if code != 200:
        return False, f"/healthz 상태 {code or '연결 실패'}"
    if body.strip() != "ok":
        return False, f"/healthz 본문이 ok 가 아님: {body.strip()[:40]!r}"
    if max_latency_ms is not None and ms > max_latency_ms:
        return False, f"응답이 느림: {ms:.0f}ms > {max_latency_ms:.0f}ms"
    detail = f"/healthz 200 ({ms:.0f}ms)"
    if expect_sha:
        code, body, _ = fetch(f"{base}/version.json", timeout)
        if code != 200:
            return False, f"/version.json 상태 {code or '연결 실패'}"
        try:
            sha = json.loads(body).get("sha", "")
        except json.JSONDecodeError:
            return False, "/version.json 이 JSON 이 아님"
        if sha != expect_sha:
            return False, f"배포된 리비전이 다름: {sha[:7] or '없음'} (기대 {expect_sha[:7]})"
        detail += f", 리비전 {sha[:7]} 일치"
    return True, detail


def check(base: str, *, expect_sha: str | None = None, max_latency_ms: float | None = None,
          retries: int = 1, interval: float = 5.0, timeout: float = 10.0, sleep=time.sleep) -> tuple[bool, list[str]]:
    """재시도하며 확인한다. (통과 여부, 시도별 기록)"""
    log: list[str] = []
    for attempt in range(1, max(retries, 1) + 1):
        ok, detail = check_once(base, expect_sha, max_latency_ms, timeout)
        log.append(f"[{attempt}/{max(retries, 1)}] {'OK ' if ok else 'FAIL'} {base} — {detail}")
        if ok:
            return True, log
        if attempt < retries:
            sleep(interval)
    return False, log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--expect-sha")
    ap.add_argument("--max-latency-ms", type=float)
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--timeout", type=float, default=10.0)
    args = ap.parse_args()
    ok, log = check(args.url, expect_sha=args.expect_sha, max_latency_ms=args.max_latency_ms,
                    retries=args.retries, interval=args.interval, timeout=args.timeout)
    print("\n".join(log))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
