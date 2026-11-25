# Docker 기반 배포 파이프라인 전략

NotiCatch 의 컨테이너 이미지를 **어떻게 만들고, 검증하고, 환경으로 올리고, 문제가 생기면 되돌리는지** 정한 설계 문서다. 지금 구현된 부분과 앞으로 필요한 부분을 구분해서 적었다. 구현은 [`docker.yml`](../../.github/workflows/docker.yml), [`deploy-cloudrun.yml`](../../.github/workflows/deploy-cloudrun.yml), [`uptime-monitor.yml`](../../.github/workflows/uptime-monitor.yml) 이다.

## 1. 원칙

| 원칙 | 의미 | 이 저장소에서 |
|---|---|---|
| **한 번 빌드하고 같은 이미지를 승격한다** | 환경마다 다시 빌드하면 "검증한 이미지"와 "배포한 이미지"가 달라질 수 있다 | ghcr.io 에서 검증한 이미지를 **digest 그대로** Artifact Registry 로 복사해 배포한다 (복사 뒤 digest 비교) |
| **이미지는 바뀌지 않는다** | 같은 태그가 다른 내용을 가리키면 롤백이 불가능해진다 | 배포 기준은 `sha-<커밋>` 태그와 digest. `latest` 는 사람이 편하게 쓰는 용도이고 배포에는 쓰지 않는다 |
| **이미지가 어느 커밋인지 스스로 말한다** | 배포된 것이 의도한 버전인지 확인할 수 있어야 한다 | 라벨 `org.opencontainers.image.revision`, 그리고 서비스의 `/version.json` |
| **배포 전에 검증하고, 전환 전에 또 검증한다** | 문제를 사용자가 겪기 전에 잡는다 | 푸시 전 로컬 실행 검증 → 푸시 뒤 재검증 → 트래픽 0% 후보 리비전 헬스체크 → 전환 뒤 재확인 |
| **되돌리는 길이 항상 있다** | 배포 속도보다 복구 속도가 중요하다 | 이전 리비전을 지우지 않고, 전환 후 실패하면 자동으로 되돌린다 |
| **설정과 비밀은 이미지 밖에 둔다** | 이미지를 환경마다 새로 만들 필요가 없다 | 지금 이미지는 정적 사이트라 설정이 없다. 생기면 환경변수와 Secret Manager 로 넣는다 |
| **권한은 최소로, 키는 없이** | 배포 자격이 새면 서비스 전체가 위험해진다 | OIDC(Workload Identity Federation)로 로그인, 배포 계정은 이 저장소에서 온 요청만 허용, 실행 계정은 권한 없음 |

## 2. 전체 흐름

```
 PR 올림
   │  docker.yml (PR)        빌드 → 컨테이너 실행 검증 (올리지 않음)
   │  pages-preview*.yml      대시보드 PR 프리뷰 URL (정적 파일은 Pages 로 미리 보기)
   ▼
 main 에 머지 (Squash)
   │  docker.yml (main)      빌드 → 로컬 실행 검증 → ghcr.io 푸시 (sha-xxxxxxx, latest)
   │                          → 푸시한 이미지를 digest 로 다시 받아 실행 검증
   ▼  (Docker 워크플로우 성공 시)
 deploy-cloudrun.yml
   │  1 승격     ghcr.io@digest → Artifact Registry (같은 digest, 복사 후 비교, 이미지 리비전 라벨 = 커밋 확인)
   │  2 후보     새 리비전을 트래픽 0% 로 배포 (태그 candidate, 임시 주소)
   │  3 검증     임시 주소 /healthz + /version.json(커밋 일치) + 응답시간
   │  4 전환     통과하면 트래픽 100%, candidate 태그 제거
   │  5 확인     실제 주소로 다시 검증 ── 실패 ──▶ 이전 리비전으로 자동 롤백
   ▼
 운영 중
      uptime-monitor.yml     30분마다 헬스체크 → 실패 시 incident 이슈, 복구 시 닫음 (DORA MTTR)
      Cloud Monitoring       업타임 체크, 5xx 증가, 지연 알림 (이메일)
```

## 3. 환경 전략

| 환경 | 무엇이 올라가나 | 어떻게 | 비고 |
|---|---|---|---|
| PR 프리뷰 | 대시보드 정적 파일 | GitHub Pages `/pr-preview/pr-N/` | 컨테이너가 아니라 파일만 미리 본다. PR 이 닫히면 사라진다 |
| 운영(production) | 컨테이너 이미지 | Cloud Run 서비스 `noticatch-dashboard` | GitHub Environment `production` 으로 배포 기록이 남는다 |

**스테이징 환경을 따로 두지 않은 이유.** 사용자가 적고 서비스가 정적 사이트 하나라서, 별도 환경의 비용과 관리 부담이 얻는 안전보다 크다. 대신 운영 서비스 안에서 **트래픽 0% 후보 리비전**이 스테이징 역할을 한다. 같은 서비스·같은 설정에서 새 이미지를 먼저 검증하므로, 별도 스테이징보다 운영과 더 비슷하다.

스테이징이 필요해지는 시점과 방법: 서비스가 DB·외부 API 에 연결되거나, 사람이 눈으로 확인한 뒤 올려야 할 때. 이때는 `noticatch-dashboard-staging` 서비스를 하나 더 만들어 **같은 digest** 를 먼저 올리고, GitHub Environment 의 *required reviewers* 로 승인을 받은 뒤 운영으로 승격한다. 이미지는 다시 빌드하지 않는다.

## 4. 이미지 태그

| 태그 | 언제 | 용도 |
|---|---|---|
| `sha-<7자리>` | main 푸시마다 | **배포 기준.** 어느 커밋인지 바로 알 수 있고 바뀌지 않는다 |
| `latest` | main 푸시마다 | 로컬에서 `docker run` 해 보는 용도. 배포에는 쓰지 않는다 |
| `1.2.3`, `1.2` | `v*` 태그 푸시 | 릴리스. 사람이 읽는 버전 |
| (digest `sha256:…`) | 항상 | 실제 배포에 쓰는 고정 참조 |

## 5. 롤백

| 상황 | 동작 |
|---|---|
| 후보 리비전 헬스체크 실패 | 트래픽을 옮기지 않는다. 사용자는 아무 영향이 없고 워크플로우만 실패한다 |
| 전환 뒤 확인 실패 | 직전에 100% 였던 리비전으로 트래픽을 자동으로 되돌린다 |
| 며칠 뒤 문제를 발견 | `gcloud run services update-traffic noticatch-dashboard --to-revisions <이전 리비전>=100` 한 줄. 리비전과 이미지(Artifact Registry)는 지우지 않는다 |
| 다시 배포 | 같은 커밋의 `sha-…` 이미지로 `Deploy to Cloud Run` 을 수동 실행(`sha` 입력) |

## 6. 보안과 공급망

- 컨테이너는 root 가 아닌 `nginx` 사용자로 실행한다 (`nginx-unprivileged`). 스모크 테스트가 매번 확인한다.
- 이미지 안의 `version.json` 과 OCI 라벨의 커밋이 배포하려는 커밋과 다르면 배포를 멈춘다.
- 배포 계정(`noticatch-deployer`)은 Cloud Run 관리, 이 저장소 이미지 쓰기, 실행 계정 사용 권한만 가진다. 실행 계정(`noticatch-runtime`)은 아무 권한도 없다.
- GitHub 쪽 권한: 워크플로우 기본 `contents: read`, 필요한 작업에만 올린다 (`id-token: write` 는 배포 작업만).
- 의존성(베이스 이미지 포함)은 Dependabot 이 주 1회 올린다 ([9주차 문서](../ci/package-security-report.md)).

## 7. 왜 Cloud Run 인가

| 선택지 | 장점 | 이 프로젝트에서 안 쓴 이유 |
|---|---|---|
| **Cloud Run** (선택) | 서버 관리 없음, 요청 없으면 0 대로 줄어 비용 거의 0, 리비전·트래픽 분할이 내장되어 후보 검증·롤백이 쉽다 | — |
| GKE / EKS | 오케스트레이션을 모두 직접 제어 | 서비스 하나에 비해 과하고 클러스터 상시 비용이 든다 |
| VM + Docker | 단순하고 익숙하다 | 배포·롤백·확장·패치를 직접 해야 한다 |
| AWS Lambda / App Runner | 비슷한 서버리스 | 계정과 학습 비용은 비슷하다. 트래픽 분할과 리비전 모델은 Cloud Run 이 더 직접적이다 |

## 8. 현재 구현 범위와 앞으로

| 항목 | 상태 |
|---|---|
| 빌드, 로컬 실행 검증, ghcr.io 푸시와 재검증 | 구현·실행 확인 ([Docker 워크플로우](../../.github/workflows/docker.yml)) |
| digest 승격, 후보 리비전, 헬스체크, 전환, 롤백 | 워크플로우 작성. **Google Cloud 프로젝트 설정 후에 실제로 실행된다** ([설정 안내](cloud-run-setup.md)) |
| 업타임 모니터와 장애 이슈 | 구현·실행 확인 |
| Cloud Monitoring 알림 | 설정 파일과 스크립트 작성. 프로젝트 설정 후 적용 |
| 이미지 취약점 스캔(Trivy 등)과 서명(cosign) | 하지 않았다. 다음 단계 후보 |
| 스테이징 환경과 승인 단계 | 필요해질 때 추가 (3장) |
