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
ZERO_DOWNTIME="${ZERO_DOWNTIME:-true}"
STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-600}"
KEEP_NEXT_CONTAINER_ON_FAILURE="${KEEP_NEXT_CONTAINER_ON_FAILURE:-false}"

PORT_RANGE_START="${PORT_RANGE_START:-8050}"
PORT_RANGE_END="${PORT_RANGE_END:-8099}"
AUTO_PORT="${AUTO_PORT:-false}" # set true to auto-pick a free port if HOST_PORT is busy

STATE_DIR=".deploy_state"
STATE_FILE="${STATE_DIR}/host_port"

is_port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltnH "( sport = :${port} )" 2>/dev/null | grep -q .
    return $?
  fi
  sudo netstat -tlnp 2>/dev/null | grep -q ":${port} .*LISTEN"
}

pick_free_port() {
  local start="$1"
  local end="$2"
  local port
  for port in $(seq "$start" "$end"); do
    if ! is_port_listening "$port"; then
      echo "$port"
      return 0
    fi
  done
  return 1
}

container_exists() {
  local name="$1"
  docker ps -a --format '{{.Names}}' | grep -Fxq "$name"
}

container_running() {
  local name="$1"
  docker ps --format '{{.Names}}' | grep -Fxq "$name"
}

wait_for_http_ready() {
  local port="$1"
  local timeout="$2"
  local url="http://127.0.0.1:${port}/"
  local start_ts
  start_ts="$(date +%s)"

  echo "Waiting for app to become ready on ${url} (timeout: ${timeout}s)..."
  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "OK: app is responding on ${url}"
      return 0
    fi
    local now_ts
    now_ts="$(date +%s)"
    if (( now_ts - start_ts >= timeout )); then
      echo "ERROR: app did not become ready within ${timeout}s on ${url}"
      return 1
    fi
    sleep 2
  done
}

mkdir -p "${STATE_DIR}" || true
HOST_STATE_DIR="$(pwd)/${STATE_DIR}"
: "${CHATBOT_RAG_ENABLED:=true}"
: "${CHATBOT_RAG_TOP_K:=30}"
: "${CHATBOT_RAG_INDEX_PATH:=/app/.deploy_state/chatbot_rag_index.pkl}"

# Allow "HOST_PORT=auto" to enable auto port selection without extra flags.
if [[ "${HOST_PORT}" == "auto" ]]; then
  AUTO_PORT="true"
fi

echo "Deploying container: ${CONTAINER_NAME}"
echo "Requested bind   : 127.0.0.1:${HOST_PORT} -> ${DASH_PORT}"
echo "Domain           : ${DOMAIN_NAME:-<none>}"
echo "Zero downtime    : ${ZERO_DOWNTIME}"

# Zero-downtime requires the ability to switch nginx to a new port.
CAN_SWITCH_PORT="false"
if [[ "${CONFIGURE_NGINX}" == "true" && -n "${DOMAIN_NAME}" ]]; then
  CAN_SWITCH_PORT="true"
fi
if [[ "${ZERO_DOWNTIME}" == "true" && "${CAN_SWITCH_PORT}" != "true" ]]; then
  echo "WARNING: ZERO_DOWNTIME=true requires CONFIGURE_NGINX=true and DOMAIN_NAME; falling back to in-place restart."
  ZERO_DOWNTIME="false"
fi

# Remember the previous port (used by the currently-running nginx config).
OLD_HOST_PORT=""
if [[ -f "${STATE_FILE}" ]]; then
  OLD_HOST_PORT="$(cat "${STATE_FILE}" 2>/dev/null || true)"
fi

# If we have a persisted port, prefer it in auto mode.
if [[ "${AUTO_PORT}" == "true" ]]; then
  if [[ -f "${STATE_FILE}" ]]; then
    saved="$(cat "${STATE_FILE}" 2>/dev/null || true)"
    if [[ -n "${saved}" && "${saved}" != "auto" && ! $(is_port_listening "${saved}") ]]; then
      HOST_PORT="${saved}"
    fi
  fi
fi

# Port conflict handling
if is_port_listening "${HOST_PORT}"; then
  if [[ "${ZERO_DOWNTIME}" == "true" ]]; then
    echo "Port ${HOST_PORT} is busy; selecting a free port in ${PORT_RANGE_START}-${PORT_RANGE_END}..."
    HOST_PORT="$(pick_free_port "${PORT_RANGE_START}" "${PORT_RANGE_END}")" || {
      echo "ERROR: No free port found in range ${PORT_RANGE_START}-${PORT_RANGE_END}."
      exit 1
    }
  else
    # In-place restart expects the port to be in use by the current container.
    if container_exists "${CONTAINER_NAME}"; then
      echo "Port ${HOST_PORT} is currently in use by ${CONTAINER_NAME}; will restart in-place."
    else
      echo "ERROR: Port ${HOST_PORT} is already in use on this EC2 instance."
      sudo netstat -tlnp 2>/dev/null | grep ":${HOST_PORT} .*LISTEN" || true
      echo "Tip: set ZERO_DOWNTIME=true and CONFIGURE_NGINX=true to deploy on a new port without downtime."
      exit 1
    fi
  fi
fi

echo "Using bind       : 127.0.0.1:${HOST_PORT} -> ${DASH_PORT}"

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

docker build -t resulam-royalties:latest .

if [[ "${ZERO_DOWNTIME}" == "true" ]]; then
  NEXT_CONTAINER_NAME="${CONTAINER_NAME}--next"
  DEPLOY_FAILED="false"
  docker rm -f "${NEXT_CONTAINER_NAME}" 2>/dev/null || true
  cleanup_next() {
    if [[ "${KEEP_NEXT_CONTAINER_ON_FAILURE}" == "true" && "${DEPLOY_FAILED}" == "true" ]]; then
      echo "Keeping failed container ${NEXT_CONTAINER_NAME} for debugging."
      return 0
    fi
    docker rm -f "${NEXT_CONTAINER_NAME}" 2>/dev/null || true
  }
  trap cleanup_next EXIT

  docker run -d \
    --name "${NEXT_CONTAINER_NAME}" \
    --restart unless-stopped \
    -p 127.0.0.1:${HOST_PORT}:${DASH_PORT} \
    -v ~/.aws:/root/.aws:ro \
    -v "${HOST_STATE_DIR}:/app/.deploy_state" \
    -e USE_S3_DATA="${USE_S3_DATA}" \
    -e S3_BUCKET="${S3_BUCKET}" \
    -e AWS_DEFAULT_REGION="${AWS_REGION}" \
    -e AUTO_SYNC_INTERVAL="${AUTO_SYNC_INTERVAL}" \
    -e PUBLIC_BASE_URL="${PUBLIC_BASE_URL}" \
    -e CHATBOT_RAG_ENABLED="${CHATBOT_RAG_ENABLED}" \
    -e CHATBOT_RAG_INDEX_PATH="${CHATBOT_RAG_INDEX_PATH}" \
    -e CHATBOT_RAG_TOP_K="${CHATBOT_RAG_TOP_K}" \
    resulam-royalties:latest

  echo "Waiting for container to start..."
  sleep 2

  if container_running "${NEXT_CONTAINER_NAME}"; then
    echo "OK: next container is running: ${NEXT_CONTAINER_NAME}"
  else
    echo "ERROR: next container failed to start: ${NEXT_CONTAINER_NAME}"
    DEPLOY_FAILED="true"
    docker logs "${NEXT_CONTAINER_NAME}" || true
    docker ps -a | grep -F "${NEXT_CONTAINER_NAME}" || true
    exit 1
  fi

  if ! wait_for_http_ready "${HOST_PORT}" "${STARTUP_TIMEOUT_SECONDS}"; then
    echo "ERROR: next container did not become ready; keeping existing deployment unchanged."
    echo "Last 200 lines of logs from ${NEXT_CONTAINER_NAME}:"
    DEPLOY_FAILED="true"
    docker ps -a | grep -F "${NEXT_CONTAINER_NAME}" || true
    docker inspect --format='{{.State.Status}} (exit={{.State.ExitCode}})' "${NEXT_CONTAINER_NAME}" 2>/dev/null || true
    docker logs "${NEXT_CONTAINER_NAME}" --tail 200 || true
    exit 1
  fi

  if [[ -f scripts/deploy/setup_nginx_vhost.sh ]]; then
    chmod +x scripts/deploy/setup_nginx_vhost.sh || true
    DOMAIN_NAME="${DOMAIN_NAME}" OLD_DOMAIN_NAME="${OLD_DOMAIN_NAME}" UPSTREAM_PORT="${HOST_PORT}" \
      bash scripts/deploy/setup_nginx_vhost.sh
  else
    echo "ERROR: scripts/deploy/setup_nginx_vhost.sh not found; cannot switch nginx upstream port."
    exit 1
  fi

  if container_exists "${CONTAINER_NAME}"; then
    echo "Stopping previous container: ${CONTAINER_NAME}"
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
  fi

  echo "Promoting ${NEXT_CONTAINER_NAME} -> ${CONTAINER_NAME}"
  docker rename "${NEXT_CONTAINER_NAME}" "${CONTAINER_NAME}"
  echo "${HOST_PORT}" > "${STATE_FILE}" || true
  trap - EXIT

  echo "Container logs (last 80 lines):"
  docker logs "${CONTAINER_NAME}" --tail 80 || true
else
  # In-place restart: same upstream port, but will cause brief downtime.
  echo "In-place restart (may show 502 until the app finishes loading data)."
  docker stop "${CONTAINER_NAME}" 2>/dev/null || true
  docker rm "${CONTAINER_NAME}" 2>/dev/null || true

  docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    -p 127.0.0.1:${HOST_PORT}:${DASH_PORT} \
    -v ~/.aws:/root/.aws:ro \
    -v "${HOST_STATE_DIR}:/app/.deploy_state" \
    -e USE_S3_DATA="${USE_S3_DATA}" \
    -e S3_BUCKET="${S3_BUCKET}" \
    -e AWS_DEFAULT_REGION="${AWS_REGION}" \
    -e AUTO_SYNC_INTERVAL="${AUTO_SYNC_INTERVAL}" \
    -e PUBLIC_BASE_URL="${PUBLIC_BASE_URL}" \
    -e CHATBOT_RAG_ENABLED="${CHATBOT_RAG_ENABLED}" \
    -e CHATBOT_RAG_INDEX_PATH="${CHATBOT_RAG_INDEX_PATH}" \
    -e CHATBOT_RAG_TOP_K="${CHATBOT_RAG_TOP_K}" \
    resulam-royalties:latest

  if ! wait_for_http_ready "${HOST_PORT}" "${STARTUP_TIMEOUT_SECONDS}"; then
    echo "ERROR: container did not become ready."
    docker logs "${CONTAINER_NAME}" --tail 200 || true
    exit 1
  fi

  # If nginx is managed here, keep it pointing at HOST_PORT.
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

  echo "${HOST_PORT}" > "${STATE_FILE}" || true
fi
