#!/usr/bin/env bash
# Cloud Monitoring 설정: 업타임 체크 + 알림 정책 3개 + 이메일 알림 채널. (첫 배포 뒤에 한 번 실행한다)
#
#   bash infra/gcp/monitoring.sh <프로젝트 ID> <알림 받을 이메일>
#
# 만드는 것
#   - 업타임 체크: 서비스의 /healthz 를 5분마다 확인한다.
#   - 알림 1: 업타임 체크 실패
#   - 알림 2: 5xx 오류가 5분에 5건 넘음
#   - 알림 3: 응답시간 p95 가 5분 동안 1초 넘음
set -euo pipefail

PROJECT_ID="${1:?사용법: bash infra/gcp/monitoring.sh <프로젝트 ID> <이메일>}"
EMAIL="${2:?알림 받을 이메일이 필요합니다}"
REGION="${REGION:-asia-northeast3}"
SERVICE="noticatch-dashboard"
HERE="$(cd "$(dirname "$0")" && pwd)"

gcloud config set project "$PROJECT_ID" > /dev/null

URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format 'value(status.url)')
HOST="${URL#https://}"
echo "서비스: $URL"

echo "==> 알림 채널 (이메일)"
CHANNEL=$(gcloud beta monitoring channels list --filter "type=email AND labels.email_address=$EMAIL" --format 'value(name)' | head -n1)
if [ -z "$CHANNEL" ]; then
  CHANNEL=$(gcloud beta monitoring channels create --display-name "NotiCatch alerts" --type email \
    --channel-labels "email_address=$EMAIL" --format 'value(name)')
fi

echo "==> 업타임 체크 (/healthz, 5분 간격)"
CHECK_NAME="$SERVICE-healthz"
CHECK_ID=$(gcloud monitoring uptime list-configs --filter "displayName=$CHECK_NAME" --format 'value(name)' | head -n1 | awk -F/ '{print $NF}')
if [ -z "$CHECK_ID" ]; then
  gcloud monitoring uptime create "$CHECK_NAME" --resource-type uptime-url \
    --resource-labels "host=$HOST,project_id=$PROJECT_ID" --path /healthz --protocol https \
    --period 5 --timeout 10 --status-classes 2xx --content-matchers "ok"
  CHECK_ID=$(gcloud monitoring uptime list-configs --filter "displayName=$CHECK_NAME" --format 'value(name)' | head -n1 | awk -F/ '{print $NF}')
fi

echo "==> 알림 정책"
create_policy() {  # create_policy <파일>  (같은 이름이 있으면 건너뜀)
  local file="$1" name tmp
  name=$(grep -m1 '^displayName:' "$file" | sed 's/^displayName: *"\(.*\)"$/\1/')
  if gcloud alpha monitoring policies list --filter "displayName=\"$name\"" --format 'value(name)' | grep -q .; then
    echo "  이미 있음: $name"; return
  fi
  tmp=$(mktemp)
  sed -e "s|__CHECK_ID__|$CHECK_ID|g" -e "s|__CHANNEL__|$CHANNEL|g" -e "s|__SERVICE__|$SERVICE|g" "$file" > "$tmp"
  gcloud alpha monitoring policies create --policy-from-file "$tmp" > /dev/null
  rm -f "$tmp"
  echo "  만듦: $name"
}
for f in "$HERE"/monitoring/alert-*.yaml; do create_policy "$f"; done

echo "완료. 콘솔: https://console.cloud.google.com/monitoring/alerting?project=$PROJECT_ID"
