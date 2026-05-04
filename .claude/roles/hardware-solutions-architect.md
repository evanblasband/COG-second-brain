---
role_id: hardware-solutions-architect
display_name: Hardware Solutions Architect
aliases: [hardware architect, solutions architect, hw architect, special projects engineer, hardware solutions, iot architect, connectivity architect]
---

# Role Pack: Hardware Solutions Architect

## Recommended Skills

| Skill | Why it matters for you |
|-------|------------------------|
| `daily-brief` | Surface competitor moves, IoT protocol updates, regulatory changes, and sensing tech developments before standup |
| `auto-research` | Deep research on technology domains — spawn parallel agents across mmWave, BLE, LoRa, HIPAA, market landscape simultaneously |
| `scout` | Evaluate a URL or tool before saving — check vault coverage, assess relevance to current projects |
| `url-dump` | Capture datasheets, whitepapers, vendor docs, and academic papers with auto-extracted key technical specs |
| `braindump` | Capture raw thoughts from hardware sessions, field observations, or architecture sketches — auto-classified by domain |
| `generate-prd` | Produce structured specs, business cases, and architecture docs for C-suite and engineering audiences |
| `knowledge-consolidation` | Build synthesis docs from scattered technology notes — the foundation for tech evaluation deliverables |
| `meeting-transcript` | Process meeting notes into decisions, action items, and people intelligence |
| `weekly-checkin` | Cross-domain pattern analysis — what changed this week in the tech landscape, what decisions need to be made |
| `comprehensive-analysis` | Deep-dive for board prep, major tech evaluations, or architecture reviews |
| `team-brief` | Intelligence brief on team and project activity (activate after day one when integrations are live) |
| `onboarding` | Run once to personalize the COG skill layer |
| `update-cog` | Keep the framework current |
| `update-knowledge-base` | Maintain 04-knowledge/ entries as domains evolve |

## Project Archetypes (from design doc Section 2)

When a new project arrives, classify it immediately — this determines which agents and skills to activate:

| Archetype | Trigger phrase | Primary skills |
|-----------|---------------|----------------|
| Emerging tech evaluation | "evaluate X", "should we use X", "compare X and Y" | `auto-research`, `generate-prd`, `comprehensive-analysis` |
| Connectivity / architecture mapping | "map X system", "trace end-to-end", "failure modes" | `auto-research`, `generate-prd` |
| Monitoring and metrics design | "what should we measure", "dashboard for X" | `generate-prd`, `braindump` |
| Academic / market research | "what does the literature say", "competitive landscape" | `auto-research`, `knowledge-consolidation` |
| Integration scoping | "LOE for X", "timeline for integrating Y" | `auto-research`, `generate-prd` |

## Recommended Integrations (in priority order)

| Integration | Why it matters for you |
|-------------|------------------------|
| Google Calendar | Trigger meeting prep 30 min before any event; surface prep context automatically |
| Gmail | Capture stakeholder threads and technical decisions from email chains |
| GitHub | Track internal hardware firmware repos, integration codebases |
| Slack | Async team intelligence (activate after day one) |
| Foundry | Hardware data, device specs, telemetry as first-class graph entities (activate after access granted) |

## Agent Mode

`solo` — Hardware architects work in focused sessions. Direct interaction is faster than delegated analysis for most tasks. Use worker agents for parallel data collection on large research tasks only.

## Suggested Session Protocol

1. Load: `SOUL.md` → `USER.md` → `MEMORY.md` → `OPEN_LOOPS.md`
2. Check `00-inbox/` for any new files or flagged items
3. Check `01-daily/briefs/` for today's brief — run `/daily-brief` if it doesn't exist
4. Identify today's primary archetype and activate appropriate skills
