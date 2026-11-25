# 실험 로그: `cta-style`

> **시뮬레이션 결과입니다.** 가상 사용자 10,000명과 가정한 전환율(`control` 10%, `treatment` 12%, seed=11)으로
> 만든 합성 데이터이며 실제 방문자 데이터가 아닙니다. 할당 일관성과 분석 로직이 동작함을 보이는 용도입니다.
> 재현: `python scripts/ab_simulation.py --users 10000 --seed 11 --out docs/experiments`

## 설정

- 가설: 버튼 문구 A/B 테스트. 노출은 exposure, 성공 지표는 cta_click
- variant: `control`(50%), `treatment`(50%)
- 성공 지표: `cta_click` / 노출 이벤트: `exposure` (사용자·실험당 1회)

## 할당 일관성

- 같은 사용자 id 를 두 번 할당해 같은 variant 가 나오는지 10,000명 모두 확인했습니다. (어긋나면 스크립트가 중단됨)
- 할당은 `FNV-1a("exp:cta-style:<userId>") mod 10000` 으로 정해지므로 저장소나 서버 없이도 일정합니다.
- 브라우저 구현(`dashboard/flags.js`)과 같은 결과를 내는지는 `tests/test_flags.py` 가 Node 로 비교합니다.

## 결과

| variant | 노출 | 비율 | cta_click | 전환율 |
|---|---|---|---|---|
| `control` | 5,000 | 50.0% | 480 | 9.60% |
| `treatment` | 5,000 | 50.0% | 647 | 12.94% |

- z = 5.28, p = 0.0000 → p < 0.05: 차이가 통계적으로 유의함
- 원시 이벤트: [`events-sample.jsonl`](events-sample.jsonl) (앞 200건)
