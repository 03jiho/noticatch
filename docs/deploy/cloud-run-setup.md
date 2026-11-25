# Cloud Run 배포 설정 (한 번만 하면 된다)

`Deploy to Cloud Run` 워크플로우가 실제로 배포하려면 Google Cloud 프로젝트와 인증 설정이 필요하다. 아래를 한 번 하면 이후에는 main 에 머지될 때마다 자동으로 배포된다. 설정이 없으면 워크플로우는 배포 없이 "설정 필요" 안내만 남기고 성공으로 끝난다.

## 준비물

- Google 계정, 결제가 연결된 Google Cloud 프로젝트 (새 계정의 무료 크레딧으로 충분하다. 이 서비스는 요청이 없으면 0 대로 줄어 비용이 거의 들지 않는다)
- 저장소 Settings 를 바꿀 권한 (변수 4개를 넣는다)

## 1. 리소스 만들기

[Cloud Shell](https://shell.cloud.google.com) 을 열고 실행한다. 이미 로그인되어 있다.

```bash
git clone https://github.com/03jiho/noticatch && cd noticatch
bash infra/gcp/setup.sh <프로젝트 ID>
```

스크립트가 만드는 것(여러 번 실행해도 안전): API 켜기, Artifact Registry 저장소, 서비스 계정 2개(배포용, 실행용), Workload Identity Federation(이 저장소에서 온 요청만 허용). 끝나면 넣어야 할 변수 4개를 출력한다.

## 2. 저장소 Variables 넣기

Settings → Secrets and variables → Actions → **Variables** 에 출력된 값을 넣는다. (비밀값이 아니라 Variables 이다. 키 파일은 만들지 않는다.)

| 변수 | 예 |
|---|---|
| `GCP_PROJECT_ID` | `my-project-123` |
| `GCP_REGION` | `asia-northeast3` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/123456789/locations/global/workloadIdentityPools/github/providers/github-actions` |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | `noticatch-deployer@my-project-123.iam.gserviceaccount.com` |

Cloud Shell 에서 `gh` 로 로그인했다면 `bash infra/gcp/setup.sh <프로젝트 ID> --set-github-vars` 로 한 번에 넣을 수도 있다.

## 3. 첫 배포

Actions → **Deploy to Cloud Run** → Run workflow. 입력은 비워 둔다. 첫 배포는 서비스가 없어서 트래픽 0% 후보 단계 없이 바로 올라가고, 헬스체크를 거친다.

성공하면 Job Summary 에 서비스 주소(`https://noticatch-dashboard-….run.app`)가 나온다. 열어서 대시보드와 `/healthz`, `/version.json` 을 확인한다.

## 4. 모니터링 켜기

서비스 주소를 저장소 Variables 에 `CLOUD_RUN_URL` 로 넣으면 `Uptime Monitor` 가 30분마다 Cloud Run 도 확인한다. Cloud Monitoring 알림(업타임 체크, 5xx, 지연)은 Cloud Shell 에서:

```bash
bash infra/gcp/monitoring.sh <프로젝트 ID> <알림 받을 이메일>
```

## 문제가 생기면

| 증상 | 원인과 해결 |
|---|---|
| 인증 단계에서 `unauthorized_client` | `GCP_WORKLOAD_IDENTITY_PROVIDER` 값 오타, 또는 `GITHUB_REPO` 가 저장소 이름과 다름 (`setup.sh` 를 `GITHUB_REPO=소유자/저장소` 로 다시 실행) |
| `PERMISSION_DENIED` (Artifact Registry) | `setup.sh` 의 저장소 권한 단계가 끝나지 않음. 다시 실행 |
| 서비스가 403 을 돌려줌 | 조직 정책이 `allUsers` 를 막고 있다. 개인 프로젝트로 만들거나 조직 정책 예외를 요청 |
| 후보 헬스체크 실패 | Actions 로그의 시도별 기록과 Cloud Run 로그를 본다. 트래픽은 옮겨지지 않았으니 서비스는 이전 버전 그대로다 |

## 비용을 멈추려면

```bash
gcloud run services delete noticatch-dashboard --region asia-northeast3
gcloud artifacts repositories delete noticatch --location asia-northeast3
```
