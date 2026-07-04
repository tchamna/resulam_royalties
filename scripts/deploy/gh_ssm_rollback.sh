#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCE_ID="${1:?instance id required}"
chmod +x "${ROOT}/ci_ssm_run.sh"

DOMAIN_NAME_EFFECTIVE="${DOMAIN_NAME:-africanlanguagelibrary.tchamna.com}"
if [[ "${DOMAIN_NAME_EFFECTIVE}" == "resulam-royalties.tchamna.com" ]]; then
  DOMAIN_NAME_EFFECTIVE="africanlanguagelibrary.tchamna.com"
fi
CN="${CONTAINER_NAME:-resulam-royalties}"

REMOTE_SCRIPT=$(cat <<EOF
set -euo pipefail
if ! docker image inspect ${CN}:previous >/dev/null 2>&1; then
  echo 'No previous image found; rollback skipped.'
  exit 0
fi
TARGET_PORT='${HOST_PORT:-8050}'
if command -v nginx >/dev/null 2>&1; then
  P=\$(sudo nginx -T 2>/dev/null | awk -v domain='${DOMAIN_NAME_EFFECTIVE}' '
    /^# configuration file / {file=\$4; sub(":\$","",file)}
    \$0 ~ /server_name/ && index(\$0, domain) {in_server=1}
    in_server && match(\$0, /proxy_pass[[:space:]]+http:\\/\\/127\\.0\\.0\\.1:([0-9]+)/, m) {print m[1]; exit}
    in_server && \$0 ~ /^}/ {in_server=0}
  ' || true)
  if [ -n "\${P:-}" ]; then TARGET_PORT="\$P"; fi
fi
echo "Rollback bind port: \$TARGET_PORT"
docker stop '${CN}' 2>/dev/null || true
docker rm '${CN}' 2>/dev/null || true
docker run -d \
  --name '${CN}' \
  --restart unless-stopped \
  -p 127.0.0.1:\$TARGET_PORT:${DASH_PORT:-8050} \
  -v ~/.aws:/root/.aws:ro \
  -e USE_S3_DATA='true' \
  -e S3_BUCKET='${S3_BUCKET:-resulam-royalties}' \
  -e AWS_DEFAULT_REGION='${AWS_REGION:-us-east-1}' \
  -e AUTO_SYNC_INTERVAL='${AUTO_SYNC_INTERVAL:-60}' \
  -e PUBLIC_BASE_URL='https://${DOMAIN_NAME_EFFECTIVE}' \
  ${CN}:previous
if [ -f '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}/scripts/deploy/setup_nginx_vhost.sh' ]; then
  chmod +x '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}/scripts/deploy/setup_nginx_vhost.sh' || true
  DOMAIN_NAME='${DOMAIN_NAME_EFFECTIVE}' UPSTREAM_PORT="\$TARGET_PORT" bash '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}/scripts/deploy/setup_nginx_vhost.sh' || true
fi
docker logs '${CN}' --tail 50 || true
EOF
)

printf '%s\n' "${REMOTE_SCRIPT}" | bash "${ROOT}/ci_ssm_run.sh" "${INSTANCE_ID}" "rollback"