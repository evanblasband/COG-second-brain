#!/usr/bin/env bash
# on-ingest.sh — Post-ingest notification utility.
# NOT a native Claude Code hook event. Called by ingest.py after successful ingestion.
#
# Usage: bash .claude/hooks/on-ingest.sh <source_key> <nodes_created> <nodes_updated>
#
# Logs the ingest event. If nodes_created is high (>10), prints a notice so
# Claude surfaces it to the user as a potential high-impact ingest.

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TODAY=$(date +%Y-%m-%d)
INGEST_LOG="$VAULT_DIR/AI/sessions/$TODAY-ingest.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

SOURCE_KEY="${1:-unknown}"
NODES_CREATED="${2:-0}"
NODES_UPDATED="${3:-0}"

# Append to daily ingest log
echo "{\"ts\":\"$TIMESTAMP\",\"event\":\"ingest\",\"source\":\"$SOURCE_KEY\",\"created\":$NODES_CREATED,\"updated\":$NODES_UPDATED}" >> "$INGEST_LOG"

# Surface high-impact ingests (many new nodes = potentially important new domain)
if [[ "$NODES_CREATED" -gt 10 ]]; then
    echo ""
    echo "📥 High-impact ingest: $NODES_CREATED new graph nodes from $SOURCE_KEY"
    echo "   Consider reviewing graph/graph.json for accuracy."
fi
