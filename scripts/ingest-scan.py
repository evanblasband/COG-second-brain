#!/usr/bin/env python3
"""
ingest-scan.py — Scan Drive + Notion for items not yet ingested, append to INGEST_QUEUE.md.

Does NOT run ingest.py. Discovery only.

Sources scanned (configured in 00-inbox/ingest-scan.json):
  - Google Drive — "Shared with me" (controlled by scan_shared_with_me flag)
  - Google Drive — shared drives listed under shared_drives (each has enabled: true/false)
  - Notion — recently edited pages (meeting notes + docs)

Cross-reference logic (skip if already ingested):
  1. Notion page ID found in vault frontmatter (notion_id: ...)
  2. Drive file ID found in vault frontmatter (drive_id: ...)
  3. Saved path found in graph/ingest_manifest.json
  4. Source ID already present in INGEST_QUEUE.md (pending or done)

Usage:
    python3 scripts/ingest-scan.py               # scan last 7 days (default)
    python3 scripts/ingest-scan.py --days 14     # scan last 14 days
    python3 scripts/ingest-scan.py --days 3      # quick scan, last 3 days
    python3 scripts/ingest-scan.py --dry-run     # print candidates, don't write to queue
    python3 scripts/ingest-scan.py --source notion   # only scan Notion
    python3 scripts/ingest-scan.py --source drive    # only scan Drive sources
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
QUEUE_FILE = VAULT_ROOT / "INGEST_QUEUE.md"
MANIFEST_FILE = VAULT_ROOT / "graph" / "ingest_manifest.json"
TOKEN_FILE = VAULT_ROOT / ".auth" / "google-token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
]

SCAN_CONFIG_FILE = VAULT_ROOT / "00-inbox" / "ingest-scan.json"

INGESTIBLE_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.presentation",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

DRIVE_TYPE_MAP = {
    "application/vnd.google-apps.document": "Google Doc",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/pdf": "PDF",
    "text/plain": "text",
    "text/markdown": "markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Word doc",
}


def _die(msg: str):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def load_scan_config() -> dict:
    """Load shared drive IDs and other site-specific config from gitignored 00-inbox/ingest-scan.json."""
    if not SCAN_CONFIG_FILE.exists():
        print(f"Config not found: {SCAN_CONFIG_FILE}", file=sys.stderr)
        print("Create it with your shared drive IDs — example:", file=sys.stderr)
        print('  {"shared_drives": [{"id": "YOUR_DRIVE_ID", "name": "drive-primary"}]}', file=sys.stderr)
        print("Drive IDs come from the URL when viewing a shared drive in Google Drive.", file=sys.stderr)
        sys.exit(1)
    with open(SCAN_CONFIG_FILE) as f:
        return json.load(f)


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(VAULT_ROOT / ".env")
    except ImportError:
        env_file = VAULT_ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


# ─── Cross-reference: what's already ingested ──────────────────────────────────

def load_ingested_notion_ids() -> set[str]:
    """Scan all vault .md files for notion_id: frontmatter."""
    ids: set[str] = set()
    for path in VAULT_ROOT.rglob("*.md"):
        if ".git" in path.parts or "AI/sessions" in str(path):
            continue
        try:
            text = path.read_text(errors="replace")
            if text.startswith("---"):
                header = text.split("---", 2)[1] if text.count("---") >= 2 else ""
                m = re.search(r"^notion_id:\s*([a-f0-9\-]+)", header, re.MULTILINE)
                if m:
                    ids.add(m.group(1).replace("-", ""))
        except OSError:
            pass
    return ids


def load_ingested_drive_ids() -> set[str]:
    """Scan all vault .md files for drive_id: frontmatter."""
    ids: set[str] = set()
    for path in VAULT_ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        try:
            text = path.read_text(errors="replace")
            if text.startswith("---"):
                header = text.split("---", 2)[1] if text.count("---") >= 2 else ""
                m = re.search(r"^drive_id:\s*(\S+)", header, re.MULTILINE)
                if m:
                    ids.add(m.group(1))
        except OSError:
            pass
    return ids


def load_manifest_paths() -> set[str]:
    """Return all save paths recorded in the ingest manifest."""
    if not MANIFEST_FILE.exists():
        return set()
    try:
        data = json.loads(MANIFEST_FILE.read_text())
        return set(data.get("entries", {}).keys())
    except Exception:
        return set()


def load_queue_ids() -> set[str]:
    """Return all source IDs already present in INGEST_QUEUE.md (pending or done)."""
    ids: set[str] = set()
    if not QUEUE_FILE.exists():
        return ids
    for line in QUEUE_FILE.read_text().splitlines():
        # IDs are wrapped in backticks: `SOME_ID`
        for m in re.finditer(r"`([A-Za-z0-9_\-]{10,})`", line):
            ids.add(m.group(1).replace("-", ""))
    return ids


# ─── INGEST_QUEUE.md writer ────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:60]


def _entry_block(date: str, source_type: str, title: str, source_id: str,
                  command: str, source_label: str, context: str) -> str:
    return (
        f"### {date} | {title}\n"
        f"- **Source:** {source_label} (`{source_type}`)\n"
        f"- **ID:** `{source_id}`\n"
        f"- **Proposed command:** `{command}`\n"
        f"- **Flags to add:** *(none yet)*\n"
        f"- **Context:** {context}\n"
    )


def append_to_queue(entries: list[str], dry_run: bool):
    if not entries:
        return
    if dry_run:
        print(f"\n{'─'*60}")
        print("Would add to INGEST_QUEUE.md:")
        for e in entries:
            print(e)
        return

    if not QUEUE_FILE.exists():
        _die(f"INGEST_QUEUE.md not found at {QUEUE_FILE}")

    text = QUEUE_FILE.read_text()

    pending_match = re.search(r"^## Pending\s*\n", text, re.MULTILINE)
    if not pending_match:
        _die("Could not find '## Pending' section in INGEST_QUEUE.md")

    insert_pos = pending_match.end()
    new_block = "\n" + "\n".join(entries) + "\n"
    text = text[:insert_pos] + new_block + text[insert_pos:]

    QUEUE_FILE.write_text(text)


# ─── Google Drive scanning ─────────────────────────────────────────────────────

def get_drive_service():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        _die("google-api-python-client not installed. Run: pip install -r requirements.txt")

    if not TOKEN_FILE.exists():
        _die(f"No Google token at {TOKEN_FILE}. Run: python scripts/google_auth.py")

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


def scan_shared_with_me(service, cutoff: datetime) -> list[dict]:
    """List files shared with me since cutoff."""
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    page_token = None

    while True:
        kwargs = dict(
            q=f"sharedWithMe=true and trashed=false and modifiedTime >= '{cutoff_str}'",
            pageSize=50,
            orderBy="modifiedTime desc",
            fields="nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink,owners)",
        )
        if page_token:
            kwargs["pageToken"] = page_token

        resp = service.files().list(**kwargs).execute()
        for item in resp.get("files", []):
            if item.get("mimeType") in INGESTIBLE_MIMES:
                results.append({**item, "_scan_source": "drive-shared"})
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results


def scan_shared_drive(service, drive_id: str, drive_name: str, cutoff: datetime) -> list[dict]:
    """List top-level ingestible files in a shared drive since cutoff."""
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    results = []
    page_token = None

    while True:
        kwargs = dict(
            corpora="drive",
            driveId=drive_id,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            q=f"trashed=false and modifiedTime >= '{cutoff_str}'",
            pageSize=50,
            orderBy="modifiedTime desc",
            fields="nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)",
        )
        if page_token:
            kwargs["pageToken"] = page_token

        resp = service.files().list(**kwargs).execute()
        for item in resp.get("files", []):
            if item.get("mimeType") in INGESTIBLE_MIMES:
                results.append({**item, "_scan_source": drive_name})
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return results


def scan_drive(cutoff: datetime, config: dict) -> list[dict]:
    service = get_drive_service()
    results = []
    if config.get("scan_shared_with_me", True):
        results += scan_shared_with_me(service, cutoff)
    for drive in config.get("shared_drives", []):
        if not drive.get("enabled", True):
            print(f"  Skipping {drive.get('name', drive['id'])} (disabled in config)")
            continue
        results += scan_shared_drive(service, drive["id"], drive.get("name", drive["id"]), cutoff)
    return results


def drive_to_entry(item: dict, today: str) -> str:
    fid = item["id"]
    title = item.get("name", fid)
    mime = item.get("mimeType", "")
    source_type = item["_scan_source"]
    file_type = DRIVE_TYPE_MAP.get(mime, "file")
    modified = item.get("modifiedTime", "")[:10]

    slug = _slugify(title)
    if "document" in mime or "pdf" in mime or "word" in mime:
        save_path = f"04-knowledge/{slug}.md"
        cmd = f"python3 scripts/ingest.py --drive {fid} --save {save_path}"
    elif "presentation" in mime:
        save_path = f"04-knowledge/{slug}.md"
        cmd = f"python3 scripts/ingest.py --drive {fid} --save {save_path}"
    else:
        cmd = f"python3 scripts/ingest.py --drive {fid}"

    source_label = "Google Drive (Shared with me)" if source_type == "drive-shared" else f"Google Drive ({source_type})"
    context = f"{file_type}; modified {modified}"
    return _entry_block(modified or today, source_type, title, fid, cmd, source_label, context)


# ─── Notion scanning ───────────────────────────────────────────────────────────

def _notion_req(token: str, method: str, path: str, body: dict | None = None) -> dict:
    import urllib.request
    import urllib.error

    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        _die(f"Notion API error {e.code} for {path}: {body_text[:200]}")


def scan_notion(cutoff: datetime) -> list[dict]:
    """Search for recently edited Notion pages via REST API.

    Requires NOTION_TOKEN in .env. In interactive Claude sessions, Notion
    scanning is handled via MCP instead — run with --source drive and let
    Claude cover Notion separately.
    """
    token = os.getenv("NOTION_TOKEN")
    if not token:
        print("  Notion scan skipped: NOTION_TOKEN not set.", file=sys.stderr)
        print("  In an interactive Claude session, ask Claude to scan Notion via MCP.", file=sys.stderr)
        return []

    results = []
    cursor = None
    cutoff_naive = cutoff.replace(tzinfo=None)

    while True:
        body: dict = {
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "filter": {"property": "object", "value": "page"},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor

        data = _notion_req(token, "POST", "/search", body)

        for page in data.get("results", []):
            edited_raw = page.get("last_edited_time", "")
            if not edited_raw:
                continue
            # Parse ISO timestamp (2026-05-14T12:00:00.000Z)
            edited = datetime.fromisoformat(edited_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            if edited < cutoff_naive:
                # Results are sorted descending — once we go past cutoff, stop
                return results
            results.append(page)

        cursor = data.get("next_cursor")
        if not cursor or not data.get("has_more"):
            break

    return results


def notion_page_title(page: dict) -> str:
    """Extract the title from a Notion page object."""
    props = page.get("properties", {})
    for key in ("Name", "Title", "title"):
        prop = props.get(key, {})
        title_arr = prop.get("title", []) or prop.get("rich_text", [])
        if title_arr:
            return "".join(t.get("plain_text", "") for t in title_arr).strip()
    # Fallback: check page title at root level
    title_arr = page.get("title", [])
    if isinstance(title_arr, list):
        return "".join(t.get("plain_text", "") for t in title_arr).strip()
    return ""


def is_meeting_note(page: dict, title: str) -> bool:
    """Heuristic: is this page a meeting note?"""
    meeting_patterns = [
        r"\<\>", r"\bmeeting\b", r"\bintro\b", r"\bonboarding\b",
        r"\bsync\b", r"\b1:1\b", r"\bkickoff\b", r"\boverview\b",
        r"\blunch\b", r"\ball.hands\b", r"\bdebrief\b", r"\bcall\b",
        r" x ", r" & ", r"<>", r"\bsession\b",
    ]
    t = title.lower()
    return any(re.search(p, t) for p in meeting_patterns)


def notion_to_entry(page: dict, today: str) -> str:
    page_id = page["id"].replace("-", "")
    title = notion_page_title(page) or f"(Notion page {page_id[:8]})"
    edited = page.get("last_edited_time", "")[:10] or today

    slug = _slugify(title)
    if is_meeting_note(page, title):
        source_type = "notion-meeting"
        save_path = f"03-projects/{slug}-{edited}.md"
    else:
        source_type = "notion-doc"
        save_path = f"04-knowledge/{slug}.md"

    cmd = f"python3 scripts/ingest.py --notion {page_id} --save {save_path}"
    context = f"Last edited {edited}"
    return _entry_block(edited, source_type, title, page_id, cmd, "Notion meeting notes", context)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scan Drive + Notion for uningest items.")
    parser.add_argument("--days", type=int, default=7, help="Look back N days (default: 7)")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates, don't write to queue")
    parser.add_argument("--source", choices=["notion", "drive"], help="Scan only one source type")
    args = parser.parse_args()

    _load_env()
    config = load_scan_config()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"Scanning last {args.days} days (since {cutoff.strftime('%Y-%m-%d')})...")

    # Load already-ingested IDs
    print("Loading cross-reference data...")
    ingested_notion = load_ingested_notion_ids()
    ingested_drive = load_ingested_drive_ids()
    manifest_paths = load_manifest_paths()
    queue_ids = load_queue_ids()

    all_known = ingested_notion | ingested_drive | queue_ids | manifest_paths

    # Scan sources
    candidates: list[dict] = []
    source_label: list[str] = []

    if args.source in (None, "drive"):
        active_drives = []
        if config.get("scan_shared_with_me", True):
            active_drives.append("shared-with-me")
        active_drives += [d.get("name", d["id"]) for d in config.get("shared_drives", []) if d.get("enabled", True)]
        print(f"Scanning Google Drive ({', '.join(active_drives) if active_drives else 'none enabled'})...")
        try:
            drive_files = scan_drive(cutoff, config)
            candidates += [{"_type": "drive", "_item": f} for f in drive_files]
            source_label.append(f"Drive: {len(drive_files)} files found")
        except SystemExit:
            raise
        except Exception as e:
            print(f"  Drive scan failed: {e}", file=sys.stderr)

    if args.source in (None, "notion"):
        print("Scanning Notion (recently edited pages)...")
        try:
            notion_pages = scan_notion(cutoff)
            candidates += [{"_type": "notion", "_item": p} for p in notion_pages]
            source_label.append(f"Notion: {len(notion_pages)} pages found")
        except SystemExit:
            raise
        except Exception as e:
            print(f"  Notion scan failed: {e}", file=sys.stderr)

    # Cross-reference and build new entries
    new_entries: list[str] = []
    skipped = 0

    for c in candidates:
        if c["_type"] == "drive":
            item = c["_item"]
            fid = item["id"]
            norm_id = fid.replace("-", "")
            if norm_id in all_known or fid in all_known:
                skipped += 1
                continue
            new_entries.append(drive_to_entry(item, today))
            all_known.add(norm_id)

        elif c["_type"] == "notion":
            item = c["_item"]
            pid = item["id"].replace("-", "")
            if pid in all_known:
                skipped += 1
                continue
            new_entries.append(notion_to_entry(item, today))
            all_known.add(pid)

    # Report
    print()
    for label in source_label:
        print(f"  {label}")
    print(f"  Already ingested / in queue: {skipped}")
    print(f"  New candidates: {len(new_entries)}")

    if not new_entries:
        print("Nothing new to add.")
        return

    append_to_queue(new_entries, args.dry_run)

    if not args.dry_run:
        print(f"\nAdded {len(new_entries)} item(s) to {QUEUE_FILE.name}.")
        print("Review save paths and context, then run the ingest commands.")


if __name__ == "__main__":
    main()
