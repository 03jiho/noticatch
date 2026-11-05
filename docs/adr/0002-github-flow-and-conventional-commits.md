# ADR-0002: GitHub Flow, Conventional Commits, Squash merge를 쓴다

- 상태: Accepted
- 날짜: 2026-11-05
- 결정한 사람: @03jiho
- 관련: README 6장(오픈소스 운영 계획), PR #19, #20, #21

## 배경 (Context)

README 6장에서 브랜치 전략을 `main`(배포) / `feat/*` → PR → 리뷰 후 병합으로 정했다. 4주차에 이를 실제로 적용하면서 커밋 메시지 형식과 병합 방식도 정해야 했다. 이 저장소에서는 `main`에 push되면 GitHub Pages로 자동 배포되고(Deploy 워크플로우), 자동화 봇도 `main`에 직접 커밋한다.

## 선택지 (Options)

### 선택지 A: `main`에 직접 커밋, 자유 형식 메시지

- 장점: 가장 빠르다.
- 단점: 리뷰 없이 바로 배포되고, 이력에서 변경 종류를 구분할 수 없다.

### 선택지 B: Git Flow (`develop`, `release/*`, `hotfix/*`)

- 장점: 릴리스를 단계별로 관리할 수 있다.
- 단점: 브랜치가 많아 1인·소규모 프로젝트에는 무겁고, 이미 `main` 머지가 곧 배포인 구조와 맞지 않는다.

### 선택지 C: GitHub Flow + Conventional Commits + Squash merge

- 장점: 브랜치가 `main`과 작업 브랜치뿐이라 단순하다. PR마다 리뷰가 들어가고, 커밋 type으로 이력을 읽기 쉽다. Squash merge로 PR 1개가 커밋 1개가 되어 `main` 이력이 깔끔하다.
- 단점: Squash하면 작업 브랜치의 세부 커밋이 사라진다. PR 제목 규칙을 지켜야 한다.

## 결정 (Decision)

선택지 C를 쓴다.

- 브랜치: `main` + 작업 브랜치(`feat/`, `fix/`, `docs/`, `chore/`, `ci/` 등), `main` 직접 push 금지
- 커밋과 PR 제목: Conventional Commits (`type(scope): 설명`, 72자 이내)
- 병합: Squash and merge, PR 제목이 그대로 커밋 메시지

## 이유 (Rationale)

`main` 머지가 곧 배포이므로 모든 변경이 리뷰를 거쳐야 한다. 규모가 작아 Git Flow의 장점이 필요 없고, Squash merge는 PR 제목 하나만 형식을 지키면 되어 규칙을 자동으로 검사하기 쉽다(PR #21).

## 결과 (Consequences)

- 좋아지는 점: 변경 종류를 제목으로 구분할 수 있고, 리뷰 기록이 PR에 남는다.
- 감수해야 할 점: 자동화 봇이 `main`에 직접 커밋하므로 작업 브랜치가 금방 뒤처진다. 작업 전 최신 `main`을 받고 rebase해야 한다(Wiki 문제 해결 문서에 정리).
- 후속 작업: PR 제목 검사 워크플로우 머지(#21), 브랜치 보호 규칙 설정.

## 다시 검토할 조건

기여자가 여럿이 되어 릴리스 단위 관리가 필요해지면 릴리스 브랜치 도입을 다시 검토한다.
