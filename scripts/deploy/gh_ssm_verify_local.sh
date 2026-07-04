#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCE_ID="${1:?instance id required}"
chmod +x "${ROOT}/ci_ssm_run.sh"

REMOTE_SCRIPT=$(cat <<EOF
set -euo pipefail
UP=\$(cat '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}/.deploy_state/host_port' 2>/dev/null || echo '${HOST_PORT:-8050}')
curl -sf "http://127.0.0.1:\${UP}/" >/dev/null 2>&1 && curl -sf "http://127.0.0.1:\${UP}/authors/" >/dev/null 2>&1
EOF
)

printf '%s\n' "${REMOTE_SCRIPT}" | bash "${ROOT}/ci_ssm_run.sh" "${INSTANCE_ID}" "verify-local"