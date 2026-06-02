---
name: ingest
description: Ingest documents into the knowledge graph via entity extraction. Runs ingest.py to extract entities, merge into graph.json, and update ingest_manifest.json.
roles: [all]
integrations: []
slash_command: /ingest
---

# Ingest Skill

## Purpose

Runs the knowledge graph ingest pipeline on one or more vault files.
Calls Claude Haiku to extract entities and relationships, then merges them into `graph/graph.json`.

## When to Invoke

- User says `/ingest path/to/file.md`
- User says "ingest this document", "add to the graph", "process this file"
- After running `research.py` to fetch a URL — ingest the resulting note
- Batch ingest after adding multiple notes to a knowledge directory

## Pre-Flight Checks

1. Verify `graph/graph.json` exists — if not, stop and tell the user to run `python scripts/ingest.py --stats` first
2. Verify `ANTHROPIC_API_KEY` is set in `.env`
3. Confirm the target path exists

## Process

### Single file

```bash
python scripts/ingest.py {path}
```

The script will:
1. Hash check — skip if file hasn't changed since last ingest
2. Show estimated token count and cost
3. Prompt for Y/N if cost exceeds $0.10 (rarely needed for single files)
4. Extract entities chunk by chunk via Haiku
5. Merge into graph.json (create new nodes or update existing)
6. Update ingest_manifest.json
7. Print summary: N created, N updated, N relationships

### Batch ingest (directory)

```bash
python scripts/ingest.py 04-knowledge/technologies/ --batch
```

Shows a batch cost estimate upfront before proceeding.
Use `--yes` to skip all prompts (for automated/cron contexts).

### Force re-ingest (file changed or you want fresh extraction)

```bash
python scripts/ingest.py path/to/file.md --force
```

### Figma file

```bash
python scripts/ingest.py --figma FILE_KEY
python scripts/ingest.py --figma FILE_KEY --save 04-knowledge/technologies/my-diagram.md
```

Accepts a raw file key (e.g. `abc123XYZ`) or a full Figma URL (`figma.com/file/...` or `figma.com/design/...`).

Requires `FIGMA_ACCESS_TOKEN` in `.env` — generate a Personal Access Token at figma.com → Account Settings → Personal access tokens.

Extracts: page names, frame names, component names, text annotations. Produces a markdown note with YAML frontmatter, then runs it through the standard entity extraction pipeline.

Top-level frames are automatically rendered as PNG and described via Claude Haiku vision, injecting `> [Visual: ...]` blocks into the markdown note. Cap is `figma.max_rendered_frames` in `config/config.yaml` (default: 5). Set to `0` to disable rendering (text-only mode).

### Check what's already been ingested

```bash
python scripts/ingest.py --manifest
```

### Check graph node counts by type

```bash
python scripts/ingest.py --stats
```

## After Ingest

Report to the user:
- How many nodes were created vs updated
- Any conflicts detected (type changes on existing nodes)
- Suggest running `--stats` to see the graph state
- If this was a significant domain (>10 new nodes), suggest verifying the top entities look correct

## Integration with research.py

For ingesting web content, the two-step pattern is:

```bash
# Step 1: fetch URL → write markdown note to 04-knowledge/
python scripts/research.py --url {url} --category {category}

# Step 2: extract entities from the note → merge to graph.json
python scripts/ingest.py {resulting_note_path}
```

The /ingest skill can run both steps in sequence when given a URL.
When given a URL, first call `research.py` to create the note, then call `ingest.py` on it.

## Error Handling

- If Haiku returns malformed JSON: the chunk is skipped silently, extraction continues
- If a file can't be read: error is logged to `06-mistakes/error-log.md` via `on-error.sh`
- If `ANTHROPIC_API_KEY` is missing: clear error message with fix instructions
- Conflicts (entity type changed on existing node): printed as warnings, original node preserved

## Gemini Meeting Notes — Summary-Only Default

When ingesting a Google Drive file whose name contains **"Notes by Gemini"** (Google Meet auto-generated notes), the script **strips the raw transcript by default**, keeping only the AI summary, decisions, and next steps sections. This avoids burning 10× the tokens on word-for-word conversation that the summary already captures.

To include the full transcript:
```bash
python scripts/ingest.py --drive FILE_ID --full-transcript
```

This default applies to both `--drive` (single file) and `--drive-folder` (recursive). It does **not** affect Notion pages, local files, or any Drive file that isn't a Gemini notes doc.

## Cost Profile

- Typical vault note (2-5KB): < $0.001
- Large research doc (20KB): ~$0.005
- Full 04-knowledge/ directory (~8 files, ~40KB): ~$0.02
- Figma file (typical, 3-5 pages, 5 frames rendered): ~$0.005–0.01
- Cost gate fires at $0.10/file — essentially never for normal vault notes
