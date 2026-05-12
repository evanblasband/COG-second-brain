#!/usr/bin/env bash
# export-vault.sh — Export personal (gitignored) vault content to a USB drive or backup directory.
#
# Usage:
#   bash scripts/export-vault.sh /Volumes/MYUSB
#   bash scripts/export-vault.sh /path/to/backup-dir
#
# What gets exported (mirrors .gitignore personal content):
#   .env, SOUL.md, USER.md, MEMORY.md, OPEN_LOOPS.md
#   .auth/  (Google OAuth credentials + token)
#   00-inbox/  (MY-PROFILE, MY-INTERESTS, MY-INTEGRATIONS, drive-sync.json)
#   01-daily/, 02-people/, 03-projects/, 04-knowledge/
#   05-decisions/, 06-mistakes/, 07-resources/, AI/, graph/
#
# What does NOT get exported (already in git):
#   .claude/, scripts/, templates/, config/, CLAUDE.md, AGENTS.md, setup.sh, etc.

set -euo pipefail

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-}"

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

if [[ -z "$DEST" ]]; then
  echo "Usage: bash scripts/export-vault.sh /path/to/usb-or-backup-dir"
  exit 1
fi

if [[ ! -d "$DEST" ]]; then
  fail "Destination not found: $DEST"
  info "Mount your USB drive first, or create the backup directory."
  exit 1
fi

EXPORT_DIR="$DEST/cog-vault-export"

echo ""
echo "Second Brain — Personal Content Export"
echo "From: $VAULT_DIR"
echo "To:   $EXPORT_DIR"
echo ""

if [[ -d "$EXPORT_DIR" ]]; then
  warn "Export directory already exists: $EXPORT_DIR"
  read -r -p "  Overwrite it? [y/N] " _reply
  [[ "$_reply" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
  rm -rf "$EXPORT_DIR"
fi

mkdir -p "$EXPORT_DIR"

# ─── Helper: copy a single file if it exists ─────────────────────────────────
total_files=0
skipped_missing=0

copy_file() {
  local rel="$1"
  local src="$VAULT_DIR/$rel"
  local dest="$EXPORT_DIR/$rel"
  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
    ok "  $rel"
    (( total_files++ )) || true
  else
    warn "  Not found, skipping: $rel"
    (( skipped_missing++ )) || true
  fi
}

# ─── Helper: copy a directory recursively ────────────────────────────────────
copy_dir() {
  local rel="$1"
  local src="$VAULT_DIR/$rel"
  local dest="$EXPORT_DIR/$rel"
  if [[ ! -d "$src" ]]; then
    warn "  Not found, skipping: $rel/"
    (( skipped_missing++ )) || true
    return 0
  fi
  mkdir -p "$dest"
  if command -v rsync &>/dev/null; then
    rsync -a --exclude='.gitkeep' --exclude='*.pyc' --exclude='__pycache__' \
      "$src/" "$dest/" 2>/dev/null
  else
    cp -r "$src/." "$dest/"
    find "$dest" -name '.gitkeep' -delete 2>/dev/null || true
  fi
  local count
  count=$(find "$dest" -type f | wc -l | tr -d ' ')
  ok "  $rel/ ($count files)"
  (( total_files += count )) || true
}

# ─── Identity & secrets ───────────────────────────────────────────────────────
section "Identity & secrets"
copy_file ".env"
copy_file "SOUL.md"
copy_file "USER.md"
copy_file "MEMORY.md"
copy_file "OPEN_LOOPS.md"

# ─── Auth tokens ──────────────────────────────────────────────────────────────
section "Auth tokens (.auth/)"
copy_dir ".auth"

# ─── Inbox config ─────────────────────────────────────────────────────────────
section "Inbox config (00-inbox/)"
copy_file "00-inbox/MY-PROFILE.md"
copy_file "00-inbox/MY-INTERESTS.md"
copy_file "00-inbox/MY-INTEGRATIONS.md"
copy_file "00-inbox/drive-sync.json"

# ─── Vault content ────────────────────────────────────────────────────────────
section "Daily notes (01-daily/)"
copy_dir "01-daily"

section "People CRM (02-people/)"
copy_dir "02-people"

section "Projects (03-projects/)"
copy_dir "03-projects"

section "Knowledge base (04-knowledge/)"
copy_dir "04-knowledge"

section "Decisions (05-decisions/)"
copy_dir "05-decisions"

section "Mistakes log (06-mistakes/)"
copy_dir "06-mistakes"

section "Resources (07-resources/)"
copy_dir "07-resources"

section "AI agent outputs (AI/)"
copy_dir "AI"

section "Knowledge graph (graph/)"
info "The graph can be rebuilt on the new machine with:"
info "  python scripts/ingest.py 04-knowledge/ --batch --yes"
echo ""
read -r -p "  Include knowledge graph in export? [y/N] " _graph_reply
if [[ "$_graph_reply" =~ ^[Yy]$ ]]; then
  copy_dir "graph"
else
  info "Skipping graph/ — rebuild it on the new machine from 04-knowledge/"
fi

# ─── Manifest ────────────────────────────────────────────────────────────────
python3 - <<PYEOF
import json, os
from datetime import datetime, timezone

manifest = {
    "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "vault_dir": "$VAULT_DIR",
    "hostname": os.uname().nodename,
    "total_files": $total_files,
}
with open("$EXPORT_DIR/.export-manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
PYEOF

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
ok "Export complete"
info "Files exported:      $total_files"
info "Items not found:     $skipped_missing"
info "Destination:         $EXPORT_DIR"
echo ""
warn "Remember:"
info "  • .env contains API keys and tokens — keep the USB secure"
info "  • Google OAuth token (.auth/) works until revoked — no re-auth needed"
info "    unless you revoke it in Google Cloud Console"
info "  • The knowledge graph (graph/) can be rebuilt from 04-knowledge/ if needed:"
info "    python scripts/ingest.py 04-knowledge/ --batch --yes"
echo ""
info "To import on the new machine after cloning the repo and running setup.sh:"
info "  bash scripts/import-vault.sh $EXPORT_DIR"
echo ""
