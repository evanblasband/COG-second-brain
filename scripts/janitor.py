#!/usr/bin/env python3
"""
janitor.py — Light context janitor.

Keeps the vault lean by:
  1. Archiving session logs older than archive_after_days (default: 14)
  2. Reporting stale graph nodes (staleness_score > threshold)
  3. Flagging OPEN_LOOPS.md items older than LOOP_WARN_DAYS (default: 14)
  4. Rolling up unsummarized sessions every N files (rolling_summary_every)

Does NOT modify OPEN_LOOPS.md or graph.json autonomously —
prints a report so the user (or Claude) can act on it.

Usage:
    python scripts/janitor.py              # full report
    python scripts/janitor.py --archive    # also move old sessions to archive/
    python scripts/janitor.py --roll       # generate rolling summary if threshold met
    python scripts/janitor.py --dry-run    # report only, no file moves or writes

Cron (Friday at 17:00):
    0 17 * * 5 cd /path/to/vault && .venv/bin/python scripts/janitor.py --archive --roll >> /tmp/janitor.log 2>&1
"""

import argparse
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False

VAULT_ROOT = Path(__file__).parent.parent
SESSIONS_DIR = VAULT_ROOT / "AI" / "sessions"
ROLLING_DIR = SESSIONS_DIR / "rolling"
ARCHIVE_DIR = SESSIONS_DIR / "archive"
GRAPH_FILE = VAULT_ROOT / "graph" / "graph.json"
OPEN_LOOPS = VAULT_ROOT / "OPEN_LOOPS.md"
SUMMARY_MANIFEST = SESSIONS_DIR / ".summary_manifest.json"
CONFIG_FILE = VAULT_ROOT / "config" / "config.yaml"

# Fallback defaults (overridden by config.yaml when present)
_DEFAULTS = {
    "archive_after_days": 14,
    "staleness_threshold": 0.7,
    "rolling_summary_every": 5,
}
LOOP_WARN_DAYS = 14


def load_config() -> dict:
    if not _YAML_OK or not CONFIG_FILE.exists():
        return _DEFAULTS.copy()
    try:
        with open(CONFIG_FILE) as f:
            raw = yaml.safe_load(f) or {}
        janitor = raw.get("context_janitor", {})
        return {
            "archive_after_days": janitor.get("archive_after_days", _DEFAULTS["archive_after_days"]),
            "staleness_threshold": raw.get("knowledge_graph", {}).get(
                "staleness_threshold", _DEFAULTS["staleness_threshold"]
            ),
            "rolling_summary_every": janitor.get("rolling_summary_every", _DEFAULTS["rolling_summary_every"]),
        }
    except Exception:
        return _DEFAULTS.copy()


def _session_files() -> list[Path]:
    """Session markdown files only — exclude precompact, archive subdirs, dotfiles."""
    return sorted(
        f for f in SESSIONS_DIR.glob("*.md")
        if not f.name.startswith(".") and "precompact" not in f.name
    )


# ── Rolling summary manifest ──────────────────────────────────────────────────

def _load_manifest() -> set:
    if not SUMMARY_MANIFEST.exists():
        return set()
    try:
        with open(SUMMARY_MANIFEST) as f:
            return set(json.load(f).get("summarized", []))
    except Exception:
        return set()


def _save_manifest(summarized: set) -> None:
    data = {"summarized": sorted(summarized), "updated": datetime.now().isoformat()}
    with open(SUMMARY_MANIFEST, "w") as f:
        json.dump(data, f, indent=2)


# ── Scan functions ────────────────────────────────────────────────────────────

def scan_sessions(archive: bool, dry_run: bool, archive_after_days: int) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=archive_after_days)
    old_files, kept_files = [], []

    for f in _session_files():
        mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        (old_files if mtime < cutoff else kept_files).append(f)

    archived = []
    if archive and not dry_run and old_files:
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


def scan_graph(staleness_threshold: float) -> dict:
    if not GRAPH_FILE.exists():
        return {"error": "graph.json not found"}

    with open(GRAPH_FILE) as f:
        graph = json.load(f)

    raw_nodes = graph.get("nodes", {})
    nodes = list(raw_nodes.values()) if isinstance(raw_nodes, dict) else raw_nodes
    stale = [
        {"name": n.get("name", n.get("id", "?")), "type": n.get("type", "?"),
         "staleness_score": n.get("staleness_score", 0)}
        for n in nodes if n.get("staleness_score", 0) >= staleness_threshold
    ]
    stale.sort(key=lambda n: n["staleness_score"], reverse=True)

    return {
        "total_nodes": len(nodes),
        "stale_count": len(stale),
        "stale_nodes": stale[:10],
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
            try:
                item_date = datetime.strptime(line[2:12], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if item_date < cutoff:
                    old_items.append(line)
            except ValueError:
                continue

    return {"old_items": old_items, "count": len(old_items)}


def scan_rolling(threshold: int) -> dict:
    summarized = _load_manifest()
    pending = [f for f in _session_files() if f.name not in summarized]
    return {
        "pending_count": len(pending),
        "threshold": threshold,
        "ready": len(pending) >= threshold,
        "pending_files": [f.name for f in pending],
        "_pending_paths": pending,
    }


# ── Rolling summary generation ────────────────────────────────────────────────

def _is_stub(content: str) -> bool:
    """True if the body (after frontmatter) has no real content — only blanks/comments/headings."""
    body = _strip_frontmatter(content)
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith("<!--") and not s.startswith("#"):
            return False
    return True


def _strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        parts = content.split("---", 2)
        return parts[2].strip() if len(parts) >= 3 else content
    return content.strip()


def generate_rolling_summary(pending_paths: list[Path], dry_run: bool) -> str:
    if not pending_paths:
        return "No pending sessions to summarize."

    dates = [f.stem[:10] for f in pending_paths]
    date_from, date_to = min(dates), max(dates)
    out_file = ROLLING_DIR / f"{date_from}-to-{date_to}.md"

    if dry_run:
        return (
            f"[dry-run] Would write {out_file.relative_to(VAULT_ROOT)} "
            f"({len(pending_paths)} sessions, "
            f"{sum(1 for f in pending_paths if _is_stub(f.read_text()))} stubs)"
        )

    ROLLING_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"created: {datetime.now().strftime('%Y-%m-%d')}",
        f"updated: {datetime.now().strftime('%Y-%m-%d')}",
        "type: research",
        "tags: [session, rolling-summary, ai-generated]",
        "status: reference",
        "source: agent-generated",
        "---",
        "",
        f"# Rolling Session Summary — {date_from} to {date_to}",
        f"_Consolidates {len(pending_paths)} sessions. "
        f"Stubs (no content written): "
        f"{sum(1 for f in pending_paths if _is_stub(f.read_text()))}_",
        "",
    ]

    for f in sorted(pending_paths):
        content = f.read_text()
        stub = _is_stub(content)
        body = _strip_frontmatter(content)
        # Drop the first heading — we use the filename as the section header
        body_lines = body.splitlines()
        if body_lines and body_lines[0].startswith("# "):
            body_lines = body_lines[1:]
        body = "\n".join(body_lines).strip()

        lines.append(f"---\n## {f.stem}" + (" _(stub)_" if stub else ""))
        lines.append("")
        if stub:
            lines.append("_No content recorded for this session._")
        else:
            lines.append(body)
        lines.append("")

    out_file.write_text("\n".join(lines))

    summarized = _load_manifest()
    for f in pending_paths:
        summarized.add(f.name)
    _save_manifest(summarized)

    return str(out_file.relative_to(VAULT_ROOT))


# ── Report formatting ─────────────────────────────────────────────────────────

def format_report(sessions: dict, graph: dict, loops: dict, rolling: dict,
                  cfg: dict, archive: bool, dry_run: bool, rolled: str | None) -> str:
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
            lines.append(
                f"- {len(sessions['old'])} session files older than "
                f"{cfg['archive_after_days']} days:"
            )
            for name in sessions["old"][:10]:
                lines.append(f"  - {name}")
            if not archive:
                lines.append("\n_Run with --archive to move these to AI/sessions/archive/_")
    else:
        lines.append(f"- All session files are recent (< {cfg['archive_after_days']} days)")
    lines.append(f"- {sessions['kept']} files kept in active sessions/\n")

    # Rolling summaries
    lines.append("## Rolling Summaries")
    if rolled:
        lines.append(f"- Generated: {rolled}")
    pending = rolling["pending_count"]
    threshold = rolling["threshold"]
    if pending >= threshold:
        lines.append(
            f"- {pending} unsummarized sessions (threshold: {threshold}) — "
            + ("✅ rolled up" if rolled else "run with --roll to consolidate")
        )
    else:
        lines.append(
            f"- {pending}/{threshold} unsummarized sessions — not yet at threshold"
        )
    lines.append("")

    # Graph staleness
    lines.append("## Knowledge Graph Staleness")
    if "error" in graph:
        lines.append(f"- {graph['error']}")
    else:
        lines.append(f"- Total nodes: {graph['total_nodes']:,}")
        lines.append(f"- Stale nodes (score ≥ {cfg['staleness_threshold']}): {graph['stale_count']}")
        if graph["stale_nodes"]:
            lines.append("\nTop stale nodes:")
            for node in graph["stale_nodes"]:
                lines.append(
                    f"  - [{node['type']}] {node['name']} — score {node['staleness_score']:.2f}"
                )
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
        lines.append(
            f"- {loops['count']} loop(s) open for > {LOOP_WARN_DAYS} days — review and resolve:"
        )
        for item in loops["old_items"]:
            lines.append(f"  {item}")
    lines.append("")

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Light context janitor — reports stale content")
    parser.add_argument("--archive", action="store_true", help="Move old session files to archive/")
    parser.add_argument("--roll", action="store_true", help="Generate rolling summary if threshold met")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no file operations")
    args = parser.parse_args()

    cfg = load_config()

    sessions = scan_sessions(args.archive, args.dry_run, cfg["archive_after_days"])
    graph = scan_graph(cfg["staleness_threshold"])
    loops = scan_open_loops()
    rolling = scan_rolling(cfg["rolling_summary_every"])

    rolled = None
    if args.roll and rolling["ready"]:
        rolled = generate_rolling_summary(rolling["_pending_paths"], args.dry_run)

    report = format_report(sessions, graph, loops, rolling, cfg, args.archive, args.dry_run, rolled)
    print(report)


if __name__ == "__main__":
    main()
