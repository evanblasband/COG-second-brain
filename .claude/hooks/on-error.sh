#!/usr/bin/env bash
# on-error.sh — Error capture utility.
# NOT a native Claude Code hook event. Called explicitly by scripts on failure.
#
# Usage: bash .claude/hooks/on-error.sh <script> <context> <error_message>
#
# Appends a structured error entry to 06-mistakes/error-log.md.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MISTAKES_FILE="$VAULT_DIR/06-mistakes/error-log.md"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE=$(date +%Y-%m-%d)

SCRIPT="${1:-unknown}"
CONTEXT="${2:-unknown}"
ERROR_MSG="${3:-no error message provided}"

# Initialize file if it doesn't exist
if [[ ! -f "$MISTAKES_FILE" ]]; then
    cat > "$MISTAKES_FILE" <<INIT
---
created: $DATE
updated: $DATE
type: knowledge
tags: [mistakes, errors, log]
status: active
source: agent-generated
---

# Error Log

_Append-only. Entries written by on-error.sh. Review weekly for prevention rules._

---

INIT
fi

# Append error entry
cat >> "$MISTAKES_FILE" <<ENTRY

## $TIMESTAMP | $SCRIPT

- **Context:** $CONTEXT
- **Error:** $ERROR_MSG
- **Prevention rule:** <!-- fill in after root cause analysis -->

---
ENTRY

echo "Error logged: $MISTAKES_FILE"
