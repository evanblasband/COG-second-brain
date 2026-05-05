#!/usr/bin/env bash
# tmux-brain.sh — Launch multi-pane second brain workspace.
#
# Creates session 'brain' with 4 windows; attaches if already running.
#
# Usage: bash scripts/tmux-brain.sh

set -euo pipefail

SESSION="brain"
VAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v tmux &>/dev/null; then
  echo "tmux not installed. Run: sudo apt-get install -y tmux (Linux) or brew install tmux (Mac)"
  exit 1
fi

# Attach to existing session rather than re-creating it
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already running — attaching..."
  exec tmux attach-session -t "$SESSION"
fi

VENV_ACTIVATE="[ -f .venv/bin/activate ] && source .venv/bin/activate"

# ── Window 0: main ───────────────────────────────────────────────────────────
# Left (65%): Claude Code session
# Right (35%): General shell (quick vault edits, git, grep)
tmux new-session -d -s "$SESSION" -n "main" -c "$VAULT"
tmux split-window -h -t "$SESSION:main" -c "$VAULT" -p 35

tmux send-keys -t "$SESSION:main.0" "$VENV_ACTIVATE && clear && echo 'Second Brain workspace ready.' && echo 'Run: claude'" Enter
tmux send-keys -t "$SESSION:main.1" "$VENV_ACTIVATE && clear" Enter

# ── Window 1: research ───────────────────────────────────────────────────────
# Top (70%): Research pipeline runner (research.py / docker compose run)
# Bottom (30%): Live log tail
tmux new-window -t "$SESSION" -n "research" -c "$VAULT"
tmux split-window -v -t "$SESSION:research" -c "$VAULT" -p 30

tmux send-keys -t "$SESSION:research.0" "$VENV_ACTIVATE && clear" Enter
tmux send-keys -t "$SESSION:research.1" "clear && echo 'Waiting for research logs...' && tail -f /tmp/research-*.log 2>/dev/null || true" Enter

# ── Window 2: integrations ───────────────────────────────────────────────────
# Top (60%): Google Calendar / Gmail scripts, query.py
# Bottom (40%): Output / API responses
tmux new-window -t "$SESSION" -n "integrations" -c "$VAULT"
tmux split-window -v -t "$SESSION:integrations" -c "$VAULT" -p 40

tmux send-keys -t "$SESSION:integrations.0" "$VENV_ACTIVATE && clear" Enter
tmux send-keys -t "$SESSION:integrations.1" "$VENV_ACTIVATE && clear && echo 'Integration output pane'" Enter

# ── Window 3: sandbox ────────────────────────────────────────────────────────
# Top (65%): Docker sandbox shell (or isolated venv runner)
# Bottom (35%): Container/process logs
tmux new-window -t "$SESSION" -n "sandbox" -c "$VAULT"
tmux split-window -v -t "$SESSION:sandbox" -c "$VAULT" -p 35

if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
  tmux send-keys -t "$SESSION:sandbox.0" "clear && echo 'Docker available. Run: docker compose run --rm brain-sandbox'" Enter
else
  tmux send-keys -t "$SESSION:sandbox.0" "$VENV_ACTIVATE && clear && echo 'Docker not found — using venv isolation. docker compose run commands will work on work machine.'" Enter
fi
tmux send-keys -t "$SESSION:sandbox.1" "clear && echo 'Sandbox output'" Enter

# ── Focus: window 0, pane 0 (Claude Code pane) ───────────────────────────────
tmux select-window -t "$SESSION:main"
tmux select-pane -t "$SESSION:main.0"

echo "Starting session '$SESSION'..."
exec tmux attach-session -t "$SESSION"
