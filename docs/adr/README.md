# 기술결정기록 (ADR)

중요한 기술 결정을 "무엇을, 왜 그렇게 정했는가"와 함께 남기는 폴더입니다. 시간이 지나 코드만 보고는 이유를 알 수 없을 때 이 기록을 봅니다.

## 언제 쓰나

아래 중 하나라도 해당하면 ADR을 씁니다.

- 되돌리기 어렵거나 비용이 큰 결정 (DB, 프레임워크, 배포 방식)
- 둘 이상의 선택지를 놓고 고민했고, 팀이 이유를 알아야 하는 결정
- 외부 기여자가 "왜 이렇게 했지?"라고 물을 만한 결정

오타 수정이나 단순 리팩터링에는 쓰지 않습니다.

## 쓰는 방법

1. [`0000-template.md`](0000-template.md)를 복사해 `NNNN-짧은-제목.md`로 저장합니다. 번호는 마지막 번호 + 1이고, 한 번 쓴 번호는 재사용하지 않습니다.
2. 큰 결정이면 먼저 [GitHub Discussions](https://github.com/03jiho/noticatch/discussions)의 RFC 카테고리에서 의견을 받고, 토론 링크를 ADR의 `관련`에 적습니다.
3. `docs/adr-NNNN-제목` 브랜치를 따서 PR을 올립니다. 커밋 제목은 `docs(adr): ADR-NNNN 제목` 형식입니다.
4. 상태는 PR이 머지될 때 `Accepted`로 바꿉니다. 논의 중에는 `Proposed`입니다.

## 고치는 규칙

- `Accepted`된 ADR의 본문은 **고치지 않습니다.** 오타는 고쳐도 됩니다.
- 결정이 바뀌면 새 ADR을 쓰고, 옛 ADR의 상태를 `Superseded by ADR-NNNN`으로 바꿉니다. 이력이 남아야 하기 때문입니다.

## 목록

| 번호 | 제목 | 상태 | 날짜 |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | 기술 결정을 ADR로 기록한다 | Proposed | 2026-11-05 |
| [0002](0002-github-flow-and-conventional-commits.md) | GitHub Flow, Conventional Commits, Squash merge를 쓴다 | Accepted | 2026-11-05 |
