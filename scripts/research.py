#!/usr/bin/env python3
"""
research.py — Background research pipeline for 04-knowledge/ ingest.
Intended for autonomous/cron contexts. For interactive Claude sessions,
use WebFetch/WebSearch directly instead.

Usage:
    python scripts/research.py --url URL --category CATEGORY [--subcategory SUB]
    python scripts/research.py --url URL --category technologies --subcategory iot-protocols
    python scripts/research.py --manifest   # show ingest manifest summary

Categories: technologies | regulations | competitors | consolidated | patterns

Pipeline:
    URL → fetch → hash check (skip if unchanged) → extract text →
    write structured note to 04-knowledge/{category}/{slug}.md →
    update ingest_manifest.json → log

Note: Entity extraction and graph merging (design doc full pipeline) are V2.
V1 = structured markdown notes + manifest tracking.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

VAULT_ROOT = Path(__file__).parent.parent
KNOWLEDGE_DIR = VAULT_ROOT / "04-knowledge"
MANIFEST_FILE = VAULT_ROOT / "graph" / "ingest_manifest.json"
VALID_CATEGORIES = {"technologies", "regulations", "competitors", "consolidated", "patterns", "booklets", "timeline"}


# ─── Manifest ─────────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    return {"version": 1, "entries": {}}


def save_manifest(manifest: dict):
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2, default=str)


def already_ingested(url: str, content_hash: str, manifest: dict) -> bool:
    entry = manifest["entries"].get(url)
    if not entry:
        return False
    return entry.get("hash") == content_hash


# ─── Fetch ────────────────────────────────────────────────────────────────────

def fetch_url(url: str) -> tuple[str, str]:
    """Fetch URL, return (text_content, content_type)."""
    try:
        import requests
    except ImportError:
        _die("requests not installed. Run: pip install -r requirements.txt")

    headers = {"User-Agent": "Mozilla/5.0 (research-pipeline/1.0; personal knowledge base)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")

    if "html" in content_type:
        return _extract_html(resp.text), "html"
    else:
        return resp.text[:50000], "text"


def _extract_html(html: str) -> str:
    """Strip HTML tags and boilerplate, return readable text."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove nav, footer, ads
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # Collapse whitespace
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:40000]
    except ImportError:
        # Fallback: crude tag strip
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text[:40000]


# ─── Slug + path ──────────────────────────────────────────────────────────────

def url_to_slug(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.netloc + parsed.path
    slug = re.sub(r"[^\w-]", "-", path).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:80].lower()


def note_path(category: str, slug: str) -> Path:
    return KNOWLEDGE_DIR / category / f"{slug}.md"


# ─── Note writer ──────────────────────────────────────────────────────────────

def write_note(path: Path, url: str, content: str, title: str, tags: list[str]):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path.parent.mkdir(parents=True, exist_ok=True)

    # Truncate content to reasonable note length
    preview = content[:6000].strip()
    if len(content) > 6000:
        preview += "\n\n... [truncated — fetch full content via WebFetch]"

    frontmatter = f"""---
created: {today}
updated: {today}
type: knowledge
tags: {json.dumps(tags)}
status: reference
source: external
confidence: medium
url: {url}
pipeline: research.py
---"""

    body = f"""# {title}

**Source:** {url}
**Ingested:** {today}
**Confidence:** medium — auto-extracted, needs review

---

## Extracted Content

{preview}

---

## Key Facts

<!-- Claude: extract 5-10 bullet-point key facts from the content above -->

## Related

<!-- Link to related notes in 04-knowledge/ -->
"""

    with open(path, "w") as f:
        f.write(frontmatter + "\n\n" + body)

    print(f"✓ Written: {path.relative_to(VAULT_ROOT)}")


# ─── Main pipeline ─────────────────────────────────────────────────────────────

def run_ingest(path: Path):
    """Call ingest.py on a newly written note to extract entities into the graph."""
    import subprocess
    ingest_script = VAULT_ROOT / "scripts" / "ingest.py"
    python = sys.executable
    result = subprocess.run(
        [python, str(ingest_script), str(path), "--yes"],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"  ⚠️  ingest.py returned non-zero for {path.name} — check graph/conflicts.json")


def ingest_url(url: str, category: str, subcategory: str | None, force: bool, no_ingest: bool = False):
    if category not in VALID_CATEGORIES:
        _die(f"Unknown category '{category}'. Valid: {', '.join(sorted(VALID_CATEGORIES))}")

    manifest = load_manifest()

    print(f"Fetching: {url}")
    try:
        content, _ = fetch_url(url)
    except Exception as e:
        _die(f"Fetch failed: {e}")

    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    if not force and already_ingested(url, content_hash, manifest):
        print(f"Skipped (unchanged): {url}")
        return

    slug = url_to_slug(url)
    target_category = f"{category}/{subcategory}" if subcategory else category
    path = note_path(target_category, slug)

    # Extract a rough title from first non-empty line
    first_line = next((l for l in content.splitlines() if len(l) > 10), url)
    title = first_line[:100].strip()

    tags = [category]
    if subcategory:
        tags.append(subcategory)

    write_note(path, url, content, title, tags)

    manifest["entries"][url] = {
        "hash": content_hash,
        "path": str(path.relative_to(VAULT_ROOT)),
        "category": category,
        "ingested": datetime.now(timezone.utc).isoformat(),
    }
    save_manifest(manifest)

    if not no_ingest:
        print(f"  → Running entity extraction on {path.name}...")
        run_ingest(path)


def show_manifest():
    manifest = load_manifest()
    entries = manifest.get("entries", {})
    if not entries:
        print("Manifest is empty — no URLs ingested yet.")
        return
    print(f"Ingest manifest — {len(entries)} entries\n")
    for url, meta in entries.items():
        print(f"  {meta['path']}")
        print(f"    url:      {url}")
        print(f"    ingested: {meta['ingested'][:10]}")
        print()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _die(msg: str):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Research pipeline — fetch URL → extract → write to 04-knowledge/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", help="URL to ingest")
    parser.add_argument("--category", help=f"Knowledge category: {', '.join(sorted(VALID_CATEGORIES))}")
    parser.add_argument("--subcategory", help="Optional subcategory (e.g. 'iot-protocols')")
    parser.add_argument("--force", action="store_true", help="Re-ingest even if hash unchanged")
    parser.add_argument("--no-ingest", action="store_true", help="Skip entity extraction — write note only, do not update graph")
    parser.add_argument("--manifest", action="store_true", help="Show ingest manifest")

    args = parser.parse_args()

    if args.manifest:
        show_manifest()
        return

    if not args.url or not args.category:
        parser.print_help()
        sys.exit(1)

    ingest_url(args.url, args.category, args.subcategory, args.force, args.no_ingest)


if __name__ == "__main__":
    main()
