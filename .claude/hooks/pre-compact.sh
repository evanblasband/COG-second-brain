#!/usr/bin/env bash
# pre-compact.sh
# Fires before Claude's automatic context compaction.
# Writes a state snapshot so context can be reconstructed after compaction.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP=$(date +%Y-%m-%d-%H-%M)
SNAPSHOT_FILE="$VAULT_DIR/AI/sessions/$TIMESTAMP-precompact.md"

cat > "$SNAPSHOT_FILE" <<EOF
---
created: $(date +%Y-%m-%d)
updated: $(date +%Y-%m-%d)
type: reference
tags: [session, pre-compact, ai-generated]
status: reference
source: agent-generated
---

# Pre-Compact Snapshot — $(date "+%Y-%m-%d %H:%M")

> Context compaction is about to occur. This file preserves state so the
> session can be reconstructed. Claude: read this file at the start of the
> next turn and continue from where you left off.

## What I was doing

<!-- Claude should fill this in before compaction triggers -->

## What is done

<!-- Completed subtasks this session -->

## What remains

<!-- Incomplete subtasks — resume here after compaction -->

## Files to reload on resume

- $VAULT_DIR/SOUL.md
- $VAULT_DIR/USER.md
- $VAULT_DIR/MEMORY.md
- $VAULT_DIR/OPEN_LOOPS.md

## Critical context not to lose

<!-- Decisions, constraints, or intermediate results that must survive compaction -->

## Active file paths

<!-- Key files being worked on this session -->
EOF

echo "Pre-compact snapshot: $SNAPSHOT_FILE"
echo "BEFORE COMPACTION: Fill in $SNAPSHOT_FILE now — write what you were doing, what is done, what remains, active file paths, and critical context not to lose"
echo "Claude: read this file and continue from 'What remains' after compaction."
