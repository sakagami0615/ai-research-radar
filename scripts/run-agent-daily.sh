#!/usr/bin/env bash
set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DATE="${1:-$(date +%F)}"
AGENT="${AI_RADAR_AGENT:-claude}"

mkdir -p logs
LOG_FILE="logs/agent-daily-run-${DATE}.log"

PROMPT="$(sed "s/{date}/${DATE}/g" skills/agent-daily-run/entry-prompt.txt)"

{
  echo "=== agent-daily-run start: $(date -Iseconds) date=${DATE} agent=${AGENT} ==="

  case "$AGENT" in
    claude)
      claude -p "$PROMPT" --permission-mode bypassPermissions
      CLI_EXIT=$?
      ;;
    codex)
      codex exec "$PROMPT" --sandbox workspace-write
      CLI_EXIT=$?
      ;;
    *)
      echo "unknown AI_RADAR_AGENT: ${AGENT} (expected 'claude' or 'codex')" >&2
      CLI_EXIT=1
      ;;
  esac

  REPORT_PATH="reports/daily/${DATE}.md"
  if [ ! -f "$REPORT_PATH" ]; then
    echo "ERROR: report not found at ${REPORT_PATH}" >&2
    CLI_EXIT=1
  fi

  echo "=== agent-daily-run end: $(date -Iseconds) exit=${CLI_EXIT} ==="
  exit "$CLI_EXIT"
} >> "$LOG_FILE" 2>&1
