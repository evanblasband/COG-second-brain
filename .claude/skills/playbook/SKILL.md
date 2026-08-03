---
name: playbook
description: Generate a first-30-days onboarding playbook — identifies top knowledge gaps from the knowledge graph and people CRM, and maps each gap to the right person to talk to and specific questions to ask.
roles: [hardware-solutions-architect]
integrations: []
---

# Playbook Skill — Job Onboarding Intelligence

## Purpose

Answer the question: *"Given what I know right now, what are my top knowledge gaps and who do I talk to?"*

This skill synthesizes the knowledge graph, people CRM, and role context into a prioritized learning plan for the first 30 days. Run it before starting, then re-run after each significant new intake to see gaps close.

## When to Invoke

- `/playbook` — run at session start in the first 30 days on the job
- User asks "what don't I know yet", "what should I learn first", "who should I meet"
- After a large ingest (new internal docs, org chart, architecture docs)
- Weekly during month one to track gap closure

## Process Flow

### 1. Load Context Sources

Read these in order:
- `USER.md` — role, responsibilities, goals
- `OPEN_LOOPS.md` — already-identified unknowns
- `graph/graph.json` — knowledge graph (entities and confidence scores)
- `02-people/*.md` — people CRM (roles, expertise areas, relationship context)
- `04-knowledge/` — existing domain knowledge coverage

### 2. Assess Knowledge Graph Coverage

Scan graph.json for:
- Entity types with low confidence scores (< 0.7) or `staleness_score` > 0.5
- Entity types with sparse coverage (few nodes relative to their importance for the role)
- Missing entity types entirely (e.g., no `DataStream` nodes, no `BackendService` nodes)

Map coverage against the role's required knowledge domains:
- Sage platform architecture and device portfolio
- Core product/device specifics (sensors, data points, connectivity)
- Connectivity topology and failure modes
- Foundry data platform structure
- Cross-functional team workflows and handoffs
- Regulatory requirements by product line and customer segment
- Manufacturing and supply chain state
- Competitive landscape

### 3. Synthesize Knowledge Gaps

Produce a ranked list of gaps. Rank by:
1. **Day-one impact** — will this gap cause a mistake or missed expectation in week 1?
2. **Blocking dependencies** — does this gap block other work?
3. **Time sensitivity** — will the information change soon, making it harder to learn later?
4. **Confidence** — how uncertain is the current state of this knowledge?

Format each gap:
```
Gap N: [Gap title]
- What's missing: [specific knowledge that doesn't exist or is low-confidence]
- Why it matters: [what decisions or actions this would enable]
- Current confidence: [low / medium / unknown]
- Urgency: [day 1 / week 1 / month 1]
```

### 4. Map Gaps to People

For each gap, scan `02-people/*.md` to find the best person to close it:
- Match gap domain to person's role, scope, and expertise notes
- Check relationship context — prefer people already met vs. cold intros
- Note their working style to frame the conversation correctly

Format each recommendation:
```
Who to talk to: [Name] — [title]
Why: [what they know that closes this gap]
Ask them: [2-3 specific questions, not generic ones]
Approach: [how to frame the conversation given their working style]
```

### 5. Generate Playbook Document

Write to `AI/drafts/playbook-YYYY-MM-DD.md`:

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: playbook
tags: [onboarding, gaps, first-30-days]
status: active
source: agent-generated
---

# First 30 Days — Onboarding Playbook
_Generated: YYYY-MM-DD_

## Knowledge Graph Coverage Summary
- Total entities: N
- High-confidence entities: N (≥0.8)
- Low-confidence entities: N (<0.7)
- Missing domains: [list]

## Top Knowledge Gaps

[Gaps ranked 1–10, each with gap description + recommended person + specific questions]

## Suggested Conversation Cadence

### Week 1 — Must-haves
[List the 2-3 most urgent conversations with who and why]

### Week 2 — Architecture depth
[List conversations that require week-1 context first]

### Week 3–4 — Strategic context
[Longer-horizon conversations: competitive, product direction, growth]

## Open Questions Already Tracked
[Pull from OPEN_LOOPS.md and link to the person who can answer each]

## Gap Closure Tracking
_Re-run `/playbook` after major ingests to see this list shrink._

| Gap | Status | Closed by |
|-----|--------|-----------|
| [Gap 1] | Open | — |
| ... | | |
```

### 6. Output Summary to Chat

After writing the file, output to chat:
- Top 5 gaps (brief, not full detail)
- Top 3 recommended conversations for week 1
- Path to the full document

## Output Location

`AI/drafts/playbook-YYYY-MM-DD.md`

## Confidence Gate

If the knowledge graph has fewer than 50 entities or the people CRM has fewer than 5 enriched profiles (i.e., no real interview/interaction context), flag this:
```
⚠️ Knowledge graph is sparse — playbook will be incomplete.
Run /ingest on any available internal docs first for a richer gap analysis.
Proceeding with what's available...
```
