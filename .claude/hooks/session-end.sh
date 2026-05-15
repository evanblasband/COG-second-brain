#!/usr/bin/env bash
# session-end.sh
# Fires on Stop (after every Claude response). Creates a session stub on first
# fire, then launches a background summarizer to fill it in automatically.
# Never blocks the session — summary is written silently in the background.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP=$(date +%Y-%m-%d-%H)
SUMMARY_FILE="$VAULT_DIR/AI/sessions/$TIMESTAMP.md"
PYTHON="$VAULT_DIR/.venv/bin/python3"

# Create stub on first fire this hour
if [[ ! -f "$SUMMARY_FILE" ]]; then
  mkdir -p "$(dirname "$SUMMARY_FILE")"
  cat > "$SUMMARY_FILE" <<EOF
---
created: $(date +%Y-%m-%d)
updated: $(date +%Y-%m-%d)
type: session
tags: [session, ai-generated]
status: reference
source: agent-generated
---

# Session Summary — $(date "+%Y-%m-%d %H:%M")

## What was worked on

## Decisions made

## Knowledge updates

## Open loops opened

## Open loops closed

## Files modified

EOF
fi

# Launch summarizer in background — never blocks
if [[ -x "$PYTHON" ]]; then
  nohup "$PYTHON" "$VAULT_DIR/scripts/session_summarizer.py" \
    --summary-file "$SUMMARY_FILE" \
    >> /tmp/session-summarizer.log 2>&1 &
  disown $!

  # Append cost data (fast, synchronous)
  "$PYTHON" "$VAULT_DIR/scripts/cost_report.py" session --append-to "$SUMMARY_FILE" 2>/dev/null
fi
