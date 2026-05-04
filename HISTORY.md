# Project History — Second Brain

Tracks structural and architectural changes to this system: vault organization, tooling, integrations, agents, skills, configuration. Does not track content changes (notes, knowledge entries, people profiles, daily logs).

Append new entries at the top. Each entry gets a date and a clear description of what changed and why.

---

## 2026-05-04 — Day 2 (follow-up): PII removal and content gitignore

**Trigger:** Fork cannot be made private; all personal content must be excluded from git.

### Gitignore expanded

Added to `.gitignore`:
- Identity files at vault root: `SOUL.md`, `USER.md`, `MEMORY.md`, `OPEN_LOOPS.md`
- All 00-inbox personal config files: `MY-PROFILE.md`, `MY-INTERESTS.md`, `MY-INTEGRATIONS.md`
- All vault content directories: `01-daily/`, `02-people/`, `03-projects/`, `04-knowledge/` content, `05-decisions/`, `06-mistakes/`, `07-resources/`, `AI/` outputs
- Framework files (skills, agents, hooks, templates, CLAUDE.md, settings.json) remain committed

### Files sanitized (PII removed)

| File | What was removed |
|------|-----------------|
| `.env.example` | Real email addresses and GitHub username replaced with empty placeholders |
| `CLAUDE.md` | Company name removed from header; "Evan's" → "User's" in comments |
| `setup.sh` | Hardcoded emails replaced with .env variable references |
| `templates/meeting-note.md` | Real name replaced with `{{your-name}}` placeholder |
| `HISTORY.md` | GitHub username removed from fork URL and clone instruction |

### New: `templates/identity/` directory

Committed sanitized starter templates so `setup.sh` can create identity files on any new machine. Files are NOT personal — they are blank-slate frameworks:

| Template | Creates |
|----------|---------|
| `SOUL.template.md` | `SOUL.md` |
| `USER.template.md` | `USER.md` |
| `MEMORY.template.md` | `MEMORY.md` |
| `OPEN_LOOPS.template.md` | `OPEN_LOOPS.md` |
| `MY-PROFILE.template.md` | `00-inbox/MY-PROFILE.md` |
| `MY-INTERESTS.template.md` | `00-inbox/MY-INTERESTS.md` |
| `MY-INTEGRATIONS.template.md` | `00-inbox/MY-INTEGRATIONS.md` |

`setup.sh` now checks for each identity file and copies from template if missing. User fills in personal details locally — never pushed.

### Git history wiped

All prior commits contained PII. Replaced with a single clean orphan commit so no PII exists anywhere in git history.

---

## 2026-05-04 — Day 2: Role configuration and session hooks

### 00-inbox config files added

| File | Purpose |
|------|---------|
| `00-inbox/MY-PROFILE.md` | Evan's COG profile — role pack pointer, agent mode, active projects |
| `00-inbox/MY-INTERESTS.md` | Topic priorities for `/daily-brief` — 6 primary domains, 4 secondary |
| `00-inbox/MY-INTEGRATIONS.md` | Integration registry — active (GitHub), pending (Google Calendar/Gmail), disabled (Slack, Foundry, etc.) |

### Role pack added

| File | Notes |
|------|-------|
| `.claude/roles/hardware-solutions-architect.md` | Custom role pack for this specific job; includes project archetype classification table and integration priority order |

### Hooks wired

New directory: `.claude/hooks/`

| Hook script | Trigger | What it does |
|-------------|---------|--------------|
| `session-start.sh` | `UserPromptSubmit` | Prints core files to load, daily brief status, inbox check, overdue open-loops count |
| `session-end.sh` | `Stop` | Creates stub session summary in `AI/sessions/YYYY-MM-DD-HH.md` if none exists |
| `pre-compact.sh` | `PreCompact` | Writes state snapshot to `AI/sessions/YYYY-MM-DD-HH-MM-precompact.md` before context resets |
| `post-tool-use.sh` | `PostToolUse` | Appends JSONL tool log to `AI/sessions/YYYY-MM-DD-tool-log.jsonl` |

### Settings file added

| File | Notes |
|------|-------|
| `.claude/settings.json` | Registers all 4 hooks with Claude Code; uses relative paths for portability |

---

## 2026-05-04 — Day 1: Initial setup

### Source
Forked `huytieu/COG-second-brain` → personal fork  
Cloned to local staging machine at: `claude_examples/second-brain/COG-second-brain/`

**Why COG:** 17 skills, 6 worker agents, validate script — fastest path to a working system before day one at new role.

### Stripped from COG base
| Removed | Reason |
|---------|--------|
| `.gemini/` | Gemini CLI extension — not used |
| `.kiro/` | Kiro IDE extension — not used |
| `.cursor-plugin/`, `.cursorrules` | Cursor IDE extension — not used |
| `.claude-plugin/` | Claude marketplace plugin wrapper — not needed for personal fork |
| `GEMINI.md` | Gemini-specific doc |
| Roles: `designer`, `engineering-lead`, `founder`, `marketer`, `product-manager` | Not relevant to Hardware Solutions Architect role |
| Skills: `create-user-story`, `export-open-issues`, `generate-release-notes`, `publish-to-confluence` | PM/software-team specific — not relevant |

### Vault directory restructure
Renamed and reorganized COG's default folder structure to match design doc (Section 4):

| Before (COG default) | After | Notes |
|----------------------|-------|-------|
| `02-personal/` | `02-people/` | CRM — one file per person |
| `03-professional/` | *(removed)* | Merged into project structure |
| `04-projects/` | `03-projects/` | Renumbered |
| `05-knowledge/` | `04-knowledge/` | Renumbered; people subfolder moved to `02-people/` |
| `06-templates/` | `templates/` | Removed numbering prefix |
| *(new)* | `04-knowledge/regulations/` | HIPAA, FCC, state privacy |
| *(new)* | `04-knowledge/technologies/` | IoT protocols, sensing, edge |
| *(new)* | `04-knowledge/competitors/` | Senior living tech landscape |
| *(new)* | `05-decisions/` | Append-only decisions log |
| *(new)* | `06-mistakes/` | Error log + prevention rules |
| *(new)* | `07-resources/` | Tools, scripts, reference docs |
| *(new)* | `AI/sessions/` | Per-session summaries |
| *(new)* | `AI/research/` | Research agent outputs |
| *(new)* | `AI/evaluations/` | Tech eval outputs |
| *(new)* | `AI/drafts/` | Document drafts |

### Files added
| File | Purpose |
|------|---------|
| `SOUL.md` | Agent personality, values, operating style |
| `USER.md` | Evan's profile, role, domain depths, working style |
| `MEMORY.md` | Cross-session key learnings (append-only) |
| `OPEN_LOOPS.md` | Unresolved questions and waiting-fors (loaded every session) |
| `HISTORY.md` | This file |
| `templates/daily-note.md` | Templater template for daily notes |
| `templates/person.md` | Templater template for people CRM entries |
| `templates/project-brief.md` | Templater template for project briefs |
| `templates/meeting-note.md` | Templater template for meeting notes |
| `setup.sh` | Idempotent new-machine installer |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for secrets and config vars |

### Files modified
| File | Change |
|------|--------|
| `CLAUDE.md` | Rewritten for Hardware Solutions Architect context; preserved COG model routing, worker output rule, and brain-first knowledge protocol |
| `.gitignore` | Added: `.env`, `.auth/`, `.venv/`, `__pycache__/`, `*.pyc` |

### Remaining skills (14 of original 17)
`auto-research`, `braindump`, `comprehensive-analysis`, `daily-brief`, `generate-prd`, `knowledge-consolidation`, `meeting-transcript`, `onboarding`, `scout`, `team-brief`, `update-cog`, `update-knowledge-base`, `url-dump`, `weekly-checkin`

### Remaining agents (6 — all kept)
`worker-data-collector`, `worker-researcher`, `worker-file-ops`, `worker-executor`, `worker-publisher`, `brief-people-updater`

### Tooling installed on staging machine
| Tool | Version | Install method |
|------|---------|---------------|
| `gh` CLI | 2.71.0 | Binary to `~/bin/` (no sudo) |

### Deployment target
This setup is on a **staging machine only**. On the new work machine: `git clone <your-fork-url> && bash setup.sh`
