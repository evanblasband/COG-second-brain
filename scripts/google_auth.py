#!/usr/bin/env python3
"""
google_auth.py — One-time Google OAuth setup for Calendar + Gmail + Drive.

Usage:
    python scripts/google_auth.py

Prerequisites:
    1. Go to https://console.cloud.google.com/
    2. Create a project (or use an existing one)
    3. Enable: Google Calendar API, Gmail API, Google Drive API
    4. Go to APIs & Services > Credentials
    5. Create OAuth 2.0 Client ID > Desktop application
    6. Download the JSON file
    7. Save it as .auth/google-credentials.json in the vault root
    8. Run this script
"""

import json
import os
import sys
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
CREDENTIALS_FILE = VAULT_ROOT / ".auth" / "google-credentials.json"
TOKEN_FILE = VAULT_ROOT / ".auth" / "google-token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def check_dependencies():
    missing = []
    for pkg in ["google.auth", "google_auth_oauthlib", "googleapiclient"]:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)


def run_auth():
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    # Check for existing valid token
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        print(f"✓ Already authenticated. Token: {TOKEN_FILE}")
        _print_token_info(creds)
        return

    if creds and creds.expired and creds.refresh_token:
        print("Refreshing expired token...")
        creds.refresh(Request())
        _save_token(creds)
        print(f"✓ Token refreshed and saved to {TOKEN_FILE}")
        return

    # No valid token — run OAuth flow
    if not CREDENTIALS_FILE.exists():
        print(f"\n✗ Credentials file not found: {CREDENTIALS_FILE}")
        print("\nSetup steps:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Create or select a project")
        print("  3. Enable: Google Calendar API + Gmail API")
        print("  4. APIs & Services > Credentials > Create OAuth 2.0 Client ID")
        print("  5. Application type: Desktop app")
        print("  6. Download JSON > save as .auth/google-credentials.json")
        print("  7. Re-run this script")
        sys.exit(1)

    print("Opening browser for Google authentication...")
    print(f"Scopes requested: {', '.join(s.split('/')[-1] for s in SCOPES)}")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    # open_browser=False for WSL compatibility — copy the printed URL into your Windows browser
    creds = flow.run_local_server(port=0, open_browser=False)

    _save_token(creds)
    print(f"\n✓ Authentication complete. Token saved to {TOKEN_FILE}")
    print("\nYou can now run: python scripts/query.py calendar today")


def _save_token(creds):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())


def _print_token_info(creds):
    if creds.expiry:
        print(f"  Expires: {creds.expiry.strftime('%Y-%m-%d %H:%M UTC')}")
    scopes_short = [s.split("/")[-1] for s in (creds.scopes or [])]
    if scopes_short:
        print(f"  Scopes:  {', '.join(scopes_short)}")


if __name__ == "__main__":
    check_dependencies()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    run_auth()
