#!/usr/bin/env python3
"""
drive_sync.py — Google Drive folder watcher and ingest agent.

Watches configured Drive folders for new and changed files, downloads them,
and feeds them to the ingest pipeline (ingest.py).

Workflow:
  1. Read watched folders from 00-inbox/drive-sync.json
  2. List all ingestible files recursively in each watched folder
  3. Compare Drive modifiedTime against graph/drive-sync-state.json
  4. Report (--check) or download + ingest (--run) new/changed files
  5. Update drive-sync-state.json after successful ingest

Usage:
    python scripts/drive_sync.py --check           # list new/changed, no download
    python scripts/drive_sync.py --run             # download + ingest (with cost prompts)
    python scripts/drive_sync.py --run --yes       # download + ingest, skip cost prompts

Config:    00-inbox/drive-sync.json   (list of watched folder IDs — gitignored)
State:     graph/drive-sync-state.json (per-file modifiedTime cache — gitignored)
Downloads: /tmp/drive-sync/           (temp files, cleaned after ingest)

Cron (daily at 7am — checks for changes):
    0 7 * * * cd /path/to/vault && .venv/bin/python scripts/drive_sync.py --check >> /tmp/drive-sync.log 2>&1
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = VAULT_ROOT / "00-inbox" / "drive-sync.json"
STATE_FILE = VAULT_ROOT / "graph" / "drive-sync-state.json"
TOKEN_FILE = VAULT_ROOT / ".auth" / "google-token.json"
INGEST_SCRIPT = VAULT_ROOT / "scripts" / "ingest.py"
DOWNLOAD_DIR = Path("/tmp/drive-sync")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
]

# MIME types the ingest pipeline can process
INGESTIBLE_MIMES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Google Workspace types must be exported (not downloaded directly)
EXPORT_MIMES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}


# ─── Config / state I/O ────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"No config found at {CONFIG_FILE}")
        print("Create it with watched folder IDs — example:")
        print('  {"watched_folders": [{"id": "FOLDER_ID", "name": "Sage Docs", "recursive": true}]}')
        print("Get folder IDs from Drive URLs: drive.google.com/drive/folders/FOLDER_ID")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"files": {}, "last_sync": None}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_sync"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ─── Google Drive auth ─────────────────────────────────────────────────────────

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
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ─── Drive file listing ────────────────────────────────────────────────────────

def list_folder(service, folder_id: str, recursive: bool) -> list[dict]:
    """Return all ingestible files in a folder."""
    results = []
    _walk(service, folder_id, results, recursive)
    return results


def _walk(service, folder_id: str, results: list, recursive: bool):
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            pageSize=100,
            orderBy="modifiedTime desc",
            fields="nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)",
            pageToken=page_token or "",
        ).execute()

        for item in resp.get("files", []):
            mime = item.get("mimeType", "")
            if mime == "application/vnd.google-apps.folder":
                if recursive:
                    _walk(service, item["id"], results, recursive)
            elif mime in INGESTIBLE_MIMES:
                results.append(item)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break


# ─── Diff: detect new / changed ────────────────────────────────────────────────

def diff_against_state(all_files: list[dict], known: dict) -> tuple[list, list]:
    """Return (new_files, changed_files) by comparing Drive modifiedTime to state."""
    new_files, changed_files = [], []
    for f in all_files:
        fid = f["id"]
        drive_modified = f.get("modifiedTime", "")
        if fid not in known:
            new_files.append(f)
        elif known[fid].get("modified_time") != drive_modified:
            changed_files.append(f)
    return new_files, changed_files


# ─── Download ─────────────────────────────────────────────────────────────────

def download_file(service, file_id: str, name: str, mime: str) -> Path:
    """Download a Drive file to /tmp/drive-sync/. Returns local path."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

    # Determine extension
    export_mime = EXPORT_MIMES.get(mime)
    if export_mime == "text/csv":
        ext = ".csv"
    elif mime == "application/pdf":
        ext = ".pdf"
    else:
        ext = ".txt"

    if not safe_name.endswith(ext):
        safe_name += ext

    out_path = DOWNLOAD_DIR / f"{file_id}_{safe_name}"

    if export_mime:
        content = service.files().export(fileId=file_id, mimeType=export_mime).execute()
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
        out_path.write_text(text, encoding="utf-8")
    else:
        import io
        from googleapiclient.http import MediaIoBaseDownload
        buf = io.BytesIO()
        req = service.files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        out_path.write_bytes(buf.getvalue())

    return out_path


# ─── Ingest ────────────────────────────────────────────────────────────────────

def run_ingest(file_path: Path, yes: bool) -> tuple[bool, str]:
    """Call ingest.py on a local file. Returns (success, output)."""
    cmd = [sys.executable, str(INGEST_SCRIPT), str(file_path)]
    if yes:
        cmd.append("--yes")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(VAULT_ROOT))
    output = result.stdout + result.stderr
    return result.returncode == 0, output


# ─── CLI ──────────────────────────────────────────────────────────────────────

def cmd_check(config: dict, state: dict, service) -> tuple[list, list]:
    """Scan watched folders and report new/changed files. No downloads."""
    watched = config.get("watched_folders", [])
    if not watched:
        print("No watched folders in drive-sync.json.")
        print('Add entries: {"id": "FOLDER_ID", "name": "Label", "recursive": true}')
        return [], []

    all_files = []
    for folder in watched:
        fid = folder.get("id")
        label = folder.get("name", fid)
        recursive = folder.get("recursive", True)
        print(f"Scanning: {label} ({'recursive' if recursive else 'top-level only'})...")
        files = list_folder(service, fid, recursive)
        for f in files:
            f["_folder"] = label
        all_files.extend(files)

    known = state.get("files", {})
    new_files, changed_files = diff_against_state(all_files, known)
    up_to_date = len(all_files) - len(new_files) - len(changed_files)

    last_sync = state.get("last_sync")
    last_sync_str = last_sync[:19].replace("T", " ") + " UTC" if last_sync else "never"

    print(f"\n{'─' * 50}")
    print(f"Drive Sync Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Last sync: {last_sync_str}")
    print(f"Files scanned: {len(all_files)} across {len(watched)} folder(s)")
    print(f"  New:        {len(new_files)}")
    print(f"  Changed:    {len(changed_files)}")
    print(f"  Up to date: {up_to_date}")

    if new_files:
        print("\nNew files:")
        for f in new_files:
            print(f"  [{f['_folder']}] {f['name']}")

    if changed_files:
        print("\nChanged files:")
        for f in changed_files:
            prev = known[f['id']].get('modified_time', '')[:10]
            curr = f.get('modifiedTime', '')[:10]
            print(f"  [{f['_folder']}] {f['name']}  ({prev} → {curr})")

    if not new_files and not changed_files:
        print("\nAll files are up to date.")

    if new_files or changed_files:
        print(f"\nRun: python scripts/drive_sync.py --run   to ingest pending files")

    return new_files, changed_files


def cmd_run(config: dict, state: dict, service, yes: bool):
    """Download and ingest all new and changed Drive files."""
    new_files, changed_files = cmd_check(config, state, service)
    to_process = new_files + changed_files

    if not to_process:
        return

    print(f"\nIngesting {len(to_process)} file(s)...\n")
    known = state.setdefault("files", {})
    ingested = failed = 0

    for f in to_process:
        fid = f["id"]
        name = f["name"]
        mime = f["mimeType"]
        folder = f.get("_folder", "")

        print(f"  [{folder}] {name}")
        print(f"    Downloading...", end=" ", flush=True)

        try:
            local_path = download_file(service, fid, name, mime)
            print(f"done  ({local_path.stat().st_size // 1024}KB)")
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1
            continue

        print(f"    Ingesting...", end=" ", flush=True)
        ok, output = run_ingest(local_path, yes)

        if ok:
            print("ok")
            ingested += 1
            known[fid] = {
                "name": name,
                "folder": folder,
                "modified_time": f.get("modifiedTime", ""),
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "local_path_used": str(local_path),
            }
        else:
            print(f"FAILED")
            # Print first 3 lines of output for context
            for line in output.splitlines()[:3]:
                print(f"      {line}")
            failed += 1

        # Clean up temp file regardless of ingest outcome
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            pass

    save_state(state)

    print(f"\n{'─' * 50}")
    print(f"Sync complete: {ingested} ingested, {failed} failed")
    if ingested > 0:
        print(f"State saved to {STATE_FILE.relative_to(VAULT_ROOT)}")


def _die(msg: str):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Google Drive sync agent — watches folders and ingests new/changed files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--check", action="store_true", help="Report new/changed files (no download)")
    parser.add_argument("--run", action="store_true", help="Download and ingest new/changed files")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip ingest cost confirmation prompts")
    args = parser.parse_args()

    if not args.check and not args.run:
        parser.print_help()
        sys.exit(0)

    config = load_config()
    state = load_state()
    service = get_drive_service()

    if args.check:
        cmd_check(config, state, service)
    elif args.run:
        cmd_run(config, state, service, yes=args.yes)


if __name__ == "__main__":
    main()
