# 기타 과제: BML 기반 Lean PRD Skill (`lean-prd`)

## 제출물 위치

| 요구 | 위치 |
|---|---|
| Agent Skill `lean-prd` | [`.claude/skills/lean-prd/`](../../.claude/skills/lean-prd) — `SKILL.md`, `references/`, `templates/`, `scripts/` |
| 아이디어로 만든 PRD (목차별 MD 12개) | [`docs/prd/`](../prd) |
| 가장 위험한 가설의 BML 사이클 1회 | [`experiments/bml-cycle-1/`](../../experiments/bml-cycle-1) (데이터, 평가 스크립트, 결과) |
| `/lean-prd cycle` 로 반영한 Pivot/Persevere 결정과 회고 | [`docs/prd/11-cycle-log.md`](../prd/11-cycle-log.md), [`00-overview.md`](../prd/00-overview.md) |

## 스킬이 강제하는 것

- **BML 기반**: `SKILL.md` 의 "왜 가설을 먼저 세우고 00-overview 를 마지막에 쓰는가", 근거는 [`references/bml-cycle.md`](../../.claude/skills/lean-prd/references/bml-cycle.md)
- **목차별 개별 MD 12개**: [`validate_prd.py`](../../.claude/skills/lean-prd/scripts/validate_prd.py) 가 파일 12개, 필수 헤딩, H#→M#→E#→MS#→P# 교차 참조를 검사
- **팀·기술스택 구체성**: 팀은 FTE·담당 MS#·채용 우선순위·Pivot 규칙, 스택은 6열(선택·근거·대안·월 비용·전환 조건) 모두, 비용과 전환 조건은 숫자 ([예시](../../.claude/skills/lean-prd/references/sufficiency-examples.md))
- **MVP와 마일스톤**: MVP 유형, 모든 In 항목에 검증 가설, 숫자 성공 기준. MS0~MS3 각각 검증 가설, 숫자 종료 조건, No-Go 시 Pivot 옵션
- 테스트: `tests/test_lean_prd.py` (위반 사례 30여 개와 `cycle.py` 동작, 저장소의 PRD 가 항상 규격을 지키는지 확인)

## BML 사이클 1회 요약

- **가장 위험한 가설**: H2 "마감일을 규칙 기반 추출로 90% 이상 맞춘다" (위험도 20)
- **측정**: 실제 공개 학교 게시판 공지 19건에서 마감일 줄을 모아 정답과 대조 → **16/19 = 84.2%** (95% 신뢰구간 62~95%)
- **결정**: 실험 전에 커밋해 둔 기준(90%)에 미달이므로 **Pivot (P1: 완전 자동 → 후보 날짜를 보여 주는 반자동)**
- 자세한 틀린 사례와 회고: [`results.md`](../../experiments/bml-cycle-1/results.md), [`11-cycle-log.md`](../prd/11-cycle-log.md)

## 한계 (정직하게)

- **과제 명세서와 zip(스켈레톤, `validate_prd.py`)을 받지 못했습니다.** Canvas 첨부는 로그인이 필요해서 제가 열 수 없었고, 메시지에 적힌 설명만으로 스킬과 검증기를 직접 만들었습니다. 그래서 **12개 파일 이름·필수 헤딩은 제가 정한 것**이고 공식 규격과 다를 수 있습니다. 공식 검증기가 있다면 `docs/prd/` 를 그걸로 한 번 돌려 보세요.
- `SKILL.md` 의 "왜 가설을 먼저 세우는가" 절은 **초안**입니다. 과제는 학생 본인의 설명을 요구하므로 본인의 말로 고쳐서 제출하세요.
- **가장 위험한 가설을 H2 로 고른 것은 동점 중에서 고른 것**입니다. 수요(H1)도 위험도 20점이고, 사실은 H1 이 더 근본적인 위험입니다. H2 를 먼저 한 이유는 사람 없이 하루, 0원으로 검증할 수 있어서입니다. 수요 검증(H1, 재학생 인터뷰 10명)은 **아직 하지 않았고** Cycle 2 로 남겼습니다.
- 사이클 1의 데이터는 실제 공개 공지이지만 **표본이 19건**이고 서울권 대학 위주이며, 공지 전체가 아니라 마감일이 적힌 줄만 잘라 평가했습니다. 실제 서비스보다 쉬운 조건이고 신뢰구간이 넓습니다. 정답은 제가 원문을 읽고 붙였습니다.
- 결정은 "기준을 먼저 정하고 그대로 적용한다"는 규칙을 따랐습니다. 틀린 3건 중 2건은 표기 형식 결함이라 고치기 쉬우니, Cycle 2 에서 고친 추출기를 **처음 보는 새 공지**로 다시 재야 합니다.
