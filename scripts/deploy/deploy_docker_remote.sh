#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CONTAINER_NAME:-resulam-royalties}"
HOST_PORT="${HOST_PORT:-8050}"
DASH_PORT="${DASH_PORT:-8050}"
S3_BUCKET="${S3_BUCKET:-resulam-royalties}"
AWS_REGION="${AWS_REGION:-us-east-1}"
USE_S3_DATA="${USE_S3_DATA:-true}"
AUTO_SYNC_INTERVAL="${AUTO_SYNC_INTERVAL:-60}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
CONFIGURE_NGINX="${CONFIGURE_NGINX:-false}"
DOMAIN_NAME="${DOMAIN_NAME:-}"
OLD_DOMAIN_NAME="${OLD_DOMAIN_NAME:-}"

echo "Deploying container: ${CONTAINER_NAME}"
echo "Host bind       : 127.0.0.1:${HOST_PORT} -> ${DASH_PORT}"
echo "Domain          : ${DOMAIN_NAME:-<none>}"

# Port conflict check (EC2 often hosts many apps)
if sudo netstat -tlnp 2>/dev/null | grep -q ":${HOST_PORT} .*LISTEN"; then
  echo "ERROR: Port ${HOST_PORT} is already in use on this EC2 instance."
  sudo netstat -tlnp 2>/dev/null | grep ":${HOST_PORT} .*LISTEN" || true
  exit 1
fi

# Ensure AWS credentials exist for S3 sync (Dash container reads from /root/.aws mount)
if [[ -n "${AWS_ACCESS_KEY_ID:-}" && -n "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  mkdir -p ~/.aws
  cat > ~/.aws/credentials <<CREDS
[default]
aws_access_key_id = ${AWS_ACCESS_KEY_ID}
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}
CREDS
  cat > ~/.aws/config <<CFG
[default]
region = ${AWS_REGION}
CFG
  chmod 600 ~/.aws/credentials
else
  echo "WARNING: AWS credentials not provided to remote deploy script; S3 sync may fail."
fi

# Keep previous image for rollback
if docker image inspect resulam-royalties:latest >/dev/null 2>&1; then
  docker tag resulam-royalties:latest resulam-royalties:previous || true
fi

docker stop "${CONTAINER_NAME}" 2>/dev/null || true
docker rm "${CONTAINER_NAME}" 2>/dev/null || true

docker build -t resulam-royalties:latest .

docker run -d \
  --name "${CONTAINER_NAME}" \
  --restart unless-stopped \
  -p 127.0.0.1:${HOST_PORT}:${DASH_PORT} \
  -v ~/.aws:/root/.aws:ro \
  -e USE_S3_DATA="${USE_S3_DATA}" \
  -e S3_BUCKET="${S3_BUCKET}" \
  -e AWS_DEFAULT_REGION="${AWS_REGION}" \
  -e AUTO_SYNC_INTERVAL="${AUTO_SYNC_INTERVAL}" \
  -e PUBLIC_BASE_URL="${PUBLIC_BASE_URL}" \
  resulam-royalties:latest

echo "Waiting for container to start..."
sleep 5

if docker ps | grep -q "${CONTAINER_NAME}"; then
  echo "OK: container is running"
else
  echo "ERROR: container failed to start"
  docker logs "${CONTAINER_NAME}" || true
  docker ps -a | grep "${CONTAINER_NAME}" || true
  exit 1
fi

if [[ "${CONFIGURE_NGINX}" == "true" && -n "${DOMAIN_NAME}" ]]; then
  if [[ -f scripts/deploy/setup_nginx_vhost.sh ]]; then
    chmod +x scripts/deploy/setup_nginx_vhost.sh || true
    DOMAIN_NAME="${DOMAIN_NAME}" OLD_DOMAIN_NAME="${OLD_DOMAIN_NAME}" UPSTREAM_PORT="${HOST_PORT}" \
      bash scripts/deploy/setup_nginx_vhost.sh
  else
    echo "WARNING: scripts/deploy/setup_nginx_vhost.sh not found; skipping nginx config"
  fi
else
  echo "Nginx configuration skipped (CONFIGURE_NGINX=${CONFIGURE_NGINX}, DOMAIN_NAME=${DOMAIN_NAME:-<none>})"
fi

echo "Container logs (last 50 lines):"
docker logs "${CONTAINER_NAME}" --tail 50 || true
