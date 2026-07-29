# COG Test Suite

Targeted regression tests for COG's scripts and skills. Bootstrapped by **P1-0** in
`COG-IMPLEMENTATION-PLAN.md`.

## Run

```bash
.venv/bin/pytest -q            # whole suite
.venv/bin/pytest tests/test_smoke.py -q   # one file
```

Install the (dev-only) test dependency first if needed:

```bash
.venv/bin/pip install -r requirements-dev.txt
```

## Conventions

- **Scripts import by module name.** `tests/conftest.py` puts `scripts/` on `sys.path`,
  so tests do `import janitor`, `import ingest`, etc. (the scripts are standalone
  modules, not a package).
- **No network / external APIs.** Tests must not hit Anthropic, Google, Slack, etc.
  Mock those calls. `pytest.ini` documents this.
- **Shared fixtures** live in `conftest.py`:
  - `sample_graph` — a small, schema-accurate knowledge graph (nodes dict + relationships
    list matching `graph/graph.json`). Seeded with an `owns_by`/`owned_by` pair, a
    singleton relationship type, a near-duplicate Person pair, and a hub node — so
    P1-2 / P1-6 / P2-1 / P3-1 can all reuse it.
  - `sample_graph_file` — the same graph written to a temp `graph.json` (for code that
    loads from disk).
  - `sample_config` — a minimal temp `config.yaml`.
  - `repo_root` — absolute repo path.

## Policy (per COG-IMPLEMENTATION-PLAN.md)

New code items add their tests **in the same branch**, passing before the item is
marked `READY`. Docs/config-only items are verification-only (no committed test).
