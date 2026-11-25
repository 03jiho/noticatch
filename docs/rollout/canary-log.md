# 카나리 롤아웃 검증 로그

단계: 1% → 10% → 50% → 100% · 단계마다 3회 검사

### 시나리오 healthy: 100% 승격 완료

> 가상 헬스체크 값을 쓰는 시뮬레이션입니다. 실제 트래픽을 옮기지는 않습니다.

기준: 오류율 ≤ 2.0%, p95 ≤ 800ms

| 트래픽 | 검사 | 오류율 | p95 | 판정 |
|---|---|---|---|---|
| 1% | 1 | 0.2% | 190ms | 통과 |
| 1% | 2 | 0.3% | 200ms | 통과 |
| 1% | 3 | 0.4% | 210ms | 통과 |
| 10% | 1 | 0.2% | 190ms | 통과 |
| 10% | 2 | 0.3% | 200ms | 통과 |
| 10% | 3 | 0.4% | 210ms | 통과 |
| 50% | 1 | 0.2% | 190ms | 통과 |
| 50% | 2 | 0.3% | 200ms | 통과 |
| 50% | 3 | 0.4% | 210ms | 통과 |
| 100% | 1 | 0.2% | 190ms | 통과 |
| 100% | 2 | 0.3% | 200ms | 통과 |
| 100% | 3 | 0.4% | 210ms | 통과 |

실행했다면 쓸 명령:

```bash
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=1,STABLE=99
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=10,STABLE=90
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=50,STABLE=50
gcloud run services update-traffic noticatch-dashboard --to-latest
```

### 시나리오 error-spike: 롤백됨

> 가상 헬스체크 값을 쓰는 시뮬레이션입니다. 실제 트래픽을 옮기지는 않습니다.

기준: 오류율 ≤ 2.0%, p95 ≤ 800ms

| 트래픽 | 검사 | 오류율 | p95 | 판정 |
|---|---|---|---|---|
| 1% | 1 | 0.2% | 190ms | 통과 |
| 1% | 2 | 0.3% | 200ms | 통과 |
| 1% | 3 | 0.4% | 210ms | 통과 |
| 10% | 1 | 0.2% | 190ms | 통과 |
| 10% | 2 | 0.3% | 200ms | 통과 |
| 10% | 3 | 0.4% | 210ms | 통과 |
| 50% | 1 | 6.0% | 190ms | 실패 (오류율 6.0% > 2.0%) |

→ 50% 단계에서 실패해 안정 리비전으로 100% 되돌렸습니다.

실행했다면 쓸 명령:

```bash
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=1,STABLE=99
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=10,STABLE=90
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=50,STABLE=50
gcloud run services update-traffic noticatch-dashboard --to-revisions=STABLE=100   # 자동 롤백
```

### 시나리오 slow: 롤백됨

> 가상 헬스체크 값을 쓰는 시뮬레이션입니다. 실제 트래픽을 옮기지는 않습니다.

기준: 오류율 ≤ 2.0%, p95 ≤ 800ms

| 트래픽 | 검사 | 오류율 | p95 | 판정 |
|---|---|---|---|---|
| 1% | 1 | 0.2% | 190ms | 통과 |
| 1% | 2 | 0.3% | 200ms | 통과 |
| 1% | 3 | 0.4% | 210ms | 통과 |
| 10% | 1 | 0.2% | 1400ms | 실패 (p95 1400ms > 800ms) |

→ 10% 단계에서 실패해 안정 리비전으로 100% 되돌렸습니다.

실행했다면 쓸 명령:

```bash
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=1,STABLE=99
gcloud run services update-traffic noticatch-dashboard --to-revisions=CANARY=10,STABLE=90
gcloud run services update-traffic noticatch-dashboard --to-revisions=STABLE=100   # 자동 롤백
```
