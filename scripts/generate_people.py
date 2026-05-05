#!/usr/bin/env python3
"""
generate_people.py — Generate 02-people/*.md CRM stubs from an org chart JSON file.

Usage:
    python scripts/generate_people.py [--data PATH]

By default reads from data/org-chart.json (gitignored — never commit that file).

Expected JSON schema per person:
    {
      "name": "First Last",
      "title": "Job Title",
      "department": "Dept Name",
      "location": "HQ | Remote",
      "employment_type": "Employee | Part-time employee | Paid owner",
      "tenure": "X years Y months | Recently joined | Starts on YYYY-MM-DD",
      "reports_count": 0,
      "manager": "Manager Full Name" | null
    }

Skips an entry whose name matches SELF_NAME in config.yaml (or hardcode below).
"""

import argparse
import json
import re
import sys
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
PEOPLE_DIR = VAULT_ROOT / "02-people"
DEFAULT_DATA = VAULT_ROOT / "data" / "org-chart.json"
TODAY = "2026-05-05"
EVAN_START = "2026-05-12"

# Name of the vault owner — skipped in CRM generation
SELF_NAME = "Evan Blasband"

# ─── Relationship tiers — edit to match your actual org ──────────────────────
DIRECT_MANAGER: set[str] = set()      # populated from org data by manager field
DIRECT_TEAM: set[str] = set()         # populated from org data (same manager as self)
COFOUNDERS: set[str] = set()          # populated: anyone with "Co-founder" in title
HARDWARE_ADJACENT: set[str] = set()   # populated: anyone in Hardware Design dept


def load_org(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Error: org chart file not found: {path}", file=sys.stderr)
        print("Create it by saving the org chart JSON to that path (gitignored).", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def build_tiers(org: list[dict]) -> None:
    self_entry = next((p for p in org if p["name"] == SELF_NAME), None)
    if self_entry:
        my_manager = self_entry.get("manager")
        if my_manager:
            DIRECT_MANAGER.add(my_manager)
        for p in org:
            if p["name"] == SELF_NAME:
                continue
            if p.get("manager") == my_manager and my_manager:
                DIRECT_TEAM.add(p["name"])
            if p.get("manager") == SELF_NAME:
                DIRECT_TEAM.add(p["name"])

    for p in org:
        if "co-founder" in p["title"].lower():
            COFOUNDERS.add(p["name"])
        if "hardware" in p.get("department", "").lower():
            HARDWARE_ADJACENT.add(p["name"])


def relationship_tier(person: dict) -> str:
    name = person["name"]
    if name in DIRECT_MANAGER:
        return "direct-manager"
    if name in DIRECT_TEAM:
        return "direct-team"
    if name in COFOUNDERS:
        return "cofounder-leadership"
    if name in HARDWARE_ADJACENT:
        return "hardware-adjacent"
    return "colleague"


def priority_note(tier: str) -> str:
    notes = {
        "direct-manager":      "DIRECT MANAGER — meet Day 1, understand working style immediately",
        "direct-team":         "DIRECT TEAM — meet first week, understand current work and gaps",
        "cofounder-leadership":"CO-FOUNDER / C-SUITE — understand their priorities and communication style",
        "hardware-adjacent":   "HARDWARE-ADJACENT — likely frequent collaborator on architecture/HW projects",
    }
    return notes.get(tier, "")


def reports_str(count: int) -> str:
    if count == 0:
        return "Individual contributor"
    return f"{count} direct report{'s' if count > 1 else ''}"


def scope_from_title(title: str) -> str:
    t = title.lower()
    if "co-founder" in t and "ceo" in t:
        return "Company strategy, investor relations, go-to-market, overall execution"
    if "co-founder" in t and "cto" in t:
        return "Engineering org, technical strategy, product architecture"
    if "co-founder" in t and "cpo" in t:
        return "Product strategy, design, hardware product, clinical"
    if "coo" in t:
        return "Operations, customer success, growth, revenue operations"
    if "cmo" in t or "chief marketing" in t:
        return "Brand, demand gen, content, events, product marketing"
    if "chief sales" in t:
        return "Sales strategy, revenue, new business"
    if "vp of engineering" in t:
        return "Engineering org management, delivery, technical execution"
    if "vp of finance" in t:
        return "Financial planning, accounting, budgeting"
    if "head of hardware" in t:
        return "Hardware design team, device architecture, supplier relationships"
    if "head of product design" in t:
        return "UX/design team, design system, user research"
    if "head of product" in t:
        return "Product roadmap, PM team, feature prioritization"
    if "head of analytics" in t:
        return "Data platform, analytics engineering, data science"
    if "head of people" in t:
        return "People ops, recruiting, culture, HR"
    if "head of clinical" in t:
        return "Clinical validation, care workflow, regulatory positioning"
    if "head of sales" in t:
        return "Sales team, pipeline, quota management"
    if "head of growth" in t:
        return "Client expansion, upsell, account growth"
    if "head of implementation" in t:
        return "Client onboarding, field deployment, implementation team"
    if "head of client operations" in t:
        return "Client ops, RevOps, SDR, support, implementation"
    if "head of" in t:
        return "Team leadership and execution for their domain"
    if "gm" in t:
        return "General management for their product line or vertical"
    if "systems engineering architect" in t:
        return "Systems-level hardware architecture, cross-functional integration"
    if "hardware solutions architect" in t:
        return "Hardware architecture, technology evaluation, connectivity strategy"
    if "engineering architect" in t:
        return "Technical architecture for their product area"
    if "supply chain" in t:
        return "Hardware supply chain, vendor management, procurement"
    if "iot" in t and "software" in t:
        return "IoT firmware/software, device connectivity"
    if "edge iot" in t:
        return "Edge computing software for IoT devices"
    if "integrations" in t:
        return "Third-party integrations, API connectors"
    return "Day-to-day execution within their team"


def name_to_slug(name: str) -> str:
    parts = name.strip().split()
    # Remove duplicate consecutive last name (e.g. "Jim Turner Turner")
    if len(parts) >= 2 and parts[-1] == parts[-2]:
        parts = parts[:-1]
    slug = "-".join(parts).lower()
    slug = re.sub(r"[^\w-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def generate_file(person: dict) -> tuple[str, str]:
    name = person["name"]
    title = person["title"]
    dept = person["department"]
    location = person["location"]
    tenure = person["tenure"]
    reports = person["reports_count"]
    manager = person.get("manager") or "None (C-suite)"
    emp_type = person["employment_type"]
    tier = relationship_tier(person)
    priority = priority_note(tier)
    scope = scope_from_title(title)

    tags = ["crm", "people"]
    if "co-founder" in title.lower():
        tags.append("cofounder")
    if tier in ("direct-manager", "direct-team"):
        tags.append("direct-team")
    if "hardware" in dept.lower() or "hardware" in title.lower():
        tags.append("hardware")

    frontmatter = f"""---
created: {TODAY}
updated: {TODAY}
type: people
tags: {tags}
status: active
source: internal
confidence: high
department: {dept}
manager: {manager}
location: {location}
---"""

    priority_block = f"\n> {priority}\n" if priority else ""

    body = f"""# {name}
{priority_block}
## Executive Snapshot

- {title}, {dept} dept, reports to {manager} [{reports_str(reports)}] [Source: org-chart | {TODAY} | confidence: high]
- Tenure: {tenure} | Location: {location} | Employment: {emp_type} [Source: org-chart | {TODAY} | confidence: high]

## Role & Responsibilities

- **Title:** {title}
- **Department:** {dept}
- **Reports to:** {manager}
- **Direct reports:** {reports_str(reports)}
- **Location:** {location}
- **Scope:** {scope}
- **Projects shared with me:** TBD — fill in from interactions

## Working Style

- **Communication:** Unknown — update after first interaction
- **Decision-making:** Unknown
- **Meeting style:** Unknown

## Strengths

- Unknown — update after working together

## How to Work With Effectively

- Unknown — update from interactions

## Relationship Context

- **First met:** Not yet (starts {EVAN_START})
- **How connected:** Colleague
- **Relationship quality:** unknown

## Open Threads

-

---

## Timeline (Append-Only)

### {TODAY}
- Added from org chart, pre-start date. Not yet met. [Source: org-chart | {TODAY} | confidence: high]
"""

    slug = name_to_slug(name)
    return f"{slug}.md", frontmatter + "\n\n" + body


def main():
    parser = argparse.ArgumentParser(description="Generate people CRM stubs from org chart JSON")
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="Path to org chart JSON file")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    org = load_org(Path(args.data))
    build_tiers(org)
    PEOPLE_DIR.mkdir(parents=True, exist_ok=True)

    created = skipped = 0
    for person in org:
        if person["name"] == SELF_NAME:
            skipped += 1
            continue

        filename, content = generate_file(person)
        path = PEOPLE_DIR / filename

        if path.exists() and not args.overwrite:
            skipped += 1
            continue

        path.write_text(content)
        tier = relationship_tier(person)
        marker = " *" if tier in ("direct-manager", "direct-team") else ""
        print(f"  created: {filename}{marker}")
        created += 1

    print(f"\nDone — {created} files created, {skipped} skipped")


if __name__ == "__main__":
    main()
