#!/usr/bin/env bash
# setup.sh — Second Brain new-machine installer
# Run once on a fresh machine to get the full system operational.
# Idempotent: safe to run multiple times.
#
# Usage: bash setup.sh

set -euo pipefail

VAULT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m"

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }
info() { echo -e "  $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
section() { echo -e "\n${GREEN}=== $1 ===${NC}"; }

echo ""
echo "Second Brain — new machine setup"
echo "Vault: $VAULT_DIR"
echo ""

# ─── 1. DETECT OS ────────────────────────────────────────────────────────────
section "Detecting OS"
OS="unknown"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  if grep -qi microsoft /proc/version 2>/dev/null; then
    OS="wsl"
    ok "WSL (Ubuntu/Debian)"
  else
    OS="linux"
    ok "Linux"
  fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
  OS="mac"
  ok "macOS"
else
  warn "Unknown OS: $OSTYPE — proceeding with Linux assumptions"
fi

# ─── 2. SYSTEM DEPENDENCIES ──────────────────────────────────────────────────
section "System dependencies"

check_cmd() {
  if command -v "$1" &>/dev/null; then
    ok "$1 already installed ($(command -v "$1"))"
    return 0
  fi
  return 1
}

_apt_updated=false
_apt_update_once() {
  if [[ "$_apt_updated" == "false" ]]; then
    info "Running apt-get update..."
    sudo apt-get update -q
    _apt_updated=true
  fi
}

# Ask user before installing a missing dependency.
# Usage: prompt_install "label" "install_cmd"
# Returns 0 if user said yes and install succeeded, 1 otherwise.
prompt_install() {
  local label="$1"
  local cmd="$2"
  echo ""
  read -r -p "  Install $label now? [y/N] " _reply
  if [[ "$_reply" =~ ^[Yy]$ ]]; then
    if [[ "$cmd" == *"apt-get install"* ]]; then
      _apt_update_once
    fi
    eval "$cmd"
    return $?
  fi
  return 1
}

# git (required)
check_cmd git || {
  warn "git not found"
  if [[ "$OS" == "mac" ]]; then
    prompt_install "git" "brew install git"
  else
    prompt_install "git" "sudo apt-get install -y git"
  fi
  command -v git &>/dev/null && ok "git installed" || { fail "git is required — install it and re-run setup.sh"; exit 1; }
}

# python3 (required)
if check_cmd python3; then
  PY_VERSION=$(python3 --version 2>&1)
  info "Version: $PY_VERSION"
else
  warn "python3 not found"
  if [[ "$OS" == "mac" ]]; then
    prompt_install "Python 3.12" "brew install python@3.12"
  else
    prompt_install "Python 3 + pip + venv" "sudo apt-get install -y python3 python3-pip python3-venv"
  fi
  if command -v python3 &>/dev/null; then
    ok "python3 installed ($(python3 --version 2>&1))"
  else
    fail "Python 3.10+ is required — install it and re-run setup.sh"
    exit 1
  fi
fi

# tmux (optional)
check_cmd tmux || {
  warn "tmux not installed (optional — needed for multi-agent sessions)"
  if [[ "$OS" == "mac" ]]; then
    prompt_install "tmux (optional)" "brew install tmux"
  else
    prompt_install "tmux (optional)" "sudo apt-get install -y tmux"
  fi
  command -v tmux &>/dev/null && ok "tmux installed"
}

# gh CLI (optional)
if check_cmd gh; then
  true
elif [[ -f "$HOME/bin/gh" ]]; then
  ok "gh found at ~/bin/gh"
  export PATH="$HOME/bin:$PATH"
else
  warn "gh CLI not installed (optional — needed for GitHub integration)"
  if [[ "$OS" == "mac" ]]; then
    prompt_install "gh CLI (optional)" "brew install gh"
  else
    prompt_install "gh CLI (optional, no sudo)" \
      'mkdir -p ~/bin && curl -sL https://github.com/cli/cli/releases/download/v2.71.0/gh_2.71.0_linux_amd64.tar.gz | tar -xz -C /tmp && cp /tmp/gh_2.71.0_linux_amd64/bin/gh ~/bin/gh && export PATH="$HOME/bin:$PATH"'
  fi
  { command -v gh &>/dev/null || [[ -f "$HOME/bin/gh" ]]; } && ok "gh installed" || warn "gh not installed — GitHub features will be unavailable"
fi

# Claude Code (optional but strongly recommended)
if check_cmd claude; then
  true
else
  warn "Claude Code (claude CLI) not installed"
  if command -v npm &>/dev/null; then
    prompt_install "Claude Code (optional)" "npm install -g @anthropic-ai/claude-code"
    command -v claude &>/dev/null && ok "Claude Code installed" || warn "Claude Code not installed — install from https://claude.ai/code"
  else
    warn "npm not found — install Node.js first, then run: npm install -g @anthropic-ai/claude-code"
    info "Node.js: https://nodejs.org or brew install node"
  fi
fi

# Obsidian (GUI app — auto-install only on macOS via brew)
if [[ "$OS" == "mac" ]]; then
  if [[ -d "/Applications/Obsidian.app" ]]; then
    ok "Obsidian installed"
  else
    warn "Obsidian not installed (optional — for visual vault browsing)"
    prompt_install "Obsidian (optional)" "brew install --cask obsidian"
    [[ -d "/Applications/Obsidian.app" ]] && ok "Obsidian installed" || info "Install manually from https://obsidian.md/download"
  fi
else
  warn "Obsidian: install manually from https://obsidian.md/download"
  info "After installing, open vault at: $VAULT_DIR"
fi

# ─── 3. PYTHON ENVIRONMENT ───────────────────────────────────────────────────
section "Python virtual environment"

VENV_DIR="$VAULT_DIR/.venv"
if [[ -d "$VENV_DIR" ]]; then
  ok "Virtual environment already exists at .venv"
else
  python3 -m venv "$VENV_DIR"
  ok "Created .venv"
fi

# Activate and install
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$VAULT_DIR/requirements.txt"
ok "Python dependencies installed from requirements.txt"

# ─── 4. ENVIRONMENT FILE ─────────────────────────────────────────────────────
section "Environment file"

ENV_FILE="$VAULT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  ok ".env already exists — skipping"
else
  cp "$VAULT_DIR/.env.example" "$ENV_FILE"
  ok "Created .env from .env.example"
  warn "Open .env and fill in your API keys before using integrations"
fi

# Create .auth dir for OAuth tokens
mkdir -p "$VAULT_DIR/.auth"
ok ".auth/ directory ready for OAuth tokens"

# ─── 4b. IDENTITY FILES ──────────────────────────────────────────────────────
section "Identity files"

IDENTITY_TEMPLATES="$VAULT_DIR/templates/identity"
IDENTITY_FILES=(
  "SOUL.md:$IDENTITY_TEMPLATES/SOUL.template.md"
  "USER.md:$IDENTITY_TEMPLATES/USER.template.md"
  "MEMORY.md:$IDENTITY_TEMPLATES/MEMORY.template.md"
  "OPEN_LOOPS.md:$IDENTITY_TEMPLATES/OPEN_LOOPS.template.md"
  "00-inbox/MY-PROFILE.md:$IDENTITY_TEMPLATES/MY-PROFILE.template.md"
  "00-inbox/MY-INTERESTS.md:$IDENTITY_TEMPLATES/MY-INTERESTS.template.md"
  "00-inbox/MY-INTEGRATIONS.md:$IDENTITY_TEMPLATES/MY-INTEGRATIONS.template.md"
)

for entry in "${IDENTITY_FILES[@]}"; do
  dest="${entry%%:*}"
  src="${entry##*:}"
  dest_path="$VAULT_DIR/$dest"
  if [[ -f "$dest_path" ]]; then
    ok "$dest already exists"
  else
    cp "$src" "$dest_path"
    warn "$dest created from template — fill in your personal details"
  fi
done

echo ""
info "Identity files are gitignored — they exist only on this machine."
info "Fill them in with your real details. They will never be pushed to git."

# ─── 5. GITHUB AUTH ──────────────────────────────────────────────────────────
section "GitHub authentication"

if command -v gh &>/dev/null; then
  if gh auth status &>/dev/null 2>&1; then
    ok "Already authenticated with GitHub ($(gh api user --jq .login 2>/dev/null || echo 'unknown'))"
  else
    warn "Not logged in to GitHub"
    info "Run: gh auth login"
    info "Choose: GitHub.com → HTTPS → Login with a web browser"
  fi
else
  warn "gh CLI not available — skip GitHub auth for now"
fi

# ─── 6. GOOGLE AUTH ──────────────────────────────────────────────────────────
section "Google OAuth (Calendar + Gmail)"

TOKEN_PATH="$VAULT_DIR/.auth/google-token.json"
if [[ -f "$TOKEN_PATH" ]]; then
  ok "Google OAuth token found at .auth/google-token.json"
else
  warn "Google not authenticated yet"
  info "Steps to set up Google OAuth:"
  info "  1. Go to https://console.cloud.google.com/"
  info "  2. Create a project (or select existing)"
  info "  3. APIs & Services > Enable: Google Calendar API, Gmail API"
  info "  4. APIs & Services > Credentials > Create OAuth 2.0 Client ID"
  info "  5. Application type: Desktop application"
  info "  6. Download JSON > save as: .auth/google-credentials.json"
  info "  7. Run: python scripts/google_auth.py"
  info "     (opens browser for approval, saves token to .auth/google-token.json)"
  info ""
  info "  Test it: python scripts/query.py calendar today"
  info ""
  info "Set PERSONAL_EMAIL and WORK_EMAIL in .env before running OAuth."
  info "If your work email is not yet active, authenticate with personal email"
  info "first, then re-authorize once the work account is provisioned."
fi

# ─── 6c. SLACK AUTH ──────────────────────────────────────────────────────────
section "Slack (user token)"

SLACK_TOKEN=$(grep "^SLACK_BOT_TOKEN=" "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
if [[ -n "$SLACK_TOKEN" && "$SLACK_TOKEN" != "" ]]; then
  ok "SLACK_BOT_TOKEN set in .env"
  if python3 -c "
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path('$VAULT_DIR')))
try:
    from dotenv import load_dotenv
    load_dotenv('$ENV_FILE')
except ImportError:
    pass
token = os.getenv('SLACK_BOT_TOKEN','')
import urllib.request, urllib.parse, json
req = urllib.request.Request(
    'https://slack.com/api/auth.test',
    headers={'Authorization': f'Bearer {token}'}
)
with urllib.request.urlopen(req, timeout=5) as r:
    data = json.loads(r.read())
if data.get('ok'):
    print(f'  Authenticated as: {data.get(\"user\",\"unknown\")} ({data.get(\"team\",\"unknown\")})')
    sys.exit(0)
else:
    sys.exit(1)
" 2>/dev/null; then
    ok "Slack token valid"
  else
    warn "Slack token set but auth check failed — verify the token in .env"
  fi
else
  warn "Slack not configured"
  info "To set up Slack:"
  info "  1. Go to https://api.slack.com/apps → Create New App → From scratch"
  info "  2. OAuth & Permissions → User Token Scopes → add:"
  info "       channels:history, channels:read, im:history, users:read, search:read"
  info "  3. Install App → copy 'User OAuth Token' (starts with xoxp-)"
  info "  4. Add to .env: SLACK_BOT_TOKEN=xoxp-..."
  info "  Test: python scripts/query.py slack mentions --limit 3"
fi

# ─── 6b. DOCKER SANDBOX ──────────────────────────────────────────────────────
section "Docker sandbox"

if command -v docker &>/dev/null; then
  if docker compose version &>/dev/null 2>&1; then
    ok "Docker + Compose available"
    if docker image inspect brain-sandbox &>/dev/null 2>&1; then
      ok "brain-sandbox image already built"
    else
      info "Building brain-sandbox image..."
      docker compose build --quiet
      ok "brain-sandbox image built"
    fi
    info "Run research pipeline in sandbox:"
    info "  docker compose run --rm brain-sandbox scripts/research.py \\"
    info "    --url URL --category technologies"
  else
    warn "Docker found but 'docker compose' not available — install Docker Desktop or Compose plugin"
  fi
else
  warn "Docker not installed — sandbox runs will fall back to local .venv"
  if [[ "$OS" == "mac" ]]; then
    info "Install: brew install --cask docker"
  elif [[ "$OS" == "wsl" ]]; then
    info "Install Docker Desktop for Windows with WSL2 integration enabled"
    info "  https://docs.docker.com/desktop/windows/install/"
  else
    info "Install: sudo apt-get install -y docker.io docker-compose-plugin"
    info "         sudo usermod -aG docker \$USER && newgrp docker"
  fi
  info "After installing Docker, re-run setup.sh or: docker compose build"
fi

# ─── 7. VAULT STRUCTURE CHECK ────────────────────────────────────────────────
section "Vault structure check"

REQUIRED_DIRS=(
  "00-inbox" "01-daily" "02-people" "03-projects"
  "04-knowledge/regulations" "04-knowledge/technologies" "04-knowledge/competitors"
  "05-decisions" "06-mistakes" "07-resources"
  "AI/sessions" "AI/research" "AI/evaluations" "AI/drafts"
  "templates" ".claude/skills" ".claude/agents"
)
REQUIRED_FILES=(
  "SOUL.md" "USER.md" "MEMORY.md" "OPEN_LOOPS.md" "CLAUDE.md"
  "requirements.txt" ".env.example"
  "templates/daily-note.md" "templates/person.md"
  "templates/project-brief.md" "templates/meeting-note.md"
)

all_ok=true
for dir in "${REQUIRED_DIRS[@]}"; do
  if [[ -d "$VAULT_DIR/$dir" ]]; then
    ok "Dir: $dir"
  else
    fail "Missing dir: $dir"
    all_ok=false
  fi
done
for file in "${REQUIRED_FILES[@]}"; do
  if [[ -f "$VAULT_DIR/$file" ]]; then
    ok "File: $file"
  else
    warn "Missing file: $file"
    all_ok=false
  fi
done

# ─── 8. OBSIDIAN VAULT OPEN ──────────────────────────────────────────────────
section "Open vault in Obsidian"

if [[ "$OS" == "mac" ]] && [[ -d "/Applications/Obsidian.app" ]]; then
  info "Opening vault in Obsidian..."
  open -a Obsidian "$VAULT_DIR"
  ok "Vault opened"
else
  info "Open Obsidian manually and add vault at: $VAULT_DIR"
  info "In Obsidian: Settings → Community Plugins → Enable: Dataview, Templater, Git, Canvas, Tasks"
fi

# ─── 9. MANUAL STEPS REMINDER ────────────────────────────────────────────────
section "Manual steps still required"

echo ""
warn "The following cannot be automated — complete these manually:"
echo ""
echo "  1. Fill in .env with ANTHROPIC_API_KEY and Google credentials"
echo "  2. Run: gh auth login  (if not already done)"
echo "  3. Set up Google OAuth (see steps above in section 6)"
echo "  4. WORK_EMAIL (.env) — if not yet active, set it when provisioned"
echo "     and re-run Google OAuth to add the work account."
echo "  5. Install Obsidian plugins: Dataview, Templater, Obsidian Git,"
echo "     Canvas, Tasks, Excalidraw"
echo "  6. In Obsidian Templater settings, set template folder to: templates/"
echo "  7. On day one: request Foundry access and pull internal Sage docs"
echo "     into 04-knowledge/ via the research agent"
echo "  8. Launch multi-pane workspace: bash scripts/tmux-brain.sh"
echo ""

# ─── 10. CRON JOBS (optional) ────────────────────────────────────────────────
section "Background agent cron jobs (optional)"

info "To enable background agents, add these to your crontab (crontab -e):"
echo ""
echo "  # Heartbeat — checks calendar/email/Slack every 30 min"
echo "  */30 * * * * cd $VAULT_DIR && $VENV_DIR/bin/python scripts/heartbeat.py >> /tmp/heartbeat.log 2>&1"
echo ""
echo "  # Janitor — archives old session logs every Friday at 5pm"
echo "  0 17 * * 5 cd $VAULT_DIR && $VENV_DIR/bin/python scripts/janitor.py --archive >> /tmp/janitor.log 2>&1"
echo ""
info "These are optional — the system works without them. Set up after Google OAuth is complete."

ok "Setup complete. Run 'claude' in this directory to start a session."
