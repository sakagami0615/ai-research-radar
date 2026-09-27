#!/usr/bin/env bash
set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DATE="${1:-$(date +%F)}"
AGENT="${AI_RADAR_AGENT:-claude}"

mkdir -p logs
LOG_FILE="logs/agent-daily-run-${DATE}.log"

run_agent() {
  local prompt="$1"
  case "$AGENT" in
    claude)
      claude -p "$prompt" --permission-mode bypassPermissions
      ;;
    codex)
      codex exec "$prompt" --sandbox workspace-write
      ;;
  esac
}

{
  echo "=== agent-daily-run start: $(date -Iseconds) date=${DATE} agent=${AGENT} ==="

  case "$AGENT" in
    claude|codex) ;;
    *)
      echo "unknown AI_RADAR_AGENT: ${AGENT} (expected 'claude' or 'codex')" >&2
      echo "=== agent-daily-run end: $(date -Iseconds) exit=1 ==="
      exit 1
      ;;
  esac

  PROMPT="$(sed "s/{date}/${DATE}/g" skills/agent-daily-run/entry-prompt.txt)"
  run_agent "$PROMPT"
  CLI_EXIT=$?

  REPORT_PATH="reports/daily/${DATE}.md"
  if [ ! -f "$REPORT_PATH" ]; then
    echo "ERROR: report not found at ${REPORT_PATH}" >&2
    CLI_EXIT=1
  fi

  if [ "$CLI_EXIT" -eq 0 ]; then
    REVIEW_ATTEMPTS=0
    MAX_REVIEW_ATTEMPTS=3
    FEEDBACK_PATH="data/runs/${DATE}/review_feedback.md"

    while [ "$REVIEW_ATTEMPTS" -lt "$MAX_REVIEW_ATTEMPTS" ]; do
      REVIEW_ATTEMPTS=$((REVIEW_ATTEMPTS + 1))
      echo "=== review cycle ${REVIEW_ATTEMPTS} start: $(date -Iseconds) ==="
      REVIEW_PROMPT="$(sed "s/{date}/${DATE}/g" skills/review-daily-report/entry-prompt.txt)"
      run_agent "$REVIEW_PROMPT"

      if [ ! -f "$FEEDBACK_PATH" ]; then
        echo "=== review cycle ${REVIEW_ATTEMPTS}: approved ==="
        break
      fi

      echo "=== review cycle ${REVIEW_ATTEMPTS}: issues found, requesting fix ==="
      FIX_PROMPT="$(sed "s/{date}/${DATE}/g" skills/agent-daily-run/fix-prompt.txt)"
      run_agent "$FIX_PROMPT"
    done

    if [ -f "$FEEDBACK_PATH" ]; then
      echo "=== review not resolved after ${MAX_REVIEW_ATTEMPTS} cycles: marking needs_review ==="
      python3.14 - "$DATE" <<'PYEOF'
import json
import sys
from pathlib import Path

date = sys.argv[1]
path = Path("data/runs") / date / "run_state.json"
state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
state["needs_review"] = True
path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
PYEOF

      BANNER="> ⚠️ **要確認**: 自動レビューで解消できなかった指摘があります。\`data/runs/${DATE}/review_feedback.md\` を確認してください。"
      TMP_REPORT="$(mktemp)"
      { printf '%s\n\n' "$BANNER"; cat "$REPORT_PATH"; } > "$TMP_REPORT"
      mv "$TMP_REPORT" "$REPORT_PATH"
      CLI_EXIT=1
    fi
  fi

  echo "=== agent-daily-run end: $(date -Iseconds) exit=${CLI_EXIT} ==="
  exit "$CLI_EXIT"
} >> "$LOG_FILE" 2>&1
