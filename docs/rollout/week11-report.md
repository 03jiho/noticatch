# 11주차 보고서: Feature Flags 및 점진적 배포

- 라이브 데모(웹사이트 URL): https://03jiho.github.io/noticatch/flags.html
- PR 프리뷰에서는 환경이 자동으로 `staging` 으로 잡힙니다. (`/pr-preview/` 경로)

## 요구사항 대응

| 요구 | 구현 | 위치 |
|---|---|---|
| Feature Flag 3개 이상 | 플래그 4개: `beta-banner`, `compact-mode`, `experimental-export`, `legacy-widget` | [`flags.config.json`](../../dashboard/flags.config.json) |
| 환경 변수 기준 토글 | `experimental-export` 는 `environments: [development, staging]` 에서만 켜짐. 환경은 호스트 이름과 경로로 자동 판별하고 `?env=` 로 바꿀 수 있음 | [`flags.js`](../../dashboard/flags.js) `detectEnv` |
| 대상 사용자 기준 토글 | `beta-banner` 는 사용자 id 목록(`allowUsers`)과 그룹(`allowGroups`)에 해당할 때만 켜짐 | `evaluate` |
| 점진 공개 | `compact-mode` 는 사용자의 30% 에게만 켜짐 (해시 칸 기준) | `evaluate` |
| 킬 스위치 | `legacy-widget` 은 `enabled:false` 라서 다른 조건과 상관없이 꺼짐 | `evaluate` |
| A/B 테스트 2 variant | `cta-style`: `control` / `treatment` 50:50 | [`flags.config.json`](../../dashboard/flags.config.json) |
| 사용자 할당 일관성 | `FNV-1a("exp:cta-style:<userId>") mod 10000`. 저장소나 서버 없이 id 만으로 결정되어 새로고침·다른 기기에서도 같음 | `assign` |
| 이벤트 추적 | `exposure`(실험당 1회), `cta_click`. 화면 로그와 localStorage 에 기록, 내보내기 버튼 | `createClient().track` |
| 실험 로그 | [`docs/experiments/ab-log.md`](../experiments/ab-log.md), [`events-sample.jsonl`](../experiments/events-sample.jsonl) | [`ab_simulation.py`](../../scripts/ab_simulation.py) |
| (선택) 카나리 1-10-50-100% + 자동 롤백 | 단계별 헬스체크 후 실패하면 즉시 안정 리비전으로 100% 복귀 | [`canary_rollout.py`](../../scripts/canary_rollout.py), [`rollout/canary.json`](../../rollout/canary.json), [`canary-rollout.yml`](../../.github/workflows/canary-rollout.yml), [`canary-log.md`](canary-log.md) |

## 검증

- `tests/test_flags.py`: 플래그 규칙(킬 스위치, 환경, 사용자, 그룹, 비율), 할당 일관성과 균형, 카나리 승격·롤백 시나리오.
- **브라우저용 JS 와 파이썬 구현이 같은 결과를 내는지** Node 로 303명에 대해 비교합니다.
- 카나리 로직은 가상 시나리오 3개로 확인합니다. `healthy` 는 100% 승격, `error-spike` 는 50% 에서 롤백, `slow` 는 10% 에서 롤백.

## 한계 (정직하게)

- **A/B 실험 로그는 시뮬레이션입니다.** 가상 사용자 1만 명과 가정한 전환율(10% / 12%)로 만든 합성 데이터이며 실제 방문자 데이터가 아닙니다. 수집된 이벤트는 방문자의 브라우저에만 저장되고 서버로 보내지 않습니다.
- **카나리는 실제 트래픽을 옮기지 않습니다.** GitHub Pages 는 트래픽 분할을 지원하지 않습니다. 롤아웃·롤백 판단 로직은 검증했고, 실제 Cloud Run 에 적용할 `gcloud` 명령은 로그에 계획으로 남깁니다. 워크플로우를 수동 실행하면 실제 사이트 URL 을 같은 기준(오류율, p95)으로 검사합니다.
- 플래그는 정적 설정 파일이라 값을 바꾸려면 배포가 필요합니다. 운영 서비스라면 LaunchDarkly, Unleash 같은 플래그 서버를 쓰고, 같은 해시 방식으로 평가하면 됩니다.
