---
name: eval
description: Run a structured technology evaluation using TRL scoring (1-9) and 8 evaluation dimensions. Produces a scored comparison table and recommendation. Invoke before any significant technology adoption decision.
roles: [all]
integrations: []
slash_command: /eval
---

# Eval Skill

## Purpose

Apply a consistent, repeatable framework before adopting any technology. Prevents gut-feel decisions by forcing explicit scoring on maturity, complexity, regulatory exposure, and strategic fit. Produces a durable record in `04-knowledge/technologies/` that future sessions can load as prior art.

## When to Invoke

- User says `/eval {technology name}` or `/eval {Tech A} vs {Tech B}`
- User says "evaluate this", "score this tech", "help me decide between X and Y"
- Before recommending a technology in a proposal or PRD
- After scouting a new tool and finding it worth deeper analysis (after `/scout`)

## Pre-Flight

Run `date '+%Y-%m-%d'` to get today's date.

## Process

### 1. Clarify scope

If the technology or comparison is ambiguous, ask ONE question:

> "What's the use-case context? (e.g., 'real-time fall detection at the edge' or 'replacing our current BLE stack')"

Do not proceed until the use-case is clear — scores are meaningless without it.

### 2. Load prior knowledge

Before scoring, read:
- `04-knowledge/technologies/` — any existing eval or note on this technology
- `04-knowledge/regulations/` — if regulatory exposure is likely
- `04-knowledge/competitors/` — if vendor stability is in question
- `graph/graph.json` (nodes section) — check if this tech is already a node with relationships

Surface any prior findings to avoid re-research. Note the date of prior evals — technology landscape changes fast.

### 3. Research gaps (if needed)

If the vault has no coverage of a technology:
- Use `worker-researcher` to fetch 3-5 sources
- Cap at 5 web fetches unless user says otherwise
- Look for: official docs, GitHub activity, production case studies, known failure modes

### 4. Score each dimension

Score on a 1-9 scale. Use half-points only if genuinely ambiguous (e.g., 5.5).

**Confidence check:** Before scoring each dimension, ask: "Do I have enough information to score this with ≥70% confidence?"
- If yes: score it
- If no: mark it `?` and list what's missing. **Do not guess.**

After scoring all 8 dimensions, if more than 2 are marked `?`: stop, surface the gaps to the user, and ask whether to proceed with caveats or do additional research first.

#### The 8 Dimensions

| # | Dimension | What it measures | Low (1-3) | Mid (4-6) | High (7-9) |
|---|-----------|-----------------|-----------|-----------|------------|
| 1 | **Maturity (TRL)** | Technology Readiness Level | Lab/prototype (TRL 1-4) | Pilot/early production (TRL 5-7) | Proven at scale (TRL 8-9) |
| 2 | **Integration Complexity** | Effort to wire into existing stack | Deep rework, no SDK, custom protocol | Moderate: SDK exists, some custom work | Drop-in: REST/standard, existing patterns |
| 3 | **Regulatory Exposure** | HIPAA, FCC, state law risk surface | High exposure, unresolved compliance questions | Some exposure, known mitigation path | Low/no exposure, or fully resolved |
| 4 | **Vendor Stability** | Risk of vendor failure or lock-in | Single source, early-stage company | Mid-market or open-source with active community | Tier-1 vendor or fully open-source, multiple sources |
| 5 | **LOE Estimate** | Engineer-weeks to implement to production | >8 weeks | 3-8 weeks | <3 weeks |
| 6 | **Strategic Risk** | Risk of wrong bet (hard to unwind) | Long-term lock-in, no exit path | Moderate coupling, exit path exists but costly | Low coupling, easy to swap out |
| 7 | **Privacy / Security Fit** | Data residency, encryption, access control | Major gaps, PHI exposure risk | Acceptable with additional controls | Strong defaults, meets PHI/HIPAA bar out of box |
| 8 | **Cost Trajectory** | 3-year TCO direction | Escalating or unpredictable | Stable, known licensing model | Declining or fixed (open-source, one-time) |

**TRL Reference (for Dimension 1):**
- TRL 1-2: Basic principles observed, concept formulated
- TRL 3-4: Proof of concept, lab validation
- TRL 5-6: Prototype validated in relevant environment
- TRL 7: System prototype demonstrated in operational environment
- TRL 8: System complete and qualified
- TRL 9: Actual system proven in operational environment

### 5. Compute composite score

```
Composite = (sum of 8 dimension scores) / 8
```

Apply weights only if the user specifies a use-case that makes certain dimensions critical (e.g., "this is PHI-adjacent" → weight Regulatory Exposure ×1.5 and Privacy/Security ×1.5, then renormalize).

**Score interpretation:**
- 7.0-9.0: Recommend adoption — proceed to POC
- 5.0-6.9: Conditional — identify the lowest-scoring dimension as the blocking risk
- 3.0-4.9: Do not recommend — surface what would need to change to reconsider
- <3.0: Reject — document why for future reference

### 6. Generate the eval document

Write to `AI/evaluations/eval-YYYY-MM-DD-{slug}.md` AND `04-knowledge/technologies/{slug}.md` (overwrite if exists):

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: evaluation
tags: [eval, technology, {slug}]
status: active
source: agent-generated
confidence: high | medium | low
tech_stack: [{technology names}]
---

# Technology Evaluation: {Technology Name(s)}

**Date:** YYYY-MM-DD  
**Use case:** {The specific use-case context provided}  
**Evaluator:** Claude (agent-generated) — reviewed by owner

---

## Summary

**Recommendation:** {Adopt | Conditional — resolve {dimension} first | Do not adopt | Reject}  
**Composite score:** {X.X} / 9.0  
**Confidence:** {high | medium | low}

{2-3 sentence executive summary of the finding}

---

## Scoring

| Dimension | Score | Notes |
|-----------|-------|-------|
| 1. Maturity (TRL) | {X}/9 | TRL {N}: {brief justification} |
| 2. Integration Complexity | {X}/9 | {brief justification} |
| 3. Regulatory Exposure | {X}/9 | {brief justification} |
| 4. Vendor Stability | {X}/9 | {brief justification} |
| 5. LOE Estimate | {X}/9 | ~{N} weeks, {brief justification} |
| 6. Strategic Risk | {X}/9 | {brief justification} |
| 7. Privacy / Security Fit | {X}/9 | {brief justification} |
| 8. Cost Trajectory | {X}/9 | {brief justification} |
| **Composite** | **{X.X}/9** | |

{If any dimension is marked `?`: "⚠ Dimensions marked ? were not scored due to insufficient data. See gaps below."}

---

## Key Strengths

- {Strength 1}
- {Strength 2}

## Key Risks

- {Risk 1 — include severity: high/medium/low}
- {Risk 2}

## Gaps / Unknown

{List any dimensions scored `?` and what information would resolve them. If none: omit section.}

---

{If comparing multiple options, include:}
## Options Comparison

| Dimension | {Option A} | {Option B} | {Option C} |
|-----------|-----------|-----------|-----------|
| Maturity (TRL) | | | |
| Integration Complexity | | | |
| Regulatory Exposure | | | |
| Vendor Stability | | | |
| LOE Estimate | | | |
| Strategic Risk | | | |
| Privacy / Security Fit | | | |
| Cost Trajectory | | | |
| **Composite** | | | |
| **Recommendation** | | | |

**Winner:** {Option X} — {one sentence why}

---

## Recommended next step

{Specific, concrete next action — e.g., "Run a 2-week POC against mmWave hardware in Room 12B" or "Request vendor pricing for 50-unit pilot before Q3 budget freeze"}

---

## Sources

{List sources used — vault notes, URLs, or "vault-only (no web research)"}
```

### 7. Update the knowledge graph

After writing the file, run:
```
/ingest 04-knowledge/technologies/{slug}.md
```

This adds the evaluated technology as a node in graph.json with its relationships to hardware, compliance requirements, and projects.

### 8. Confirm

Tell the user:
- Eval saved to: `AI/evaluations/eval-YYYY-MM-DD-{slug}.md`
- Knowledge base updated: `04-knowledge/technologies/{slug}.md`
- Recommendation and composite score (repeat verbatim)
- Any dimensions left unscored (`?`) and what would resolve them
- Whether a `/decide` log is warranted (suggest if score is ≥7.0 or if user seems ready to commit)

## Notes on confidence

- "High confidence" = scored from primary sources, production data, or direct experience
- "Medium confidence" = scored from secondary sources, vendor claims, or analogous systems
- "Low confidence" = scored from limited data; flag explicitly in the document

If overall confidence is low, say so clearly in the summary — a low-confidence 7.0 is not the same as a high-confidence 7.0.
