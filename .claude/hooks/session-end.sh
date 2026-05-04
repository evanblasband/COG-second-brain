#!/usr/bin/env bash
# session-end.sh
# Fires on Stop. Creates a session summary stub in AI/sessions/ if one
# doesn't already exist for this hour.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP=$(date +%Y-%m-%d-%H)
SUMMARY_FILE="$VAULT_DIR/AI/sessions/$TIMESTAMP.md"

if [[ -f "$SUMMARY_FILE" ]]; then
  exit 0
fi

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

<!-- Fill in or ask Claude to summarize at session end -->

## Decisions made

<!-- Copy to 05-decisions/ if significant -->

## Knowledge updates

<!-- New facts to add to 04-knowledge/ -->

## Open loops opened

<!-- Add to OPEN_LOOPS.md -->

## Open loops closed

<!-- Remove from OPEN_LOOPS.md -->

## Files modified

<!-- List of vault files changed this session -->
EOF

echo "Session summary stub created: $SUMMARY_FILE"
