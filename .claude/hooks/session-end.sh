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

  # Prompt Claude to complete the session-end protocol.
  # This output is injected back into the conversation — Claude must act on it.
  cat <<PROMPT

=== SESSION END PROTOCOL — ACTION REQUIRED ===

The session is ending. Complete the following before closing:

1. **Fill in AI/sessions/$TIMESTAMP.md** — summarize what was worked on, decisions
   made, knowledge updates, open loops opened/closed, and files modified.

2. **Update MEMORY.md** — append any cross-session learnings to the relevant section:
   - Key Decisions: new architectural choices or tool selections
   - Patterns Learned: recurring observations
   - Domain Knowledge Updates: significant new facts ingested
   - Lessons from Mistakes: prevention rules extracted

3. **Update OPEN_LOOPS.md** — mark resolved items ✅ DONE, add any new
   unresolved questions or waiting-fors that surfaced this session.

Do not skip this step — MEMORY.md is the compounding value of the system.

PROMPT
fi

# Append actual cost data from session JSONL
if [[ -x "$PYTHON" ]]; then
  "$PYTHON" "$VAULT_DIR/scripts/cost_report.py" session --append-to "$SUMMARY_FILE" 2>/dev/null
fi
