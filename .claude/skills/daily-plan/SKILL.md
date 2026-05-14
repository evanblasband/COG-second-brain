---
name: daily-plan
description: Generate today's operational plan — calendar events, meeting attendee CRM lookups, open loops, and 3 prioritized actions. Saves to 01-daily/briefs/YYYY-MM-DD.md.
roles: [all]
integrations: [google-calendar]
slash_command: /daily-plan
---

# Daily Plan Skill

## Purpose

Start each day with a clear operational picture: what's on the calendar, who you're meeting, what's pending from open loops, and what the top 3 priorities are. Different from `/daily-brief` (which is news/research) — this is the execution layer.

## When to Invoke

- User says `/daily-plan`
- User says "what's my day look like", "morning plan", "what do I have today"
- Before standup or first meeting of the day

## Pre-Flight

1. Run `date '+%Y-%m-%d'` to get today's date
2. Check if `01-daily/briefs/YYYY-MM-DD.md` already exists — if yes, load it and ask "Update the existing plan or start fresh?"

## Process

### 0. Yesterday's Recap

Before looking ahead, pull a quick summary of yesterday:

1. Compute yesterday's date (today - 1 day)
2. Fetch yesterday's calendar events using `mcp__claude_ai_Google_Calendar__list_events` for that date — extract meeting titles and attendees
3. Check if `01-daily/briefs/YYYY-MM-DD.md` exists for yesterday — if yes, read the Notes section and any completed/updated items
4. Check `AI/sessions/` for any session file from yesterday (`YYYY-MM-DD-*.md`) — if found, read the summary

Synthesize into a short recap block (written into the daily plan before the calendar section):

```markdown
## Yesterday's Recap — {YYYY-MM-DD}

### Meetings
- **{HH:MM} — {Event title}** with {attendee names} — {1-line takeaway or outcome if known from notes}
- If no meetings: "No meetings on calendar."

### Key Activity
{2-4 bullets drawn from session notes or yesterday's plan — what got done, what moved, what came up}
- If no notes found: "No session notes for yesterday."
```

If none of these sources exist (no calendar, no brief, no session), skip the section silently.

### 1. Fetch today's calendar

Use the MCP Google Calendar integration (available in interactive sessions):
```
mcp__claude_ai_Google_Calendar__list_events
```
Fetch events for today. For each event extract:
- Time and duration
- Title
- Attendees (names + emails)
- Location / video link

### 2. CRM lookup for attendees

For each meeting attendee, check `02-people/{first-last}.md`:
- If file exists: extract role, relationship context, last interaction, shared projects, anything flagged as important
- If file missing: note "No CRM entry — create one after the meeting"

### 3. Load open loops and active projects

Read `OPEN_LOOPS.md` — surface any items due today or overdue.
Read `MEMORY.md` — note active projects under `## Active Projects`.

### 4. Generate the daily plan

Write to `01-daily/briefs/YYYY-MM-DD.md`:

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: knowledge
tags: [daily-plan, operational]
status: active
source: agent-generated
---

# Daily Plan — {Day of week}, YYYY-MM-DD

## Yesterday's Recap — {YYYY-MM-DD}

### Meetings
- {meeting list or "No meetings on calendar."}

### Key Activity
- {bullets from session notes or "No session notes for yesterday."}

---

## Top 3 Priorities

1. **{Priority 1}** — {why this is #1 today}
2. **{Priority 2}** — {brief context}
3. **{Priority 3}** — {brief context}

---

## Calendar

### {HH:MM} — {Event title}
- **Attendees:** {names}
- **Context:** {CRM summary for each attendee — role, relationship, last interaction}
- **Prep:** {anything to know or prepare — open items with these people, project context}
- **Video/Location:** {if applicable}

{repeat for each event}

---

## Open Loops — Due or Overdue

{Items from OPEN_LOOPS.md that are due today or past their follow-up date}
- If none: "No overdue items."

---

## Blockers

{Anything flagged as blocked in OPEN_LOOPS.md or MEMORY.md}
- If none: "No active blockers."

---

## Notes

<!-- Space for anything added during the day -->
```

### 5. Confirm and surface

Tell the user:
- Plan saved to `01-daily/briefs/YYYY-MM-DD.md`
- Highlight: next event and time until it starts
- Flag: any meetings with no CRM entry (attendees to profile)
- Flag: any open loops that are overdue

### 6. Slack prep (when Slack integration is active)

If Slack is in `00-inbox/MY-INTEGRATIONS.md` as Active:
Draft pre-written Slack messages for any commitments due today (check open loops).
Surface as suggestions — do not send without explicit approval.

If Slack is Disabled or Unknown: skip silently.

## Notes on Calendar access

- **Interactive sessions (Claude Code CLI):** use `mcp__claude_ai_Google_Calendar__list_events` directly — no Python auth needed
- **Background / cron contexts:** use `python3 scripts/query.py calendar today`

## Calibration

The Top 3 Priorities are derived from:
1. Items in OPEN_LOOPS.md with today's date or overdue
2. Active projects in MEMORY.md with next actions
3. Any prep needed for today's meetings
4. Your judgment — ask "What would make today a success?" if unclear
