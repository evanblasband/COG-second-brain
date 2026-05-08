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

Environment:
    ANTHROPIC_API_KEY   required (or set in .env)
"""

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
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

EXTRACTION_PROMPT = """You are a knowledge graph entity extractor for an AI second brain system focused on senior living technology and IoT hardware.

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
- If no clear entities exist in this chunk, return {{"entities": [], "relationships": []}}

DOCUMENT:
{content}"""


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

    prompt = EXTRACTION_PROMPT.format(
        entity_types=", ".join(ENTITY_TYPES),
        content=chunk.strip(),
    )
    msg = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=4096,  # rich documents can need 2k+ tokens for entity JSON
        messages=[{"role": "user", "content": prompt}],
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


# ─── Core ingest pipeline ──────────────────────────────────────────────────────

def ingest_file(path: Path, force: bool, yes: bool, client) -> dict:
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

    # Update manifest
    manifest["entries"][source_key] = {
        "hash": content_hash,
        "path": source_key,
        "ingested": datetime.now(timezone.utc).isoformat(),
        "nodes_created": created,
        "nodes_updated": updated,
        "relationships_added": rels_added,
    }
    save_manifest(manifest)

    print(f"  ✓ {created} created, {updated} updated, {rels_added} relationships")
    _run_on_ingest_hook(source_key, created, updated)

    return {"status": "ok", "path": source_key, "created": created, "updated": updated, "relationships": rels_added}


def ingest_batch(root: Path, pattern: str, force: bool, yes: bool, client) -> None:
    """Ingest all matching files under root."""
    files = sorted(root.rglob(pattern))
    md_files = [f for f in files if f.is_file() and not any(
        part.startswith(".") for part in f.parts
    )]

    if not md_files:
        print(f"No files found matching {pattern} under {root}")
        return

    # Batch cost estimate
    total_chars = sum(f.stat().st_size for f in md_files)
    total_tokens = total_chars // CHARS_PER_TOKEN
    total_cost = total_chars / CHARS_PER_TOKEN / 1_000_000 * HAIKU_INPUT_COST_PER_MTOK

    print(f"\nBatch ingest: {len(md_files)} files | ~{total_tokens:,} tokens | Est. ${total_cost:.3f}")

    if not yes:
        answer = input("Proceed? [Y/n]: ").strip()
        if answer.lower() == "n":
            print("Cancelled.")
            return

    stats = {"ok": 0, "skipped": 0, "error": 0, "cancelled": 0,
             "total_created": 0, "total_updated": 0}

    for f in md_files:
        result = ingest_file(f, force=force, yes=True, client=client)
        status = result.get("status", "error")
        stats[status] = stats.get(status, 0) + 1
        stats["total_created"] += result.get("created", 0)
        stats["total_updated"] += result.get("updated", 0)

    print(f"\nBatch complete: {stats['ok']} ingested, {stats['skipped']} skipped, "
          f"{stats['error']} errors | "
          f"{stats['total_created']} nodes created, {stats['total_updated']} updated")


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
    parser.add_argument("--manifest", action="store_true", help="Show ingest manifest and exit")
    parser.add_argument("--stats", action="store_true", help="Show graph stats and exit")

    args = parser.parse_args()

    if args.manifest:
        show_manifest()
        return

    if args.stats:
        show_stats()
        return

    if not args.path:
        parser.print_help()
        sys.exit(1)

    target = Path(args.path)
    if not target.exists():
        _die(f"Path not found: {target}")

    client = get_client()

    if args.batch or target.is_dir():
        ingest_batch(target, "*.md", args.force, args.yes, client)
    else:
        ingest_file(target, args.force, args.yes, client)


if __name__ == "__main__":
    main()
