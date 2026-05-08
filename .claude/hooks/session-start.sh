#!/usr/bin/env bash
# session-start.sh
# Fires on UserPromptSubmit. Injects context into Claude's awareness.
# Keep fast — this runs on every message.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TODAY=$(date +%Y-%m-%d)

echo "=== SESSION CONTEXT ==="
echo "Vault: $VAULT_DIR"
echo "Date: $TODAY"
echo ""

# ── Core files to load ────────────────────────────────────────────────────────
echo "Load these files before responding (in order):"
echo "  1. $VAULT_DIR/SOUL.md"
echo "  2. $VAULT_DIR/USER.md"
echo "  3. $VAULT_DIR/MEMORY.md"
echo "  4. $VAULT_DIR/OPEN_LOOPS.md"
echo ""

# ── Daily brief status ────────────────────────────────────────────────────────
BRIEF="$VAULT_DIR/01-daily/briefs/$TODAY.md"
if [[ -f "$BRIEF" ]]; then
  echo "Daily brief: exists ($BRIEF)"
else
  echo "Daily brief: MISSING — consider running /daily-brief"
fi
echo ""

# ── Today's calendar ─────────────────────────────────────────────────────────
# Prefer MCP (already connected via claude.ai — no setup needed).
# Fall back to Python CLI for background/autonomous agent contexts.
echo "Calendar: use mcp__claude_ai_Google_Calendar__list_events to fetch today's events."
echo "  (MCP is connected — no Python auth needed for interactive sessions)"
echo ""

# ── Inbox check ───────────────────────────────────────────────────────────────
INBOX_FILES=$(find "$VAULT_DIR/00-inbox" -name "*.md" -newer "$VAULT_DIR/00-inbox/MY-PROFILE.md" 2>/dev/null | grep -v "MY-PROFILE\|MY-INTERESTS\|MY-INTEGRATIONS" | wc -l)
if [[ "$INBOX_FILES" -gt 0 ]]; then
  echo "Inbox: $INBOX_FILES new file(s) in 00-inbox/ — review before starting"
else
  echo "Inbox: clear"
fi
echo ""

# ── Overdue open loops ────────────────────────────────────────────────────────
# Surface any items in OPEN_LOOPS.md older than 14 days
LOOPS_FILE="$VAULT_DIR/OPEN_LOOPS.md"
if [[ -f "$LOOPS_FILE" ]]; then
  CUTOFF=$(date -d "14 days ago" +%Y-%m-%d 2>/dev/null || date -v-14d +%Y-%m-%d 2>/dev/null)
  OVERDUE=$(grep -oP '\d{4}-\d{2}-\d{2}' "$LOOPS_FILE" | awk -v cutoff="$CUTOFF" '$0 < cutoff' | wc -l)
  if [[ "$OVERDUE" -gt 0 ]]; then
    echo "Open loops: $OVERDUE item(s) older than 14 days — surface and resolve or escalate"
  else
    echo "Open loops: no overdue items"
  fi
fi


# ── Graph conflict check ───────────────────────────────────────────────────────
CONFLICTS_FILE="$VAULT_DIR/graph/conflicts.json"
if [[ -f "$CONFLICTS_FILE" ]]; then
  UNRESOLVED=$(python3 -c "
import json, sys
try:
    d = json.load(open('$CONFLICTS_FILE'))
    print(len([c for c in d.get('conflicts', []) if c.get('status') == 'unresolved']))
except: print(0)
" 2>/dev/null)
  if [[ "$UNRESOLVED" -gt 0 ]]; then
    echo "Graph conflicts: $UNRESOLVED unresolved — review graph/conflicts.json before ingesting"
    echo ""
  fi
fi

echo "========================================================"
