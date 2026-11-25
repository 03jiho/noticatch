# 12주차 보고서: Shift-Left 테스트 자동화

## 요구사항 대응

| 요구 | 결과 | 증거 |
|---|---|---|
| 단위 테스트 80% 이상 커버리지 + CI 자동 실행 | **줄·분기 합산 86.8%** (기준 80%). 미만이면 CI 가 실패 | [`pyproject.toml`](../../pyproject.toml) `fail_under = 80`, [`python-tests.yml`](../../.github/workflows/python-tests.yml) 의 coverage gate 단계 |
| TDD(Red-Green-Refactor)로 핵심 기능 5개 이상 | **6개** (아래 표). 기능마다 테스트 먼저 커밋 → 구현 커밋 → 정리 커밋 | 아래 커밋 링크 |
| (선택) Playwright E2E 1개, 실패 시 스크린샷 아티팩트 | 시나리오 1개 + 실패 시 `e2e-failure-screenshots` 아티팩트 저장 | [`e2e/`](../../e2e), [`e2e.yml`](../../.github/workflows/e2e.yml) |
| (선택) 레거시 테스트 보강 후 리팩토링 안정성 검증 | 레거시 스크립트 4개의 `main()` 흐름을 특성화 테스트로 고정한 뒤 `build_pages_site.main` 을 리팩토링 | [`test_legacy_characterization.py`](../../tests/test_legacy_characterization.py) |

## TDD 로 만든 핵심 기능 6개

공지 수집 → 구독 매칭 → 마감일 추출 → 캘린더·리마인드로 이어지는 NotiCatch 의 서버 쪽 핵심 로직입니다(`noticatch/` 패키지).

| # | 기능 | 모듈 | 🔴 Red (테스트만) | 🟢 Green (최소 구현) | 🔵 Refactor |
|---|---|---|---|---|---|
| 1 | 마감일 추출 (`~` 기간의 끝, 연도 보정) | `deadlines.py` | [`cb7a123`](https://github.com/03jiho/noticatch/commit/cb7a123) | [`de7eb4f`](https://github.com/03jiho/noticatch/commit/de7eb4f) | [`49f68e7`](https://github.com/03jiho/noticatch/commit/49f68e7) |
| 2 | 중복 공지 제거 (URL 정규화, 같은 게시판 같은 제목) | `dedupe.py` | [`880e5ac`](https://github.com/03jiho/noticatch/commit/880e5ac) | [`7505fe0`](https://github.com/03jiho/noticatch/commit/7505fe0) | [`5dff8cc`](https://github.com/03jiho/noticatch/commit/5dff8cc) |
| 3 | 키워드·제외 키워드·게시판 구독 매칭 | `matcher.py` | [`c9e3d62`](https://github.com/03jiho/noticatch/commit/c9e3d62) | [`5402468`](https://github.com/03jiho/noticatch/commit/5402468) | [`bf197b0`](https://github.com/03jiho/noticatch/commit/bf197b0) |
| 4 | `.ics` 캘린더 피드 (RFC 5545 줄 접기, 이스케이프) | `ics.py` | [`418cc9f`](https://github.com/03jiho/noticatch/commit/418cc9f) | [`190aa23`](https://github.com/03jiho/noticatch/commit/190aa23) | [`98d9233`](https://github.com/03jiho/noticatch/commit/98d9233) |
| 5 | D-day 표시 | `reminders.py` | [`ba56fe7`](https://github.com/03jiho/noticatch/commit/ba56fe7) | [`30a3e38`](https://github.com/03jiho/noticatch/commit/30a3e38) | 6번과 함께 [`64897bf`](https://github.com/03jiho/noticatch/commit/64897bf) |
| 6 | D-3 / D-1 리마인드 선정 (중복 발송 방지) | `reminders.py` | [`783877f`](https://github.com/03jiho/noticatch/commit/783877f) | [`acaaead`](https://github.com/03jiho/noticatch/commit/acaaead) | [`64897bf`](https://github.com/03jiho/noticatch/commit/64897bf) |

- **Red 단계의 실패**: 각 Red 커밋 시점에는 구현 모듈이 없어서 테스트 수집 단계에서 `ModuleNotFoundError` 로 실패했습니다. 이를 로컬에서 실행해 확인한 뒤 커밋했습니다. (그래서 Red 커밋 자체는 CI 를 통과하지 못하는 상태입니다. PR 의 최종 커밋 기준으로 CI 가 통과합니다.)
- **Green 은 일부러 거칠게**: 예를 들어 마감일 추출의 첫 구현은 정규식 네 개를 복사해 붙인 형태였고, Refactor 에서 패턴 표와 함수로 정리했습니다. 정리 전후로 테스트는 그대로 통과했습니다.
- 5번과 6번은 같은 모듈이라 Refactor 를 한 번에 했습니다.
- **실제로 잡은 버그**: `.ics` 의 `\;` 이스케이프 문자열이 잘못 쓰인 것을 ruff(W605)가 잡아 고쳤습니다. 테스트는 통과하던 상태였습니다.

## 커버리지

`pytest --cov` (줄 + 분기) 결과 **86.8%**, 테스트 308개.

| 영역 | 커버리지 |
|---|---|
| `noticatch/` (TDD 신규 코드) | 거의 100% (분기 포함) |
| 레거시 `scripts/` | 56%~100%. 보강 전 73% 였던 전체를 86.8% 로 끌어올림 |

한계: `sprint_metrics.py`(56%)와 `dora_metrics.py`(73%)는 GitHub API 호출과 matplotlib 차트 그리기 코드가 많아 아직 덜 덮였습니다. 전체 기준은 넘었지만 이 둘이 가장 약한 부분입니다.

## 레거시 코드 보강과 리팩토링

1. 먼저 [`test_legacy_characterization.py`](https://github.com/03jiho/noticatch/commit/a5be004) 로 `build_pages_site.main`, `dependabot_automerge.main`, `canary_rollout` 의 현재 동작을 고정했습니다. (`gh`, `git`, 네트워크 호출은 가짜로 대체)
2. 그 다음 [`e840394`](https://github.com/03jiho/noticatch/commit/e840394): 길었던 `main()` 안의 프리뷰 생성 루프를 `build_preview()` 함수로 분리했습니다. 리팩토링 전후로 같은 테스트 26개가 모두 통과했습니다.

## E2E (Playwright)

시나리오 1개: [`e2e/test_flags_page.py`](../../e2e/test_flags_page.py). 실제 Chromium 으로 Feature Flag 실습 페이지를 열어서 다음을 확인합니다.

1. 운영 환경의 베타 대상 사용자에게 베타 띠가 보이고, 환경 한정 플래그가 꺼져 있다
2. 환경을 스테이징으로 바꾸면 내보내기 버튼이 나타난다
3. 새로고침해도 같은 A/B variant 를 받는다
4. CTA 를 누르면 `cta_click` 이벤트가 남고 노출 이벤트는 한 번만 기록된다
5. 사용자 id 를 바꾸면 베타 띠가 사라진다

실패하면 `e2e/conftest.py` 훅이 그 순간의 화면을 저장하고, 워크플로우가 `e2e-failure-screenshots` 아티팩트로 올립니다.

**검증:** 일부러 실패하는 테스트를 켠 수동 실행([실행 기록](https://github.com/03jiho/noticatch/actions/runs/45649441213))이 실패했고, 아티팩트 `e2e-failure-screenshots` 에 스크린샷이 저장된 것을 확인했습니다. 정상 시나리오는 PR #49 의 `e2e` 검사에서 통과했습니다.

## 한계

- Red 커밋들은 단독으로는 CI 를 통과하지 못합니다. (TDD 의 정의상 그렇고, PR 단위로 최종 상태를 검사합니다.)
- E2E 는 로컬 환경에서 브라우저를 설치할 수 없어서 GitHub Actions 에서만 실행해 검증했습니다.
- 테스트 도구는 과제 예시의 Jest 대신 이 저장소가 쓰던 pytest(파이썬)와 Node 내장 테스트 러너를 썼습니다.
