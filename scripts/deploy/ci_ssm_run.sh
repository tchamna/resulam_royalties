#!/usr/bin/env bash
set -euo pipefail

INSTANCE_ID="${1:?Usage: ci_ssm_run.sh INSTANCE_ID [comment]}"
COMMENT="${2:-github-actions}"
TIMEOUT_SECONDS="${SSM_TIMEOUT_SECONDS:-7200}"
POLL_SECONDS="${SSM_POLL_SECONDS:-10}"

SCRIPT="$(cat)"
if [[ -z "${SCRIPT//[[:space:]]/}" ]]; then
  echo "ERROR: empty script on stdin" >&2
  exit 1
fi

PARAMS="$(jq -n --arg script "$SCRIPT" '{commands: [$script]}')"

CMD_ID="$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "$COMMENT" \
  --timeout-seconds "$TIMEOUT_SECONDS" \
  --parameters "$PARAMS" \
  --query Command.CommandId \
  --output text)"

echo "SSM command id: ${CMD_ID} (instance: ${INSTANCE_ID})"
START_TS="$(date +%s)"

while true; do
  INV="$(aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" --output json)"
  STATUS="$(echo "$INV" | jq -r .Status)"
  case "$STATUS" in
    Pending|InProgress|Delayed)
      NOW_TS="$(date +%s)"
      if (( NOW_TS - START_TS > TIMEOUT_SECONDS )); then
        echo "ERROR: timed out waiting for SSM command ${CMD_ID}" >&2
        exit 1
      fi
      sleep "$POLL_SECONDS"
      ;;
    Success)
      echo "=== SSM stdout ==="
      echo "$INV" | jq -r .StandardOutputContent
      STDERR="$(echo "$INV" | jq -r .StandardErrorContent)"
      if [[ -n "${STDERR}" ]]; then
        echo "=== SSM stderr ==="
        echo "$STDERR"
      fi
      exit 0
      ;;
    *)
      echo "ERROR: SSM command failed with status: ${STATUS}" >&2
      echo "$INV" | jq -r .StandardOutputContent
      echo "$INV" | jq -r .StandardErrorContent >&2
      exit 1
      ;;
  esac
done
