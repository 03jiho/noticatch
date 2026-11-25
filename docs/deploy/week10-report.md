# 10주차 보고서: 멀티 플랫폼 배포 자동화

- 라이브 URL: https://03jiho.github.io/noticatch/
- 프리뷰 URL 형식: `https://03jiho.github.io/noticatch/pr-preview/pr-<번호>/`

## 요구사항 대응

| 요구 | 구현 | 증거 |
|---|---|---|
| 프런트엔드 자동 배포 | [`deploy-pages.yml`](../../.github/workflows/deploy-pages.yml): main 푸시 시 GitHub Pages 배포, 배포 후 라이브 URL 검증 | [실행](https://github.com/03jiho/noticatch/actions/runs/45644299646) |
| PR 프리뷰 환경 | [`pages-preview.yml`](../../.github/workflows/pages-preview.yml) 검증 → [`pages-preview-deploy.yml`](../../.github/workflows/pages-preview-deploy.yml) 배포, PR 에 주소 댓글, PR 이 닫히면 프리뷰를 내리고 댓글 갱신 | [실행](https://github.com/03jiho/noticatch/actions/runs/45644407405), PR #42 댓글 |
| Docker 배포 파이프라인 전략 | [`docker-pipeline-strategy.md`](docker-pipeline-strategy.md) (한 번 빌드·digest 승격, 태그, 롤백) | [Docker 실행](https://github.com/03jiho/noticatch/actions/runs/45639253844) (스모크 테스트 통과) |
| 클라우드 배포 자동화 (GCP Cloud Run) | [`deploy-cloudrun.yml`](../../.github/workflows/deploy-cloudrun.yml): 후보 리비전 → 헬스체크 → 트래픽 전환 → 실패 시 롤백 | 설정 가이드: [`cloud-run-setup.md`](cloud-run-setup.md) |
| 헬스체크 / 모니터링 | `/healthz`, `/version.json`, [`healthcheck.py`](../../scripts/healthcheck.py), [`uptime-monitor.yml`](../../.github/workflows/uptime-monitor.yml), Cloud Monitoring 알림 ([`infra/gcp`](../../infra/gcp)) | 단위 테스트 223개 통과 |

## 설계 메모

- Pages 는 배포할 때마다 사이트 전체를 교체하므로, 매 배포마다 "main + 열린 PR 프리뷰"를 다시 조립한다 ([`build_pages_site.py`](../../scripts/build_pages_site.py)).
- Pages 배포는 기본 브랜치에서만 되므로 PR 검증과 배포 워크플로우를 `workflow_run` 으로 나눴다.
- Pages 배포가 가끔 일시적으로 실패해서 3회 재시도를 넣었다.

## 한계 (정직하게)

- **Cloud Run 실제 배포와 Cloud Monitoring 은 아직 실행하지 않았다.** GCP 프로젝트와 권한이 필요해서, 변수가 없으면 `deploy-cloudrun.yml` 은 "설정 필요" 요약만 남기고 건너뛴다. 이 경로는 실제로 확인했다. 실제 배포는 `infra/gcp/setup.sh` 실행 후 저장소 Variables 4개를 설정하면 된다.
- Uptime Monitor 는 아직 실제 장애 훈련(drill)을 돌리지 않았다.
- Docker 이미지는 로컬(Docker Hub 차단)이 아니라 GitHub Actions 에서 빌드·검증했다.
