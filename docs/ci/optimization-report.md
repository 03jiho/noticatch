# 8주차 워크플로우 실행 최적화: 전후 비교 리포트

7주차에 만든 CI/CD 파이프라인(`lint → test(matrix) → build → deploy`)을 **재사용(Composite Action·Reusable Workflow)**, **캐싱**, **조건부 실행**으로 최적화하고, 효과를 실제 GitHub Actions 실행 기록으로 측정했다.

- 측정일: 2026-11-09 (KST). 모든 숫자는 Actions API의 `started_at`/`completed_at`에서 계산했고, 아래 [재현 방법](#8-재현-방법)으로 누구나 같은 실행 번호로 다시 계산할 수 있다.
- 측정 환경: GitHub 호스티드 러너(`ubuntu-latest`, `windows-latest`, `macos-latest`), Python 3.12, 공개 저장소.
- **시간은 1초 단위로만 측정된다.** 2초짜리 단계가 1초 줄어도 "50%"로 보이므로, 작은 값의 개선율은 크기보다 방향을 본다. 한계는 [7장](#7-한계와-주의)에 적었다.

## 1. 한눈에 보기

| 목표 | 측정 | 전 | 후 | 개선 |
|---|---|---|---|---|
| 캐싱 | 의존성 설치 시간, Windows(스크립트 의존성) | 16.0초 (캐시 없음) | 3.0초 (venv 캐시) | **+81.2%** |
| 캐싱 | 의존성 설치 시간, Ubuntu(dev 의존성) | 3.0초 | 1.0초 | +66.7% |
| 캐싱 | 같은 커밋 재실행, 작업 시간 합 | 112초 (캐시 미스) | 82초 (캐시 적중) | **+26.8%** |
| 캐싱 | 같은 커밋 재실행, 실행 구간 | 64초 | 48초 | **+25.0%** |
| 조건부 실행 | 문서만 바꾼 PR, 실행된 작업 | 11개 | **1개** | -10개 |
| 조건부 실행 | 문서만 바꾼 PR, 작업 시간 합 | 170초 | 5초 | **+97.1%** |
| 조건부 실행 + matrix 조정 | 코드 변경 PR, 작업 시간 합 | 176초 | 112초 | +36.4% |
| 조건부 실행 + matrix 조정 | 코드 변경 PR, 과금 환산(비공개 저장소 기준) | 655초 | 269초 | +58.9% |
| 재사용 | `actions/setup-python` 직접 사용 | 7곳 | 1곳(+측정용 1곳) | -6곳 |

**나빠진 것도 있다.** 코드 변경 PR의 *실행 구간*(첫 작업 시작 → 마지막 작업 종료)은 55초에서 64초로 **16.4% 늘었다**. 원인은 [6장](#6-파이프라인-전후-비교)에서 설명한다. 캐시가 채워진 뒤의 재실행에서는 48초로 줄어 7주차(55초)보다 빠르다.

## 2. 무엇을 바꿨나

```
changes ─▶ lint ─▶ test-pr   (PR: 5개 조합)        ─┐
   │              test-full (main/태그: 10개 조합) ──┴▶ build ─▶ deploy
   └ 변경 파일을 보고 필요한 단계만 실행           (PR 에서는 deploy 없음)
```

| 과제 요구 | 구현 | 위치 |
|---|---|---|
| Matrix 확장 테스트 | PR은 작은 matrix(Ubuntu 3.11·3.12·3.13 + Windows·macOS 3.12 = 5개), main·태그·수동 실행은 전체 matrix(3 OS × 3 버전 = 9개 + 참고용 3.14 `experimental` 1개) | [`ci.yml`](../../.github/workflows/ci.yml) |
| Reusable Workflow | matrix를 JSON 입력으로 받아 pytest를 실행하는 하나의 정의를 PR용·전체용이 호출 | [`python-tests.yml`](../../.github/workflows/python-tests.yml) |
| Composite Action | Python 설치 + 의존성 설치 + 캐시를 한 곳에 모음 | [`.github/actions/setup-python-env`](../../.github/actions/setup-python-env/action.yml) |
| 캐싱 전후 측정 | 같은 설치를 "캐시 없음 / pip 캐시 / 가상환경 캐시"로 나눠 측정 | [`cache-benchmark.yml`](../../.github/workflows/cache-benchmark.yml), [`ci_timing.py`](../../scripts/ci_timing.py) |
| 조건부·선택적 배포 | 변경 파일 감지, 브랜치·이벤트 조건 | [`changed_paths.py`](../../scripts/changed_paths.py), `ci.yml`의 `if:` |

## 3. 중복 제거 (Composite Action, Reusable Workflow)

7주차에는 `actions/setup-python` + pip 캐시 + `pip install` 묶음이 `ci.yml`의 lint·test·build·deploy 네 작업과 운영 워크플로우 세 개(백로그·DORA·스프린트)에 따로 적혀 있었다.

| 항목 | 전 | 후 |
|---|---|---|
| `uses: actions/setup-python` 직접 사용 | 7곳 (`ci.yml` 4, 백로그 1, DORA 1, 스프린트 1) | 2곳 (Composite Action 1, 캐시 측정 워크플로우 1) |
| Composite Action을 쓰는 곳 | 0곳 | 8곳 (`ci.yml` 3, `python-tests.yml` 1, 백로그·DORA·스프린트 각 1, 측정 워크플로우 1) |
| 테스트 matrix 정의 | `ci.yml` 안에 1개(고정) | 정의 1개(`python-tests.yml`)를 PR용·전체용이 서로 다른 matrix로 호출 |

캐시 전략을 바꿀 때(아래 4장에서 pip → 가상환경으로 바꿈) 고칠 파일이 7곳에서 1곳이 됐다. 이것이 중복 제거의 실제 이득이다. 전체 줄 수는 측정·감지용 파일이 늘어서 오히려 늘었다(워크플로우·액션 합계 622줄 → 922줄), 그래서 줄 수는 지표로 쓰지 않았다.

## 4. 캐싱 전후 측정

### 방법

[`cache-benchmark.yml`](../../.github/workflows/cache-benchmark.yml)이 한 작업 안에서 같은 의존성 설치를 세 가지 방식으로 순서대로 측정한다. 같은 러너에서 번갈아 측정하므로 러너 성능 차이가 섞이지 않는다.

| 방식 | 측정하는 시간 |
|---|---|
| 캐시 없음 | `pip install --no-cache-dir` |
| pip 캐시 | pip 다운로드 캐시 **복원 시간 + 복원 뒤 `pip install` 시간** (setup-python의 `cache: pip`와 같은 방식) |
| 가상환경 캐시 | 설치가 끝난 `.venv` 폴더 **복원 시간** (설치를 건너뜀) |

OS 3종 × 의존성 2묶음(`requirements-dev.txt`, `requirements-scripts.txt`) × 한 실행당 3회 반복. 같은 측정 정의로 돈 세 번의 실행(`eda5ffc`, `0b20f4c`, `39d7e29` 커밋)을 합쳐 **그룹당 9개 샘플의 중앙값**을 냈다.

### 결과

| OS | 의존성 | 캐시 없음(초) | pip 캐시(초) | 개선율 | 가상환경 캐시(초) | 개선율 |
|---|---|---|---|---|---|---|
| ubuntu | dev | 3.0 | 2.0 | +33.3% | 1.0 | **+66.7%** |
| ubuntu | scripts | 7.0 | 8.0 | -14.3% | 3.0 | **+57.1%** |
| windows | dev | 7.0 | 7.0 | 0.0% | 2.0 | **+71.4%** |
| windows | scripts | 16.0 | 17.0 | -6.2% | 3.0 | **+81.2%** |
| macos | dev | 2.0 | 3.0 | -50.0% | 1.0 | **+50.0%** |
| macos | scripts | 7.0 | 7.0 | 0.0% | 3.0 | **+57.1%** |

(`scripts` = matplotlib·PyYAML, `dev` = pytest·PyYAML·ruff. 실행별 원자료는 [실행 42558511858](https://github.com/03jiho/noticatch/actions/runs/42558511858), [42558746905](https://github.com/03jiho/noticatch/actions/runs/42558746905), [42559193611](https://github.com/03jiho/noticatch/actions/runs/42559193611).)

### 해석

- **pip 다운로드 캐시는 효과가 없었다.** 개선율이 -50%~+33%로 오가는데, 1초 해상도에서 1~2초 차이라 노이즈로 봐야 한다. 캐시를 복원하는 시간과 압축 해제가 내려받기 시간을 상쇄한다. 즉 7주차에 쓰던 `cache: pip`는 사실상 이득이 없었다.
- **가상환경 캐시는 모든 조합에서 +50~81%로 일관됐다.** 설치 자체를 건너뛰기 때문이다. 의존성이 클수록(matplotlib이 있는 `scripts`, 느린 Windows) 절대 절약량이 크다. Windows `scripts`는 16초 → 3초다.
- 그래서 Composite Action의 기본 캐시 전략을 **가상환경 캐시**로 바꿨다. 캐시 키에 OS, CPU 구조, 정확한 Python 버전, requirements 파일 내용의 해시를 넣어, 러너 이미지가 바뀌었을 때 깨진 환경을 복원하지 않게 했다.

## 5. 선택적 파이프라인 (조건부 실행)

### 규칙

[`changed_paths.py`](../../scripts/changed_paths.py)가 변경된 파일 목록으로 `test`(lint + pytest)와 `build` 실행 여부를 정한다.

| 바뀐 파일 | lint·test | build | deploy |
|---|---|---|---|
| `scripts/`, `tests/`, `.github/workflows/`, `.github/actions/`, `pyproject.toml`, `requirements*.txt` | 실행 | 실행 | main·태그 push만 |
| `dashboard/`, `project/`, `LICENSE`, `README.md` (배포 번들에 들어가는 파일만) | 건너뜀 | 실행 | main·태그 push만 |
| `docs/`, `reports/`, `metrics/`, 그 밖의 문서 | **건너뜀** | **건너뜀** | **건너뜀** |

| 이벤트·브랜치 | 동작 |
|---|---|
| Pull Request | lint → 작은 matrix → build. **deploy는 절대 실행하지 않음** |
| `main` push | 변경 파일 규칙에 따라 전체 matrix → build → deploy |
| `v*` 태그 push | 변경 파일과 무관하게 전체 실행 + deploy + GitHub Release |
| 수동 실행(`workflow_dispatch`) | 전체 실행. `deploy` 입력을 켠 경우에만 deploy (릴리스는 만들지 않음) |

**안전한 쪽으로 판단하는 경우**(전부 실행): 새 브랜치·태그 push처럼 비교 기준 커밋이 없을 때, `git diff`가 실패했을 때, 강제 실행을 지정했을 때. 테스트를 잘못 건너뛰는 것이 불필요하게 도는 것보다 나쁘기 때문이다.

### 시연: 문서만 바꾼 PR

[PR #32](https://github.com/03jiho/noticatch/pull/32)는 `docs/` 파일 하나만 바꾼다. 결과: `Detect changes`만 실행되고 `Lint`, `test-pr`, `test-full`, `Build bundle`, `Deploy` 5개가 건너뛰어졌다([실행 42559054416](https://github.com/03jiho/noticatch/actions/runs/42559054416)).

## 6. 파이프라인 전후 비교

같은 지표를 실행 쌍마다 계산했다. **실행 구간**은 첫 작업 시작부터 마지막 작업 종료까지(대기열 시간 제외), **작업 시간 합**은 실행된 모든 작업 시간의 합(병렬이라 실행 구간보다 길다)이다. **과금 환산**은 비공개 저장소의 분 단위 배수(Linux 1, Windows 2, macOS 10)를 곱한 값으로, 이 저장소는 공개라 실제 과금은 없고 비용 규모를 가늠하는 참고용이다.

### 6-1. 코드 변경 PR (7주차 → 8주차, 캐시 미스인 첫 실행)

| 항목 | 전 ([실행 42554865353](https://github.com/03jiho/noticatch/actions/runs/42554865353)) | 후 ([실행 42559193674 1차](https://github.com/03jiho/noticatch/actions/runs/42559193674/attempts/1)) | 개선율 |
|---|---|---|---|
| 실행된 작업 수 | 11 / 12 | 8 / 10 | |
| 실행 구간(초) | 55.0 | 64.0 | **-16.4%** |
| 작업 시간 합(초) | 176.0 | 112.0 | +36.4% |
| 과금 환산(초) | 655.0 | 269.0 | +58.9% |

작업 시간 합과 과금 환산은 크게 줄었다. PR에서 Windows·macOS를 각 1개 조합만 돌려(전: 각 3개) 비싼 러너 시간이 줄었기 때문이다. 반면 실행 구간은 길어졌는데, ① 맨 앞에 `Detect changes` 작업(약 4초)이 직렬로 추가됐고 ② 이 실행은 새 캐시 키라서 가상환경을 처음 만들고 캐시를 저장하는 비용이 들었기 때문이다.

### 6-2. 같은 PR 재실행 (캐시 미스 → 캐시 적중)

같은 커밋·같은 워크플로우를 다시 실행해서 캐시 상태만 다르게 한 가장 통제된 비교다.

| 항목 | 전 ([1차 시도](https://github.com/03jiho/noticatch/actions/runs/42559193674/attempts/1)) | 후 ([2차 시도](https://github.com/03jiho/noticatch/actions/runs/42559193674/attempts/2)) | 개선율 |
|---|---|---|---|
| 실행 구간(초) | 64.0 | 48.0 | **+25.0%** |
| 작업 시간 합(초) | 112.0 | 82.0 | **+26.8%** |
| 과금 환산(초) | 269.0 | 204.0 | +24.2% |

캐시가 채워진 뒤에는 실행 구간이 48초로, 7주차 파이프라인(55초)보다도 12.7% 빠르다(55 → 48).

### 6-3. 문서만 바꾼 PR (7주차 → 8주차)

| 항목 | 전 ([실행 42555536814](https://github.com/03jiho/noticatch/actions/runs/42555536814)) | 후 ([실행 42559054416](https://github.com/03jiho/noticatch/actions/runs/42559054416)) | 개선율 |
|---|---|---|---|
| 실행된 작업 수 | 11 / 12 | **1 / 6** | |
| 실행 구간(초) | 49.0 | 5.0 | +89.8% |
| 작업 시간 합(초) | 170.0 | 5.0 | **+97.1%** |
| 과금 환산(초) | 671.0 | 5.0 | **+99.3%** |

전은 [PR #19](https://github.com/03jiho/noticatch/pull/19)(`docs/REVIEW_GUIDE.md` 하나만 변경)가 7주차 파이프라인에서 9개 matrix 조합을 전부 돌린 실행이다. 문서만 바꿨는데 Windows·macOS를 포함한 테스트가 모두 돌았다.

## 7. 한계와 주의

- **1초 해상도.** Actions API는 초 단위로만 시간을 준다. 1~3초짜리 단계의 개선율은 ±1초 오차가 크게 보인다. 그래서 반복 측정(그룹당 9개)의 중앙값을 썼고, 방향이 일관된 것(가상환경 캐시)만 결론으로 삼았다.
- **러너 변동.** 호스티드 러너의 성능은 시각마다 다르다. 같은 러너에서 번갈아 측정하는 캐시 벤치마크와 같은 커밋 재실행(6-2)은 영향을 줄였지만, 6-1·6-3은 서로 다른 시각의 실행을 비교하므로 오차가 있다. 6-3의 97%는 "작업을 건너뛴" 효과가 압도적이라 러너 변동과 무관하게 결론이 같다.
- **실행 구간이 늘 줄어드는 것은 아니다.** 변경 감지 작업은 직렬 비용 약 4초를 추가한다. 캐시 미스인 첫 실행은 7주차보다 느릴 수 있다(6-1). 이 최적화의 이득은 주로 *총 작업량*과 *캐시가 찬 이후의 실행*에서 나온다.
- **측정한 의존성이 작다.** pytest·PyYAML·ruff는 설치가 몇 초뿐이라 절대 절약량이 작다(Ubuntu dev는 2초). 이 저장소의 의존성이 커지면 효과도 커진다.
- **과금 환산은 참고용.** 공개 저장소라 호스티드 러너가 무료이므로 실제 비용 절감액이 아니다.
- **전략 선택은 이 저장소 기준.** 가상환경 캐시는 같은 OS·Python 버전·requirements에서만 재사용되고 캐시 용량(저장소당 10GB)을 쓴다. 의존성이 자주 바뀌거나 용량이 부족하면 pip 캐시나 `uv`가 더 맞을 수 있다.
- Python 3.14는 아직 정식이 아니라 `experimental`로 두어, 실패해도 전체 결과를 막지 않는다.

## 8. 재현 방법

```bash
export GITHUB_TOKEN=...   # 없어도 되지만 호출 한도가 낮다

# 4장: 캐시 효과 (여러 실행의 샘플을 합쳐 중앙값을 냄)
python3 scripts/ci_timing.py bench --run 42558511858 --run 42558746905 --run 42559193611

# 6장: 파이프라인 전후 (123 또는 123@시도번호)
python3 scripts/ci_timing.py pipeline \
  --pair "코드 변경 PR|42554865353|42559193674@1" \
  --pair "같은 PR 재실행|42559193674@1|42559193674@2" \
  --pair "문서만 바꾼 PR|42555536814|42559054416"
```

캐시 벤치마크는 Actions 탭에서 **Cache Benchmark**를 수동 실행(Run workflow)하면 새로 돌릴 수 있고, 끝나면 요약 화면에 같은 표가 나온다.
