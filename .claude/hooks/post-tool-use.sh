#!/usr/bin/env bash
# post-tool-use.sh
# Fires after every tool use. Pipes stdin (Claude Code tool JSON) to
# log_tool_use.py which extracts tool name and content sizes for the daily
# tool log. Actual token costs are aggregated at session end by cost_report.py.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$VAULT_DIR/AI/sessions/$TODAY-tool-log.jsonl"
PYTHON="$VAULT_DIR/.venv/bin/python3"

mkdir -p "$(dirname "$LOG_FILE")"

# Pipe stdin directly — log_tool_use.py reads tool JSON from stdin
CLAUDE_TOOL_NAME="${CLAUDE_TOOL_NAME:-unknown}" \
  "$PYTHON" "$VAULT_DIR/scripts/log_tool_use.py" "$LOG_FILE"
