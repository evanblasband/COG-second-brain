#!/usr/bin/env python3
"""
janitor.py — Light context janitor.

Keeps the vault lean by:
  1. Archiving session logs older than ARCHIVE_AFTER_DAYS (default: 14)
  2. Reporting stale graph nodes (staleness_score > 0.7)
  3. Flagging OPEN_LOOPS.md items older than LOOP_WARN_DAYS (default: 14)

Does NOT modify OPEN_LOOPS.md or graph.json autonomously —
prints a report so the user (or Claude) can act on it.

Usage:
    python scripts/janitor.py              # full report
    python scripts/janitor.py --archive    # also move old sessions to archive/
    python scripts/janitor.py --dry-run    # report only, no file moves

Cron (Friday at 17:00):
    0 17 * * 5 cd /path/to/vault && .venv/bin/python scripts/janitor.py --archive >> /tmp/janitor.log 2>&1
"""

import argparse
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = VAULT_ROOT / "AI" / "sessions"
ARCHIVE_DIR = SESSIONS_DIR / "archive"
GRAPH_FILE = VAULT_ROOT / "graph" / "graph.json"
OPEN_LOOPS = VAULT_ROOT / "OPEN_LOOPS.md"

ARCHIVE_AFTER_DAYS = 14
LOOP_WARN_DAYS = 14
STALENESS_THRESHOLD = 0.7


def scan_sessions(archive: bool, dry_run: bool) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_AFTER_DAYS)
    old_files = []
    kept_files = []

    for f in sorted(SESSIONS_DIR.glob("*.md")):
        if f.name.startswith("."):
            continue
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            old_files.append(f)
        else:
            kept_files.append(f)

    archived = []
    if archive and not dry_run:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        for f in old_files:
            dest = ARCHIVE_DIR / f.name
            if not dest.exists():
                shutil.move(str(f), str(dest))
                archived.append(f.name)

    return {
        "old": [f.name for f in old_files],
        "kept": len(kept_files),
        "archived": archived,
    }


def scan_graph() -> dict:
    if not GRAPH_FILE.exists():
        return {"error": "graph.json not found"}

    with open(GRAPH_FILE) as f:
        graph = json.load(f)

    raw_nodes = graph.get("nodes", {})
    nodes = list(raw_nodes.values()) if isinstance(raw_nodes, dict) else raw_nodes
    stale = []
    for node in nodes:
        score = node.get("staleness_score", 0)
        if score >= STALENESS_THRESHOLD:
            stale.append({
                "name": node.get("name", node.get("id", "?")),
                "type": node.get("type", "?"),
                "staleness_score": score,
            })

    stale.sort(key=lambda n: n["staleness_score"], reverse=True)

    return {
        "total_nodes": len(nodes),
        "stale_count": len(stale),
        "stale_nodes": stale[:10],  # top 10 most stale
    }


def scan_open_loops() -> dict:
    if not OPEN_LOOPS.exists():
        return {"error": "OPEN_LOOPS.md not found"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOP_WARN_DAYS)
    old_items = []

    with open(OPEN_LOOPS) as f:
        for line in f:
            line = line.strip()
            if not line.startswith("- ") or not line[2:6].isdigit():
                continue
            # Format: - YYYY-MM-DD | Question | ...
            try:
                date_str = line[2:12]
                item_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if item_date < cutoff:
                    old_items.append(line)
            except ValueError:
                continue

    return {"old_items": old_items, "count": len(old_items)}


def format_report(sessions: dict, graph: dict, loops: dict, archive: bool, dry_run: bool) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Janitor Report — {now}\n"]

    # Sessions
    lines.append("## Session Logs")
    if sessions.get("old"):
        if archive and not dry_run:
            moved = sessions.get("archived", [])
            lines.append(f"- Archived {len(moved)} files to AI/sessions/archive/")
            not_moved = [f for f in sessions["old"] if f not in moved]
            if not_moved:
                lines.append(f"- {len(not_moved)} files already in archive (skipped)")
        else:
            lines.append(f"- {len(sessions['old'])} session files older than {ARCHIVE_AFTER_DAYS} days:")
            for name in sessions["old"][:10]:
                lines.append(f"  - {name}")
            if not archive:
                lines.append(f"\n_Run with --archive to move these to AI/sessions/archive/_")
    else:
        lines.append(f"- All session files are recent (< {ARCHIVE_AFTER_DAYS} days)")
    lines.append(f"- {sessions['kept']} files kept in active sessions/\n")

    # Graph staleness
    lines.append("## Knowledge Graph Staleness")
    if "error" in graph:
        lines.append(f"- {graph['error']}")
    else:
        lines.append(f"- Total nodes: {graph['total_nodes']:,}")
        lines.append(f"- Stale nodes (score ≥ {STALENESS_THRESHOLD}): {graph['stale_count']}")
        if graph["stale_nodes"]:
            lines.append("\nTop stale nodes:")
            for node in graph["stale_nodes"]:
                lines.append(f"  - [{node['type']}] {node['name']} — score {node['staleness_score']:.2f}")
        else:
            lines.append("- No stale nodes detected")
    lines.append("")

    # Open loops
    lines.append("## Open Loops")
    if "error" in loops:
        lines.append(f"- {loops['error']}")
    elif loops["count"] == 0:
        lines.append(f"- No loops older than {LOOP_WARN_DAYS} days")
    else:
        lines.append(f"- {loops['count']} loop(s) open for > {LOOP_WARN_DAYS} days — review and resolve:")
        for item in loops["old_items"]:
            lines.append(f"  {item}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Light context janitor — reports stale content")
    parser.add_argument("--archive", action="store_true", help="Move old session files to archive/")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no file operations")
    args = parser.parse_args()

    sessions = scan_sessions(args.archive, args.dry_run)
    graph = scan_graph()
    loops = scan_open_loops()

    report = format_report(sessions, graph, loops, args.archive, args.dry_run)
    print(report)


if __name__ == "__main__":
    main()
