---
name: system-analyst
description: Break down product requirements, PRDs, or feature specs into structured epics and stories with dependency mapping. Invokes the system-analyst agent and saves the plan to 03-projects/. Run after /generate-prd or when given PM/CTO requirements that need to become actionable development work.
roles: [all]
integrations: []
slash_command: /system-analyst
---

# System Analyst Skill

## Purpose

Translate product requirements, PRDs, or feature specifications into a structured development plan (epics + stories + dependency map) that engineers can immediately work from. Invokes the `system-analyst` subagent, saves output to the vault, and suggests follow-up vault actions for any flagged decisions or spike evaluations.

## When to Invoke

- User types `/system-analyst` (with or without arguments)
- User says "break this down into stories", "create a dev plan", "turn this PRD into tasks", "plan this feature"
- After running `/generate-prd` and needing the next step
- When a PM or architect provides requirements and wants actionable tickets

## Pre-Flight

Run these before invoking the agent:

```bash
date '+%Y-%m-%d'
```

Then check for existing project context:
1. Scan `03-projects/` for a folder matching the project name — load any existing PRD or plan files as context
2. Check `05-decisions/` for prior architectural decisions relevant to this project
3. Check `04-knowledge/technologies/` for prior `/eval` outputs that may answer spike questions
4. Scan `OPEN_LOOPS.md` for unresolved items tagged to this project

## Process

### 1. Identify the input

If the user ran `/system-analyst` with content inline (e.g., `/system-analyst Here are the requirements: ...`), use that directly.

If run with no arguments, ask ONE question:

> "What are the requirements? You can paste a PRD, a PM brief, CTO constraints, or describe the feature directly. If there's an existing file in 03-projects/ I should load, tell me the path."

Do not ask follow-up questions before running the agent — the agent handles clarification internally.

### 2. Determine the project name

Extract from the requirements text or ask: "What's the project name?" (one word, kebab-case preferred, e.g., `bathroom-fall-detection`).

### 3. Invoke the system-analyst agent

Use the Task tool with `subagent_type="system-analyst"`. Pass:

```
Requirements:
[full requirements text]

Project name: [project-name]

Context loaded from vault:
- PRD: [path if found, or "none"]
- Relevant decisions: [list from 05-decisions/ or "none"]
- Relevant tech evals: [list from 04-knowledge/technologies/ or "none"]
- Open loops: [relevant items from OPEN_LOOPS.md or "none"]
```

### 4. Save the plan

When the agent returns its output, save to:

```
03-projects/{project-name}/plans/{date}-plan.md
```

Use this frontmatter:

```yaml
---
created: {date}
updated: {date}
tags: [project, plan, active]
status: active
project: {project-name}
type: plan
source: agent-generated
---
```

If `03-projects/{project-name}/` does not exist, create the directory first.

### 5. Suggest follow-up actions

After saving, surface any flagged items from the plan:

**Architectural decisions** — For each item in the plan's "Architectural Decisions Flagged" section, present:
> "Decision flagged: [decision text]. Run `/decide` to log it permanently."

**Spike tech evaluations** — For any Spike story with `/eval` in its Notes, present:
> "Spike EPIC-XXX-SYY involves evaluating [technology options]. Run `/eval [options]` before the sprint starts."

**Open questions** — If the plan's "Open Questions" section is non-empty, ask:
> "The plan has [N] open questions. Should I add them to OPEN_LOOPS.md?"

If the user confirms, append each question to `OPEN_LOOPS.md` under a new section header `## [project-name] — [date]`.

## Output to User

After all steps complete, report:

```
Plan saved: 03-projects/{project-name}/plans/{date}-plan.md

  Epics: N
  Stories: N  (Small: N | Medium: N | Large: N | Spikes: N)
  Decisions to log: N  ← run /decide
  Spikes needing eval: N  ← run /eval
  Open questions: N  ← add to OPEN_LOOPS.md? (y/n)
```

Then show the full plan inline so the user can review it.

## Notes

- Linear is available but not actively used — do not attempt to sync tickets unless the user explicitly asks.
- If the user asks to push to Linear later, that is a future integration; note it as a backlog item.
- For complex multi-service plans or when PM/CTO inputs conflict significantly, suggest the user change the agent's model to `opus` for that run: "This looks complex — consider running with `model: opus` for stronger dependency analysis."
