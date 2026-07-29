# Second Brain — Session Protocol

**Role:** Hardware Solutions Architect / Special Projects Engineer  
**System:** AI second brain built on COG-second-brain fork  
**Primary interface:** Claude Code CLI

---

## Session Start Protocol

At the start of every session, load these files in order:
1. `SOUL.md` — agent personality and values
2. `USER.md` — User profile, accounts, domain depths, working style
3. `MEMORY.md` — key decisions, active projects, patterns, lessons
4. `OPEN_LOOPS.md` — unresolved questions, waiting-fors, incomplete tasks

If the user runs `/daily-plan`, also load today's note from `01-daily/` if it exists.

---

## Session End Protocol

Before closing any substantive session:
1. Update `MEMORY.md` with any new decisions, patterns, or lessons
2. Clear resolved items from `OPEN_LOOPS.md` (move to `05-decisions/` or `06-mistakes/`)
3. Write a session summary to `AI/sessions/YYYY-MM-DD-HH.md`

---

## Vault Structure

```
vault/
├── SOUL.md              ← Agent personality, values, operating style
├── USER.md              ← User profile, accounts, domain depths
├── MEMORY.md            ← Cross-session key learnings (append-only)
├── OPEN_LOOPS.md        ← Unresolved items (loaded every session)
├── CLAUDE.md            ← This file — session protocol
│
├── 00-inbox/            ← Uncategorized input; agent checks here first
│   ├── MY-PROFILE.md    ← COG user profile (role pack, agent mode)
│   ├── MY-INTERESTS.md  ← Topics for daily briefs
│   └── MY-INTEGRATIONS.md ← Active/disabled integrations
│
├── 01-daily/            ← Daily notes
│   ├── briefs/          ← Morning brief outputs (YYYY-MM-DD.md)
│   ├── checkins/        ← End-of-day logs (YYYY-MM-DD.md)
│   └── weekly/          ← Weekly career log entries (YYYY-WW.md) — future career-log query target
│
├── 02-people/           ← People CRM — one file per person
├── 03-projects/         ← Active and archived projects
│
├── 04-knowledge/        ← Domain knowledge, tech evals, research
│   ├── regulations/     ← HIPAA, FCC, state privacy laws
│   ├── technologies/    ← IoT protocols, sensing tech, edge computing
│   ├── competitors/     ← Senior living tech competitive landscape
│   ├── consolidated/    ← Synthesized frameworks
│   ├── patterns/        ← Identified patterns
│   └── booklets/        ← URL bookmarks by category
│
├── 05-decisions/        ← All decisions with rationale (append-only)
├── 06-mistakes/         ← Error log with prevention rules
├── 07-resources/        ← Tools, scripts, reference docs
│
├── AI/                  ← Agent output folder
│   ├── sessions/        ← YYYY-MM-DD-HH.md per session summary
│   ├── research/        ← Research agent outputs
│   ├── evaluations/     ← Tech eval outputs
│   └── drafts/          ← Document drafts
│
└── templates/           ← Templater templates for all note types
```

---

## Model Routing — Always Apply

| Task type | Model | Agent |
|-----------|-------|-------|
| Data collection, file reads, web fetch | Sonnet | `worker-data-collector` |
| Web research, URL extraction | Sonnet | `worker-researcher` |
| File operations (vault reads/writes) | Sonnet | `worker-file-ops` |
| Pre-approved API calls, mutations | Sonnet | `worker-executor` |
| People profile updates | Sonnet | `brief-people-updater` |
| Publishing (Slack, Confluence, Notion, webhooks) | Sonnet | `worker-publisher` |
| Requirements → epics & stories breakdown | Sonnet | `system-analyst` |
| Reasoning, synthesis, writing | Opus | Lead session (no delegation) |
| Strategic decisions, editorial judgment | Opus | Lead session (no delegation) |

**Rule:** Delegate collection and file ops to Sonnet workers. Lead session handles thinking and writing only.

### Worker Output Rule

Workers write results to a file and return only a short status + path. Never return large text inline.

| Output size | Action |
|------------|--------|
| < 2K tokens | Return inline |
| ≥ 2K tokens | Write to `/tmp/{task-slug}.md`, return path only |

---

## Testing

COG has a pytest suite in `tests/`. Run it with `.venv/bin/pytest -q` (dev dep in `requirements-dev.txt`). Scripts are importable by module name inside tests (`conftest.py` adds `scripts/` to `sys.path`); shared fixtures (`sample_graph`, `sample_graph_file`, `sample_config`) live in `tests/conftest.py`. Tests must not hit the network — mock external APIs. Code changes with real invariants ship with tests in the same change; see `tests/README.md`.

---

## Brain-First Knowledge Protocol

Before answering any question about people, projects, strategy, decisions, or domain context:
1. Read relevant notes from `04-knowledge/` first
2. Check `02-people/{name}.md` for people questions
3. Check `03-projects/{project}/` for project questions
4. Only then synthesize

If the user corrects a factual statement, update the relevant knowledge note immediately.

### Citation rule
In durable notes (`04-knowledge/**`, people profiles, consolidated docs):
`[Source: [[path/to/note]] | YYYY-MM-DD | confidence: high|medium|low]`

---

## Integration Preferences

Check `00-inbox/MY-INTEGRATIONS.md` before using any external integration:
- **Active**: use normally
- **Disabled**: skip silently, do not suggest setup
- **Unknown**: ask the user; if they decline, add to Disabled

Current integrations: GitHub (active), Google Calendar (active), Gmail (active), Google Drive (active), Slack (active)

---

## Agent Roster

See `AGENTS.md` for full worker agent specifications.

**Core workers (7):** `worker-data-collector`, `worker-researcher`, `worker-file-ops`, `worker-executor`, `worker-publisher`, `brief-people-updater`, `system-analyst`

**Skills (25):** `auto-research`, `braindump`, `cog-backlog`, `comprehensive-analysis`, `compress`, `daily-brief`, `daily-plan`, `decide`, `eval`, `generate-prd`, `ingest`, `knowledge-consolidation`, `meeting-transcript`, `mistake`, `onboarding`, `playbook`, `prep`, `scout`, `system-analyst`, `team-brief`, `update-cog`, `update-knowledge-base`, `url-dump`, `weekly-checkin`, `weekly-summary`

---

## Human-in-the-Loop Checkpoints

Pause and confirm before:
- Sending any external communication (email, Slack, calendar invite)
- Making any API call that writes data to external systems
- Deleting any file (prefer archiving)
- Executing any shell command with side effects on shared systems

### Git rules — strict

- **Never commit.** Staging (`git add`) is allowed; `git commit` is not. The user reviews staged changes and commits manually.
- **Never push** to any branch unless the user explicitly says "push this."
- **Never force-push, reset, or rebase** under any circumstances without explicit instruction.
- If you have changes ready to commit, stage them, then tell the user what was staged and why.

---

## Cost Budgeting

- Prefer Sonnet for data collection and file operations
- Only escalate to Opus for synthesis, reasoning, and writing tasks
- For research tasks: cap web fetches at 10 sources unless the user explicitly asks for more
- Avoid spawning multiple Opus agents in parallel — sequential is fine for most tasks

---

## YAML Frontmatter Standard

Every note in the vault uses:

```yaml
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: [project, hardware, active]
status: active | archived | reference | draft
project: project-name
type: decision | research | meeting | evaluation | people | knowledge
related: [[Note A]], [[Note B]]
people_involved: [name1, name2]
tech_stack: [LoRa, BLE, mmWave]
confidence: high | medium | low
source: internal | external | agent-generated
---
```
