#!/usr/bin/env python3
"""
query.py — Unified CLI wrapper for external integrations.
Intended for background/autonomous agent contexts where MCPs are unavailable.
API keys and tokens never appear in output or prompts.

WHEN TO USE THIS vs MCPs
─────────────────────────
  Interactive Claude Code sessions → use MCPs (already connected via claude.ai)
    mcp__claude_ai_Google_Calendar__list_events
    mcp__claude_ai_Gmail__search_threads

  Background agents / heartbeat / cron / non-Claude processes → use this script
    python scripts/query.py calendar today
    (requires: python scripts/google_auth.py run once first)

Usage:
    python scripts/query.py calendar today
    python scripts/query.py calendar week
    python scripts/query.py calendar next
    python scripts/query.py calendar upcoming 5
    python scripts/query.py calendar range 2026-05-04 2026-05-10
    python scripts/query.py gmail unread --limit 10     (Week 2)
    python scripts/query.py github prs --repo NAME      (uses gh CLI)

Output: markdown by default, --json for structured output.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
TOKEN_FILE = VAULT_ROOT / ".auth" / "google-token.json"


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def get_google_creds():
    """Load and auto-refresh Google OAuth token."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        _die("google-auth not installed. Run: pip install -r requirements.txt")

    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    if not TOKEN_FILE.exists():
        _die(
            f"No Google token found at {TOKEN_FILE}\n"
            "Run: python scripts/google_auth.py"
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            _die("Token invalid or expired. Run: python scripts/google_auth.py")

    return creds


def _die(msg: str):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


# ─── Calendar ─────────────────────────────────────────────────────────────────

def calendar_cmd(args):
    """Dispatch calendar subcommands."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        _die("google-api-python-client not installed. Run: pip install -r requirements.txt")

    creds = get_google_creds()
    service = build("calendar", "v3", credentials=creds)

    if args.period == "today":
        events = _fetch_range(service, *_today_range())
    elif args.period == "week":
        events = _fetch_range(service, *_week_range())
    elif args.period == "next":
        events = _fetch_upcoming(service, max_results=1)
    elif args.period == "upcoming":
        n = args.n if hasattr(args, "n") and args.n else 5
        events = _fetch_upcoming(service, max_results=n)
    elif args.period == "range":
        start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        events = _fetch_range(service, start, end)
    else:
        _die(f"Unknown calendar period: {args.period}")

    if args.json:
        print(json.dumps(events, indent=2, default=str))
    else:
        print(_format_calendar_md(events, args.period))


def _today_range():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _week_range():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return start, end


def _fetch_range(service, start: datetime, end: datetime, max_results: int = 20):
    result = service.events().list(
        calendarId="primary",
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def _fetch_upcoming(service, max_results: int = 5):
    now = datetime.now(timezone.utc)
    result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return result.get("items", [])


def _format_calendar_md(events: list, period: str) -> str:
    now = datetime.now(timezone.utc)
    header_date = now.strftime("%A, %Y-%m-%d")

    if period == "today":
        title = f"Today's Calendar — {header_date}"
    elif period == "week":
        title = f"This Week's Calendar — from {header_date}"
    elif period == "next":
        title = "Next Event"
    elif period == "upcoming":
        title = f"Upcoming Events — from {header_date}"
    else:
        title = f"Calendar — {header_date}"

    if not events:
        return f"## {title}\n\n_No events found._\n"

    lines = [f"## {title}\n"]

    for event in events:
        start_raw = event.get("start", {})
        end_raw = event.get("end", {})

        # All-day events use 'date', timed events use 'dateTime'
        if "dateTime" in start_raw:
            start_dt = datetime.fromisoformat(start_raw["dateTime"])
            end_dt = datetime.fromisoformat(end_raw["dateTime"])
            time_str = f"{start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')}"
        else:
            start_dt = datetime.fromisoformat(start_raw["date"])
            time_str = "All day"

        title_str = event.get("summary", "(No title)")
        location = event.get("location", "")
        description = event.get("description", "")
        attendees = event.get("attendees", [])

        # Format date prefix only for multi-day views
        if period in ("week", "upcoming", "range"):
            if "dateTime" in start_raw:
                date_prefix = start_dt.strftime("%a %b %-d")
            else:
                date_prefix = start_dt.strftime("%a %b %-d")
            lines.append(f"### {date_prefix} {time_str} | {title_str}")
        else:
            lines.append(f"### {time_str} | {title_str}")

        if location:
            lines.append(f"- **Location:** {location}")

        if attendees:
            names = []
            for a in attendees[:8]:
                name = a.get("displayName") or a.get("email", "")
                if a.get("self"):
                    continue  # skip self
                names.append(name)
            if names:
                lines.append(f"- **Attendees:** {', '.join(names)}")

        # Flag if starting within 30 minutes
        if "dateTime" in start_raw:
            local_now = datetime.now(start_dt.tzinfo)
            minutes_until = (start_dt - local_now).total_seconds() / 60
            if 0 < minutes_until <= 30:
                lines.append(f"- ⚠️ **Starting in {int(minutes_until)} min — prep now**")

        if description:
            # Only include first 200 chars of description
            desc_preview = description.strip()[:200].replace("\n", " ")
            if len(description.strip()) > 200:
                desc_preview += "..."
            lines.append(f"- **Notes:** {desc_preview}")

        lines.append("")

    return "\n".join(lines)


# ─── Gmail (stub — Week 2) ────────────────────────────────────────────────────

def gmail_cmd(args):
    print("## Gmail\n")
    print("_Gmail integration coming Week 2. Run: python scripts/google_auth.py first._")
    print("\nRequired scope already included in Google token if auth was run with current scopes.")


# ─── GitHub (delegates to gh CLI) ─────────────────────────────────────────────

def github_cmd(args):
    import subprocess

    if args.sub == "prs":
        repo = args.repo or ""
        cmd = ["gh", "pr", "list"]
        if repo:
            cmd += ["--repo", repo]
        cmd += ["--state", args.state or "open", "--limit", str(args.limit or 20)]
    elif args.sub == "issues":
        repo = args.repo or ""
        cmd = ["gh", "issue", "list"]
        if repo:
            cmd += ["--repo", repo]
        cmd += ["--state", args.state or "open", "--limit", str(args.limit or 20)]
    else:
        _die(f"Unknown github subcommand: {args.sub}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _die(f"gh CLI error: {result.stderr.strip()}")
    print(result.stdout)


# ─── CLI wiring ───────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        description="Second brain query CLI — wraps external integrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", help="Output JSON instead of markdown")
    sub = parser.add_subparsers(dest="service", required=True)

    # calendar
    cal = sub.add_parser("calendar", aliases=["cal"], help="Google Calendar queries")
    cal.add_argument(
        "period",
        choices=["today", "week", "next", "upcoming", "range"],
        help="Time range to fetch",
    )
    cal.add_argument("n", nargs="?", type=int, default=5, help="Number of events (for 'upcoming')")
    cal.add_argument("--start", help="Start date for 'range' (YYYY-MM-DD)")
    cal.add_argument("--end", help="End date for 'range' (YYYY-MM-DD)")

    # gmail
    gm = sub.add_parser("gmail", help="Gmail queries (Week 2)")
    gm.add_argument("sub", nargs="?", default="unread")
    gm.add_argument("--limit", type=int, default=10)

    # github
    gh = sub.add_parser("github", aliases=["gh"], help="GitHub queries (via gh CLI)")
    gh.add_argument("sub", choices=["prs", "issues"])
    gh.add_argument("--repo", help="Repository (owner/name)")
    gh.add_argument("--state", default="open")
    gh.add_argument("--limit", type=int, default=20)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    service = args.service
    if service in ("calendar", "cal"):
        calendar_cmd(args)
    elif service == "gmail":
        gmail_cmd(args)
    elif service in ("github", "gh"):
        github_cmd(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
