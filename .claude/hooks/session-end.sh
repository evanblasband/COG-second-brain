#!/usr/bin/env bash
# session-end.sh
# Fires on Stop. First fire: creates session stub and prompts Claude to
# complete the session-end protocol (MEMORY.md, OPEN_LOOPS.md, summary).
# Subsequent fires (stub already exists): appends cost data only.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP=$(date +%Y-%m-%d-%H)
SUMMARY_FILE="$VAULT_DIR/AI/sessions/$TIMESTAMP.md"
PYTHON="$VAULT_DIR/.venv/bin/python3"

if [[ ! -f "$SUMMARY_FILE" ]]; then
  cat > "$SUMMARY_FILE" <<EOF
---
created: $(date +%Y-%m-%d)
updated: $(date +%Y-%m-%d)
type: research
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

# Block stop if summary is still empty, forcing Claude to write it.
# Use -A3 to skip the blank line between the heading and content.
# Once Claude fills in content, the hook won't block and the session ends normally.
CONTENT_CHECK=$(grep -A3 "## What was worked on" "$SUMMARY_FILE" 2>/dev/null | grep -v "^##" | tr -d '[:space:]')
if [[ -z "$CONTENT_CHECK" ]]; then
  printf '{"decision":"block","reason":"SESSION END PROTOCOL — ACTION REQUIRED. The session summary at AI/sessions/%s.md is empty. Before this session closes you must: (1) Fill in AI/sessions/%s.md — what was worked on, decisions made, knowledge updates, open loops opened/closed, files modified. (2) Update MEMORY.md with any cross-session learnings. (3) Update OPEN_LOOPS.md — mark resolved items done, add new ones. Do not skip — MEMORY.md is the compounding value of the system."}' "$TIMESTAMP" "$TIMESTAMP"
fi

# Append actual cost data from session JSONL
if [[ -x "$PYTHON" ]]; then
  "$PYTHON" "$VAULT_DIR/scripts/cost_report.py" session --append-to "$SUMMARY_FILE" 2>/dev/null
fi
