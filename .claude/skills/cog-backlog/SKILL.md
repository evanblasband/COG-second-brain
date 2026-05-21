---
name: cog-backlog
description: Add a feature or improvement idea to the COG second brain backlog (COG-BACKLOG.md). Use for system-level improvements — not work tasks.
roles: [all]
integrations: []
slash_command: /cog-backlog
---

# COG Backlog Skill

## Purpose

Capture feature ideas, improvement requests, and investigation tasks for the COG second brain itself. Keeps them in one place for future work sessions without cluttering OPEN_LOOPS.md (which is for external/work items).

## When to Invoke

- User says `/cog-backlog {idea}`
- User says "add this to the COG backlog", "save this for the brain later", "backlog this"
- User describes an improvement to COG skills, agents, hooks, or workflows
- User pastes a reference (GitHub, LinkedIn, article) they want to revisit for COG improvements

## Pre-Flight

Run `date '+%Y-%m-%d'` to get today's date.

## Process

### 1. Extract from user input

From what the user provides, extract:

- **Title** — short verb-noun phrase (e.g. "Token optimization — reduce ingestion cost")
- **Description** — what the feature/investigation involves; bullet points if multi-part
- **Source** — URL or reference if provided (optional)
- **Priority** — if the user signals urgency, note it; otherwise omit

If the user provides a bare idea with no detail, write the title and a one-sentence description — don't ask clarifying questions unless the idea is genuinely ambiguous.

### 2. Format the entry

```markdown
### [ ] {Title}
*Added: YYYY-MM-DD{source_line}*

{Description — 1 paragraph or bullets. Include specific sub-tasks or investigation angles if known.}
```

Where `{source_line}` is ` | Source: {URL}` if a source was given, otherwise omit.

### 3. Append to COG-BACKLOG.md

Read `COG-BACKLOG.md`, then insert the new entry at the **top** of the `## Active` section (after the `## Active` heading and any blank lines, before the first existing entry).

Update the `updated:` frontmatter field to today's date.

### 4. Confirm

Tell the user:
- What was added (title only)
- That it's in `COG-BACKLOG.md` under Active

Keep the confirmation to one line. No summaries or repeating the description back.

## Output example

```
✓ Added to COG backlog: "Agent audit + expansion"
```
