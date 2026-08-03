#!/usr/bin/env python3
"""normalize_graph_vocab.py — normalize relationship-type strings in the graph.

Fixes the malformed ``owns_by`` relationship type (→ ``owned_by``) and reports any
relationship types outside the canonical extraction enum for human review.

Design (see COG-IMPLEMENTATION-PLAN.md P1-2, audit 2026-07-16 §C4):
  - Auto-remaps ONLY clearly-malformed spelling variants (string-only relabel;
    never changes source_id/target_id or any node data).
  - Semantically-distinct off-enum verbs (owns, used_by, enables, generates, ...)
    are REPORTED, never auto-merged — folding them would change meaning/direction.
  - Idempotent: a second run is a no-op. Never drops relationships, so the total
    relationship count is always preserved.

Usage:
    python scripts/normalize_graph_vocab.py --dry-run     # show the plan, write nothing
    python scripts/normalize_graph_vocab.py --apply       # back up, then rewrite graph.json
    python scripts/normalize_graph_vocab.py --dry-run --graph /path/to/graph.json
"""

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
GRAPH_FILE = VAULT_ROOT / "graph" / "graph.json"

# Canonical relationship enum — MUST stay in sync with the extraction prompt's
# relationship-type list in scripts/ingest.py (SYSTEM_PROMPT_TEMPLATE).
CANONICAL_TYPES = {
    "depends_on", "is_a", "part_of", "competes_with",
    "regulates", "uses", "owned_by", "implements",
}

# Safe, meaning-preserving remaps: malformed spelling variants only. Keys are the
# bad string, values the canonical replacement. Direction (source/target) is never
# touched. Do NOT add semantically-distinct verbs here (owns, used_by, ...) — those
# are reported for human review instead.
REMAP = {
    "owns_by": "owned_by",
}


def normalize_relationships(graph: dict, remap: dict | None = None) -> tuple[dict, dict]:
    """Return ``(new_graph, stats)``. Pure — does not mutate the input graph.

    ``new_graph`` is a shallow copy with a rebuilt ``relationships`` list whose
    types have been remapped per ``remap``. ``stats`` reports before/after type
    counts, how many edges were remapped, and any remaining off-enum types.
    """
    if remap is None:
        remap = REMAP
    rels = graph.get("relationships", [])
    before = Counter(r.get("type") for r in rels)

    new_rels = []
    remapped = 0
    for r in rels:
        r2 = dict(r)
        if r2.get("type") in remap:
            r2["type"] = remap[r2["type"]]
            remapped += 1
        new_rels.append(r2)

    after = Counter(r.get("type") for r in new_rels)
    new_graph = dict(graph)
    new_graph["relationships"] = new_rels

    off_enum = {t: c for t, c in sorted(after.items()) if t not in CANONICAL_TYPES}
    stats = {
        "total_before": len(rels),
        "total_after": len(new_rels),
        "remapped": remapped,
        "before": dict(before),
        "after": dict(after),
        "off_enum_remaining": off_enum,
    }
    return new_graph, stats


def _print_report(stats: dict) -> None:
    print(f"Relationships: {stats['total_before']} before -> {stats['total_after']} after "
          f"({stats['remapped']} remapped)")
    print("\nType counts (before -> after):")
    all_types = sorted(set(stats["before"]) | set(stats["after"]))
    for t in all_types:
        b = stats["before"].get(t, 0)
        a = stats["after"].get(t, 0)
        arrow = "" if b == a else f"   ({b} -> {a})"
        canon = "" if t in CANONICAL_TYPES else "  [off-enum]"
        print(f"  {t:16} {a}{canon}{arrow}")
    if stats["off_enum_remaining"]:
        print("\n⚠️  Off-enum types remaining (reported for human review, NOT auto-merged):")
        for t, c in stats["off_enum_remaining"].items():
            print(f"      {t} ({c})")
        print("  These are semantically-distinct verbs, not misspellings. Fold them only")
        print("  with an explicit, direction-aware decision — or leave them.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    mode.add_argument("--apply", action="store_true", help="back up graph.json, then rewrite it")
    ap.add_argument("--graph", default=str(GRAPH_FILE), help="path to graph.json")
    args = ap.parse_args()

    path = Path(args.graph)
    graph = json.loads(path.read_text())
    new_graph, stats = normalize_relationships(graph)
    _print_report(stats)

    if args.apply:
        if stats["remapped"] == 0:
            print("\nNothing to remap — graph already normalized. No file written.")
            return
        backup = path.with_name(path.name + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(path, backup)
        print(f"\nBackup written: {backup}")
        with open(path, "w") as f:
            json.dump(new_graph, f, indent=2, default=str)
        print(f"Applied: {stats['remapped']} relationship(s) remapped in {path}")
    else:
        print("\n(dry run — no file written; re-run with --apply to persist)")


if __name__ == "__main__":
    main()
