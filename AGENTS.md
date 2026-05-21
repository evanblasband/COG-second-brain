# COG: Agentic Second Brain - Universal Agent Commands

This document defines the available commands/skills for AI agents interacting with COG (Cognition + Obsidian + Git) - a self-evolving agentic second brain system.

**Compatible with:** OpenAI agents, Claude (via this file), and any AI that reads markdown.

> **Note:** Claude Code users should use `.claude/skills/` and Kiro users should use `.kiro/powers/` for native support. This file serves as universal documentation for all other agents.

## Available Commands

### /onboarding

**Description:** Personalize COG for your workflow - creates profile, interests, and watchlist files with a smart, conversational setup.

**Triggers:**
- `/onboarding`
- "onboarding"
- "setup COG"
- "setup my profile"
- "get started"

**Purpose:** Welcome new users and collect essential information to personalize their COG experience through natural conversation - not sequential form-filling. Creates profile documents stored as markdown files within the vault.

**How it works:**
1. Asks ONE open-ended question: "Tell me about yourself - name, role, and what you're interested in"
2. Intelligently parses the response to extract name, role, interests, projects, news sources, and competitive watchlist
3. Only asks a follow-up if required info (name, role, interests) is still missing
4. Asks about agent mode preference (solo vs team) during confirmation
5. Confirms extracted info before creating files
6. Matches role to a role pack (`.claude/roles/*.md`) for personalized skill and integration recommendations
7. Discovers integrations — presents role-specific recommendations, asks which tools the user already uses
8. Creates `00-inbox/MY-PROFILE.md` with role_pack, agent_mode, and preferences
9. Creates `00-inbox/MY-INTERESTS.md` with topics for daily briefs
10. Creates `00-inbox/MY-INTEGRATIONS.md` with active/disabled integrations
11. Optionally creates project structures in `03-projects/` (only if mentioned)
12. Generates a welcome guide with role-ordered skills and integration status

**Agent modes:**
- **Solo** (default): All skills handle everything directly in one conversation
- **Team**: Skills delegate research, analysis, and writing to specialist sub-agents for deeper results (works best with Claude Code)

**Design principle:** Never ask redundant questions. Never show numbered option menus. Infer what you can from context.

**Run this first** if you're new to COG.

---

### /braindump

**Description:** Quick capture of raw thoughts with intelligent domain classification and competitive intelligence extraction.

**Triggers:**
- `/braindump`
- "braindump"
- "brain dump"
- "capture thoughts"
- "write down ideas"
- "get thoughts out of my head"

**Purpose:** Transform raw thoughts into strategic intelligence through quick capture, systematic analysis, pattern recognition, and domain-aware insight extraction with minimal user friction.

**What it does:**
1. Accepts stream-of-consciousness input (any format)
2. Classifies content by domain (personal/professional/project-specific)
3. Extracts themes, questions, decisions, and action items
4. Generates strategic insights and pattern recognition
5. Auto-extracts competitive intelligence if watchlist exists
6. Saves structured output to appropriate domain folder

**Output locations:**
- Work braindumps: `AI/research/braindump-YYYY-MM-DD.md`
- Project: `03-projects/[project-slug]/braindumps/`
- Mixed/uncategorized: `00-inbox/`

---

### /daily-brief

**Description:** Generate personalized news intelligence with verified sources (7-day freshness requirement).

**Triggers:**
- `/daily-brief`
- "daily brief"
- "news"
- "what's happening"
- "morning brief"
- "daily news"

**Purpose:** Find verified, relevant news for personalized daily briefings with strict verification standards and strategic relevance analysis tailored to user's specific interests and projects.

**What it does:**
1. Reads user interests from `00-inbox/MY-INTERESTS.md`
2. Searches for news within last 7 days only
3. Verifies sources with credibility assessment (Tier 1/2/3)
4. Analyzes strategic relevance to user's role and projects
5. Identifies opportunities and threats
6. Generates comprehensive briefing with sources

**Output location:** `01-daily/briefs/daily-brief-YYYY-MM-DD.md`

**Key features:**
- All news must be from last 7 days (mandatory)
- Minimum 2 credible sources per claim
- Confidence levels explicitly stated
- Action items and recommendations included

---

### /weekly-checkin

**Description:** Cross-domain pattern analysis and strategic reflection for weekly review.

**Triggers:**
- `/weekly-checkin`
- "weekly checkin"
- "weekly check-in"
- "weekly review"
- "reflect on my week"
- "week reflection"

**Purpose:** Comprehensive weekly review and analysis integrating insights across all domains (personal, professional, projects) with pattern recognition and strategic planning.

**What it does:**
1. Scans recent braindumps, briefs, and check-ins
2. Guides user through reflection questions
3. Reviews each domain (personal, professional, projects)
4. Identifies patterns across the week
5. Helps set priorities for next week
6. Generates structured check-in document

**Output location:** `01-daily/checkins/weekly-checkin-YYYY-MM-DD.md`

**Covers:**
- Overall week assessment and rating
- Personal wellness and growth
- Professional accomplishments
- Project progress for each active project
- Cross-domain patterns and insights
- Forward planning with priorities

---

### /weekly-summary

**Description:** Automated weekly career log entry — synthesizes everything that happened Mon–Fri from calendar, session notes, decisions, open loops, and people interactions.

**Triggers:**
- `/weekly-summary`
- "weekly summary"
- "write up my week"
- "log this week"

**Purpose:** Generate a factual, data-driven record of the week — who you met, what shipped, what decisions were made, what remains open, and what was learned. Designed for future querying: performance reviews, resume updates, retrospectives, and long-term pattern analysis.

**Distinct from `/weekly-checkin`:** `/weekly-checkin` is interactive and reflective (asks questions). This skill is automated and factual (reads sources and synthesizes without asking questions).

**What it does:**
1. Reads this week's Google Calendar events
2. Scans `AI/sessions/` for session summaries from the week
3. Reviews `05-decisions/` for decisions logged this week
4. Reviews `OPEN_LOOPS.md` for items opened or resolved this week
5. Scans `02-people/` for any profiles updated this week
6. Synthesizes into a structured career log entry

**Output location:** `01-daily/weekly/YYYY-WW.md`

**Auto-triggered:** Also runs automatically every Friday morning when `/daily-plan` is invoked (Step 0.5 in daily-plan).

---

### /knowledge-consolidation

**Description:** Build frameworks from scattered insights across all braindumps and notes.

**Triggers:**
- `/knowledge-consolidation`
- "consolidate knowledge"
- "build frameworks"
- "synthesize insights"
- "extract patterns"

**Purpose:** Transform scattered insights from braindumps, daily briefs, and check-ins into coherent frameworks and "single source of truth" knowledge documents through pattern recognition and systematic synthesis.

**What it does:**
1. Scans vault for unprocessed content (braindumps, briefs, check-ins)
2. Applies pattern recognition (frequency, temporal, domain correlation)
3. Identifies contradictions and cross-cutting patterns
4. Develops actionable frameworks from patterns
5. Updates existing frameworks or creates new ones
6. Generates consolidation report
7. Marks processed braindumps as consolidated

**Output locations:**
- Frameworks: `04-knowledge/consolidated/[framework-name]-framework.md`
- Patterns: `04-knowledge/patterns/pattern-[name].md`
- Reports: `04-knowledge/consolidated/consolidation-YYYY-MM-DD.md`

---

### /url-dump

**Description:** Quick capture URLs with automatic content extraction, insights, and categorization into knowledge booklets.

**Triggers:**
- `/url-dump`
- "url dump"
- "save this link"
- "bookmark this"
- "save for later"
- Pasting a URL

**Purpose:** Transform raw URLs into structured, insightful knowledge entries through intelligent content extraction, categorization, and integration with the user's knowledge base.

**What it does:**
1. Validates and fetches URL content
2. Extracts title, author, date, main content
3. Auto-categorizes (articles, tools, reference, research, etc.)
4. Generates summary and key insights
5. Assesses relevance to user interests/projects
6. Creates structured bookmark file

**Categories:**
- Articles & Blogs
- Tools & Resources
- Reference & Documentation
- Research & Papers
- Inspiration & Design
- Videos & Media
- News & Updates
- Project-Specific

**Output locations:**
- Standard: `04-knowledge/booklets/[category]/[title-slug]-YYYY-MM-DD.md`
- Project-specific: `03-projects/[project-slug]/resources/`
- Unclear: `00-inbox/`

---

### /team-brief

**Description:** Generate a daily team intelligence brief by cross-referencing Linear, Slack, GitHub, PostHog, meetings, and braindumps — then sync the resulting intelligence back into Linear.

**Triggers:**
- `/team-brief`
- "team brief"
- "what did we ship?"
- "daily team update"
- "summarize the team's progress"

**Purpose:** Build an evidence-backed operating brief for product and engineering leads by combining multiple sources of truth, highlighting blockers and momentum, and writing the most important updates back to Linear.

**What it does:**
1. Pulls active initiatives, projects, and issues from Linear
2. Cross-references GitHub PRs, Slack discussions, meetings, PostHog, and braindumps
3. Summarizes shipped work, in-progress work, risks, and signals that matter
4. Writes initiative status updates and issue/project sync-backs into Linear where appropriate
5. Produces a concise brief with a Linear sync report

**Output location:** `AI/drafts/team-brief-{name}-YYYY-MM-DD.md`

---

### /meeting-transcript

**Description:** Process meeting transcripts into structured decisions, action items, and strategic themes.

**Triggers:**
- `/meeting-transcript`
- "process this meeting"
- "analyze this transcript"
- "summarize this meeting"
- "meeting notes from transcript"

**Purpose:** Turn noisy transcripts into clean decision records, action items, and key strategic signals without losing the substance of the conversation.

**What it does:**
1. Cleans transcript noise and identifies speakers/topics
2. Extracts decisions, action items, unresolved questions, and strategic themes
3. Highlights stakeholder concerns, alignment, and follow-up needs
4. Formats the result into a reusable meeting note

**Output location:** `AI/sessions/meeting-YYYY-MM-DD-[slug].md`  
**People CRM:** After processing, ingest the output file to trigger automatic CRM profile updates for identified speakers and attendees.

---

### /comprehensive-analysis

**Description:** Run a deep 7-day product, team, and strategy analysis for weekly reviews, board prep, or planning.

**Triggers:**
- `/comprehensive-analysis`
- "weekly analysis"
- "board prep"
- "comprehensive analysis"
- "deep weekly review"

**Purpose:** Synthesize the last week across product, engineering, customer signals, and strategy into a single high-signal analysis for leaders.

**What it does:**
1. Reviews recent team briefs, meetings, project artifacts, and external signals
2. Identifies what shipped, what changed, what is blocked, and what needs leadership attention
3. Surfaces trends, risks, opportunities, and recommended actions
4. Produces an executive-ready synthesis with confidence levels and open questions

**Output location:** `AI/research/comprehensive-analysis-YYYY-MM-DD.md`

---

### /scout

**Description:** Evaluate URLs and tools — check vault coverage, assess relevance, recommend save or skip.

**Triggers:**
- `/scout`
- "scout this"
- "evaluate this"
- "should I save this?"
- "is this relevant?"

**Purpose:** Lightweight triage that sits between "ignore" and `/url-dump`. Checks existing vault coverage, assesses relevance to your profile and interests, and recommends save or skip.

**What it does:**
1. Accepts URL(s) or tool name(s)
2. Searches the entire vault for existing coverage (duplicates, mentions)
3. If new — fetches content, detects type (tool, article, repo, research, news, reference)
4. Assesses relevance against your profile (projects, role, tech stack) and interests
5. Recommends **Save** (hands off to `/url-dump` with pre-filled category) or **Skip** (explains why)
6. Supports batch mode (multiple URLs in one invocation)

**Boundary with `/url-dump`:** Scout evaluates ("should I save this?"). URL-dump saves ("save this now"). If you already know you want to save, use `/url-dump` directly.

---

### /update-cog

**Description:** Check for and apply upstream COG framework updates without touching personal content.

**Triggers:**
- `/update-cog`
- "update COG"
- "check for updates"
- "get latest COG version"
- "upgrade COG"
- "new COG version"

**Purpose:** Safely update framework files (skills, docs, scripts) from the official upstream repository while leaving all personal content untouched.

**What it does:**
1. Reads `COG-VERSION` to determine current version
2. Adds/fetches the `cog-upstream` remote from the official repo
3. Compares each framework file against upstream
4. Detects customizations and offers per-file keep/overwrite/backup
5. Applies updates via surgical `git checkout` (no merge conflicts)
6. Reports updated files and suggests committing

**Shell script alternative:**
```bash
./cog-update.sh           # Interactive
./cog-update.sh --check   # Check for updates
./cog-update.sh --dry-run # Preview changes
./cog-update.sh --force   # Update all without prompting
```

**Safety:** Content folders (`00-inbox/`, `01-daily/`, `02-people/`, `03-projects/`, `04-knowledge/`, `05-decisions/`, `06-mistakes/`, `07-resources/`, `AI/`, `graph/`) are NEVER touched. Only framework files (skills, docs, scripts) are updated.

---

### /auto-research

**Description:** Deep strategic research engine — decomposes questions into parallel research threads, spawns multiple agents, and synthesizes into actionable strategic analysis.

**Triggers:**
- `/auto-research`
- "research [topic]"
- "investigate [question]"
- "strategic analysis"
- "deep dive into [topic]"

**Purpose:** Take a high-level strategic question, decompose it into 5-7 parallel research threads, investigate each with real web sources, and synthesize findings into an actionable strategic analysis with scenarios and recommendations.

**What it does:**
1. Decomposes the question into independent research threads (market forces, historical precedent, player analysis, technology trajectory, emerging tech, contrarian view, etc.)
2. Presents decomposition for user approval before launching research
3. Spawns parallel research agents (team mode) or runs sequential research passes (solo mode)
4. Each thread searches 8-12 high-quality sources via web search
5. Synthesizes all threads into a unified strategic analysis with scenarios, options, and recommendations
6. Saves to vault with executive summary

**Output location:** `AI/research/YYYY-MM-DD-[slug].md`

**Key features:**
- No hallucinated sources — every claim traces to real web search results
- Emerging tech thread always included — surfaces pre-mainstream concepts
- Contrarian view section challenges consensus
- Confidence levels and gaps explicitly stated

---

### /generate-prd

**Description:** Draft product requirement documents with an approval gate before publishing.

**Triggers:**
- `/generate-prd`
- "generate a PRD"
- "draft PRD"
- "product requirements"

**Purpose:** Generate structured PRDs from problem context, save to vault, and optionally publish to Confluence/Notion with explicit human approval.

**What it does:**
1. Collects problem statement, goals, user context from user
2. Reads existing project context from `03-projects/` and `04-knowledge/`
3. Drafts PRD with standard sections (Problem, Goals, Non-goals, User workflows, Functional requirements, Iterations, Dependencies, Risks, Success metrics)
4. Saves to `AI/drafts/prd-[slug]-YYYY-MM-DD.md`
5. Presents summary and asks for explicit approval before any publishing
6. Only publishes to external systems if user explicitly approves

**Output location:** `AI/drafts/prd-[slug]-YYYY-MM-DD.md`

---

### /decide

**Description:** Log a decision with rationale, alternatives, and confidence level.

**Triggers:**
- `/decide`
- "log this decision"
- "decision record"

**Purpose:** Capture architectural, strategic, or technical decisions the moment they're made. Creates a permanent, searchable record so future sessions understand why choices were made.

**Output location:** `05-decisions/YYYY-MM-DD-{slug}.md`

---

### /cog-backlog

**Description:** Add a feature or improvement idea to the COG second brain backlog.

**Triggers:**
- `/cog-backlog {idea}`
- "add this to the COG backlog"
- "backlog this"
- "save this for the brain later"

**Purpose:** Capture system-level improvement ideas in `COG-BACKLOG.md` without cluttering OPEN_LOOPS.md. Accepts a bare description or a detailed spec; source URLs optional. Inserts at the top of the Active section with today's date.

**Output location:** `COG-BACKLOG.md`

---

### /mistake

**Description:** Log an error or wrong assumption with root cause analysis and a prevention rule.

**Triggers:**
- `/mistake`
- "log this mistake"
- "record this error"

**Purpose:** Capture mistakes immediately after discovery. Extracts root cause and generates a prevention rule. Saved to `06-mistakes/` and surfaced in future sessions.

**Output location:** `06-mistakes/YYYY-MM-DD-{slug}.md`

---

### /eval

**Description:** Structured technology evaluation using a TRL-based framework.

**Triggers:**
- `/eval`
- "evaluate [technology]"
- "compare [option A] vs [option B]"

**Purpose:** Score technology choices across 8 dimensions: maturity, integration complexity, regulatory exposure, vendor stability, LOE estimate, strategic risk, privacy/security fit, cost trajectory. Produces a scored comparison and recommendation.

**Output location:** `AI/evaluations/YYYY-MM-DD-{tech}.md` + entry in `04-knowledge/technologies/`

---

### /ingest

**Description:** Feed a document into the knowledge graph.

**Triggers:**
- `/ingest [path]`
- "ingest this document"
- "add to the graph"

**Purpose:** Extract entities from any document, merge into `graph/graph.json`, and automatically update People CRM profiles if the document is a meeting record.

**Pipeline:** Hash check → entity extraction (Haiku) → graph merge → CRM auto-update (if meeting)  
**Output:** Updates `graph/graph.json` and `graph/ingest_manifest.json`

---

### /prep

**Description:** Pre-meeting briefing for an attendee.

**Triggers:**
- `/prep [person name or meeting title]`
- "prep for meeting with [name]"

**Purpose:** Load the attendee's CRM profile, relationship history, and open items. Generate talking points and a suggested agenda. Run 15–30 minutes before any meeting.

**Input:** `02-people/{name}.md`, `OPEN_LOOPS.md`, Google Calendar  
**Output location:** `AI/drafts/prep-{name}-YYYY-MM-DD.md`

---

### /daily-plan

**Description:** Morning operational planning session.

**Triggers:**
- `/daily-plan`
- "what's my day look like"
- "morning plan"

**Purpose:** Pull today's calendar, look up attendees in the CRM, surface open loops, and produce 3 prioritized actions. Run first thing every working day.

**Input:** Google Calendar (MCP), `OPEN_LOOPS.md`, `02-people/`  
**Output location:** `01-daily/briefs/YYYY-MM-DD.md`

---

### /compress

**Description:** Archive old session logs and clean resolved items from OPEN_LOOPS.md.

**Triggers:**
- `/compress`
- "clean up context"
- "archive old sessions"

**Purpose:** Keep the vault lean. Archives sessions older than 14 days, generates rolling summaries, and prompts review of old open loops. Run weekly (Fridays) or when context feels heavy.

**Output:** Archives to `AI/sessions/archive/`, rolling summaries to `AI/sessions/rolling/`

---

### /playbook

**Description:** First-30-days gap analysis.

**Triggers:**
- `/playbook`
- "what are my knowledge gaps"
- "onboarding gap analysis"

**Purpose:** Read the knowledge graph and people CRM to identify top knowledge gaps and recommend which person to talk to for each. Run on day one, then weekly.

**Input:** `graph/graph.json`, `02-people/`, `OPEN_LOOPS.md`  
**Output location:** `AI/drafts/playbook-YYYY-MM-DD.md`

---

### /update-knowledge-base

**Description:** Maintain product knowledge base from releases, features, and project changes.

**Triggers:**
- `/update-knowledge-base`
- "update knowledge base"
- "update KB"
- "sync knowledge base"

**Purpose:** Keep your knowledge base in `04-knowledge/` current by incorporating new research, feature updates, and project changes.

**What it does:**
1. Reads current knowledge base files from `04-knowledge/`
2. Accepts feature updates and/or new information as input
3. Cross-references with project notes in `03-projects/`
4. Updates knowledge base with factual, thorough changes
5. Optionally syncs to external wiki (Confluence/Notion) with approval

**Output location:** `04-knowledge/consolidated/`

---

## Worker Agents

COG includes 6 specialized worker agents (`.claude/agents/`) that handle data-heavy tasks using Sonnet while the lead session (Opus) handles reasoning and synthesis. Inspired by [garrytan/gstack](https://github.com/garrytan/gstack) specialist sessions and [garrytan/gbrain](https://github.com/garrytan/gbrain) knowledge patterns.

| Agent | What it does | When it's used |
|---|---|---|
| **worker-data-collector** | Structured extraction from GitHub, Slack, Jira, Linear, or files | Team briefs, issue audits, data gathering |
| **worker-researcher** | Web research with source citations and evidence | Auto-research threads, daily brief sourcing |
| **worker-file-ops** | Vault reads/writes, metadata, profile updates | Knowledge consolidation, profile maintenance |
| **worker-executor** | Pre-approved mutations (Jira transitions, Linear updates) | Team brief sync-back, issue management |
| **worker-publisher** | Publishing to Slack, Confluence, Notion, webhooks | Brief publishing, wiki sync |
| **brief-people-updater** | Batch-update people profiles from meetings/briefs | After team briefs, meeting processing |

**Key rule:** Workers write results to `/tmp/{task-slug}.md` and return only a short status + file path. The lead session reads the file for synthesis.

---

## People CRM

COG tracks the people you work with using progressive, evidence-based profiles stored in `02-people/`.

**Profile structure:** Each person has a two-layer file:
1. **Compiled Truth** (top) — current best understanding, updated as evidence changes
2. **Timeline** (bottom) — append-only dated entries with source citations

**Tiered enrichment** — profiles auto-escalate:
- **Tier 3 (Stub):** 1 mention → name, role, one-line context
- **Tier 2 (Moderate):** 3+ mentions → executive snapshot, working style, strengths
- **Tier 1 (Full):** 8+ mentions or direct meeting → complete profile

**Citation format:** Every observation must include:
`[Source: [[path/to/source-note]] | YYYY-MM-DD | confidence: high|medium|low]`

Create profiles manually using the template at `templates/people-profile-template.md`, or ingest a meeting document — `ingest.py` automatically calls `people_updater.py` to create/update profiles when confidence ≥ medium. Run the `brief-people-updater` agent for manual batch updates.

---

## Vault Structure

```
COG-second-brain/
├── .claude/agents/        # Worker agent definitions (6)
├── .claude/roles/         # Role packs for personalized recommendations
├── .claude/skills/        # Skill definitions (23 skills)
├── .claude/hooks/         # Automation hooks (session-start, session-end, etc.)
├── 00-inbox/              # Landing zone, profile files
│   ├── MY-PROFILE.md      # User profile with role pack (created by onboarding)
│   ├── MY-INTERESTS.md    # User interests (created by onboarding)
│   └── MY-INTEGRATIONS.md # Active/disabled integrations (created by onboarding)
├── 01-daily/              # Daily content
│   ├── briefs/            # Daily plan + intelligence briefs
│   └── checkins/          # End-of-day and weekly check-ins
├── 02-people/             # People CRM — one file per person
├── 03-projects/           # Active and archived projects
├── 04-knowledge/          # Domain knowledge, tech evals, research
│   ├── consolidated/      # Frameworks and synthesized reports
│   ├── patterns/          # Identified patterns
│   ├── technologies/      # Tech evals, protocols, architecture notes
│   ├── regulations/       # HIPAA, FCC, state privacy laws
│   ├── competitors/       # Competitive landscape
│   └── booklets/          # URL bookmarks by category
├── 05-decisions/          # Decision log (append-only)
├── 06-mistakes/           # Error log with prevention rules
├── 07-resources/          # User guide, system library, reference docs
├── AI/                    # All agent outputs
│   ├── sessions/          # Session summaries and heartbeat digests
│   │   ├── archive/       # Archived sessions (>14 days, moved by /compress)
│   │   └── rolling/       # Consolidated rolling summaries (every 5 sessions)
│   ├── research/          # Research agent outputs
│   ├── evaluations/       # /eval outputs
│   └── drafts/            # Document drafts
├── graph/                 # Knowledge graph
│   ├── graph.json         # Entity graph
│   ├── ingest_manifest.json
│   └── conflicts.json     # Entity type conflicts flagged for review
├── scripts/               # Python + shell tools
│   ├── ingest.py          # Knowledge graph ingest (+ CRM auto-update)
│   ├── ingest-scan.py     # Scan Drive + Notion for new content to queue
│   ├── people_updater.py  # CRM auto-update from meeting documents
│   ├── generate_people.py # Bulk people profile generation
│   ├── query.py           # Calendar, Gmail, Drive, Slack, GitHub CLI
│   ├── research.py        # Research agent (auto-triggers ingest)
│   ├── heartbeat.py       # Background digest agent
│   ├── janitor.py         # Context janitor + rolling summaries
│   ├── session_summarizer.py # Session summary generator
│   ├── drive_sync.py      # Google Drive folder sync
│   ├── cost_report.py     # Session cost reporting
│   ├── google_auth.py     # Google OAuth helper
│   ├── log_tool_use.py    # Tool use logger (post-tool-use hook)
│   ├── export-vault.sh    # Vault export utility
│   ├── import-vault.sh    # Vault import utility
│   └── tmux-brain.sh      # tmux session launcher for brain sessions
├── templates/             # Document templates (people profile, meeting note, etc.)
├── config/config.yaml     # System configuration (no secrets)
├── .claude/hooks/         # Claude Code automation hooks
│   ├── session-start.sh   # Load context at session open
│   ├── session-end.sh     # Write session summary at session close
│   ├── post-tool-use.sh   # Log tool use after each tool call
│   ├── pre-compact.sh     # Run before context compaction
│   ├── on-ingest.sh       # Trigger after ingest operations
│   └── on-error.sh        # Handle hook errors
└── setup.sh               # One-command machine setup
```

---

## Quick Start

1. **New user?** Run `/onboarding` first to set up your profile
2. **Morning routine?** Run `/daily-plan` first, then `/daily-brief` for news
3. **Before any meeting?** Run `/prep [person or meeting title]`
4. **Process meeting notes?** Use `/meeting-transcript [path]`
5. **Log a decision?** Use `/decide` immediately after making it
6. **Log a mistake?** Use `/mistake` while context is fresh
7. **Ingest a document?** Use `/ingest [path]`
8. **Capture thoughts?** Use `/braindump` anytime
9. **Evaluate a technology?** Use `/eval`
10. **Strategic research?** Use `/auto-research` with your question
11. **Save a link?** Use `/url-dump` with the URL
12. **Build knowledge frameworks?** Run `/knowledge-consolidation`
13. **End of week?** Use `/compress` then `/weekly-checkin`
14. **30-day gap analysis?** Use `/playbook`

---

## Configuration

All configuration is stored as readable markdown files:
- `00-inbox/MY-PROFILE.md` - Profile, role pack, agent mode, and active projects
- `00-inbox/MY-INTERESTS.md` - Topics for news curation
- `00-inbox/MY-INTEGRATIONS.md` - Active/disabled external service integrations
- `04-knowledge/competitors/` - Competitive landscape notes

Edit these files anytime - changes take effect immediately.

### Role Packs

COG matches your role to a role pack during onboarding. Role packs (in `.claude/roles/`) define:
- Which skills are most relevant for your role
- Which integrations to recommend
- Suggested agent mode (solo vs team)

Available packs: `engineer`, `hardware-solutions-architect`. Create custom packs from `_template.md`.

## Version & Updates

COG tracks its version in `COG-VERSION` (currently 3.5.0). To check for updates:
- Run `/update-cog` in any supported agent
- Or use the shell script: `./cog-update.sh --check`
- Validate packaged agent surfaces with `./scripts/validate-agent-surface.sh`

Updates only touch framework files (skills, docs, scripts) — your personal content is never modified.

---

## Task Format

All skills generate tasks with [Obsidian Tasks emoji format](https://publish.obsidian.md/tasks/Reference/Task+Formats/Tasks+Emoji+Format) for dashboard compatibility:

```markdown
- [ ] Action item 📅 YYYY-MM-DD
```

**Date calculation by context:**
- "Immediate (24-48 hours)" → tomorrow's date
- "Short-term (1-2 weeks)" → +1 week from today
- "Today/This Week" → today or end of week
- "Next Steps" → next Monday/Friday

This enables:
- Tasks dashboard queries ("due today", "due this week")
- Daily notes task views
- Date-based filtering and sorting

---

## Philosophy

COG follows these principles:
- **Verification-first:** All information sourced and verified
- **Transparency:** Confidence levels explicitly stated
- **Configuration as knowledge:** Preferences stored as editable notes
- **Self-evolving:** Patterns and frameworks grow over time
- **Low friction:** Quick capture, systematic organization
- **Obsidian Tasks compatible:** All tasks include emoji due dates
