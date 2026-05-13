#!/usr/bin/env python3
"""
ingest.py — Knowledge graph ingest pipeline.

Reads a markdown file (or directory of files), extracts structured entities
via Claude Haiku, and merges them into graph/graph.json.

Designed to work alongside research.py:
  research.py --url URL --category X   → writes 04-knowledge/{category}/{slug}.md
  ingest.py 04-knowledge/category/     → extracts entities → merges into graph.json

Usage:
    python scripts/ingest.py path/to/file.md
    python scripts/ingest.py 04-knowledge/technologies/ --batch
    python scripts/ingest.py 04-knowledge/ --batch --yes       # skip cost prompts
    python scripts/ingest.py --manifest                        # show what's ingested
    python scripts/ingest.py --stats                           # graph node counts by type

    python scripts/ingest.py --drive FILE_ID                   # fetch Drive file → ingest
    python scripts/ingest.py --drive FILE_ID --save 04-knowledge/category/name.md
    python scripts/ingest.py --drive-folder FOLDER_ID          # recursively ingest entire Drive folder
    python scripts/ingest.py --notion PAGE_ID                  # fetch Notion page → ingest
    python scripts/ingest.py --notion PAGE_ID --save 04-knowledge/category/name.md
    python scripts/ingest.py --notion-db DB_ID                 # fetch all DB rows → ingest each

Environment:
    ANTHROPIC_API_KEY   required (or set in .env)
    NOTION_TOKEN        required for --notion/--notion-db (or set in .env)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(VAULT_ROOT / ".env")
except ImportError:
    pass

GRAPH_FILE = VAULT_ROOT / "graph" / "graph.json"
MANIFEST_FILE = VAULT_ROOT / "graph" / "ingest_manifest.json"
CONFLICTS_FILE = VAULT_ROOT / "graph" / "conflicts.json"
HOOKS_DIR = VAULT_ROOT / ".claude" / "hooks"


# ─── Config ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    config_file = VAULT_ROOT / "config" / "config.yaml"
    if not config_file.exists():
        return {}
    try:
        import yaml
        with open(config_file) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


CONFIG = load_config()

HAIKU_INPUT_COST_PER_MTOK = CONFIG.get("ingest", {}).get("haiku_input_cost_per_mtok", 0.80)
HAIKU_OUTPUT_COST_PER_MTOK = CONFIG.get("ingest", {}).get("haiku_output_cost_per_mtok", 4.00)
AUTO_APPROVE_THRESHOLD_USD = CONFIG.get("cost_limits", {}).get("ingest_auto_approve_usd", 0.10)
CHUNK_SIZE = CONFIG.get("ingest", {}).get("chunk_size_chars", 4000)
EXTRACTION_MODEL = CONFIG.get("models", {}).get("extraction", "claude-haiku-4-5-20251001")

ENTITY_TYPES = [
    "HardwareComponent", "DataStream", "BackendService", "APIEndpoint",
    "ConnectivityLink", "ComplianceRequirement", "SystemFeature", "DataModel",
    "Regulation", "Competitor", "Technology", "Person", "Organization",
    "Project", "Dependency",
]

CHARS_PER_TOKEN = 4

SYSTEM_PROMPT_TEMPLATE = """You are a knowledge graph entity extractor for an AI second brain system focused on senior living technology and IoT hardware.

Extract structured entities and relationships from the document below.

ENTITY TYPES (use exactly these strings):
{entity_types}

Return ONLY valid JSON in this exact format (no markdown fences, no explanation):
{{
  "entities": [
    {{
      "type": "<entity type from list above>",
      "name": "<canonical full name>",
      "description": "<1-2 sentence description>",
      "attributes": {{}},
      "confidence": <0.0-1.0>,
      "tags": ["<tag1>", "<tag2>"]
    }}
  ],
  "relationships": [
    {{
      "source": "<source entity name>",
      "target": "<target entity name>",
      "type": "<depends_on|is_a|part_of|competes_with|regulates|uses|owned_by|implements>",
      "description": "<brief description>"
    }}
  ]
}}

RULES:
- Only extract entities clearly described in the document (not mentioned in passing)
- Confidence 0.9 = explicitly stated fact; 0.7 = implied; 0.5 = inferred
- Use canonical names (e.g. "Bluetooth Low Energy" not "BLE")
- Extract 0-15 entities per chunk; quality over quantity
- If no clear entities exist in this chunk, return {{"entities": [], "relationships": []}}"""

# Rendered once at startup — static across all extract_entities calls
SYSTEM_PROMPT = SYSTEM_PROMPT_TEMPLATE.format(entity_types=", ".join(ENTITY_TYPES))


# ─── Env / API key ─────────────────────────────────────────────────────────────

def get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = VAULT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key:
                    return key
    _die("ANTHROPIC_API_KEY not set. Add to .env or export in shell.")


def get_client():
    try:
        import anthropic
    except ImportError:
        _die("anthropic SDK not installed. Run: pip install -r requirements.txt")
    return anthropic.Anthropic(api_key=get_api_key())


# ─── Graph I/O ─────────────────────────────────────────────────────────────────

def load_graph() -> dict:
    if not GRAPH_FILE.exists():
        _die(f"graph.json not found at {GRAPH_FILE}. Expected it to exist — check setup.")
    with open(GRAPH_FILE) as f:
        return json.load(f)


def save_graph(graph: dict):
    now = datetime.now(timezone.utc).isoformat()
    graph["metadata"]["last_updated"] = now
    graph["metadata"]["total_nodes"] = len(graph["nodes"])
    graph["metadata"]["total_relationships"] = len(graph["relationships"])
    with open(GRAPH_FILE, "w") as f:
        json.dump(graph, f, indent=2, default=str)


# ─── Manifest I/O ──────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    return {"version": 1, "entries": {}}


def save_manifest(manifest: dict):
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2, default=str)


# ─── Conflicts I/O ────────────────────────────────────────────────────────────

def load_conflicts() -> dict:
    if CONFLICTS_FILE.exists():
        with open(CONFLICTS_FILE) as f:
            return json.load(f)
    return {"conflicts": []}


def save_conflicts(conflicts: dict):
    with open(CONFLICTS_FILE, "w") as f:
        json.dump(conflicts, f, indent=2, default=str)


def log_conflict(entity_name: str, conflict_type: str, existing: dict, incoming: dict, source: str):
    """Append a conflict entry to conflicts.json for human review."""
    conflicts = load_conflicts()
    conflicts["conflicts"].append({
        "id": str(uuid.uuid4())[:8],
        "detected": datetime.now(timezone.utc).isoformat(),
        "status": "unresolved",
        "entity_name": entity_name,
        "conflict_type": conflict_type,
        "existing": {
            "type": existing.get("type"),
            "description": existing.get("description", ""),
            "sources": existing.get("sources", []),
            "confidence": existing.get("confidence"),
        },
        "incoming": {
            "type": incoming.get("type"),
            "description": incoming.get("description", ""),
            "source": source,
            "confidence": incoming.get("confidence"),
        },
        "resolved_by": None,
        "resolution": None,
    })
    save_conflicts(conflicts)
    print(f"  ⚠️  Conflict logged: '{entity_name}' ({conflict_type}) → graph/conflicts.json")


# ─── Chunking ──────────────────────────────────────────────────────────────────

def chunk_document(content: str) -> list[str]:
    """Split on markdown section headers, targeting ~CHUNK_SIZE chars."""
    chunks = []
    current_lines: list[str] = []
    current_len = 0

    for line in content.splitlines(keepends=True):
        is_major_header = line.startswith("## ") and current_len > CHUNK_SIZE // 2
        if is_major_header:
            if current_lines:
                chunks.append("".join(current_lines))
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len += len(line)
            if current_len >= CHUNK_SIZE:
                chunks.append("".join(current_lines))
                current_lines = []
                current_len = 0

    if current_lines:
        chunks.append("".join(current_lines))

    return [c for c in chunks if c.strip()]


# ─── Cost estimation ───────────────────────────────────────────────────────────

def estimate_cost(content: str) -> tuple[float, int]:
    """Return (cost_usd, token_estimate). Rough but usable for gate decisions."""
    tokens = len(content) // CHARS_PER_TOKEN
    num_chunks = max(1, len(chunk_document(content)))
    output_tokens = num_chunks * 350  # rough JSON output per chunk

    cost = (tokens / 1_000_000 * HAIKU_INPUT_COST_PER_MTOK +
            output_tokens / 1_000_000 * HAIKU_OUTPUT_COST_PER_MTOK)
    return cost, tokens


# ─── Entity extraction ─────────────────────────────────────────────────────────

def extract_entities(chunk: str, client) -> dict:
    """Call Haiku to extract entities from one chunk. Returns {entities, relationships}."""
    import re

    msg = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=4096,  # rich documents can need 2k+ tokens for entity JSON
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": f"DOCUMENT:\n{chunk.strip()}"}],
    )
    raw = msg.content[0].text.strip()

    # Robust JSON extraction: find the outermost {...} regardless of surrounding text,
    # markdown fences, or preamble. Handles "```json\n{...}\n```" and plain JSON alike.
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if not json_match:
        return {"entities": [], "relationships": []}
    raw = json_match.group(0)

    try:
        result = json.loads(raw)
        if not isinstance(result.get("entities"), list):
            result["entities"] = []
        if not isinstance(result.get("relationships"), list):
            result["relationships"] = []
        return result
    except json.JSONDecodeError:
        return {"entities": [], "relationships": []}


# ─── Graph merge ───────────────────────────────────────────────────────────────

def find_node_by_name(graph: dict, name: str, type_: str) -> str | None:
    """Return node ID if a node with this name+type exists (case-insensitive)."""
    name_lower = name.lower()
    for node_id, node in graph["nodes"].items():
        if node["name"].lower() == name_lower and node["type"] == type_:
            return node_id
    return None


def merge_node(graph: dict, entity: dict, source_path: str) -> tuple[str, bool]:
    """
    Upsert entity into graph. Returns (node_id, was_newly_created).
    Prints a conflict warning if type changed on an existing node.
    """
    now = datetime.now(timezone.utc).isoformat()
    existing_id = find_node_by_name(graph, entity["name"], entity["type"])

    if existing_id:
        node = graph["nodes"][existing_id]

        # Conflict: same name, different type — log for human review, skip merge
        if node["type"] != entity["type"]:
            log_conflict(
                entity_name=entity["name"],
                conflict_type="type_mismatch",
                existing=node,
                incoming=entity,
                source=source_path,
            )
            return existing_id, False

        # Update: merge attributes, bump version
        incoming_conf = entity.get("confidence", 0.7)
        if incoming_conf >= node.get("confidence", 0.0):
            node["attributes"].update(entity.get("attributes", {}))
            node["description"] = entity.get("description", node["description"])
            node["confidence"] = incoming_conf

        node["version"] = node.get("version", 1) + 1
        node["last_updated"] = now
        node["staleness_score"] = 0.0
        if source_path not in node.get("sources", []):
            node.setdefault("sources", []).append(source_path)
        for tag in entity.get("tags", []):
            if tag not in node.get("tags", []):
                node.setdefault("tags", []).append(tag)

        return existing_id, False

    # Create new node
    node_id = str(uuid.uuid4())[:8]
    graph["nodes"][node_id] = {
        "id": node_id,
        "type": entity["type"],
        "name": entity["name"],
        "description": entity.get("description", ""),
        "attributes": entity.get("attributes", {}),
        "confidence": entity.get("confidence", 0.7),
        "version": 1,
        "sources": [source_path],
        "last_updated": now,
        "tags": entity.get("tags", []),
        "staleness_score": 0.0,
    }
    return node_id, True


def merge_relationship(graph: dict, rel: dict, name_to_id: dict[str, str]):
    """Add a relationship between two nodes if it doesn't already exist."""
    src_id = name_to_id.get(rel.get("source", "").lower())
    tgt_id = name_to_id.get(rel.get("target", "").lower())
    if not src_id or not tgt_id:
        return

    rel_type = rel.get("type", "related_to")
    for existing in graph["relationships"]:
        if (existing["source_id"] == src_id and
                existing["target_id"] == tgt_id and
                existing["type"] == rel_type):
            return  # Already exists

    graph["relationships"].append({
        "id": str(uuid.uuid4())[:8],
        "source_id": src_id,
        "target_id": tgt_id,
        "type": rel_type,
        "description": rel.get("description", ""),
        "created": datetime.now(timezone.utc).isoformat(),
    })


# ─── Filter helpers ────────────────────────────────────────────────────────────

def _print_active_filters(filters: dict):
    parts = []
    if filters.get("after"):
        parts.append(f"after {filters['after'].strftime('%Y-%m-%d')}")
    if filters.get("name_contains"):
        parts.append(f"name contains '{filters['name_contains']}'")
    if filters.get("exclude_name"):
        parts.append(f"name excludes '{filters['exclude_name']}'")
    if parts:
        print(f"  Filters: {' | '.join(parts)}")


# ─── Drive fetch ──────────────────────────────────────────────────────────────

_DRIVE_EXPORT_MIMES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

_PDF_MIME = "application/pdf"
_DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"


def _extract_pdf_text(data: bytes) -> str:
    try:
        import io as _io
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("pypdf not installed. Run: pip install -r requirements.txt")
    reader = PdfReader(_io.BytesIO(data))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_google_creds():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        _die("google-auth not installed. Run: pip install -r requirements.txt")

    token_file = VAULT_ROOT / ".auth" / "google-token.json"
    if not token_file.exists():
        _die(f"No Google token at {token_file}. Run: python scripts/google_auth.py")

    creds = Credentials.from_authorized_user_file(str(token_file), _GOOGLE_SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return creds


def _build_drive_service():
    try:
        from googleapiclient.discovery import build
    except ImportError:
        _die("google-api-python-client not installed. Run: pip install -r requirements.txt")
    return build("drive", "v3", credentials=_get_google_creds())


def _fetch_drive_file_text(service, file_id: str, mime: str) -> str | None:
    """Download one Drive file and return plain text, or None if unsupported."""
    export_mime = _DRIVE_EXPORT_MIMES.get(mime)
    if export_mime:
        content = service.files().export(fileId=file_id, mimeType=export_mime).execute()
        return content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)

    import io
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, service.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    raw = buf.getvalue()

    if mime == _PDF_MIME:
        print("  Extracting text from PDF...")
        text = _extract_pdf_text(raw)
        if not text.strip():
            print("  Warning: PDF yielded no extractable text (may be scanned/image-only).")
        return text

    return None  # unsupported binary type


def fetch_from_drive(file_id: str, save_path, force: bool, yes: bool, client, note: str = ""):
    """Fetch a Google Drive file, save locally, then ingest."""
    service = _build_drive_service()
    meta = service.files().get(fileId=file_id, fields="id,name,mimeType").execute()
    name = meta.get("name", file_id)
    mime = meta.get("mimeType", "")

    print(f"Fetching Drive file: {name}")
    text = _fetch_drive_file_text(service, file_id, mime)
    if text is None:
        _die(f"Unsupported file type: {mime}. Supported: Google Docs/Sheets/Slides, PDF.")

    if save_path is None:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        save_path = Path(f"/tmp/{safe}.md")

    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(text, encoding="utf-8")
    print(f"Saved to: {save_path}")
    ingest_file(save_path, force, yes, client, note=note)


def fetch_from_drive_folder(folder_id: str, save_dir, force: bool, yes: bool, client,
                            note: str = "", filters: dict | None = None):
    """Recursively fetch and ingest all supported files from a Google Drive folder."""
    filters = filters or {}
    service = _build_drive_service()
    meta = service.files().get(fileId=folder_id, fields="id,name,mimeType").execute()
    if meta.get("mimeType") != _DRIVE_FOLDER_MIME:
        _die(f"'{meta.get('name')}' is not a folder (mimeType: {meta.get('mimeType')})")

    folder_name = meta.get("name", folder_id)
    print(f"Ingesting Drive folder: {folder_name}")
    _print_active_filters(filters)

    if save_dir is None:
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in folder_name)
        save_dir = Path(f"/tmp/drive-{safe}")

    stats = {
        "ok": 0, "skipped": 0, "error": 0, "cancelled": 0,
        "total_created": 0, "total_updated": 0, "total_relationships": 0,
        "filtered": 0, "unsupported": 0, "unsupported_names": [],
    }
    _ingest_drive_folder_recursive(service, folder_id, Path(save_dir), force, yes, client, note, filters, stats)

    print(f"\n{'─' * 50}")
    print(f"Drive folder ingest complete: {folder_name}")
    print(f"  Ingested:          {stats['ok']}")
    print(f"  Skipped (cached):  {stats['skipped']}")
    print(f"  Filtered out:      {stats['filtered']}")
    print(f"  Errors:            {stats['error']}")
    print(f"  Unsupported types: {stats['unsupported']}")
    print(f"  Nodes created:     {stats['total_created']}")
    print(f"  Nodes updated:     {stats['total_updated']}")
    print(f"  Relationships:     {stats['total_relationships']}")
    if stats["unsupported_names"]:
        print(f"\n  Skipped files (unsupported type):")
        for n in stats["unsupported_names"]:
            print(f"    - {n}")


def _ingest_drive_folder_recursive(service, folder_id: str, save_dir: Path,
                                    force: bool, yes: bool, client, note: str,
                                    filters: dict, stats: dict):
    save_dir.mkdir(parents=True, exist_ok=True)
    after = filters.get("after")
    name_contains = (filters.get("name_contains") or "").lower()
    exclude_name = (filters.get("exclude_name") or "").lower()

    cursor = None
    while True:
        q = f"'{folder_id}' in parents and trashed = false"
        if after:
            q += f" and modifiedTime > '{after.strftime('%Y-%m-%dT%H:%M:%S')}'"
        kwargs = {
            "q": q,
            "fields": "nextPageToken, files(id, name, mimeType)",
            "pageSize": 100,
        }
        if cursor:
            kwargs["pageToken"] = cursor
        result = service.files().list(**kwargs).execute()

        for f in result.get("files", []):
            fid, fname, fmime = f["id"], f["name"], f.get("mimeType", "")

            if fmime == _DRIVE_FOLDER_MIME:
                safe_sub = "".join(c if c.isalnum() or c in "._-" else "_" for c in fname)
                print(f"\nFolder: {fname}/")
                _ingest_drive_folder_recursive(service, fid, save_dir / safe_sub, force, yes, client, note, filters, stats)
                continue

            # Client-side name filters
            fname_lower = fname.lower()
            if name_contains and name_contains not in fname_lower:
                stats["filtered"] += 1
                continue
            if exclude_name and exclude_name in fname_lower:
                stats["filtered"] += 1
                continue

            if fmime not in _DRIVE_EXPORT_MIMES and fmime != _PDF_MIME:
                stats["unsupported"] += 1
                stats["unsupported_names"].append(fname)
                continue

            print(f"\nFile: {fname}")
            try:
                text = _fetch_drive_file_text(service, fid, fmime)
                if text is None:
                    stats["unsupported"] += 1
                    stats["unsupported_names"].append(fname)
                    continue

                safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in fname)
                if not safe_name.endswith(".md"):
                    safe_name += ".md"
                save_path = save_dir / safe_name
                save_path.write_text(text, encoding="utf-8")

                r = ingest_file(save_path, force, yes, client, note=note)
                stats[r.get("status", "error")] = stats.get(r.get("status", "error"), 0) + 1
                stats["total_created"] += r.get("created", 0)
                stats["total_updated"] += r.get("updated", 0)
                stats["total_relationships"] += r.get("relationships", 0)
            except Exception as e:
                print(f"  ✗ Error: {e}")
                stats["error"] += 1

        cursor = result.get("nextPageToken")
        if not cursor:
            break


# ─── Notion fetch ─────────────────────────────────────────────────────────────

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"


def _notion_req(token: str, method: str, path: str, body=None) -> dict:
    import urllib.request
    import urllib.error
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{_NOTION_API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        _die(f"Notion API {method} {path} → {e.code}: {e.read().decode()}")


def _notion_text(rich_text: list) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _notion_page_title(page: dict) -> str:
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return _notion_text(prop.get("title", []))
    return "(untitled)"


def _blocks_to_md(token: str, block_id: str, depth: int = 0) -> list:
    """Recursively fetch Notion blocks and convert to markdown lines."""
    lines = []
    cursor = None
    indent = "  " * depth

    while True:
        qs = f"?page_size=100{f'&start_cursor={cursor}' if cursor else ''}"
        data = _notion_req(token, "GET", f"/blocks/{block_id}/children{qs}")

        for block in data.get("results", []):
            btype = block.get("type", "")
            bc = block.get(btype, {})
            text = _notion_text(bc.get("rich_text", []))

            if btype == "paragraph":
                lines.append(f"{indent}{text}" if text else "")
            elif btype == "heading_1":
                lines.append(f"# {text}")
            elif btype == "heading_2":
                lines.append(f"## {text}")
            elif btype == "heading_3":
                lines.append(f"### {text}")
            elif btype == "bulleted_list_item":
                lines.append(f"{indent}- {text}")
            elif btype == "numbered_list_item":
                lines.append(f"{indent}1. {text}")
            elif btype == "to_do":
                mark = "x" if bc.get("checked") else " "
                lines.append(f"{indent}- [{mark}] {text}")
            elif btype == "toggle":
                lines.append(f"{indent}- {text}")
            elif btype == "quote":
                lines.append(f"> {text}")
            elif btype == "callout":
                emoji = (bc.get("icon") or {}).get("emoji", "")
                lines.append(f"> {emoji} {text}".strip())
            elif btype == "code":
                lang = bc.get("language", "")
                lines.append(f"```{lang}\n{text}\n```")
            elif btype == "divider":
                lines.append("---")
            elif btype == "image":
                url = (bc.get("file") or bc.get("external") or {}).get("url", "")
                caption = _notion_text(bc.get("caption", []))
                lines.append(f"![{caption}]({url})")
            elif btype in ("child_page", "child_database"):
                lines.append(f"*[Child: {bc.get('title', btype)}]*")
                continue  # don't recurse into child pages

            if block.get("has_children") and btype not in ("child_page", "child_database"):
                lines.extend(_blocks_to_md(token, block["id"], depth + 1))

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return lines


def _notion_page_to_md(token: str, page_id: str) -> tuple:
    """Fetch a Notion page (metadata + blocks) and return (title, markdown)."""
    page = _notion_req(token, "GET", f"/pages/{page_id}")
    title = _notion_page_title(page)
    last_edited = page.get("last_edited_time", "")[:10]
    url = page.get("url", "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    frontmatter = (
        f"---\n"
        f"created: {today}\n"
        f"updated: {last_edited}\n"
        f"tags: [notion, imported]\n"
        f"status: reference\n"
        f"type: knowledge\n"
        f"source: external\n"
        f"notion_id: {page_id}\n"
        f"notion_url: {url}\n"
        f"---"
    )

    # Non-title properties
    prop_lines = []
    for pname, prop in page.get("properties", {}).items():
        ptype = prop.get("type", "")
        if ptype == "title":
            continue
        if ptype == "rich_text":
            val = _notion_text(prop.get("rich_text", []))
        elif ptype == "select":
            val = (prop.get("select") or {}).get("name", "")
        elif ptype == "multi_select":
            val = ", ".join(o.get("name", "") for o in prop.get("multi_select", []))
        elif ptype == "date":
            val = (prop.get("date") or {}).get("start", "")
        elif ptype == "checkbox":
            val = str(prop.get("checkbox", False))
        elif ptype == "number":
            val = str(prop.get("number", ""))
        elif ptype == "url":
            val = prop.get("url", "") or ""
        else:
            continue
        if val:
            prop_lines.append(f"**{pname}:** {val}")

    body_lines = _blocks_to_md(token, page_id)

    parts = [frontmatter, f"\n# {title}\n"]
    if prop_lines:
        parts.append("\n".join(prop_lines))
    if body_lines:
        parts.append("\n".join(body_lines))

    return title, "\n\n".join(parts)


def _slugify(s: str, max_len: int = 50) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in s.lower()).strip("-")[:max_len]


def fetch_from_notion(page_id: str, save_path, force: bool, yes: bool, client, note: str = ""):
    """Fetch a Notion page, save as markdown, then ingest."""
    token = os.getenv("NOTION_TOKEN")
    if not token:
        _die("NOTION_TOKEN not set in .env")

    print(f"Fetching Notion page: {page_id}")
    title, content = _notion_page_to_md(token, page_id)

    if save_path is None:
        slug = _slugify(title) or page_id[:8]
        save_path = Path(f"/tmp/notion-{slug}.md")

    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(content, encoding="utf-8")
    print(f"Saved to: {save_path}")

    ingest_file(save_path, force, yes, client, note=note)


def fetch_from_notion_db(db_id: str, save_dir, force: bool, yes: bool, client, note: str = ""):
    """Fetch all pages from a Notion database and ingest each one."""
    token = os.getenv("NOTION_TOKEN")
    if not token:
        _die("NOTION_TOKEN not set in .env")

    db_meta = _notion_req(token, "GET", f"/databases/{db_id}")
    db_title = _notion_text(db_meta.get("title", []))
    print(f"Fetching Notion DB: {db_title or db_id}")

    if save_dir is None:
        save_dir = Path(f"/tmp/notion-db-{_slugify(db_title or db_id)}")

    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    cursor = None
    total = 0

    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        data = _notion_req(token, "POST", f"/databases/{db_id}/query", body)

        for page in data.get("results", []):
            page_id = page["id"]
            row_title, content = _notion_page_to_md(token, page_id)
            slug = _slugify(row_title) or page_id[:8]
            path = save_dir / f"{slug}.md"
            path.write_text(content, encoding="utf-8")
            print(f"  Row: {row_title}")
            ingest_file(path, force, yes, client, note=note)
            total += 1

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    print(f"\nDB ingest complete: {total} pages processed")


# ─── Core ingest pipeline ──────────────────────────────────────────────────────

def ingest_file(path: Path, force: bool, yes: bool, client, note: str = "") -> dict:
    """
    Run the full ingest pipeline for one file.
    Returns a stats dict: {status, path, created, updated, relationships}.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        _log_error(path, str(e))
        print(f"  ✗ Read error: {e}")
        return {"status": "error", "path": str(path), "error": str(e)}

    if note:
        content = f"[Ingest context note: {note}]\n\n{content}"

    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    source_key = str(path.relative_to(VAULT_ROOT)) if VAULT_ROOT in path.parents else str(path)

    # Hash check
    manifest = load_manifest()
    if not force and manifest["entries"].get(source_key, {}).get("hash") == content_hash:
        print(f"Skipped (unchanged): {source_key}")
        return {"status": "skipped", "path": source_key}

    # Cost estimate
    cost_est, tokens = estimate_cost(content)
    print(f"\nIngest: {source_key}")
    if note:
        print(f"  Note: {note}")
    print(f"  ~{tokens:,} tokens | Est. cost: ${cost_est:.4f}")

    if cost_est > AUTO_APPROVE_THRESHOLD_USD and not yes:
        answer = input(f"  Cost > ${AUTO_APPROVE_THRESHOLD_USD:.2f}. Proceed? [Y/n]: ").strip()
        if answer.lower() == "n":
            print("  Cancelled.")
            return {"status": "cancelled", "path": source_key}

    # Chunk and extract
    chunks = chunk_document(content)
    graph = load_graph()
    all_entities: list[dict] = []
    all_relationships: list[dict] = []

    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}/{len(chunks)}...", end=" ", flush=True)
        result = extract_entities(chunk, client)
        n = len(result.get("entities", []))
        all_entities.extend(result.get("entities", []))
        all_relationships.extend(result.get("relationships", []))
        print(f"{n} entities")

    # Merge nodes
    created = updated = 0
    for entity in all_entities:
        if entity.get("type") not in ENTITY_TYPES:
            continue
        _, was_created = merge_node(graph, entity, source_key)
        if was_created:
            created += 1
        else:
            updated += 1

    # Build name→id map for relationship resolution (after all nodes merged)
    name_to_id = {node["name"].lower(): nid for nid, node in graph["nodes"].items()}
    rels_added = 0
    for rel in all_relationships:
        before = len(graph["relationships"])
        merge_relationship(graph, rel, name_to_id)
        if len(graph["relationships"]) > before:
            rels_added += 1

    save_graph(graph)

    # Auto-update people CRM if this looks like a meeting document
    _maybe_update_people(path, content, source_key)

    # Update manifest
    entry = {
        "hash": content_hash,
        "path": source_key,
        "ingested": datetime.now(timezone.utc).isoformat(),
        "nodes_created": created,
        "nodes_updated": updated,
        "relationships_added": rels_added,
    }
    if note:
        entry["note"] = note
    manifest["entries"][source_key] = entry
    save_manifest(manifest)

    print(f"  ✓ {created} created, {updated} updated, {rels_added} relationships")
    _run_on_ingest_hook(source_key, created, updated)

    return {"status": "ok", "path": source_key, "created": created, "updated": updated, "relationships": rels_added}


def ingest_batch(root: Path, pattern: str, force: bool, yes: bool, client,
                  note: str = "", filters: dict | None = None) -> None:
    """Ingest all matching files under root."""
    filters = filters or {}
    after = filters.get("after")
    name_contains = (filters.get("name_contains") or "").lower()
    exclude_name = (filters.get("exclude_name") or "").lower()

    files = sorted(root.rglob(pattern))
    md_files = [
        f for f in files
        if f.is_file()
        and not any(part.startswith(".") for part in f.parts)
        and (not after or f.stat().st_mtime >= after.timestamp())
        and (not name_contains or name_contains in f.name.lower())
        and (not exclude_name or exclude_name not in f.name.lower())
    ]

    if not md_files:
        print(f"No files found matching {pattern} under {root}")
        return

    _print_active_filters(filters)

    # Batch cost estimate
    total_chars = sum(f.stat().st_size for f in md_files)
    total_tokens = total_chars // CHARS_PER_TOKEN
    total_cost = total_chars / CHARS_PER_TOKEN / 1_000_000 * HAIKU_INPUT_COST_PER_MTOK

    print(f"\nBatch ingest: {len(md_files)} files | ~{total_tokens:,} tokens | Est. ${total_cost:.3f}")
    if note:
        print(f"Note (applied to all files): {note}")

    if not yes:
        answer = input("Proceed? [Y/n]: ").strip()
        if answer.lower() == "n":
            print("Cancelled.")
            return

    stats = {"ok": 0, "skipped": 0, "error": 0, "cancelled": 0,
             "total_created": 0, "total_updated": 0, "total_relationships": 0,
             "error_paths": []}

    for f in md_files:
        result = ingest_file(f, force=force, yes=True, client=client, note=note)
        status = result.get("status", "error")
        stats[status] = stats.get(status, 0) + 1
        stats["total_created"] += result.get("created", 0)
        stats["total_updated"] += result.get("updated", 0)
        stats["total_relationships"] += result.get("relationships", 0)
        if status == "error":
            stats["error_paths"].append(result.get("path", str(f)))

    print(f"\n{'─' * 50}")
    print(f"Batch ingest complete")
    print(f"  Ingested:         {stats['ok']}")
    print(f"  Skipped (cached): {stats['skipped']}")
    print(f"  Cancelled:        {stats['cancelled']}")
    print(f"  Errors:           {stats['error']}")
    print(f"  Nodes created:    {stats['total_created']}")
    print(f"  Nodes updated:    {stats['total_updated']}")
    print(f"  Relationships:    {stats['total_relationships']}")
    if stats["error_paths"]:
        print(f"\n  Failed files:")
        for p in stats["error_paths"]:
            print(f"    - {p}")


# ─── Display helpers ───────────────────────────────────────────────────────────

def show_manifest():
    manifest = load_manifest()
    entries = manifest.get("entries", {})
    if not entries:
        print("Manifest is empty — nothing ingested yet.")
        return
    print(f"Ingest manifest — {len(entries)} entries\n")
    for key, meta in sorted(entries.items()):
        print(f"  {meta.get('path', key)}")
        print(f"    ingested:  {meta.get('ingested', '?')[:19]}")
        print(f"    created:   {meta.get('nodes_created', '?')} nodes")
        print()


def show_stats():
    graph = load_graph()
    nodes = graph.get("nodes", {})
    rels = graph.get("relationships", [])

    print(f"Graph stats — {len(nodes)} nodes, {len(rels)} relationships\n")

    type_counts: dict[str, int] = {}
    for node in nodes.values():
        t = node.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<25} {count}")

    if rels:
        print(f"\nRelationship types:")
        rel_counts: dict[str, int] = {}
        for r in rels:
            rel_counts[r["type"]] = rel_counts.get(r["type"], 0) + 1
        for t, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
            print(f"  {t:<25} {count}")


# ─── People CRM update ─────────────────────────────────────────────────────────

def _maybe_update_people(path: Path, content: str, source_key: str):
    """Post-ingest: if the document is a meeting doc, auto-update 02-people/."""
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from people_updater import update_from_meeting
        result = update_from_meeting(path, content, source_key)
        if result.get("created") or result.get("updated"):
            c, u = result.get("created", 0), result.get("updated", 0)
            print(f"  👥 People CRM: {c} created, {u} updated")
    except ImportError:
        pass
    except Exception as e:
        print(f"  ⚠️  People CRM update failed: {e}")


# ─── Hook utilities ────────────────────────────────────────────────────────────

def _run_on_ingest_hook(source_key: str, created: int, updated: int):
    """Call on-ingest.sh if it exists and the ingest created new nodes."""
    hook = HOOKS_DIR / "on-ingest.sh"
    if hook.exists() and created > 0:
        import subprocess
        subprocess.run(
            ["bash", str(hook), source_key, str(created), str(updated)],
            capture_output=True,
        )


def _log_error(path: Path, error: str):
    """Write error to on-error.sh for logging."""
    hook = HOOKS_DIR / "on-error.sh"
    if hook.exists():
        import subprocess
        subprocess.run(
            ["bash", str(hook), "ingest.py", str(path), error],
            capture_output=True,
        )


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _die(msg: str):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents into graph.json via entity extraction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("path", nargs="?", help="File or directory to ingest")
    parser.add_argument("--batch", action="store_true", help="Ingest all .md files under path")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if hash unchanged")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip cost confirmation prompts")
    parser.add_argument("--note", metavar="TEXT", default="",
                        help="Context note shown to the extractor and stored in manifest "
                             "(e.g. 'this document is from 2019 and may be outdated')")
    parser.add_argument("--manifest", action="store_true", help="Show ingest manifest and exit")
    parser.add_argument("--stats", action="store_true", help="Show graph stats and exit")
    parser.add_argument("--after", metavar="YYYY-MM-DD",
                        help="Only ingest files modified on or after this date")
    parser.add_argument("--name-contains", metavar="TEXT",
                        help="Only ingest files whose name contains this string (case-insensitive)")
    parser.add_argument("--exclude-name", metavar="TEXT",
                        help="Skip files whose name contains this string (case-insensitive)")
    parser.add_argument("--drive", metavar="FILE_ID", help="Fetch a Google Drive file and ingest it")
    parser.add_argument("--drive-folder", metavar="FOLDER_ID", help="Recursively fetch and ingest all supported files in a Drive folder")
    parser.add_argument("--notion", metavar="PAGE_ID", help="Fetch a Notion page and ingest it")
    parser.add_argument("--notion-db", metavar="DB_ID", help="Fetch all rows from a Notion database and ingest each")
    parser.add_argument("--save", metavar="PATH", help="Save fetched content to this path (use with --drive or --notion)")

    args = parser.parse_args()

    if args.manifest:
        show_manifest()
        return

    if args.stats:
        show_stats()
        return

    client = get_client()
    save = Path(args.save) if args.save else None
    note = args.note or ""

    # Build filters dict
    filters: dict = {}
    if args.after:
        try:
            filters["after"] = datetime.strptime(args.after, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            _die(f"--after must be YYYY-MM-DD, got: {args.after}")
    if args.name_contains:
        filters["name_contains"] = args.name_contains
    if args.exclude_name:
        filters["exclude_name"] = args.exclude_name

    if args.drive:
        fetch_from_drive(args.drive, save, args.force, args.yes, client, note=note)
        return

    if args.drive_folder:
        fetch_from_drive_folder(args.drive_folder, save, args.force, args.yes, client,
                                note=note, filters=filters)
        return

    if args.notion:
        fetch_from_notion(args.notion, save, args.force, args.yes, client, note=note)
        return

    if args.notion_db:
        fetch_from_notion_db(args.notion_db, save, args.force, args.yes, client, note=note)
        return

    if not args.path:
        parser.print_help()
        sys.exit(1)

    target = Path(args.path)
    if not target.exists():
        _die(f"Path not found: {target}")

    if args.batch or target.is_dir():
        ingest_batch(target, "*.md", args.force, args.yes, client, note=note, filters=filters)
    else:
        ingest_file(target, args.force, args.yes, client, note=note)


if __name__ == "__main__":
    main()
