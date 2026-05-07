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
    python scripts/query.py gmail unread --limit 10
    python scripts/query.py drive list [--limit N] [--folder FOLDER_ID]
    python scripts/query.py drive search "query string"
    python scripts/query.py drive download FILE_ID [--output /path/to/file.txt]
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
        "https://www.googleapis.com/auth/drive.readonly",
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


# ─── Gmail ────────────────────────────────────────────────────────────────────

def gmail_cmd(args):
    try:
        from googleapiclient.discovery import build
    except ImportError:
        _die("google-api-python-client not installed. Run: pip install -r requirements.txt")

    creds = get_google_creds()
    service = build("gmail", "v1", credentials=creds)

    sub = getattr(args, "sub", "unread")
    limit = getattr(args, "limit", 10)

    if sub == "unread":
        _gmail_unread(service, limit, args.json)
    elif sub == "search":
        query = getattr(args, "query", "")
        _gmail_search(service, query, limit, args.json)
    else:
        _die(f"Unknown gmail subcommand: {sub}")


def _gmail_unread(service, limit: int, as_json: bool):
    result = service.users().messages().list(
        userId="me", q="is:unread", maxResults=limit
    ).execute()
    messages = result.get("messages", [])
    _gmail_format(service, messages, "Unread Messages", as_json)


def _gmail_search(service, query: str, limit: int, as_json: bool):
    result = service.users().messages().list(
        userId="me", q=query, maxResults=limit
    ).execute()
    messages = result.get("messages", [])
    _gmail_format(service, messages, f'Search: "{query}"', as_json)


def _gmail_format(service, messages: list, title: str, as_json: bool):
    if not messages:
        print(f"## Gmail — {title}\n\n_No messages found._\n")
        return

    items = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
        items.append({
            "id": msg["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "date": headers.get("Date", ""),
            "snippet": detail.get("snippet", ""),
        })

    if as_json:
        print(json.dumps(items, indent=2))
        return

    lines = [f"## Gmail — {title}\n"]
    for item in items:
        lines.append(f"### {item['subject']}")
        lines.append(f"- **From:** {item['from']}")
        lines.append(f"- **Date:** {item['date']}")
        if item["snippet"]:
            lines.append(f"- **Preview:** {item['snippet'][:200]}")
        lines.append("")
    print("\n".join(lines))


# ─── Slack ────────────────────────────────────────────────────────────────────

def slack_cmd(args):
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        _die(
            "SLACK_BOT_TOKEN not set in .env\n"
            "Add: SLACK_BOT_TOKEN=xoxb-... to your .env file\n"
            "Slack app needs scopes: channels:history, im:history, users:read"
        )

    try:
        import urllib.request
        import urllib.parse
    except ImportError:
        _die("urllib not available (should be in stdlib)")

    sub = getattr(args, "sub", "mentions")
    limit = getattr(args, "limit", 20)

    if sub == "mentions":
        _slack_search(token, f"<@{_slack_my_id(token)}>", limit, args.json)
    elif sub == "search":
        query = getattr(args, "query", "")
        _slack_search(token, query, limit, args.json)
    elif sub == "channel":
        channel = getattr(args, "channel", "")
        if not channel:
            _die("Specify --channel CHANNEL_ID_OR_NAME")
        _slack_channel(token, channel, limit, args.json)
    else:
        _die(f"Unknown slack subcommand: {sub}")


def _slack_api(token: str, endpoint: str, params: dict) -> dict:
    import urllib.request, urllib.parse
    base = f"https://slack.com/api/{endpoint}"
    query = urllib.parse.urlencode(params)
    url = f"{base}?{query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    if not data.get("ok"):
        _die(f"Slack API error on {endpoint}: {data.get('error', 'unknown')}")
    return data


def _slack_my_id(token: str) -> str:
    data = _slack_api(token, "auth.test", {})
    return data.get("user_id", "")


def _slack_search(token: str, query: str, limit: int, as_json: bool):
    data = _slack_api(token, "search.messages", {"query": query, "count": limit})
    matches = data.get("messages", {}).get("matches", [])
    _slack_format(matches, f'Slack Search: "{query}"', as_json)


def _slack_channel(token: str, channel: str, limit: int, as_json: bool):
    data = _slack_api(token, "conversations.history", {"channel": channel, "limit": limit})
    messages = data.get("messages", [])
    items = [{"text": m.get("text", ""), "ts": m.get("ts", ""), "user": m.get("user", "")} for m in messages]
    _slack_format(items, f"Slack Channel: {channel}", as_json)


def _slack_format(items: list, title: str, as_json: bool):
    if not items:
        print(f"## {title}\n\n_No messages found._\n")
        return
    if as_json:
        print(json.dumps(items, indent=2))
        return
    lines = [f"## {title}\n"]
    for item in items:
        text = item.get("text", item.get("snippet", {}).get("text", ""))
        ts = item.get("ts", item.get("permalink", ""))
        lines.append(f"- {text[:300]}")
        if ts:
            lines.append(f"  _(ts: {ts})_")
        lines.append("")
    print("\n".join(lines))


# ─── Google Drive ─────────────────────────────────────────────────────────────

# Google Workspace types that must be exported (not downloaded directly)
_DRIVE_EXPORT_MIMES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

_DRIVE_TYPE_LABELS = {
    "application/vnd.google-apps.document": "Google Doc",
    "application/vnd.google-apps.spreadsheet": "Google Sheet",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/pdf": "PDF",
    "text/plain": "Text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
}


def drive_cmd(args):
    try:
        from googleapiclient.discovery import build
    except ImportError:
        _die("google-api-python-client not installed. Run: pip install -r requirements.txt")

    creds = get_google_creds()
    service = build("drive", "v3", credentials=creds)

    sub = getattr(args, "sub", "list")
    if sub == "list":
        _drive_list(service, args)
    elif sub == "search":
        _drive_search(service, args)
    elif sub == "download":
        _drive_download(service, args)
    else:
        _die(f"Unknown drive subcommand: {sub}")


def _drive_list(service, args):
    folder = getattr(args, "folder", None)
    limit = getattr(args, "limit", 20)

    q = f"'{folder}' in parents and trashed=false" if folder else "trashed=false"
    result = service.files().list(
        q=q,
        pageSize=limit,
        orderBy="modifiedTime desc",
        fields="files(id,name,mimeType,modifiedTime,webViewLink)",
    ).execute()
    files = result.get("files", [])

    if args.json:
        print(json.dumps(files, indent=2))
        return

    if not files:
        print("## Google Drive\n\n_No files found._\n")
        return

    lines = ["## Google Drive — Recent Files\n"]
    for f in files:
        name = f.get("name", "")
        fid = f.get("id", "")
        mime = f.get("mimeType", "")
        modified = f.get("modifiedTime", "")[:10]
        link = f.get("webViewLink", "")
        type_label = _DRIVE_TYPE_LABELS.get(mime, mime.split("/")[-1])
        lines.append(f"### {name}")
        lines.append(f"- **ID:** `{fid}`")
        lines.append(f"- **Type:** {type_label}")
        lines.append(f"- **Modified:** {modified}")
        if link:
            lines.append(f"- **Link:** {link}")
        lines.append("")
    print("\n".join(lines))


def _drive_search(service, args):
    query = getattr(args, "query", "")
    limit = getattr(args, "limit", 20)

    # Escape single quotes in user query
    safe_query = query.replace("'", "\\'")
    q = f"name contains '{safe_query}' and trashed=false"
    result = service.files().list(
        q=q,
        pageSize=limit,
        orderBy="modifiedTime desc",
        fields="files(id,name,mimeType,modifiedTime,webViewLink)",
    ).execute()
    files = result.get("files", [])

    if args.json:
        print(json.dumps(files, indent=2))
        return

    if not files:
        print(f"## Drive Search: '{query}'\n\n_No files found._\n")
        return

    lines = [f"## Drive Search: '{query}'\n"]
    for f in files:
        name = f.get("name", "")
        fid = f.get("id", "")
        modified = f.get("modifiedTime", "")[:10]
        link = f.get("webViewLink", "")
        lines.append(f"- **{name}**")
        lines.append(f"  ID: `{fid}` | Modified: {modified}")
        if link:
            lines.append(f"  {link}")
        lines.append("")
    print("\n".join(lines))


def _drive_download(service, args):
    file_id = args.file_id
    output = getattr(args, "output", None)

    meta = service.files().get(
        fileId=file_id,
        fields="id,name,mimeType",
    ).execute()

    name = meta.get("name", file_id)
    mime = meta.get("mimeType", "")
    export_mime = _DRIVE_EXPORT_MIMES.get(mime)

    if export_mime:
        # Google Workspace file — export as text
        content = service.files().export(
            fileId=file_id,
            mimeType=export_mime,
        ).execute()
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    else:
        # Binary or plain file — download directly
        import io
        from googleapiclient.http import MediaIoBaseDownload
        buf = io.BytesIO()
        req = service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        text = buf.getvalue().decode("utf-8", errors="replace")

    if not output:
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        output = f"/tmp/{safe_name}.txt"

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Downloaded: {name}")
    print(f"Saved to:   {output}")
    print(f"Ingest via: /ingest {output}")


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
    gm = sub.add_parser("gmail", help="Gmail queries")
    gm.add_argument("sub", nargs="?", default="unread", choices=["unread", "search"])
    gm.add_argument("--query", help="Search query (for 'search' subcommand)")
    gm.add_argument("--limit", type=int, default=10)

    # slack
    sl = sub.add_parser("slack", help="Slack queries (requires SLACK_BOT_TOKEN in .env)")
    sl.add_argument("sub", nargs="?", default="mentions", choices=["mentions", "search", "channel"])
    sl.add_argument("--query", help="Search query (for 'search' subcommand)")
    sl.add_argument("--channel", help="Channel ID or name (for 'channel' subcommand)")
    sl.add_argument("--limit", type=int, default=20)

    # drive
    dr = sub.add_parser("drive", help="Google Drive queries")
    dr_sub = dr.add_subparsers(dest="sub", required=True)

    dr_list = dr_sub.add_parser("list", help="List recent Drive files")
    dr_list.add_argument("--folder", help="Folder ID to list (default: all files)")
    dr_list.add_argument("--limit", type=int, default=20)

    dr_search = dr_sub.add_parser("search", help="Search Drive files by name")
    dr_search.add_argument("query", help="Search string")
    dr_search.add_argument("--limit", type=int, default=20)

    dr_dl = dr_sub.add_parser("download", help="Download a Drive file for ingestion")
    dr_dl.add_argument("file_id", help="Drive file ID (from 'list' or 'search' output)")
    dr_dl.add_argument("--output", help="Local path to save to (default: /tmp/<name>.txt)")

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
    elif service == "slack":
        slack_cmd(args)
    elif service == "drive":
        drive_cmd(args)
    elif service in ("github", "gh"):
        github_cmd(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
