"""Shared pytest fixtures for the COG test suite.

Bootstrapped by P1-0 (see COG-IMPLEMENTATION-PLAN.md). Fixtures here are designed
to be reused by later items — P1-2 (graph vocab normalization), P1-6 (backfill
tests), P2-1 (graph query), and P3-1 (dedup) all build on `sample_graph`.

The `scripts/` directory is added to sys.path so tests can `import janitor`,
`import ingest`, etc. — the scripts are standalone modules, not a package.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Make scripts/*.py importable by module name (they are not packaged).
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def repo_root() -> Path:
    """Absolute path to the vault/repo root."""
    return REPO_ROOT


@pytest.fixture
def sample_graph() -> dict:
    """A small, schema-accurate knowledge graph for tests.

    Mirrors the real `graph/graph.json` schema: top-level version/schema_version/
    created/entity_types/nodes(dict keyed by id)/relationships(list)/metadata.
    Node fields and relationship fields match production (see scripts/ingest.py).

    Deliberately seeded for downstream items:
      - `owned_by` (canonical) AND `owns_by` (malformed variant) coexist  -> P1-2
      - a singleton relationship type `provides`                          -> P1-2
      - a near-duplicate Person pair ("Dana O." / "Dana Okafor")
        that share a neighbor (Project Atlas)                             -> P1-6 / P3-1
      - a hub node (Project Atlas) with a known 1-hop / 2-hop neighborhood -> P2-1

    All names/orgs/products below are FICTIONAL placeholders — do not use real
    people, employers, or product codenames in committed fixtures (public repo).
    """
    def node(id_, type_, name, desc):
        return {
            "id": id_, "type": type_, "name": name, "description": desc,
            "attributes": {}, "confidence": "high", "version": 1,
            "sources": [], "last_updated": "2026-01-01", "tags": [],
            "staleness_score": 0.0,
        }

    def rel(id_, src, tgt, type_, desc):
        return {
            "id": id_, "source_id": src, "target_id": tgt, "type": type_,
            "description": desc, "created": "2026-01-01T00:00:00+00:00",
        }

    nodes = {
        "n_p1":   node("n_p1",   "Person",       "Dana Okafor",   "HW engineer"),
        "n_p2":   node("n_p2",   "Person",       "Dana O.",       "HW engineer on Project Atlas"),
        "n_proj": node("n_proj", "Project",      "Project Atlas", "wearable device program"),
        "n_lora": node("n_lora", "Technology",   "LoRa",          "LPWAN protocol"),
        "n_ble":  node("n_ble",  "Technology",   "BLE",           "Bluetooth Low Energy"),
        "n_org":  node("n_org",  "Organization", "Acme Devices",  "hardware company"),
    }

    relationships = [
        rel("r1", "n_p1",   "n_proj", "part_of",  "Dana Okafor works on Project Atlas"),
        rel("r2", "n_p2",   "n_proj", "part_of",  "Dana O. works on Project Atlas"),  # shared neighbor -> dedup signal
        rel("r3", "n_proj", "n_lora", "uses",     "Project Atlas uses LoRa"),
        rel("r4", "n_proj", "n_ble",  "uses",     "Project Atlas uses BLE"),
        rel("r5", "n_proj", "n_org",  "owned_by", "Project Atlas owned by Acme"),      # canonical
        rel("r6", "n_lora", "n_org",  "owns_by",  "malformed variant"),       # P1-2 target
        rel("r7", "n_org",  "n_lora", "provides", "singleton relationship"),   # P1-2 singleton
    ]

    return {
        "version": 1,
        "schema_version": "1.0",
        "created": "2026-01-01",
        "entity_types": ["Person", "Project", "Technology", "Organization"],
        "nodes": nodes,
        "relationships": relationships,
        "metadata": {
            "total_nodes": len(nodes),
            "total_relationships": len(relationships),
            "last_updated": "2026-01-01T00:00:00+00:00",
        },
    }


@pytest.fixture
def sample_graph_file(tmp_path, sample_graph) -> Path:
    """`sample_graph` written to a temp graph.json; returns its Path.

    For code that loads a graph from disk rather than taking a dict.
    """
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(sample_graph, indent=2))
    return p


@pytest.fixture
def sample_config(tmp_path) -> Path:
    """A minimal config.yaml written to a temp dir; returns its Path.

    Mirrors the blocks tests care about (kb_maintenance.staleness_threshold,
    context_janitor.*). Extend as later items need more keys.
    """
    content = (
        "kb_maintenance:\n"
        "  staleness_threshold: 0.7\n"
        "context_janitor:\n"
        "  archive_after_days: 14\n"
        "  rolling_summary_every: 5\n"
    )
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p
