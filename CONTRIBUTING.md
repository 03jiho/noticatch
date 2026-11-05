# NotiCatch에 기여하기

NotiCatch에 관심 가져 주셔서 감사합니다. 이 문서는 기여를 시작해서 PR이 머지되기까지의 순서를 설명합니다. 더 자세한 설명은 [Wiki](https://github.com/03jiho/noticatch/wiki)에 있습니다.

## 시작하기 전에

- **행동강령:** 모든 참여자는 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)를 지켜야 합니다.
- **라이선스:** 기여한 코드와 문서는 이 저장소와 같은 [MIT 라이선스](LICENSE)로 배포되는 데 동의한 것으로 봅니다.
- **질문:** 사용법이나 막힌 점은 [Discussions의 Q&A](https://github.com/03jiho/noticatch/discussions)에 올려 주세요. 버그와 기능 제안은 이슈로 올립니다.
- **보안 문제:** 공개 이슈에 올리지 말고 저장소 소유자([@03jiho](https://github.com/03jiho))에게 비공개로 알려 주세요.

## 무엇을 기여할 수 있나

| 종류 | 시작하는 곳 |
|---|---|
| 쉬운 이슈 | [`good first issue`](https://github.com/03jiho/noticatch/labels/good%20first%20issue), [`help wanted`](https://github.com/03jiho/noticatch/labels/help%20wanted) 라벨이 붙은 이슈 |
| 버그 신고 | [Bug 이슈 템플릿](https://github.com/03jiho/noticatch/issues/new/choose) |
| 기능 제안 | Feature 이슈 템플릿. 설계에 영향이 큰 제안은 [Discussions의 RFC 카테고리](https://github.com/03jiho/noticatch/discussions/categories/rfc)에서 먼저 의견을 받습니다 |
| 문서 | 오타 수정, 설명 보강, Wiki 개선 |
| 크롤러 | 아래 [크롤러 기여](#크롤러-기여) 참고 |

큰 변경은 코드를 쓰기 전에 이슈나 RFC로 방향을 먼저 맞춰 주세요. 이미 진행 중인 작업과 겹치지 않도록 하기 위해서입니다. 이슈에서 작업하고 싶다고 댓글을 남기면 담당자(Assignee)로 지정해 드립니다.

## 개발 환경

필요한 것: Git, Python 3.12 이상.

```bash
# 1. 저장소를 Fork한 뒤 내 계정의 주소로 clone
git clone https://github.com/<내-계정>/noticatch.git
cd noticatch

# 2. 원본을 upstream으로 등록
git remote add upstream https://github.com/03jiho/noticatch.git
```

현재 저장소에서 실행할 수 있는 것은 프로젝트 운영 스크립트입니다(크롤러·API 코드는 아직 구현 전입니다).

| 스크립트 | 필요 패키지 | 실행 |
|---|---|---|
| `scripts/dora_metrics.py` | 없음 | `python3 scripts/dora_metrics.py` |
| `scripts/sprint_metrics.py` | `matplotlib` | `python3 scripts/sprint_metrics.py` |
| `scripts/bootstrap_backlog.py` | `pyyaml` | `DRY_RUN=1 python3 scripts/bootstrap_backlog.py` |

> 지표 스크립트는 `README.md`의 자동 갱신 구간, `metrics/`, `reports/`, `docs/images/`를 덮어씁니다. 연습으로 돌렸다면 커밋하지 마세요. 이 파일들은 GitHub Actions가 갱신하므로 직접 고치지 않습니다.

테스트 도구(pytest)는 이슈 [#15](https://github.com/03jiho/noticatch/issues/15)에서 구성할 예정입니다. 자세한 실행 방법과 문제 해결은 Wiki의 [시작하기](https://github.com/03jiho/noticatch/wiki/Getting-Started), [문제 해결](https://github.com/03jiho/noticatch/wiki/Troubleshooting)을 보세요.

## 작업 순서 (GitHub Flow)

```
이슈 확인 → 최신 main에서 브랜치 → 작업 + 커밋 → push → PR → 리뷰 → Squash and merge
```

`main`에는 직접 push하지 않고, 모든 변경은 PR을 거칩니다.

### 1. 브랜치

자동화 봇이 `main`에 직접 커밋하므로, 작업 전에는 항상 원본의 최신 `main`을 받으세요.

```bash
git fetch upstream
git checkout -b feat/keyword-subscription upstream/main
```

| 접두사 | 용도 |
|---|---|
| `feat/` | 새 기능 |
| `fix/` | 버그 수정 |
| `docs/` | 문서 |
| `chore/`, `ci/` | 설정, GitHub Actions |
| `refactor/`, `test/` | 구조 개선, 테스트 |

소문자와 하이픈만 쓰고, 이슈 하나(목적 하나)당 브랜치 하나를 씁니다.

### 2. 커밋 메시지 (Conventional Commits)

```
type(scope): 설명

본문(선택): 무엇을, 왜 바꿨는지

관련: #12
```

- type: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `perf`, `revert`
- 제목은 72자 이내, scope는 소문자(예: `crawler`, `api`, `github`)
- 호환성을 깨는 변경은 type 뒤에 `!`를 붙입니다(`feat(api)!: ...`)

예: `feat(crawler): 학과 게시판 크롤러 추가`, `fix: 중복 공지가 두 번 저장되는 문제 수정`

### 3. Pull Request

1. 내 Fork에 push하고 원본 저장소 `main`을 대상으로 PR을 엽니다. PR 템플릿이 자동으로 채워집니다.
2. **PR 제목도 위의 커밋 형식**으로 씁니다. Squash and merge 때 PR 제목이 그대로 `main`의 커밋 메시지가 되고, `PR Title Lint` 워크플로우가 형식을 검사합니다.
3. 이슈를 닫는 PR은 본문에 `closes #번호`, 참고만 할 때는 `관련: #번호`를 적습니다.
4. 변경 내용과 확인 방법을 구체적으로 적습니다. 리뷰어가 따라 해 볼 수 있어야 합니다.
5. PR은 하나의 목적만 가지게 하고, 크면(대략 300줄 이상, 자동 생성 파일 제외) 나눕니다.

### 4. 리뷰

리뷰 코멘트에는 태그를 붙여 무엇을 먼저 고쳐야 하는지 알 수 있게 합니다.

| 태그 | 의미 | 머지 조건 |
|---|---|---|
| `[MUST]` | 버그, 보안, 요구사항·저장소 규칙 위반 | 반영되거나 합의된 뒤에만 머지 |
| `[SHOULD]` | 가독성, 네이밍, 중복, 테스트 보강 | 반영하지 않으면 이유를 답글로 |
| `[Q]` | 의도를 묻는 질문 | 답변 후 필요하면 전환 |
| `[NIT]` | 오타 같은 사소한 것 | 선택 |
| `[GOOD]` | 칭찬 | - |

`[MUST]`가 있으면 Request changes, 없으면 Approve를 선택합니다. 리뷰어를 기다리는 동안 다른 PR을 리뷰해 주시면 큰 도움이 됩니다.

### 5. 머지

`[MUST]`를 모두 해결하고 CI가 통과하면 **Squash and merge**로 머지합니다. 머지한 뒤 작업 브랜치는 삭제합니다.

## 이슈 작성

- 템플릿(Bug / Feature)에 맞춰 작성합니다.
- 버그는 재현 방법, 기대한 결과, 실제 결과, 환경(OS, Python 버전)을 적어 주세요. 에러 메시지는 전체를 붙여 주세요.
- 라벨은 `type:`, `area:`, `priority:`, `size:`(스토리 포인트 1·2·3·5·8)를 씁니다. 정의는 [`project/labels.yml`](project/labels.yml)에 있습니다.

## 크롤러 기여

NotiCatch는 게시판마다 크롤러를 **파일 하나**로 분리하는 구조를 목표로 합니다. 다만 공통 인터페이스는 아직 확정되지 않았습니다.

- 인터페이스 설계는 [RFC 토론](https://github.com/03jiho/noticatch/discussions/24)과 이슈 [#8](https://github.com/03jiho/noticatch/issues/8)에서 논의 중입니다. 의견을 주시면 반영합니다.
- 인터페이스가 확정되면 이 절에 추가 방법과 예시를 적습니다. 그전에는 크롤러 PR을 열기보다 이슈로 대상 게시판을 먼저 제안해 주세요.

어떤 크롤러든 아래 규칙은 지켜야 합니다.

- 대상 사이트의 `robots.txt`와 이용약관을 확인하고 허용되는 범위에서만 수집합니다.
- 요청 간격을 제한하고 실패하면 재시도 횟수를 제한합니다.
- 공지는 원문 링크 중심으로 제공하고, 본문 전체를 재배포하지 않습니다.
- 로그인이 필요한 게시판의 계정 정보나 쿠키를 저장소에 올리지 않습니다.

## 도움이 필요하면

[Discussions](https://github.com/03jiho/noticatch/discussions)에 질문을 올리거나 관련 이슈에 댓글을 남겨 주세요. 처음 기여하는 분의 질문도 환영합니다.
