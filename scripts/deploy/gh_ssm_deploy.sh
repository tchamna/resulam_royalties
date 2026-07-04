#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTANCE_ID="${1:?instance id required}"
chmod +x "${ROOT}/ci_ssm_run.sh"

DOMAIN_NAME_EFFECTIVE="${DOMAIN_NAME:-africanlanguagelibrary.tchamna.com}"
OLD_DOMAIN_NAME_EFFECTIVE="${OLD_DOMAIN_NAME:-resulam-royalties.tchamna.com}"
if [[ "${DOMAIN_NAME_EFFECTIVE}" == "resulam-royalties.tchamna.com" ]]; then
  DOMAIN_NAME_EFFECTIVE="africanlanguagelibrary.tchamna.com"
  OLD_DOMAIN_NAME_EFFECTIVE="resulam-royalties.tchamna.com"
fi

REMOTE_SCRIPT=$(cat <<EOF
set -euo pipefail
git config --global --add safe.directory '*'
cd '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}' || { mkdir -p '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}'; cd '${APP_DIR:-/home/ec2-user/apps/resulam_royalties}'; }
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then git init; fi
if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin 'https://github.com/${GITHUB_REPOSITORY}.git'
else
  git remote add origin 'https://github.com/${GITHUB_REPOSITORY}.git'
fi
rm -f royalties_exploded_2024.csv royalties_per_author_2024.csv royalties_resulambooks_from_2015_2024_history_df.csv || true
git fetch origin main
git reset --hard origin/main
git clean -fd -e .deploy_state || true
chmod +x scripts/deploy/deploy_docker_remote.sh scripts/deploy/setup_nginx_vhost.sh || true
AWS_ACCESS_KEY_ID='${AWS_ACCESS_KEY_ID}' \
AWS_SECRET_ACCESS_KEY='${AWS_SECRET_ACCESS_KEY}' \
AWS_REGION='${AWS_REGION:-us-east-1}' \
S3_BUCKET='${S3_BUCKET:-resulam-royalties}' \
CONTAINER_NAME='${CONTAINER_NAME:-resulam-royalties}' \
HOST_PORT='${HOST_PORT:-8050}' \
DASH_PORT='${DASH_PORT:-8050}' \
DOMAIN_NAME='${DOMAIN_NAME_EFFECTIVE}' \
OLD_DOMAIN_NAME='${OLD_DOMAIN_NAME_EFFECTIVE}' \
CONFIGURE_NGINX='${CONFIGURE_NGINX:-true}' \
ZERO_DOWNTIME='${ZERO_DOWNTIME:-true}' \
KEEP_NEXT_CONTAINER_ON_FAILURE='${KEEP_NEXT_CONTAINER_ON_FAILURE:-true}' \
PUBLIC_BASE_URL='https://${DOMAIN_NAME_EFFECTIVE}' \
bash scripts/deploy/deploy_docker_remote.sh
EOF
)

printf '%s\n' "${REMOTE_SCRIPT}" | bash "${ROOT}/ci_ssm_run.sh" "${INSTANCE_ID}" "deploy"