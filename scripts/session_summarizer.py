#!/usr/bin/env python3
"""
session_summarizer.py — Background session summary writer.

Reads the current session JSONL, extracts conversation turns, calls the
Claude API to generate a structured summary, and writes it into the stub
file created by session-end.sh.

Run from session-end.sh as a background subprocess (disowned).
Never blocks the user — if it fails, the stub file stays minimal.

Usage:
    python scripts/session_summarizer.py --summary-file PATH [--jsonl-file PATH]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
MIN_TURNS = 2          # skip summary if session had fewer user turns than this
MAX_CONTENT_CHARS = 60_000  # cap sent to API to control cost


def find_project_dir() -> Path | None:
    home = Path.home()
    projects_base = home / ".claude" / "projects"
    if not projects_base.exists():
        return None
    vault_encoded = str(VAULT_ROOT).replace("_", "-").replace("/", "-")
    candidate = projects_base / vault_encoded
    if candidate.exists():
        return candidate
    vault_name = VAULT_ROOT.name.replace("_", "-")
    for d in projects_base.iterdir():
        if d.is_dir() and vault_name in d.name:
            return d
    return None


def get_latest_jsonl(project_dir: Path) -> Path | None:
    files = sorted(project_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0] if files else None


def extract_conversation(jsonl_path: Path) -> list[dict]:
    """Extract user and assistant text turns from a session JSONL."""
    turns = []
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get("message", {})
                role = msg.get("role")
                if role not in ("user", "assistant"):
                    continue

                content = msg.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                parts.append(f"[tool: {block.get('name', '?')}]")
                        elif isinstance(block, str):
                            parts.append(block)
                    content = "\n".join(parts)

                if isinstance(content, str) and content.strip():
                    turns.append({"role": role, "content": content.strip()})
    except Exception:
        pass
    return turns


def build_transcript(turns: list[dict]) -> str:
    parts = []
    for t in turns:
        prefix = "USER" if t["role"] == "user" else "ASSISTANT"
        text = t["content"][:2000]  # truncate each turn
        parts.append(f"[{prefix}]\n{text}")
    transcript = "\n\n---\n\n".join(parts)
    return transcript[:MAX_CONTENT_CHARS]


def extract_tool_calls(jsonl_path: Path) -> dict:
    """Extract file mutations and tool usage directly from JSONL — no API needed."""
    files_written = []
    files_read = []
    tools_used = set()

    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get("message", {})
                if msg.get("role") != "assistant":
                    continue

                for block in msg.get("content", []):
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    tools_used.add(name)
                    inp = block.get("input", {})
                    path = inp.get("file_path") or inp.get("path", "")
                    if name in ("Write", "Edit") and path:
                        files_written.append(path)
                    elif name == "Read" and path:
                        files_read.append(path)
    except Exception:
        pass

    return {
        "files_written": list(dict.fromkeys(files_written)),  # dedupe, preserve order
        "files_read": list(dict.fromkeys(files_read)),
        "tools_used": sorted(tools_used),
    }


def build_fallback_summary(turns: list[dict], tool_data: dict) -> str:
    """Build a structured summary from JSONL data alone, no API required."""
    user_turns = [t for t in turns if t["role"] == "user"]

    # First user message gives topic context
    first_msg = user_turns[0]["content"][:300].replace("\n", " ") if user_turns else "unknown"

    files_written = tool_data["files_written"]
    files_read = tool_data["files_read"]

    worked_on = f"- Session topic: {first_msg}"
    if len(user_turns) > 1:
        worked_on += f"\n- {len(user_turns)} user messages exchanged"

    files_section = "\n".join(f"- {f}" for f in files_written) if files_written else "- None"

    # Mention files read only if no writes (read-only research session)
    if not files_written and files_read:
        read_section = "\n".join(f"- {f}" for f in files_read[:5])
        files_section = f"- (read-only session)\n{read_section}"

    return f"""## What was worked on
{worked_on}

## Decisions made
- None captured (API unavailable — rerun /session-end to fill in)

## Knowledge updates
- None captured

## Open loops opened
- None captured

## Open loops closed
- None captured

## Files modified
{files_section}"""


def generate_summary(transcript: str) -> str:
    try:
        import anthropic
    except ImportError:
        return ""

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are writing a session summary for a second-brain system. Below is the conversation transcript from a Claude Code session.

Write a concise session summary with these exact sections (keep each section brief — 2-5 bullet points max):

## What was worked on
## Decisions made
## Knowledge updates
## Open loops opened
## Open loops closed
## Files modified

Rules:
- Be specific and factual, not generic
- If a section has nothing to report, write "- None"
- Do not add headers, preamble, or closing remarks outside these sections
- Focus on what actually happened, not meta-commentary

TRANSCRIPT:
{transcript}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else ""
    except Exception:
        return ""


def has_content(summary_file: Path) -> bool:
    """Return True if the summary file already has non-empty section content."""
    try:
        text = summary_file.read_text()
        check = text.split("## What was worked on", 1)
        if len(check) < 2:
            return False
        after = check[1].split("##")[0].strip()
        return bool(after)
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary-file", required=True)
    parser.add_argument("--jsonl-file", default=None)
    args = parser.parse_args()

    summary_path = Path(args.summary_file)

    # Already written by a previous Stop fire this session — skip
    if has_content(summary_path):
        return

    # Find session JSONL
    if args.jsonl_file:
        jsonl_path = Path(args.jsonl_file)
    else:
        project_dir = find_project_dir()
        if not project_dir:
            return
        jsonl_path = get_latest_jsonl(project_dir)
        if not jsonl_path:
            return

    turns = extract_conversation(jsonl_path)
    user_turns = [t for t in turns if t["role"] == "user"]

    # Too few turns — session was trivial, skip
    if len(user_turns) < MIN_TURNS:
        return

    tool_data = extract_tool_calls(jsonl_path)
    transcript = build_transcript(turns)
    summary_content = generate_summary(transcript) or build_fallback_summary(turns, tool_data)

    # Splice content into stub file
    try:
        existing = summary_path.read_text()

        # Replace the empty section stubs with generated content
        # Find where ## What was worked on starts and splice in the content
        marker = "## What was worked on"
        if marker in existing:
            before = existing.split(marker)[0]
            new_text = before + summary_content.strip() + "\n"
            summary_path.write_text(new_text)
    except Exception:
        pass


if __name__ == "__main__":
    main()
