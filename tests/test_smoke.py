"""Smoke tests — prove the harness works (P1-0).

These assert the test infrastructure is wired correctly: scripts import, fixtures
load. They are intentionally minimal; real regression tests arrive with P1-2, P1-5,
P1-6, P2-1, etc.
"""


def test_janitor_imports_and_load_config_runs():
    """scripts/ is on sys.path (via conftest) and a core module runs."""
    import janitor

    cfg = janitor.load_config()
    assert isinstance(cfg, dict)
    for key in ("archive_after_days", "staleness_threshold", "rolling_summary_every"):
        assert key in cfg
    assert isinstance(cfg["archive_after_days"], int)


def test_sample_graph_fixture_is_schema_accurate(sample_graph):
    """The shared graph fixture matches the production graph.json shape."""
    assert set(sample_graph) >= {
        "version", "schema_version", "entity_types", "nodes", "relationships", "metadata"
    }
    # nodes is a dict keyed by id; each node carries the production fields
    assert isinstance(sample_graph["nodes"], dict)
    a_node = next(iter(sample_graph["nodes"].values()))
    assert {"id", "type", "name", "description", "staleness_score"} <= set(a_node)
    # relationships is a list; each edge carries source_id/target_id/type
    assert isinstance(sample_graph["relationships"], list)
    a_rel = sample_graph["relationships"][0]
    assert {"source_id", "target_id", "type"} <= set(a_rel)


def test_sample_graph_file_round_trips(sample_graph_file):
    """The on-disk fixture is valid JSON and loads back."""
    import json

    data = json.loads(sample_graph_file.read_text())
    assert data["metadata"]["total_nodes"] == len(data["nodes"])
