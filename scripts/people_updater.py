#!/usr/bin/env python3
"""
people_updater.py — Auto-update 02-people/ CRM from ingested meeting documents.

Called by ingest.py after processing any file classified as a meeting document.

Attribution strategy by transcript type:
  multi-speaker  — explicit "Name: ..." labels → confidence: high for observations
  single-persp.  — Notion AI / manual notes → calendar attendees + context scan
  attendees-only — calendar match, no speech attributed → confidence: low (presence only)

Confidence rules:
  high   — explicit speaker label, OR named as action item owner
  medium — in calendar attendee list AND mentioned in doc body
  low    — in calendar attendee list only (was there, nothing attributed)

Never overwrites existing profile content. Only appends to Timeline section.
Creates stub profiles for new people when confidence >= medium (configurable).
"""

from __future__ import annotations

import re
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
PEOPLE_DIR = VAULT_ROOT / "02-people"
SELF_NAME = "Evan Blasband"
SELF_FIRST = SELF_NAME.split()[0]
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ─── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    config_file = VAULT_ROOT / "config" / "config.yaml"
    try:
        import yaml
        with open(config_file) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


_CONFIG = _load_config()
_PU_CONFIG = _CONFIG.get("people_updater", {})
PU_ENABLED = _PU_CONFIG.get("enabled", True)
PU_CALENDAR = _PU_CONFIG.get("calendar_cross_reference", True)
PU_CREATE_NEW = _PU_CONFIG.get("create_new_profiles", True)
PU_MIN_CONFIDENCE = _PU_CONFIG.get("min_confidence_to_create", "medium")  # "low"|"medium"|"high"


# ─── Detection patterns ─────────────────────────────────────────────────────────

MEETING_DOC_TYPES = {"meeting", "meeting-transcript", "transcript", "meeting-notes", "1on1"}
MEETING_TAGS = {"meeting", "transcript", "notes", "1on1", "standup", "sync", "onboarding"}

MEETING_SIGNALS = [
    "attendees:", "action items", "action item", "participants:",
    "## agenda", "## decisions", "## summary", "## next steps",
    "decisions made", "meeting notes", "## action items", "## key takeaways",
    "## speakers", "key decisions", "follow-ups",
]

# Multi-speaker: line starts with "Name:" or "Name Surname:" or "[Name]:" or "Speaker N:"
_SPEAKER_LABEL_RE = re.compile(
    r"(?m)^(?:\*?\*?)([A-Z][a-z]+(?: [A-Z][a-z]+)?)(?:\*?\*?):\s",
)
_SPEAKER_LABEL_ALT_RE = re.compile(
    r"(?m)^\[([A-Z][a-z]+(?: [A-Z][a-z]+)?)\]:\s|^(Speaker \d+):\s",
)

# Attendee section block: "## Attendees\n- Name\n- Name\n"
_ATTENDEE_SECTION_RE = re.compile(
    r"(?:^|\n)(?:#+\s*)?[Aa]ttendees?[:\s]*\n((?:\s*[-*\d.]\s*.+\n?)+)",
)

# Third-person attribution verbs
_ATTRIB_VERBS = (
    "said|mentioned|noted|asked|suggested|raised|confirmed|added|emphasized|"
    "pointed out|shared|explained|clarified|proposed|flagged|brought up|"
    "described|referenced|committed|agreed|disagreed|pushed back|followed up|"
    "highlighted|observed|reported|indicated|stressed|underscored"
)
_ATTRIBUTION_RE = re.compile(
    rf"\b([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b(?:'s)?\s+(?:{_ATTRIB_VERBS})\b"
)

# Action item ownership patterns
_ACTION_OWNER_RE = re.compile(
    r"(?:"
    r"→\s*([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+(?:to|will|should)\b|"
    r"([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s+will\s+\w+|"
    r"@([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b|"
    r"Owner:\s*([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b|"
    r"\bAI:\s*([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b"
    r")"
)

# Words that look like names but aren't
_NOT_NAMES: set[str] = {
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
    "The", "This", "That", "We", "They", "Our", "Their", "His", "Her", "Its",
    "Team", "Sage", "Gen", "Platform", "Product", "Engineering", "Hardware",
    "Software", "Data", "Cloud", "Next", "Last", "First", "Second", "Third",
    "Action", "Item", "Note", "Summary", "Decision", "Update", "Review",
    "Meeting", "Sync", "Call", "Session", "Agenda", "Follow",
    "AI", "OK", "Yes", "No", "True", "False",
    SELF_FIRST,
}

# Email domain → org name
_DOMAIN_ORG: dict[str, str] = {
    "sagehealth.com": "Sage Health",
    "hellosage.com": "Sage Health",
    "seacomp.com": "SEACOMP",
    "cloud2gnd.com": "Cloud2gnd",
}


# ─── Frontmatter parsing ───────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> dict:
    """Extract key frontmatter fields without a full YAML parser."""
    fm: dict[str, str | list] = {}
    if not content.startswith("---"):
        return fm

    end = content.find("\n---", 3)
    if end == -1:
        return fm

    block = content[3:end]
    for line in block.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if key == "tags":
            # Handle both "tags: [a, b]" and multi-line list
            val = val.strip("[]").replace("'", "").replace('"', "")
            fm["tags"] = [t.strip() for t in val.split(",") if t.strip()]
        else:
            fm[key] = val

    return fm


# ─── Document classification ───────────────────────────────────────────────────

def classify_meeting(content: str, path: Path) -> dict | None:
    """
    Return meeting metadata if the document looks like a meeting doc, else None.
    Result: {doc_date, doc_title, attribution}
      attribution: "multi-speaker" | "single-perspective"
    """
    fm = parse_frontmatter(content)

    doc_type = fm.get("type", "").lower()
    doc_tags = {t.lower() for t in (fm.get("tags") or [])}
    doc_date = fm.get("created", TODAY)[:10]

    # 1. Explicit type/tag signals
    is_meeting = (
        doc_type in MEETING_DOC_TYPES
        or bool(MEETING_TAGS & doc_tags)
    )

    # 2. Body signal count (require 3+ signals if no explicit type)
    if not is_meeting:
        body_lower = content[content.find("\n---", 3) + 4:].lower() if "---" in content else content.lower()
        signal_count = sum(1 for s in MEETING_SIGNALS if s in body_lower)
        is_meeting = signal_count >= 3

    # 3. Title pattern signals
    if not is_meeting:
        stem = path.stem.lower()
        is_meeting = any(kw in stem for kw in ("meeting", "sync", "standup", "1on1", "intro", "onboarding", "transcript"))

    if not is_meeting:
        return None

    # Determine doc title: frontmatter > H1 heading > filename stem
    h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    h1_title = h1_match.group(1).strip() if h1_match else ""
    doc_title = (
        fm.get("title") or fm.get("summary") or
        h1_title or
        path.stem.replace("-", " ").replace("_", " ")
    )

    # Detect attribution type
    body = content[content.find("\n---", 3) + 4:] if "---" in content[:5] else content
    speaker_matches = _SPEAKER_LABEL_RE.findall(body)
    unique_speakers = {n for n in speaker_matches if n not in _NOT_NAMES}
    attribution = "multi-speaker" if len(unique_speakers) >= 2 else "single-perspective"

    return {
        "doc_date": doc_date,
        "doc_title": doc_title,
        "attribution": attribution,
    }


# ─── Attendee extraction from content ─────────────────────────────────────────

def get_attendee_section_names(content: str) -> list[str]:
    """Extract names from an explicit '## Attendees' section if present."""
    matches = _ATTENDEE_SECTION_RE.search(content)
    if not matches:
        return []

    names = []
    for line in matches.group(1).splitlines():
        line = re.sub(r"^[\s\-*\d.]+", "", line).strip()
        line = re.sub(r"\(.*?\)", "", line).strip()  # strip (role) annotations
        line = re.sub(r",.*$", "", line).strip()  # strip ", Company"
        if line and len(line) > 1 and line.split()[0] not in _NOT_NAMES:
            names.append(line)
    return names


def get_multi_speaker_observations(content: str) -> dict[str, list[str]]:
    """
    For multi-speaker transcripts: extract what each named speaker said.
    Returns {name: [observation, ...]}
    """
    observations: dict[str, list[str]] = {}
    body = content[content.find("\n---", 3) + 4:] if content.startswith("---") else content

    current_speaker = None
    current_lines: list[str] = []

    for line in body.splitlines():
        m = _SPEAKER_LABEL_RE.match(line)
        if m:
            # Save previous speaker's content
            if current_speaker and current_lines:
                text = " ".join(current_lines[:3]).strip()[:200]
                if text:
                    observations.setdefault(current_speaker, []).append(text)
            current_speaker = m.group(1)
            if current_speaker in _NOT_NAMES:
                current_speaker = None
                current_lines = []
            else:
                rest = line[m.end():].strip()
                current_lines = [rest] if rest else []
        elif current_speaker:
            stripped = line.strip()
            if stripped:
                current_lines.append(stripped)
            elif current_lines:
                # Blank line = end of this speaker's turn
                text = " ".join(current_lines[:3]).strip()[:200]
                if text:
                    observations.setdefault(current_speaker, []).append(text)
                current_lines = []

    if current_speaker and current_lines:
        text = " ".join(current_lines[:3]).strip()[:200]
        if text:
            observations.setdefault(current_speaker, []).append(text)

    return {k: v for k, v in observations.items() if k not in _NOT_NAMES}


def get_context_mentions(content: str) -> dict[str, list[str]]:
    """
    For single-perspective docs: extract named mentions via attribution verbs
    and action item ownership.
    Returns {name: [observation, ...]}
    """
    body = content[content.find("\n---", 3) + 4:] if content.startswith("---") else content
    mentions: dict[str, list[str]] = {}

    # Third-person attribution ("Kevin said...", "Mark mentioned...")
    for m in _ATTRIBUTION_RE.finditer(body):
        name = m.group(1)
        if name in _NOT_NAMES or len(name) < 3:
            continue
        # Capture a bit of context around the match
        start = max(0, m.start() - 10)
        end = min(len(body), m.end() + 80)
        snippet = body[start:end].replace("\n", " ").strip()[:150]
        mentions.setdefault(name, []).append(f"Mentioned: {snippet}")

    # Action item ownership
    for m in _ACTION_OWNER_RE.finditer(body):
        name = next((g for g in m.groups() if g), None)
        if not name or name in _NOT_NAMES or len(name) < 3:
            continue
        start = max(0, m.start())
        end = min(len(body), m.end() + 60)
        snippet = body[start:end].replace("\n", " ").strip()[:120]
        mentions.setdefault(name, []).append(f"Action item: {snippet}")

    return {k: v for k, v in mentions.items() if k not in _NOT_NAMES}


# ─── Calendar cross-reference ─────────────────────────────────────────────────

def fetch_calendar_attendees(doc_date: str, title_keywords: list[str]) -> list[dict]:
    """
    Fetch attendees for the best-matching calendar event on doc_date.
    Returns list of {name, email, org, status}.
    Falls back to [] if auth is unavailable or API call fails.
    """
    if not PU_CALENDAR:
        return []

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        return []

    token_file = VAULT_ROOT / ".auth" / "google-token.json"
    if not token_file.exists():
        return []

    scopes = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    try:
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        if not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, "w") as f:
                f.write(creds.to_json())

        service = build("calendar", "v3", credentials=creds)

        # Fetch all events on the given day
        start = f"{doc_date}T00:00:00Z"
        end = f"{doc_date}T23:59:59Z"
        result = service.events().list(
            calendarId="primary",
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = result.get("items", [])

        # Match by title keyword overlap
        best_event = None
        best_score = 0
        kw_tokens = {w.lower() for w in title_keywords if len(w) > 2}

        for event in events:
            summary = event.get("summary", "")
            event_tokens = set(re.split(r"[\s\-_<>|,]+", summary.lower()))
            score = len(kw_tokens & event_tokens)
            if score > best_score:
                best_score = score
                best_event = event

        if not best_event or best_score == 0:
            # Fallback: if only one event that day, use it
            if len(events) == 1:
                best_event = events[0]
            else:
                return []

        attendees = []
        for a in best_event.get("attendees", []):
            email = a.get("email", "")
            if not email or a.get("resource"):  # skip room resources
                continue
            status = a.get("responseStatus", "")
            if status == "declined":
                continue  # skip people who declined
            display = a.get("displayName", "")
            name = display or email_to_name(email)
            org = infer_org_from_email(email)
            attendees.append({
                "name": name,
                "email": email,
                "org": org,
                "status": status,
            })

        return attendees

    except Exception:
        return []


# ─── Name/org utilities ────────────────────────────────────────────────────────

def email_to_name(email: str) -> str:
    """Convert 'kevin.shyu@sagehealth.com' → 'Kevin Shyu'. Handles partial names."""
    local = email.split("@")[0]
    parts = re.split(r"[._\-+]", local)
    return " ".join(p.capitalize() for p in parts if p)


def infer_org_from_email(email: str) -> str:
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return _DOMAIN_ORG.get(domain, "")


def name_to_slug(name: str) -> str:
    parts = name.strip().split()
    # Remove duplicate consecutive last name (e.g. "Jim Turner Turner")
    if len(parts) >= 2 and parts[-1].lower() == parts[-2].lower():
        parts = parts[:-1]
    slug = "-".join(parts).lower()
    slug = re.sub(r"[^\w-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def find_existing_by_first_name(first_name: str) -> Path | None:
    """
    If exactly one 02-people/ file starts with first_name-, return its path.
    Returns None if zero or multiple matches (ambiguous).
    """
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)
    prefix = first_name.lower() + "-"
    matches = [p for p in PEOPLE_DIR.glob("*.md") if p.stem.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    return None


def is_self(name: str) -> bool:
    """True if the name refers to the vault owner."""
    name_lower = name.lower()
    return SELF_NAME.lower() in name_lower or name_lower == SELF_FIRST.lower()


# ─── CRM read/write ─────────────────────────────────────────────────────────────

def append_timeline_entry(
    profile_path: Path,
    date: str,
    entries: list[str],
    source_path: str,
    confidence: str,
) -> bool:
    """
    Append new entries under a dated heading in the Timeline section.
    Returns True if successfully appended.
    """
    if not entries:
        return False

    try:
        content = profile_path.read_text(encoding="utf-8")
    except Exception:
        return False

    # Build entry block
    entry_lines = []
    for e in entries[:5]:  # cap at 5 observations per ingest
        entry_lines.append(f"- {e} [Source: [[{source_path}]] | {date} | confidence: {confidence}]")

    new_block = f"\n### {date}\n" + "\n".join(entry_lines) + "\n"

    # Find Timeline section and append
    timeline_marker = "## Timeline (Append-Only)"
    if timeline_marker in content:
        insert_at = content.index(timeline_marker) + len(timeline_marker)
        updated = content[:insert_at] + new_block + content[insert_at:]
    else:
        updated = content.rstrip() + f"\n\n---\n\n{timeline_marker}\n{new_block}"

    # Update the frontmatter 'updated' field
    updated = re.sub(r"(updated:\s*)\d{4}-\d{2}-\d{2}", rf"\g<1>{date}", updated, count=1)

    profile_path.write_text(updated, encoding="utf-8")
    return True


def create_stub_profile(
    slug: str,
    name: str,
    email: str,
    org: str,
    doc_date: str,
    meeting_title: str,
    entries: list[str],
    source_path: str,
    confidence: str,
) -> Path:
    """Create a new minimal CRM stub in 02-people/."""
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)

    org_tag = "sage" if org == "Sage Health" else "external"
    tags = ["crm", org_tag, "people"]

    entry_lines = []
    for e in entries[:5]:
        entry_lines.append(f"- {e} [Source: [[{source_path}]] | {doc_date} | confidence: {confidence}]")

    if not entry_lines:
        entry_lines = [
            f"- Met in: {meeting_title}. No specific observations captured. "
            f"[Source: [[{source_path}]] | {doc_date} | confidence: {confidence}]"
        ]

    timeline_block = "\n".join(entry_lines)
    email_line = f"\n- **Email:** {email}" if email else ""
    org_line = f"\n- **Organization:** {org}" if org else ""
    first_met_context = f"{meeting_title}" if meeting_title else "Sage context"

    content = f"""---
created: {doc_date}
updated: {doc_date}
type: people
tags: {tags}
status: active
source: agent-generated
confidence: {confidence}
department: Unknown
location: Unknown
---

# {name}

## Executive Snapshot

- Role unknown — update after interaction. [Source: [[{source_path}]] | {doc_date} | confidence: {confidence}]{org_line}

## Role & Responsibilities

- **Title:** Unknown — update from interactions{email_line}{org_line}
- **Scope:** Unknown — fill in from interactions
- **Projects shared with Evan:** TBD

## Working Style

- **Communication:** Unknown — update after first interaction
- **Decision-making:** Unknown
- **Meeting style:** Unknown

## Strengths

- Unknown — update after working together

## How to Work With Effectively

- Unknown — update from interactions

## Relationship Context

- **First met:** {doc_date} ({first_met_context})
- **How connected:** Met at {first_met_context}
- **Relationship quality:** unknown

## Open Threads

<!-- Update after interaction -->
-

---

## Timeline (Append-Only)

### {doc_date}
{timeline_block}
"""

    profile_path = PEOPLE_DIR / f"{slug}.md"
    profile_path.write_text(content, encoding="utf-8")
    return profile_path


# ─── Confidence gating ─────────────────────────────────────────────────────────

_CONF_RANK = {"low": 0, "medium": 1, "high": 2}


def meets_min_confidence(confidence: str) -> bool:
    return _CONF_RANK.get(confidence, 0) >= _CONF_RANK.get(PU_MIN_CONFIDENCE, 1)


# ─── Main pipeline ─────────────────────────────────────────────────────────────

def update_from_meeting(path: Path, content: str, source_key: str) -> dict:
    """
    Orchestrate meeting detection → people extraction → CRM update.
    Returns {created, updated, skipped}.
    """
    stats = {"created": 0, "updated": 0, "skipped": 0}

    if not PU_ENABLED:
        return stats

    # Step 1: Classify document
    meta = classify_meeting(content, path)
    if meta is None:
        return stats

    doc_date = meta["doc_date"]
    doc_title = meta["doc_title"]
    attribution = meta["attribution"]

    # Step 2: Collect people from all sources
    # Format: {slug: {name, email, org, observations, confidence}}
    people: dict[str, dict] = {}

    def _add_person(name: str, email: str = "", org: str = "",
                    observations: list[str] | None = None, confidence: str = "low"):
        if is_self(name):
            return
        parts = name.strip().split()
        if not parts or parts[0] in _NOT_NAMES:
            return

        # Resolve to slug
        if len(parts) >= 2:
            slug = name_to_slug(name)
        else:
            # First-name only: try to find existing profile
            existing = find_existing_by_first_name(parts[0])
            if existing:
                slug = existing.stem
                # Try to recover full name from the profile
                try:
                    profile_content = existing.read_text()
                    m = re.search(r"^# (.+)$", profile_content, re.MULTILINE)
                    if m:
                        name = m.group(1).strip()
                except Exception:
                    pass
            else:
                slug = parts[0].lower()  # single-name slug as fallback

        if slug not in people:
            people[slug] = {
                "name": name,
                "email": email,
                "org": org,
                "observations": [],
                "confidence": confidence,
            }
        else:
            # Upgrade confidence if higher
            if _CONF_RANK.get(confidence, 0) > _CONF_RANK.get(people[slug]["confidence"], 0):
                people[slug]["confidence"] = confidence
            if email and not people[slug]["email"]:
                people[slug]["email"] = email
            if org and not people[slug]["org"]:
                people[slug]["org"] = org

        if observations:
            people[slug]["observations"].extend(observations)

    # Source A: explicit attendee section in document
    for name in get_attendee_section_names(content):
        _add_person(name, confidence="medium",
                   observations=[f"Listed as attendee in: {doc_title}"])

    # Source B: multi-speaker transcript labels
    if attribution == "multi-speaker":
        for name, obs_list in get_multi_speaker_observations(content).items():
            _add_person(name, confidence="high",
                       observations=obs_list[:3])

    # Source C: third-person refs and action items (for single-perspective docs)
    for name, obs_list in get_context_mentions(content).items():
        confidence = "medium" if len(obs_list) >= 2 else "low"
        _add_person(name, confidence=confidence, observations=obs_list[:3])

    # Source D: Google Calendar attendees (most reliable ground truth)
    title_keywords = re.split(r"[\s\-_<>|,]+", doc_title)
    calendar_people = fetch_calendar_attendees(doc_date, title_keywords)

    for cp in calendar_people:
        cal_name = cp["name"]
        cal_email = cp["email"]
        cal_org = cp["org"]
        if is_self(cal_name) or is_self(cal_email):
            continue

        parts = cal_name.strip().split()
        if len(parts) >= 2:
            slug = name_to_slug(cal_name)
        else:
            existing = find_existing_by_first_name(parts[0]) if parts else None
            slug = existing.stem if existing else (parts[0].lower() if parts else "unknown")

        if slug in people:
            # Already found from content — upgrade with email/org + bump to medium if low
            if not people[slug]["email"]:
                people[slug]["email"] = cal_email
            if not people[slug]["org"]:
                people[slug]["org"] = cal_org
            if people[slug]["confidence"] == "low":
                people[slug]["confidence"] = "medium"
                people[slug]["observations"].insert(
                    0, f"Confirmed attendee (calendar): {doc_title}"
                )
        else:
            _add_person(
                cal_name, email=cal_email, org=cal_org,
                confidence="low",
                observations=[f"Attended meeting: {doc_title}"],
            )

    # Step 3: Write CRM updates
    for slug, person in people.items():
        confidence = person["confidence"]
        name = person["name"]
        email = person["email"]
        org = person["org"]
        observations = person["observations"]

        profile_path = PEOPLE_DIR / f"{slug}.md"

        if profile_path.exists():
            # Update existing profile: append to Timeline
            obs_to_write = observations if observations else [f"Attended: {doc_title}"]
            success = append_timeline_entry(
                profile_path, doc_date, obs_to_write, source_key, confidence
            )
            if success:
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

        elif PU_CREATE_NEW and meets_min_confidence(confidence):
            # Create new stub
            create_stub_profile(
                slug=slug,
                name=name,
                email=email,
                org=org,
                doc_date=doc_date,
                meeting_title=doc_title,
                entries=observations if observations else [],
                source_path=source_key,
                confidence=confidence,
            )
            stats["created"] += 1

        else:
            stats["skipped"] += 1

    return stats


if __name__ == "__main__":
    # Quick test: classify a file and report
    if len(sys.argv) < 2:
        print("Usage: python people_updater.py <path-to-md-file>")
        sys.exit(1)

    target = Path(sys.argv[1])
    content = target.read_text(encoding="utf-8")
    meta = classify_meeting(content, target)
    if meta:
        print(f"Meeting detected: {meta}")
        result = update_from_meeting(target, content, str(target.relative_to(VAULT_ROOT)))
        print(f"CRM result: {result}")
    else:
        print("Not classified as a meeting document.")
