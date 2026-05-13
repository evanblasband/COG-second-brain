#!/usr/bin/env python3
"""
heartbeat.py — Background pulse agent.

Checks calendar, Gmail, Slack (when configured), and Google Drive (when configured)
and writes a brief digest to AI/sessions/YYYY-MM-DD-heartbeat.md. Designed to run
via cron every 30 minutes.

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
DRIVE_SYNC = VAULT_ROOT / "scripts" / "drive_sync.py"
DRIVE_SYNC_CONFIG = VAULT_ROOT / "00-inbox" / "drive-sync.json"
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

    # Calendar (query.py emits its own ## header)
    cal = run_query("calendar", "upcoming", "3")
    sections.append(cal if cal.strip() else "## Calendar\n\n_No upcoming events._\n")

    # Gmail (query.py emits its own ## header)
    gmail = run_query("gmail", "unread", "--limit", "5")
    sections.append(gmail if gmail.strip() else "## Email (unread)\n\n_Gmail not configured or no unread messages._\n")

    # Slack digest: mentions + DMs + group messages + watch channels
    slack = run_query("slack", "digest", "--limit", "5")
    sections.append(slack if slack.strip() else "## Slack Digest\n\n_Slack not configured._\n")

    # Google Drive sync check (optional — skipped if config not present)
    if DRIVE_SYNC_CONFIG.exists():
        sections.append("## Google Drive")
        drive_summary = _drive_check_summary()
        sections.append(drive_summary)

    return "\n".join(sections)


def _drive_check_summary() -> str:
    """Run drive_sync --check and extract the summary line for the digest."""
    try:
        result = subprocess.run(
            [PYTHON, str(DRIVE_SYNC), "--check"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return "_Drive sync check failed — check drive-sync.json and Google auth._\n"

        # Extract the summary lines from the report
        lines = result.stdout.splitlines()
        summary_lines = []
        in_report = False
        for line in lines:
            if "Drive Sync Report" in line:
                in_report = True
            if in_report:
                summary_lines.append(line)
            if in_report and line.strip().startswith("Run:"):
                break  # Stop before the run suggestion

        if summary_lines:
            return "\n".join(summary_lines) + "\n"
        return "_Drive: no watched folders configured._\n"

    except subprocess.TimeoutExpired:
        return "_Drive sync check timed out._\n"
    except Exception as e:
        return f"_Drive sync check error: {e}_\n"


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
