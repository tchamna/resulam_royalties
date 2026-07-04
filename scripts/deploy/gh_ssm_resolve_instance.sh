#!/usr/bin/env bash
set -euo pipefail
if [ -n "${EC2_INSTANCE_ID:-}" ]; then
  echo "${EC2_INSTANCE_ID}"
  exit 0
fi
if [ -z "${EC2_HOST:-}" ]; then
  echo "ERROR: Set EC2_INSTANCE_ID or EC2_HOST" >&2
  exit 1
fi
INSTANCE_ID="$(aws ec2 describe-instances \
  --filters "Name=instance-state-name,Values=running" "Name=ip-address,Values=${EC2_HOST}" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)"
if [ -z "${INSTANCE_ID}" ] || [ "${INSTANCE_ID}" = "None" ]; then
  echo "ERROR: No running instance for EC2_HOST=${EC2_HOST}" >&2
  exit 1
fi
echo "${INSTANCE_ID}"