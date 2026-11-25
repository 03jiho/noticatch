---
name: lean-prd
description: 아이디어 한 줄을 받아 BML(Build-Measure-Learn) 방식의 린 PRD를 docs/prd/ 아래 목차별 MD 12개로 만든다. `/lean-prd <아이디어>`로 생성, `/lean-prd validate`로 검증, `/lean-prd cycle`로 BML 사이클 결과(Pivot/Persevere)를 PRD에 반영한다.
---

# lean-prd — BML 기반 린 PRD

아이디어 한 줄에서 출발해 **가설 → 지표 → MVP → 실험 → 팀/기술스택 → 마일스톤 → Pivot 안전장치** 순서로 PRD를 쓴다. 결과물은 `docs/prd/` 아래 **12개의 개별 MD 파일**이고, `scripts/validate_prd.py` 가 규격을 자동으로 검사한다.

## 명령

| 명령 | 하는 일 |
|---|---|
| `/lean-prd <아이디어 한 줄>` | 12개 파일을 아래 순서로 생성한다 |
| `/lean-prd validate` | `python .claude/skills/lean-prd/scripts/validate_prd.py` 실행. 위반을 고친다 |
| `/lean-prd cycle` | BML 사이클 1회의 결과를 받아 `scripts/cycle.py` 로 PRD 에 반영한다 |

## 왜 가설을 먼저 세우고, 00-overview 를 마지막에 쓰는가

> 이 절은 과제에서 학생이 직접 설명해야 하는 부분이다. 아래는 초안이므로 **본인의 말로 고쳐 써서 제출**한다.

BML 은 실행은 Build → Measure → Learn 순서로 돌지만, **계획은 거꾸로 Learn → Measure → Build 순서로 세운다.** 먼저 "무엇을 배워야 사업이 성립하는가"(Learn)를 정하고, 그걸 알려 줄 숫자(Measure)를 정한 다음에야, 그 숫자를 얻을 수 있는 가장 작은 것(Build)을 만든다. 그래서 가설이 PRD 의 출발점이고, 지표·MVP·실험은 모두 가설에서 파생된다. 기능 목록부터 쓰면 "무엇을 만들까"가 앞서서, 검증되지 않은 기능을 만들어 놓고 나중에 이유를 끼워 맞추게 된다.

`00-overview` 는 요약 문서이므로 요약할 내용이 확정된 뒤에 쓴다. 먼저 쓰면 아직 검증되지 않은 가설을 확정된 사실처럼 적게 되고, 나머지 11개를 쓰며 바뀐 내용이 개요와 어긋난다. 개요는 11개의 결과물을 읽고 쓰는 "마지막 한 장"이며, 사이클이 끝날 때마다 다시 갱신한다. 자세한 근거: `references/bml-cycle.md`.

## 생성 순서 (이 순서를 지킨다)

1. 아이디어 한 줄을 받는다. 모호하면 한 가지만 되묻는다.
2. `python .claude/skills/lean-prd/scripts/scaffold_prd.py "<아이디어>"` 로 뼈대를 만든다. (이미 있으면 `--force` 확인 후)
3. 아래 순서로 **하나씩 채운다.** 앞 파일의 ID 를 뒤 파일이 인용한다.

| 순서 | 파일 | 채울 내용 | 품질 기준 |
|---|---|---|---|
| 1 | `01-problem-customer` | 고객, 문제, 기존 대안, 첫 고객 | 대안마다 한계를 쓴다 |
| 2 | `02-hypotheses` | H1..Hn, 영향 x 불확실성 = 위험도, **가장 위험한 가설** 지목 | 가설마다 반증 조건. 위험도가 최고점인 것을 고른다 |
| 3 | `03-metrics` | M#, 모든 H# 에 1개 이상 | 기준값은 숫자 |
| 4 | `04-mvp` | 유형, In/Out, 성공 기준 | 모든 In 에 검증 H#. 성공 기준은 숫자 |
| 5 | `05-experiments` | E#, 모든 H# 에 1개 이상 | 통과 기준은 숫자. 가장 위험한 가설을 가장 싸게 먼저 |
| 6 | `06-team` | 역할, FTE, 담당 MS#, 채용 우선순위, Pivot 의사결정 규칙 | `references/sufficiency-examples.md` 의 '충분한 예' 수준 |
| 7 | `07-tech-stack` | 계층별 선택·근거·대안·월 비용·전환 조건 | 6열 모두. 비용과 전환 조건은 숫자 |
| 8 | `08-milestones` | MS0~MS3, 검증 단위 | 각각 검증 H#, 숫자 종료 조건, No-Go 시 P# |
| 9 | `09-pivot-safeguards` | P#, 트리거, 예산·시간 상한 | 트리거와 상한은 숫자 |
| 10 | `10-risks` | R# | 가설과 연결 |
| 11 | `11-cycle-log` | 사이클 기록 (처음엔 비어 있음) | `/lean-prd cycle` 이 채움 |
| 12 | `00-overview` | **마지막에** 요약. 가장 위험한 가설에 ★ | 모든 H# 를 언급 |

4. `/lean-prd validate` 를 실행해 위반이 0이 될 때까지 고친다. (생성 직후에는 `--stage generate`)

## 쓰는 규칙

- **ID 로 연결한다.** H# ← M# ← E# ← MS# → P#. 어느 한 칸이라도 비면 검증기가 막는다.
- **숫자 없는 기준은 기준이 아니다.** "많이", "빠르게", "충분히" 대신 임계값을 쓴다.
- **불확실한 것은 불확실하다고 쓴다.** 근거 없이 확신하는 표현을 쓰지 않는다. 추정치에는 추정이라고 표시한다.
- 팀/기술 스택은 일반론(예: "개발자 2명", "React")이 아니라 **이 프로젝트의 마일스톤에 묶인** 내용으로 쓴다.
- 자리표시자(`TODO`, `TBD`)를 남기지 않는다.

## `/lean-prd cycle` 절차

1. 가장 위험한 가설(02 에서 지목한 H#)과 그 실험(E#)을 확인한다.
2. **실제로** 실험을 실행해 데이터를 얻는다. 가상 데이터로 대신하지 않는다. 불가능하면 멈추고 사용자에게 알린다.
3. 사전에 05 에 적어 둔 통과 기준과 측정값을 비교한다. 기준을 결과를 본 뒤에 바꾸지 않는다.
4. Pivot 또는 Persevere 를 정한다. Pivot 이면 09 의 어떤 P# 인지 정한다.
5. `python .claude/skills/lean-prd/scripts/cycle.py --hypothesis H# --experiment E# --measured "..." --decision pivot|persevere [--pivot P#] --reason ... --learned ... --retro-good ... --retro-bad ... --retro-next ...` 를 실행한다. 02·09·11·00 이 갱신되고 `--stage final` 검증이 돈다.
6. 회고를 확인한다. 다음 사이클의 가설을 11 에 적는다.

## 파일 구성

```
.claude/skills/lean-prd/
  SKILL.md
  references/
    bml-cycle.md              BML 이 왜 역순 계획인지
    prd-spec.md               12개 파일 규격과 필수 헤딩, ID 규칙
    sufficiency-examples.md   팀/기술스택 불충분 vs 충분
  templates/                  12개 뼈대
  scripts/
    scaffold_prd.py           뼈대 생성
    validate_prd.py           규격 검사
    cycle.py                  사이클 결과 반영
```
