#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCE_ID="${1:?instance id required}"
chmod +x "${ROOT}/ci_ssm_run.sh"

REMOTE_SCRIPT=$(cat <<EOF
set -euo pipefail
UPSTREAM_PORT=\$(cat '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}/.deploy_state/host_port' 2>/dev/null || echo '${HOST_PORT:-8050}')
echo '=== Docker Container Status ==='
docker ps -a | grep -F '${CONTAINER_NAME:-resulam-royalties}' || echo 'Container not found'
echo ''
echo '=== Last 30 lines of container log ==='
docker logs '${CONTAINER_NAME:-resulam-royalties}' --tail 30 2>&1 || true
echo ''
echo '=== Container health status ==='
docker inspect --format='{{.State.Health.Status}}' '${CONTAINER_NAME:-resulam-royalties}' 2>/dev/null || echo 'Health check not available'
echo ''
echo "=== Checking if port \${UPSTREAM_PORT} is listening ==="
sudo netstat -tlnp | grep ":\${UPSTREAM_PORT} " || echo "Port \${UPSTREAM_PORT} not listening"
EOF
)

printf '%s\n' "${REMOTE_SCRIPT}" | bash "${ROOT}/ci_ssm_run.sh" "${INSTANCE_ID}" "check-logs" || true