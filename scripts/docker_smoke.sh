#!/usr/bin/env bash
# 컨테이너 이미지를 로컬에서 실제로 실행해 보고 응답을 확인한다.
#
#   scripts/docker_smoke.sh <이미지 이름[:태그]> [호스트 포트]
#
# 확인하는 것: 컨테이너가 healthy 가 되는지, 대시보드 페이지와 샘플 데이터가 응답하는지.
# 끝나면(실패해도) 컨테이너를 지운다.
set -euo pipefail

IMAGE="${1:?사용법: $0 <이미지> [포트]}"
PORT="${2:-8080}"
NAME="noticatch-smoke-$$"

cleanup() {
  if [ "${SMOKE_KEEP:-0}" != "1" ]; then docker rm -f "$NAME" > /dev/null 2>&1 || true; fi
}
trap cleanup EXIT

docker run -d --name "$NAME" -p "$PORT:8080" "$IMAGE" > /dev/null

echo "컨테이너가 healthy 가 될 때까지 기다립니다 (최대 60초)"
status=""
for _ in $(seq 1 30); do
  status=$(docker inspect -f '{{if .State.Running}}{{.State.Health.Status}}{{else}}exited{{end}}' "$NAME")
  [ "$status" = "healthy" ] && break
  [ "$status" = "exited" ] && break
  sleep 2
done
echo "상태: $status"
if [ "$status" != "healthy" ]; then
  docker logs "$NAME" || true
  echo "컨테이너가 healthy 상태가 되지 못했습니다." >&2
  exit 1
fi

base="http://127.0.0.1:$PORT"

code=$(curl -s -o /tmp/smoke-index.html -w '%{http_code}' "$base/")
[ "$code" = "200" ] || { echo "/ 응답 코드: $code" >&2; exit 1; }
grep -q "NotiCatch" /tmp/smoke-index.html || { echo "대시보드 페이지에 NotiCatch 제목이 없습니다." >&2; exit 1; }
echo "OK  GET /                 → 200, 대시보드 페이지"

code=$(curl -s -o /tmp/smoke-data.json -w '%{http_code}' "$base/sample-data.json")
[ "$code" = "200" ] || { echo "/sample-data.json 응답 코드: $code" >&2; exit 1; }
python3 -c "import json; d = json.load(open('/tmp/smoke-data.json')); assert 'metrics' in d" \
  || { echo "sample-data.json 형식이 올바르지 않습니다." >&2; exit 1; }
echo "OK  GET /sample-data.json → 200, JSON(metrics 포함)"

code=$(curl -s -o /dev/null -w '%{http_code}' "$base/no-such-path")
[ "$code" = "404" ] || { echo "없는 경로 응답 코드: $code (404 기대)" >&2; exit 1; }
echo "OK  GET /no-such-path          → 404"

user=$(docker exec "$NAME" id -un)
[ "$user" != "root" ] || { echo "컨테이너가 root 로 실행되고 있습니다." >&2; exit 1; }
echo "OK  실행 사용자: $user (root 아님)"

echo "스모크 테스트 통과: $IMAGE"
