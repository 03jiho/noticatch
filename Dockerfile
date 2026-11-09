# NotiCatch 대시보드(정적 사이트)를 nginx 로 서비스하는 이미지.
# root 가 아닌 사용자로 실행하는 nginx-unprivileged 이미지를 쓰므로 포트는 8080 이다.
#
#   docker build -t noticatch-dashboard .
#   docker run --rm -p 8080:8080 noticatch-dashboard   → http://localhost:8080
FROM nginxinc/nginx-unprivileged:1.27-alpine

LABEL org.opencontainers.image.title="noticatch-dashboard" \
      org.opencontainers.image.description="NotiCatch DORA dashboard served by nginx" \
      org.opencontainers.image.source="https://github.com/03jiho/noticatch" \
      org.opencontainers.image.licenses="MIT"

COPY --chown=nginx:nginx dashboard/ /usr/share/nginx/html/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
