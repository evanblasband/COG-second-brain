#!/usr/bin/env bash
# post-tool-use.sh
# Fires after every tool use. Lightweight — just logs to a daily tool log.
# Used for auditing costs and catching unexpected external calls.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TODAY=$(date +%Y-%m-%d)
LOG_FILE="$VAULT_DIR/AI/sessions/$TODAY-tool-log.jsonl"

# Claude Code injects tool name and result via env vars or stdin depending on version.
# Log a minimal record with timestamp.
TOOL_NAME="${CLAUDE_TOOL_NAME:-unknown}"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "{\"ts\":\"$TIMESTAMP\",\"tool\":\"$TOOL_NAME\"}" >> "$LOG_FILE"
