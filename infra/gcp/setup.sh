#!/usr/bin/env bash
# Cloud Run 배포에 필요한 Google Cloud 리소스를 한 번에 만든다. (여러 번 실행해도 안전하다)
#
# Cloud Shell(https://shell.cloud.google.com) 에서 실행하는 것을 권장한다. 이미 로그인되어 있다.
#
#   bash infra/gcp/setup.sh <프로젝트 ID>
#   bash infra/gcp/setup.sh <프로젝트 ID> --set-github-vars     # gh 로 저장소 Variables 까지 넣는다
#
# 만드는 것
#   - API 켜기: Cloud Run, Artifact Registry, IAM Credentials, Cloud Monitoring
#   - Artifact Registry 도커 저장소 (noticatch)
#   - 서비스 계정 2개
#       noticatch-deployer : GitHub Actions 가 배포할 때 쓴다 (Cloud Run 관리, 이미지 올리기)
#       noticatch-runtime  : 컨테이너가 실행될 때 쓴다 (아무 권한도 주지 않는다)
#   - Workload Identity Federation: GitHub Actions 가 키 파일 없이 deployer 로 로그인하게 한다.
#     이 저장소(GITHUB_REPO)에서 온 요청만 허락한다.
set -euo pipefail

PROJECT_ID="${1:?사용법: bash infra/gcp/setup.sh <프로젝트 ID> [--set-github-vars]}"
SET_VARS="${2:-}"
REGION="${REGION:-asia-northeast3}"          # 서울
GITHUB_REPO="${GITHUB_REPO:-03jiho/noticatch}"
AR_REPO="noticatch"
POOL="github"
PROVIDER="github-actions"
DEPLOYER="noticatch-deployer"
RUNTIME="noticatch-runtime"

gcloud config set project "$PROJECT_ID" > /dev/null
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
DEPLOYER_EMAIL="$DEPLOYER@$PROJECT_ID.iam.gserviceaccount.com"
RUNTIME_EMAIL="$RUNTIME@$PROJECT_ID.iam.gserviceaccount.com"

echo "==> API 켜기"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  iamcredentials.googleapis.com iam.googleapis.com monitoring.googleapis.com

echo "==> Artifact Registry 저장소 ($AR_REPO)"
gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" > /dev/null 2>&1 \
  || gcloud artifacts repositories create "$AR_REPO" --repository-format docker --location "$REGION" \
       --description "NotiCatch container images"

echo "==> 서비스 계정"
for sa in "$DEPLOYER" "$RUNTIME"; do
  gcloud iam service-accounts describe "$sa@$PROJECT_ID.iam.gserviceaccount.com" > /dev/null 2>&1 \
    || gcloud iam service-accounts create "$sa" --display-name "$sa"
done

echo "==> deployer 권한 (필요한 것만)"
# Cloud Run 서비스를 만들고 바꾼다.
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$DEPLOYER_EMAIL" \
  --role roles/run.admin --condition=None > /dev/null
# 이 저장소에만 이미지를 올린다.
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" --location "$REGION" \
  --member "serviceAccount:$DEPLOYER_EMAIL" --role roles/artifactregistry.writer > /dev/null
# runtime 계정으로 서비스를 실행하도록 허락한다. (runtime 계정 하나에만)
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_EMAIL" \
  --member "serviceAccount:$DEPLOYER_EMAIL" --role roles/iam.serviceAccountUser > /dev/null

echo "==> Workload Identity Federation"
gcloud iam workload-identity-pools describe "$POOL" --location global > /dev/null 2>&1 \
  || gcloud iam workload-identity-pools create "$POOL" --location global --display-name "GitHub Actions"
gcloud iam workload-identity-pools providers describe "$PROVIDER" --location global --workload-identity-pool "$POOL" > /dev/null 2>&1 \
  || gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location global --workload-identity-pool "$POOL" \
       --issuer-uri "https://token.actions.githubusercontent.com" \
       --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
       --attribute-condition "assertion.repository=='$GITHUB_REPO'"
# 이 저장소에서 온 토큰만 deployer 계정을 쓸 수 있다.
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_EMAIL" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository/$GITHUB_REPO" > /dev/null

WIF_PROVIDER="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER"

echo
echo "완료. GitHub 저장소(Settings → Secrets and variables → Actions → Variables)에 아래 4개를 넣어 주세요."
echo "  GCP_PROJECT_ID                  = $PROJECT_ID"
echo "  GCP_REGION                      = $REGION"
echo "  GCP_WORKLOAD_IDENTITY_PROVIDER  = $WIF_PROVIDER"
echo "  GCP_DEPLOY_SERVICE_ACCOUNT      = $DEPLOYER_EMAIL"

if [ "$SET_VARS" = "--set-github-vars" ]; then
  gh variable set GCP_PROJECT_ID --repo "$GITHUB_REPO" --body "$PROJECT_ID"
  gh variable set GCP_REGION --repo "$GITHUB_REPO" --body "$REGION"
  gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "$GITHUB_REPO" --body "$WIF_PROVIDER"
  gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --repo "$GITHUB_REPO" --body "$DEPLOYER_EMAIL"
  echo "저장소 Variables 를 설정했습니다."
fi
