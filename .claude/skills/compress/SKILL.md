---
name: compress
description: Prune stale context from AI/sessions/, summarize aging documents, clean resolved items from OPEN_LOOPS.md, and report tokens freed. Run weekly or when context feels bloated.
roles: [all]
integrations: []
slash_command: /compress
---

# Compress Skill

## Purpose

Keep the system lean. Long-running projects accumulate session logs, research notes, and open loops that bloat context. This skill prunes what's resolved and summarizes what's aging — without losing anything permanently.

## When to Invoke

- User says `/compress`
- User says "clean up context", "archive old sessions", "prune open loops"
- Before starting a large project (clear the decks)
- Every Friday (scheduled via context janitor)
- When session context is feeling heavy

## Pre-Flight

Run `date '+%Y-%m-%d'` to get today's date. Calculate the cutoff date (14 days ago).

## Process

### 1. Scan session logs

List files in `AI/sessions/` that are older than 14 days:
```bash
find AI/sessions/ -name "*.md" -older-than 14 days
```

Use Bash: `find AI/sessions/ -name "*.md" -not -newer "$(date -d '14 days ago' '+%Y-%m-%d')" 2>/dev/null`

For each file older than 14 days:
- Read it
- Generate a 3-5 bullet summary (decisions made, open loops opened/closed, files modified)
- Write summary to `AI/sessions/archive/YYYY-MM-DD-summary.md`
- Note the original filename for the report

Do NOT delete originals — archive by reporting them as processed. The files remain; we just stop loading them actively.

### 2. Scan for unsummarized meeting notes or research

Check `AI/research/` and `01-daily/briefs/` for files older than 14 days that haven't been summarized.

If 5 or more unsummarized files exist in any directory, generate a rolling summary:
- Key decisions / findings across all files
- Open questions that were never resolved
- Write to `AI/sessions/archive/rolling-summary-YYYY-MM-DD.md`

### 3. Prune OPEN_LOOPS.md

Read `OPEN_LOOPS.md`. For each item:
- If it has a date older than 14 days: flag it
- Ask the user (in a batch): "These items are 14+ days old — resolve, archive, or keep?"
  - **Resolve**: move to `05-decisions/` with a one-line note
  - **Archive**: remove from OPEN_LOOPS.md with a note it was dropped
  - **Keep**: update the date to today to reset the clock

Show the full list before taking any action — don't modify OPEN_LOOPS.md until confirmed.

### 4. Compact ingest manifest

Check `graph/ingest_manifest.json`:
- List any entries whose `path` no longer exists on disk
- Report them; ask if they should be removed from the manifest
- If yes: remove the stale entries and save

### 5. Report

```
/compress complete — {date}

Session logs processed:  {N} files older than 14 days
Rolling summaries added: {N}
Open loops pruned:       {N} resolved, {N} archived, {N} kept
Manifest cleaned:        {N} stale entries removed

Files written:
  AI/sessions/archive/...
```

## What this does NOT do

- Does not delete any file — only reports what could be pruned and writes summaries
- Does not modify OPEN_LOOPS.md without user confirmation on each item
- Does not touch 04-knowledge/ or 05-decisions/ — those are permanent records
