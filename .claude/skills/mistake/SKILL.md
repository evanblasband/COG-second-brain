---
name: mistake
description: Log an error or wrong assumption with root cause analysis and a prevention rule to 06-mistakes/. Run immediately after discovering a mistake so the prevention rule is captured while context is fresh.
roles: [all]
integrations: []
slash_command: /mistake
---

# Mistake Skill

## Purpose

Convert errors into prevention rules. The value isn't in recording what went wrong — it's in extracting the rule that makes it impossible to make the same mistake again.

## When to Invoke

- User says `/mistake {description}`
- User says "log this error", "that was wrong", "we got burned by this"
- After discovering a faulty assumption that led to rework
- After a debugging session that revealed a systemic issue
- After an external service or tool behaved unexpectedly in a way worth remembering

## Pre-Flight

Run `date '+%Y-%m-%d'` to get today's date before writing any file.

## Process

### 1. Clarify (if not already provided)

Ask these questions ONE AT A TIME. Stop writing until all are answered:

1. **What happened?** (the concrete error — be specific, not vague)
2. **What was the root cause?** (not the symptom — dig one level deeper)
3. **What's the prevention rule?** (a rule stated as an action, e.g. "Always X before Y" or "Never Z without checking W")
4. **Severity?** (high = data loss / external impact / significant rework; medium = time lost; low = caught quickly)

If the user provides the mistake inline, extract what you can and only ask for what's missing.

### 2. Write the mistake file

Filename: `06-mistakes/YYYY-MM-DD-{slug}.md`
- Slug: 3-5 word kebab-case description of the mistake
- Example: `06-mistakes/2026-05-06-ingest-max-tokens-too-low.md`

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: knowledge
tags: [mistake, {domain-tag}]
status: reference
severity: high | medium | low
source: internal
---

# Mistake: {Title}

**Date:** YYYY-MM-DD  
**Severity:** high | medium | low

## What happened

{Concrete description of the error — enough context that future-you understands it cold}

## Root cause

{One level deeper than the symptom. What assumption was wrong? What was missed?}

## Prevention rule

> **{Stated as an imperative action — "Always X", "Never Y", "Check Z before W"}**

## Impact

{Time lost, rework required, external effects if any}

## How it was caught

{What revealed the error — test, user report, observation}
```

### 3. Offer to update MEMORY.md

If the mistake reveals a systemic pattern (not a one-off), ask:
> "Should the prevention rule go in MEMORY.md Lessons from Mistakes? It will surface in every future session."

If yes, append to MEMORY.md under `## Lessons from Mistakes`:
```
{Prevention rule} | {Source: 06-mistakes/YYYY-MM-DD-{slug}.md} | YYYY-MM-DD
```

### 4. Confirm

Tell the user:
- File written to: `06-mistakes/YYYY-MM-DD-{slug}.md`
- The prevention rule (repeat it so it sticks)
- Whether MEMORY.md was updated
