# 13주차 보고서: Lean Startup 실험 운영

> **먼저 밝혀 둘 것:** 이 과제의 사용자 10명과 2주 A/B 데이터는 **LLM 이 만든 가상 데이터**입니다. 실제 방문자나 실제 응답자가 아닙니다. 과제 조건("LLM 으로 서로 다른 페르소나 10명")에 맞춘 것이고, 모든 문서에 합성 데이터임을 표시했습니다.

## 요구사항 대응

| 요구 | 구현 | 증거 |
|---|---|---|
| 사용자 시나리오 기반 코드 생성·평가, 10명 피드백 | 서로 다른 페르소나 10명의 시나리오를 실행 가능한 테스트로 옮겨 평가 → 실제 결함 1건 발견·수정 | [`user-feedback.md`](user-feedback.md), [`test_persona_scenarios.py`](../../tests/test_persona_scenarios.py), [`personas.json`](../../experiments/personas.json) |
| Feature Flag A/B 2주 운영, 핵심 지표 측정 | `cta-style` 실험을 2026-11-26 ~ 12-09 (14일) 매일 자동 수집. 1차 지표 CTR, 가드레일 세그먼트 | [`cta-style.json`](../../experiments/cta-style.json), [`experiment-daily.yml`](../../.github/workflows/experiment-daily.yml), [`metrics/experiment-daily.jsonl`](../../metrics/experiment-daily.jsonl) |
| (선택) Issues/Projects/Actions 로 백로그·수집·주간 리포트 | 실험 백로그 이슈 5건(마일스톤 "Sprint 6"), 일일 수집·주간 리포트·최종 결정 워크플로우 | [`backlog.yml`](../../project/backlog.yml), [`experiment-weekly.yml`](../../.github/workflows/experiment-weekly.yml) |
| (선택) Pivot/Persevere 결정 문서화 | 사전 고정 규칙으로 결정. 현재 잠정 **Pivot**, 운영 종료 후 자동으로 최종 결정 생성 | [`decision.md`](decision.md), [`dryrun-report.md`](dryrun-report.md), `decision-final.md` (12월 10일 자동 생성) |

## 흐름

```
페르소나 10명 ─▶ 시나리오 테스트(결함 발견·수정) ─▶ 피드백 ─▶ 실험 가설(백로그 이슈)
                                                         │
cta-style 가설 ─▶ 규칙 사전 고정 ─▶ 매일 23:50 KST 수집 ─▶ 월요일 주간 리포트(이슈+문서)
                                                         ▼
                                      12/10 최종 결정(자동) ─▶ Pivot / Persevere
```

## 결과 요약 (리허설 14일)

- 클릭률: 원본 11.28% → 신규 12.18%, 상대 +8.0%, p=0.019 → **유의하지만 기준(+10%) 미달 → Pivot**
- 평균 뒤에 숨은 세그먼트 하락: 외국인 유학생 -35%, 만학도 -26% (가드레일 위반)
- 자세한 표: [`dryrun-report.md`](dryrun-report.md)

## 실제 2주 운영에 대해

- 일일 수집은 **2026-11-26 부터 매일 23:50 KST** 에 GitHub Actions 가 실행합니다. 12월 9일까지 14일치가 쌓이고, **12월 10일 00:30 KST** 에 최종 결정 문서가 자동으로 만들어집니다.
- 제출 마감(12월 13일) 전에 `docs/lean/decision-final.md` 가 생깁니다. 제출 후에도 같은 규칙으로 갱신되니 링크는 그대로 쓸 수 있습니다.
- 리허설과 운영 값은 seed 가 달라서 결과가 약간 다를 수 있습니다. 결정이 달라지면 [`decision.md`](decision.md) 를 고칩니다.

## 한계 (정직하게)

- 10명의 사용자와 그 피드백, A/B 세션은 모두 모델이 만든 것입니다. 클릭 성향은 제가 정한 가정이라 결과가 가정에서 나왔고, 실제 사용자 반응의 증거가 아닙니다.
- 실제 방문자 데이터를 모으려면 수집 서버가 필요합니다. 정적 사이트라서 아직 없고, 이벤트는 방문자의 브라우저에만 저장됩니다.
- "2주 운영"은 오늘(11월 26일) 시작한 자동 수집이 12월 9일에 끝나는 구조입니다. 이 보고서를 쓴 시점에는 운영 1일차이고, 리허설 결과가 그 사이를 대신합니다.
