# People CRM — Knowledge Base

This directory contains structured profiles for people you work with. Each profile tracks observations, working patterns, and collaboration notes — built progressively from meetings, Slack, PRs, and daily interactions.

## Design Principles

- **Neutral & Professional** — content you'd share with the person themselves
- **Observation-based** — only what's evidenced by actual work, messages, contributions
- **Progressive** — don't fill everything at once; details emerge naturally over time
- **No gossip or judgment** — focus on working patterns and collaboration effectiveness
- **Append-only timeline** — history is never rewritten, only added to

## File Naming

`<firstname>-<lastname>.md` (lowercase, hyphenated)

Examples: `jane-doe.md`, `vu-lam.md`, `alex-martins.md`

## Profile Structure

Each profile has two layers:

### 1. Compiled Truth (Current State)
The top section reflects the current best understanding. Updated when new evidence changes the picture.

- **Executive Snapshot** — 2-3 high-confidence bullet points
- **Role & Responsibilities** — what they own/scope
- **Working Style** — communication and collaboration patterns
- **Strengths** — observed strengths tied to evidence
- **Collaboration Notes** — how to work effectively with this person
- **Open Threads** — unresolved questions or uncertain claims

### 2. Timeline (Append-Only History)
Reverse-chronological dated entries. Never deleted, only appended.

Each entry includes:
- What happened or was observed
- Source citation: `[Source: [[path/to/source-note]] | YYYY-MM-DD | confidence: high|medium|low]`

## Tiered Enrichment

Profiles auto-escalate based on interaction density (inspired by [garrytan/gbrain](https://github.com/garrytan/gbrain)):

| Tier | Trigger | What gets created |
|------|---------|-------------------|
| **Tier 3 — Stub** | 1 mention in a meeting or brief | Name, role, one-line context |
| **Tier 2 — Moderate** | 3+ cross-source mentions | Executive snapshot, working style, strengths |
| **Tier 1 — Full** | Direct meeting or 8+ mentions | Complete profile with all sections filled |

Don't force a full profile on first encounter. Let it build naturally.

## Creating New Profiles

Use the template at `06-templates/people-profile-template.md` or run the `brief-people-updater` agent.

## Automated Updates

The `brief-people-updater` agent (`.claude/agents/brief-people-updater.md`) can batch-update profiles from:
- Meeting transcripts
- Team brief data
- Slack observations
- PR activity

It follows the same rules: append-only, evidence-based, no judgments.

## Citation Format

Every factual claim must include a source:

```
[Source: [[04-projects/true-platform/meetings/2026-04-01-standup]] | 2026-04-01 | confidence: high]
```

Confidence levels:
- **high** — direct observation, explicit statement, or official announcement
- **medium** — inferred from patterns across multiple interactions
- **low** — single data point or secondhand information
