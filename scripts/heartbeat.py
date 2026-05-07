#!/usr/bin/env python3
"""
heartbeat.py — Background pulse agent.

Checks calendar, Gmail, and Slack (when configured) and writes a brief
digest to AI/sessions/YYYY-MM-DD-heartbeat.md. Designed to run via cron
every 30 minutes.

Usage:
    python scripts/heartbeat.py            # run and write digest
    python scripts/heartbeat.py --dry-run  # print to stdout, don't write

Cron setup (every 30 min):
    */30 * * * * cd /path/to/vault && .venv/bin/python scripts/heartbeat.py >> /tmp/heartbeat.log 2>&1
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = VAULT_ROOT / "AI" / "sessions"
QUERY = VAULT_ROOT / "scripts" / "query.py"
PYTHON = sys.executable


def run_query(*args) -> str:
    """Run query.py with given args, return stdout. Returns empty string on error."""
    cmd = [PYTHON, str(QUERY)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return f"_Error: {result.stderr.strip()}_\n"
    return result.stdout


def build_digest() -> str:
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M UTC")

    sections = [
        f"# Heartbeat — {timestamp}\n",
    ]

    # Calendar
    sections.append("## Calendar")
    cal = run_query("calendar", "upcoming", "3")
    sections.append(cal if cal.strip() else "_No upcoming events._\n")

    # Gmail
    sections.append("## Email (unread)")
    gmail = run_query("gmail", "unread", "--limit", "5")
    sections.append(gmail if gmail.strip() else "_Gmail not configured or no unread messages._\n")

    # Slack mentions (optional — fails gracefully if token not set)
    sections.append("## Slack Mentions")
    slack = run_query("slack", "mentions", "--limit", "5")
    sections.append(slack if slack.strip() else "_Slack not configured._\n")

    return "\n".join(sections)


def write_digest(content: str):
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = SESSIONS_DIR / f"{today}-heartbeat.md"
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Append if file already exists (multiple runs per day)
    mode = "a" if out_path.exists() else "w"
    with open(out_path, mode) as f:
        if mode == "a":
            f.write("\n\n---\n\n")
        f.write(content)

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Heartbeat agent — checks calendar, email, Slack")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing file")
    args = parser.parse_args()

    content = build_digest()

    if args.dry_run:
        print(content)
    else:
        path = write_digest(content)
        print(f"Heartbeat written to {path}")


if __name__ == "__main__":
    main()
