"""Regression tests for scripts/normalize_graph_vocab.py (P1-2).

Invariants under test (against the shared `sample_graph` fixture, which is seeded
with owned_by=1, owns_by=1, and a `provides` singleton):
  (a) owns_by -> owned_by remap is correct
  (b) idempotent — running twice equals running once
  (c) total relationship count preserved (never drops edges)
  (d) output round-trips through JSON
  plus: report-only for off-enum types, and no mutation of the input graph.
"""

from collections import Counter

import normalize_graph_vocab as ngv


def _types(graph):
    return Counter(r["type"] for r in graph["relationships"])


def test_owns_by_remapped_to_owned_by(sample_graph):
    before = _types(sample_graph)
    assert before["owns_by"] == 1 and before["owned_by"] == 1  # fixture precondition

    new_graph, stats = ngv.normalize_relationships(sample_graph)
    after = _types(new_graph)

    assert after["owns_by"] == 0
    assert after["owned_by"] == 2          # 1 original + 1 remapped
    assert stats["remapped"] == 1


def test_total_count_preserved(sample_graph):
    n_before = len(sample_graph["relationships"])
    new_graph, stats = ngv.normalize_relationships(sample_graph)
    assert len(new_graph["relationships"]) == n_before
    assert stats["total_before"] == stats["total_after"] == n_before


def test_idempotent(sample_graph):
    once, _ = ngv.normalize_relationships(sample_graph)
    twice, stats2 = ngv.normalize_relationships(once)
    assert _types(once) == _types(twice)   # second pass changes nothing
    assert stats2["remapped"] == 0


def test_does_not_mutate_input(sample_graph):
    before = _types(sample_graph)
    ngv.normalize_relationships(sample_graph)
    assert _types(sample_graph) == before  # input untouched (pure function)


def test_off_enum_reported_not_removed(sample_graph):
    new_graph, stats = ngv.normalize_relationships(sample_graph)
    # `provides` is a genuine off-enum singleton — reported, but NOT dropped.
    assert "provides" in stats["off_enum_remaining"]
    assert _types(new_graph)["provides"] == 1
    # owns_by was remapped away, so it must NOT appear as off-enum.
    assert "owns_by" not in stats["off_enum_remaining"]


def test_json_round_trips(sample_graph):
    import json
    new_graph, _ = ngv.normalize_relationships(sample_graph)
    reloaded = json.loads(json.dumps(new_graph, default=str))
    assert reloaded["metadata"]["total_nodes"] == len(reloaded["nodes"])
    assert len(reloaded["relationships"]) == len(new_graph["relationships"])
