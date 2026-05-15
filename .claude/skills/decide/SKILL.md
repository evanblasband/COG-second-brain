---
name: decide
description: Log a decision with rationale, alternatives rejected, and confidence level to 05-decisions/. Invoke before or immediately after making a significant architectural, technical, or strategic choice.
roles: [all]
integrations: []
slash_command: /decide
---

# Decide Skill

## Purpose

Capture decisions durably so future sessions have the full context — what was decided, what was rejected and why, who approved it, and how confident the decision-maker was. Prevents re-litigating settled questions.

## When to Invoke

- User says `/decide {decision description}`
- User says "log this decision", "record this choice", "document why we did this"
- After any architectural, technology, vendor, or process choice
- Before closing a session where a significant decision was made

## Pre-Flight

Run `date '+%Y-%m-%d'` to get today's date before writing any file.

## Process

### 1. Clarify (if not already provided)

Ask these questions ONE AT A TIME. Do not write anything until all are answered:

1. **What was decided?** (the specific choice made — be precise)
2. **What alternatives were considered and rejected?** (at least one; what made them lose?)
3. **What is the rationale?** (the reasoning that makes this the right call)
4. **Confidence level?** (high / medium / low — and why if not high)
5. **Any open conditions?** (circumstances that would cause this decision to be revisited)

If the user provides the decision inline with `/decide`, extract what you can from the message and only ask for what's genuinely missing.

### 2. Write the decision file

Filename: `05-decisions/YYYY-MM-DD-{slug}.md`
- Slug: 3-5 word kebab-case summary of the decision
- Example: `05-decisions/2026-05-06-graph-json-over-sqlite.md`

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: decision
tags: [decision, {domain-tag}]
status: active
confidence: high | medium | low
source: internal
project: {project if applicable, else omit}
people_involved: [owner]
---

# Decision: {Decision title}

**Date:** YYYY-MM-DD  
**Confidence:** high | medium | low  
**Status:** Active

## What was decided

{Clear 1-3 sentence statement of the decision}

## Rationale

{The reasoning that makes this the right call. What constraints, evidence, or principles drove this?}

## Alternatives rejected

| Option | Why rejected |
|--------|-------------|
| {Option A} | {Reason} |
| {Option B} | {Reason} |

## Conditions for revisiting

{What would cause this decision to be reopened? If none, write "None identified."}

## Sources / evidence

{Links, documents, or prior decisions this rests on. If none, omit section.}
```

### 3. Offer to update MEMORY.md

If the decision is significant (architectural, technology platform choice, process change), ask:
> "Should this go in MEMORY.md Key Decisions as well? It will surface in every future session."

If yes, append to MEMORY.md under `## Key Decisions`:
```
YYYY-MM-DD | {Decision one-liner} | {Rationale in 10 words} | {confidence}
```

### 4. Confirm

Tell the user:
- File written to: `05-decisions/YYYY-MM-DD-{slug}.md`
- Whether MEMORY.md was updated
- Suggest related open loops to close if applicable

## Output example

```
✓ Decision logged: 05-decisions/2026-05-06-graph-json-over-sqlite.md
  Summary: Use graph.json (flat file) for V1; migrate to SQLite at ~5k nodes
  MEMORY.md updated: yes
```
