---
name: weekly-summary
description: Automated weekly career log entry — synthesizes everything that happened Mon–Fri from calendar, session notes, decisions, open loops, and people interactions. Saves to 01-daily/weekly/YYYY-WW.md.
roles: [all]
integrations: [google-calendar]
slash_command: /weekly-summary
---

# Weekly Summary Skill

## Purpose

Generate a factual, data-driven record of what happened this week — who you met with, what got done, what decisions were made, what's still open, and what was learned. This is not a reflection prompt; it is an automated synthesis from raw sources.

Output is a **career log entry** designed to be queried later: performance reviews, resume updates, promotion cases, retrospectives, onboarding successors, or building long-term pattern analysis.

## When to Invoke

- User runs `/weekly-summary`
- `daily-plan` skill auto-triggers this every Friday morning (see daily-plan Step 0.5)
- User says "weekly summary", "write up my week", "log this week"

## Distinct from `/weekly-checkin`

`/weekly-checkin` is interactive and emotional — it asks questions about how you feel about the week. This skill is automated and factual — it reads sources and synthesizes without asking questions. Both can be run independently or together.

---

## Pre-Flight

1. Run `date '+%Y-%m-%d %u'` to get today's date and day-of-week (1=Mon, 5=Fri)
2. Compute the Monday of the current week (today minus `day_of_week - 1` days)
3. Compute ISO week number: `date '+%G-W%V'`
4. Check if `01-daily/weekly/{ISO-week}.md` already exists — if yes, ask "Update existing or regenerate fresh?"

---

## Data Sources — Pull All of These

### 1. Google Calendar (Mon–Fri this week)
Use `mcp__claude_ai_Google_Calendar__list_events` for each day Mon–Fri.
Extract per event:
- Date, time, duration
- Title
- Attendees (names + emails)
- Whether it was 1:1, group, external, or internal
- Location / video link

Aggregate into: total meetings, unique people met, external vs. internal split.

### 2. Session Notes (`AI/sessions/`)
Read all session files with dates in the current week (`YYYY-MM-DD-*.md`).
Extract per session:
- What was worked on
- Decisions made
- Files modified
- Open loops opened / closed
- Session cost

### 3. Daily Briefs (`01-daily/briefs/`)
Read all brief files for Mon–Fri this week.
Extract from the Notes section and any carry-forward items.

### 4. Decisions (`05-decisions/`)
List any decision files created this week (check `created:` frontmatter date).
Extract: decision name, rationale summary, confidence.

### 5. Open Loops (`OPEN_LOOPS.md`)
Diff against what was open at the start of the week:
- Items marked ✅ DONE this week (look for `DONE YYYY-MM-DD` in the current week range)
- Items still open that were already open Monday
- Any new items added this week

### 6. People (`02-people/`)
Find any people files with `updated:` frontmatter in the current week.
Extract: name, why updated (meeting, email, project interaction), relationship context.

### 7. Memory (`MEMORY.md`)
Check for any new entries added this week (compare dates in the file).
Extract: new key decisions, new patterns, new domain knowledge updates.

### 8. Mistakes (`06-mistakes/`)
List any mistake files created this week. Extract: what happened, prevention rule.

---

## Synthesis Rules

- **Be specific, not vague.** "Reviewed Gen3 manufacturing timeline with Tim Hearn" not "had a meeting."
- **Quantify where possible.** Files created, decisions made, loops closed, meetings held, session costs.
- **Career log lens.** Would a hiring manager or future-you care about this fact in 2 years? If yes, include it. If no, trim.
- **Group by project/domain**, not by day. Cross-day synthesis is more valuable than a day-by-day log.
- **Flag inflection points.** Did anything change direction, unblock a path, or reveal a new constraint? Make those prominent.
- **No filler.** Don't pad with "had productive conversations." Every bullet must carry information.

---

## Output Template

Save to: `01-daily/weekly/{ISO-week}.md`  
Example: `01-daily/weekly/2026-W20.md`

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: weekly-summary
tags: [career-log, weekly, YYYY]
status: reference
source: agent-generated
week: YYYY-WW
week_dates: YYYY-MM-DD to YYYY-MM-DD
---

# Weekly Summary — {ISO week}, {Mon date} – {Fri date}

## TL;DR

{2–3 sentences. The most important things that happened this week. Write as if briefing yourself in 6 months with no other context.}

---

## Accomplishments

{What got done, shipped, decided, or unblocked. Concrete and specific.}

- **{Project or domain}** — {what moved, what was completed, what was the outcome}
- {repeat}

---

## Meetings & People

**Total:** {N} meetings | {N} unique people | {N} external / {N} internal

| Date | Meeting | Key People | Takeaway / Outcome |
|------|---------|-----------|-------------------|
| {Mon} | {title} | {names} | {1-line outcome or key discussion point} |
| ... | | | |

**Relationship notes this week:**
- {Name} — {why notable: first meeting, key decision made together, relationship deepened, etc.}

---

## Decisions Made

{Formal decisions logged to 05-decisions/ or significant informal decisions from session notes}

- **{Decision title}** — {1-line rationale} | Confidence: {high/medium/low}
- If none: "No formal decisions logged this week."

---

## Open Loops

### Closed This Week
- ✅ {Item} — {how it was resolved}

### Opened This Week
- 🔄 {New item} — {why it's open, target resolution}

### Still In Flight (carried from prior weeks)
- ⏳ {Item} — {current status, blocking factor if any}

---

## What I Learned / Knowledge Updates

{New domain knowledge, technical findings, strategic insights — things that change how you think about the work}

- {Topic} — {what changed in your understanding}
- {Skill or tool} — {what you built competence in}

---

## Mistakes & Corrections

{Anything logged to 06-mistakes/ this week, or significant course corrections}

- {If none: "No mistakes logged this week."}

---

## Projects Status Snapshot

{For each active project from MEMORY.md — brief status update based on week's activity}

| Project | Status | Moved This Week | Next Action |
|---------|--------|----------------|-------------|
| {name} | {On track / Stalled / Blocked / Complete} | {what moved} | {next step} |

---

## Numbers

| Metric | Value |
|--------|-------|
| Meetings | {N} |
| Unique people met | {N} |
| Session files | {N} |
| Decisions logged | {N} |
| Open loops closed | {N} |
| Open loops opened | {N} |
| Files modified (sessions) | {N} |
| Total session cost (est.) | ${X.XX} |

---

## Open Questions Heading Into Next Week

{Things still uncertain, unresolved, or that need answers — not tasks, but questions}

- {Question} — {why it matters, who/what can answer it}

---

## Carry-Forward Intentions

{Not a task list — the 2–3 things that most deserve focus next week based on this week's picture}

1. {Intention 1} — {why this matters now}
2. {Intention 2}
3. {Intention 3}

---

*Career log entry — generated by /weekly-summary | Sources: Google Calendar, session notes, open loops, decisions, people CRM*
```

---

## Confirm and Surface

After saving the file, tell the user:
- File saved to `01-daily/weekly/{ISO-week}.md`
- TL;DR block (2–3 sentences)
- Count of meetings, people met, loops closed
- Any open questions heading into next week

---

## Friday Auto-Trigger (via daily-plan)

When `daily-plan` detects it's Friday (day of week = 5):
1. Run this skill first, before generating the daily plan
2. Append a brief "This Week" section to the daily plan referencing the weekly summary file path
3. Include the TL;DR in the daily plan output

---

## Career Log Design Notes

These files are designed for future querying. When the career log query feature is built, it will:
- Parse `type: weekly-summary` frontmatter to index entries
- Use `week:` field for date range queries ("what did I do in Q1 2026?")
- Full-text search the Accomplishments, Decisions, and People sections
- Aggregate People table across weeks to build relationship timelines
- Aggregate Numbers table for productivity trend analysis

**Do not omit the frontmatter fields** — they are the index keys for future queries.
