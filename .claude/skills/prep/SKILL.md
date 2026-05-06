---
name: prep
description: Generate a pre-meeting briefing doc — attendee CRM profiles, relationship context, open items, suggested agenda, and talking points. Run 15-30 minutes before any significant meeting.
roles: [all]
integrations: [google-calendar]
slash_command: /prep
---

# Prep Skill

## Purpose

Walk into every meeting knowing who's in the room, what your history is with them, what's open between you, and what you want to accomplish. Prevents going in cold.

## When to Invoke

- User says `/prep {event name or time}`
- User says "prep me for my 2pm", "brief me before this meeting", "who am I meeting with"
- 15-30 minutes before a significant meeting
- Before any first meeting with a new person

## Pre-Flight

Run `date '+%Y-%m-%d %H:%M'` to get current date and time.

## Process

### 1. Find the meeting

If the user provided a time (e.g., "2pm", "14:00"):
- Use `mcp__claude_ai_Google_Calendar__list_events` to fetch today's events
- Find the event closest to the specified time

If the user provided a name (e.g., "prep for the architecture review"):
- Search today's and tomorrow's calendar for a matching title

If ambiguous (multiple matches), list them and ask which one.

### 2. Extract meeting details

From the calendar event:
- Full title
- Time and duration
- Attendees (name + email)
- Description / agenda (if any)
- Location or video link

### 3. CRM lookup — every attendee

For each attendee, read `02-people/{first-last}.md`:

**If file exists**, extract:
- Role and title
- Relationship context (how you know them, reporting structure)
- Last interaction (date + what was discussed)
- Shared projects
- Anything flagged as important to know
- Communication preferences if noted
- Open items between you and this person

**If file missing**, note: "No CRM entry for {name} — create one after the meeting."

### 4. Project context

If the meeting title or attendees suggest a specific project:
- Check `03-projects/` for a matching project folder
- Load `brief.md` and `status.md` if present
- Surface any open decisions or unresolved questions from that project

### 5. Open loops check

Scan `OPEN_LOOPS.md` for any items involving the attendees or the meeting topic.
Surface any that should be resolved or discussed in this meeting.

### 6. Generate briefing

Write to `AI/drafts/prep-YYYY-MM-DD-{slug}.md` and display inline:

```markdown
---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: research
tags: [meeting-prep, {attendee-names}]
status: draft
source: agent-generated
people_involved: [{names}]
---

# Meeting Prep: {Event title}
**{Day}, {Date} at {Time} ({Duration})**
**Location:** {video link or location}

---

## Who's in the room

### {Name} — {Title}
- **Relationship:** {how you know them, reporting structure}
- **Last interaction:** {date} — {brief summary}
- **Shared projects:** {list}
- **Key context:** {anything important to know before meeting}
- **Open items:** {any unresolved items between you}

{repeat for each attendee}

---

## Meeting context

**Why this meeting:** {inferred or extracted from calendar description}
**Project:** {linked project if identifiable}

### Relevant open loops
{Items from OPEN_LOOPS.md relevant to this meeting}

### Project status (if applicable)
{Key status points from 03-projects/ if found}

---

## Suggested agenda

Based on open items and context:

1. {Agenda item 1 — with time suggestion}
2. {Agenda item 2}
3. {Agenda item 3}

---

## Talking points

- {Point 1 — key thing to cover or raise}
- {Point 2}
- {Point 3}

---

## What success looks like

{What specific outcome would make this meeting worthwhile? State it as a concrete deliverable or decision.}

---

## Post-meeting actions

- [ ] Update CRM for {attendee names}
- [ ] Log any decisions to 05-decisions/
- [ ] Update open loops resolved or opened
```

### 7. Confirm

Tell the user:
- Briefing saved to `AI/drafts/prep-YYYY-MM-DD-{slug}.md`
- Any attendees without CRM entries (flag to create after the meeting)
- Time until meeting starts
