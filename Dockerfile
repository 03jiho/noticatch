# NotiCatch 대시보드(정적 사이트)를 nginx 로 서비스하는 이미지.
# root 가 아닌 사용자로 실행하는 nginx-unprivileged 이미지를 쓰므로 포트는 8080 이다. (Cloud Run 기본 포트와 같다)
#
#   docker build --build-arg GIT_SHA=$(git rev-parse HEAD) -t noticatch-dashboard .
#   docker run --rm -p 8080:8080 noticatch-dashboard   → http://localhost:8080
#   헬스체크: /healthz   배포된 리비전: /version.json

# 1단계: 사이트 파일과 version.json 을 만든다. (최종 이미지는 root 가 아니라 파일을 만들 수 없어서 따로 만든다)
FROM alpine:3.20 AS site
ARG GIT_SHA=dev
COPY dashboard/ /site/
RUN printf '{"sha":"%s"}\n' "$GIT_SHA" > /site/version.json

# 2단계: 실행 이미지
FROM nginxinc/nginx-unprivileged:1.27-alpine

ARG GIT_SHA=dev
LABEL org.opencontainers.image.title="noticatch-dashboard" \
      org.opencontainers.image.description="NotiCatch DORA dashboard served by nginx" \
      org.opencontainers.image.source="https://github.com/03jiho/noticatch" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="MIT"

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=site --chown=nginx:nginx /site/ /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
