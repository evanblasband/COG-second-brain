#!/usr/bin/env bash
# import-vault.sh — Import personal vault content from a USB export into this vault.
#
# Usage:
#   bash scripts/import-vault.sh /path/to/usb/cog-vault-export
#   bash scripts/import-vault.sh /path/to/usb/cog-vault-export --vault /path/to/vault
#
# Run AFTER: git clone <repo> && bash setup.sh
# The vault must already exist with its framework files before importing content.

set -euo pipefail

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC=""

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault|-v)
      VAULT_DIR="$(cd "$2" && pwd)"
      shift 2
      ;;
    -*)
      echo "Unknown flag: $1"; exit 1
      ;;
    *)
      SRC="$1"
      shift
      ;;
  esac
done

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

ok()      { echo -e "${GREEN}✓${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $1"; }
info()    { echo -e "  $1"; }
fail()    { echo -e "${RED}✗${NC} $1"; }
section() { echo -e "\n${BOLD}$1${NC}"; }

# ─── Validate source ─────────────────────────────────────────────────────────
if [[ -z "$SRC" ]]; then
  echo "Usage: bash scripts/import-vault.sh /path/to/cog-vault-export [--vault /path/to/vault]"
  exit 1
fi

if [[ ! -d "$SRC" ]]; then
  fail "Source not found: $SRC"
  exit 1
fi

# ─── Validate destination looks like a COG vault ─────────────────────────────
if [[ ! -f "$VAULT_DIR/CLAUDE.md" ]] || [[ ! -d "$VAULT_DIR/.claude" ]]; then
  fail "Destination doesn't look like a COG vault: $VAULT_DIR"
  info "Expected CLAUDE.md and .claude/ to exist."
  info "Run 'git clone ...' and 'bash setup.sh' first, then import."
  exit 1
fi

# ─── Header ──────────────────────────────────────────────────────────────────
echo ""
echo "Second Brain — Personal Content Import"
echo ""

if [[ -f "$SRC/.export-manifest.json" ]]; then
  exported_at=$(python3 -c "import json; d=json.load(open('$SRC/.export-manifest.json')); print(d.get('exported_at','unknown'))" 2>/dev/null || echo "unknown")
  from_host=$(python3 -c "import json; d=json.load(open('$SRC/.export-manifest.json')); print(d.get('hostname','unknown'))" 2>/dev/null || echo "unknown")
  file_count=$(python3 -c "import json; d=json.load(open('$SRC/.export-manifest.json')); print(d.get('total_files','?'))" 2>/dev/null || echo "?")
  info "Export date:  $exported_at"
  info "From host:    $from_host"
  info "Files:        $file_count"
fi

echo ""
echo "From: $SRC"
echo "To:   $VAULT_DIR"
echo ""

read -r -p "Proceed with import? [y/N] " _confirm
[[ "$_confirm" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }

# ─── Ask overwrite policy upfront ────────────────────────────────────────────
echo ""
echo "How should existing files be handled?"
echo "  [O] Overwrite all  — full restore, replaces everything (recommended for fresh machine)"
echo "  [S] Skip existing  — only copy files that don't exist yet (safe merge)"
echo "  [A] Ask each time  — prompt for every conflicting file"
echo ""
read -r -p "Choice [O/S/A]: " _policy
_policy="${_policy^^}"  # uppercase

OVERWRITE_ALL=false
SKIP_ALL=false
ASK_EACH=false

case "$_policy" in
  O) OVERWRITE_ALL=true ;;
  S) SKIP_ALL=true ;;
  A) ASK_EACH=true ;;
  *) info "Defaulting to: skip existing"; SKIP_ALL=true ;;
esac

# ─── State counters ───────────────────────────────────────────────────────────
imported=0
skipped=0
overwritten=0

# ─── Helper: import a single file ────────────────────────────────────────────
import_file() {
  local rel="$1"
  local src_path="$SRC/$rel"
  local dest_path="$VAULT_DIR/$rel"

  if [[ ! -f "$src_path" ]]; then
    warn "  Not in export, skipping: $rel"
    return 0
  fi

  mkdir -p "$(dirname "$dest_path")"

  if [[ -f "$dest_path" ]]; then
    if $OVERWRITE_ALL; then
      cp "$src_path" "$dest_path"
      ok "  Overwritten: $rel"
      (( overwritten++ )) || true
      return 0
    elif $SKIP_ALL; then
      info "  Skipped (exists): $rel"
      (( skipped++ )) || true
      return 0
    elif $ASK_EACH; then
      echo ""
      warn "  Already exists: $rel"
      read -r -p "  [o]verwrite / [s]kip / [O]verwrite all / [S]kip all? " _choice
      case "${_choice}" in
        o)
          cp "$src_path" "$dest_path"
          ok "  Overwritten: $rel"
          (( overwritten++ )) || true
          ;;
        O)
          OVERWRITE_ALL=true; ASK_EACH=false
          cp "$src_path" "$dest_path"
          ok "  Overwritten: $rel"
          (( overwritten++ )) || true
          ;;
        S)
          SKIP_ALL=true; ASK_EACH=false
          info "  Skipped (exists): $rel"
          (( skipped++ )) || true
          ;;
        *)
          info "  Skipped (exists): $rel"
          (( skipped++ )) || true
          ;;
      esac
      return 0
    fi
  fi

  cp "$src_path" "$dest_path"
  ok "  $rel"
  (( imported++ )) || true
}

# ─── Helper: import a directory ──────────────────────────────────────────────
import_dir() {
  local rel="$1"
  local src_path="$SRC/$rel"
  local dest_path="$VAULT_DIR/$rel"

  if [[ ! -d "$src_path" ]]; then
    warn "  Not in export, skipping: $rel/"
    return 0
  fi

  mkdir -p "$dest_path"

  local rsync_flags="-a --exclude='.gitkeep' --exclude='.export-manifest.json' --exclude='*.pyc'"
  local count=0

  if command -v rsync &>/dev/null; then
    if $OVERWRITE_ALL; then
      count=$(rsync $rsync_flags "$src_path/" "$dest_path/" --stats 2>/dev/null \
        | grep "Number of files transferred" | awk '{print $NF}' || echo "?")
    else
      # --ignore-existing: never overwrite, only bring in new files
      count=$(rsync $rsync_flags --ignore-existing "$src_path/" "$dest_path/" --stats 2>/dev/null \
        | grep "Number of files transferred" | awk '{print $NF}' || echo "?")
    fi
    ok "  $rel/ ($count files)"
    (( imported++ )) || true
  else
    if $OVERWRITE_ALL; then
      cp -r "$src_path/." "$dest_path/"
    else
      cp -rn "$src_path/." "$dest_path/"   # -n = no-clobber
    fi
    count=$(find "$dest_path" -type f | wc -l | tr -d ' ')
    ok "  $rel/ (~$count files)"
    (( imported++ )) || true
  fi
}

# ─── Identity & secrets ───────────────────────────────────────────────────────
section "Identity & secrets"
import_file ".env"
import_file "SOUL.md"
import_file "USER.md"
import_file "MEMORY.md"
import_file "OPEN_LOOPS.md"

# ─── Auth tokens ──────────────────────────────────────────────────────────────
section "Auth tokens (.auth/)"
import_dir ".auth"

# ─── Inbox config ─────────────────────────────────────────────────────────────
section "Inbox config (00-inbox/)"
import_file "00-inbox/MY-PROFILE.md"
import_file "00-inbox/MY-INTERESTS.md"
import_file "00-inbox/MY-INTEGRATIONS.md"
import_file "00-inbox/drive-sync.json"

# ─── Vault content ────────────────────────────────────────────────────────────
section "Daily notes (01-daily/)"
import_dir "01-daily"

section "People CRM (02-people/)"
import_dir "02-people"

section "Projects (03-projects/)"
import_dir "03-projects"

section "Knowledge base (04-knowledge/)"
import_dir "04-knowledge"

section "Decisions (05-decisions/)"
import_dir "05-decisions"

section "Mistakes log (06-mistakes/)"
import_dir "06-mistakes"

section "Resources (07-resources/)"
import_dir "07-resources"

section "AI agent outputs (AI/)"
import_dir "AI"

section "Knowledge graph (graph/)"
if [[ -d "$SRC/graph" ]] && [[ -n "$(ls -A "$SRC/graph" 2>/dev/null)" ]]; then
  info "The graph can be rebuilt from 04-knowledge/ instead:"
  info "  python scripts/ingest.py 04-knowledge/ --batch --yes"
  echo ""
  read -r -p "  Import knowledge graph? [y/N] " _graph_reply
  if [[ "$_graph_reply" =~ ^[Yy]$ ]]; then
    import_dir "graph"
  else
    info "Skipping graph/ — rebuild it with: python scripts/ingest.py 04-knowledge/ --batch --yes"
  fi
else
  info "No graph found in export — skipping."
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
ok "Import complete"
info "Imported (new):   $imported"
info "Overwritten:      $overwritten"
info "Skipped:          $skipped"
echo ""

warn "Next steps:"
info "  1. Run setup.sh to verify everything is wired up:"
info "       bash setup.sh"
info ""
info "  2. Verify .env has the correct keys for this machine."
info "     The Slack token and Anthropic key should transfer fine."
info "     Google credentials may need re-auth if this is a new Google account:"
info "       python scripts/google_auth.py"
info ""
info "  3. Test integrations:"
info "       python scripts/query.py calendar today"
info "       python scripts/query.py slack mentions --limit 3"
info ""
info "  4. If the knowledge graph feels stale, rebuild it from the knowledge base:"
info "       python scripts/ingest.py 04-knowledge/ --batch --yes"
echo ""
