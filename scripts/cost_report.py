#!/usr/bin/env python3
"""
cost_report.py — Real-cost reporting from Claude Code session JSONL files.

Parses actual token usage from Claude Code's session logs (in ~/.claude/projects/).
Reports input_tokens, cache tokens, output_tokens, and calculated USD cost.

Usage:
    python scripts/cost_report.py session               # most recent session
    python scripts/cost_report.py session --file PATH   # specific JSONL file
    python scripts/cost_report.py daily                 # all sessions today
    python scripts/cost_report.py weekly                # all sessions this week

Called by session-end.sh automatically at session close.
Output format: markdown block suitable for appending to session summaries.
"""

import argparse
import json
import sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent

# Sonnet 5 pricing (USD per million tokens)
PRICING = {
    "input": 3.00,
    "cache_write": 3.75,
    "cache_read": 0.30,
    "output": 15.00,
}


# ─── Session JSONL location ────────────────────────────────────────────────────

def find_project_dir() -> Path | None:
    """Locate the Claude Code project directory for this vault."""
    home = Path.home()
    projects_base = home / ".claude" / "projects"
    if not projects_base.exists():
        return None

    # Claude Code encodes the vault path by replacing / and _ with -
    vault_encoded = str(VAULT_ROOT).replace("_", "-").replace("/", "-")
    candidate = projects_base / vault_encoded
    if candidate.exists():
        return candidate

    # Fallback: find by partial match on vault name
    vault_name = VAULT_ROOT.name.replace("_", "-")
    for d in projects_base.iterdir():
        if d.is_dir() and vault_name in d.name:
            return d

    return None


def get_session_files(project_dir: Path, since: datetime | None = None) -> list[Path]:
    """Return JSONL session files, optionally filtered by date."""
    files = sorted(project_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    if since:
        since_ts = since.timestamp()
        files = [f for f in files if f.stat().st_mtime >= since_ts]
    return files


# ─── JSONL parsing ─────────────────────────────────────────────────────────────

def parse_usage(jsonl_path: Path) -> dict:
    """
    Parse a session JSONL file and sum all token usage from assistant messages.
    Returns aggregated usage dict and per-message list.
    """
    totals = {
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
        "messages": 0,
        "tool_calls": 0,
    }
    messages = []

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

                usage = msg.get("usage")
                if not usage:
                    continue

                # Count tool calls in this message
                tool_count = sum(
                    1 for block in msg.get("content", [])
                    if isinstance(block, dict) and block.get("type") == "tool_use"
                )

                # Accumulate
                in_tok = usage.get("input_tokens", 0)
                cache_write = usage.get("cache_creation_input_tokens", 0)
                cache_read = usage.get("cache_read_input_tokens", 0)
                out_tok = usage.get("output_tokens", 0)

                totals["input_tokens"] += in_tok
                totals["cache_creation_input_tokens"] += cache_write
                totals["cache_read_input_tokens"] += cache_read
                totals["output_tokens"] += out_tok
                totals["messages"] += 1
                totals["tool_calls"] += tool_count

                messages.append({
                    "input": in_tok,
                    "cache_write": cache_write,
                    "cache_read": cache_read,
                    "output": out_tok,
                    "tools": tool_count,
                    "model": msg.get("model", "unknown"),
                })

    except (OSError, PermissionError):
        pass

    return totals, messages


def calculate_cost(usage: dict) -> float:
    """Calculate USD cost from token usage dict."""
    return (
        usage.get("input_tokens", 0) / 1_000_000 * PRICING["input"] +
        usage.get("cache_creation_input_tokens", 0) / 1_000_000 * PRICING["cache_write"] +
        usage.get("cache_read_input_tokens", 0) / 1_000_000 * PRICING["cache_read"] +
        usage.get("output_tokens", 0) / 1_000_000 * PRICING["output"]
    )


# ─── Report formatting ─────────────────────────────────────────────────────────

def format_session_report(jsonl_path: Path) -> str:
    """Format a cost block for a single session JSONL."""
    usage, _ = parse_usage(jsonl_path)
    cost = calculate_cost(usage)
    total_input = usage["input_tokens"] + usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]

    if usage["messages"] == 0:
        return "## Session Cost\n\n_No API usage data found in session log._\n"

    cache_savings_tok = usage["cache_read_input_tokens"]
    cache_savings_usd = cache_savings_tok / 1_000_000 * (PRICING["input"] - PRICING["cache_read"])

    lines = [
        "## Session Cost\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| API messages | {usage['messages']} |",
        f"| Tool calls | {usage['tool_calls']} |",
        f"| Input tokens | {usage['input_tokens']:,} |",
        f"| Cache write | {usage['cache_creation_input_tokens']:,} |",
        f"| Cache read | {usage['cache_read_input_tokens']:,} |",
        f"| Output tokens | {usage['output_tokens']:,} |",
        f"| **Total cost** | **${cost:.4f}** |",
    ]

    if cache_savings_usd > 0.001:
        lines.append(f"| Cache saved | ${cache_savings_usd:.4f} |")

    lines.append("")
    lines.append(f"_Pricing: Sonnet 4.6 — input ${PRICING['input']}/MTok, cache read ${PRICING['cache_read']}/MTok, output ${PRICING['output']}/MTok_")
    lines.append("")

    return "\n".join(lines)


def format_multi_session_report(title: str, files: list[Path]) -> str:
    """Format an aggregated report across multiple session files."""
    if not files:
        return f"## {title}\n\n_No sessions found._\n"

    grand = {
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
        "messages": 0,
        "tool_calls": 0,
    }
    session_rows = []

    for f in files:
        usage, _ = parse_usage(f)
        cost = calculate_cost(usage)
        if usage["messages"] == 0:
            continue
        session_rows.append((f.stem[:16], usage["messages"], usage["output_tokens"], cost))
        for k in grand:
            grand[k] += usage.get(k, 0)

    if not session_rows:
        return f"## {title}\n\n_No API usage found._\n"

    total_cost = calculate_cost(grand)
    cache_savings = (grand["cache_read_input_tokens"] / 1_000_000 *
                     (PRICING["input"] - PRICING["cache_read"]))

    lines = [f"## {title}\n"]

    # Summary
    lines += [
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Sessions | {len(session_rows)} |",
        f"| API messages | {grand['messages']} |",
        f"| Output tokens | {grand['output_tokens']:,} |",
        f"| **Total cost** | **${total_cost:.4f}** |",
    ]
    if cache_savings > 0.001:
        lines.append(f"| Cache saved | ${cache_savings:.4f} |")
    lines.append("")

    # Per-session breakdown
    if len(session_rows) > 1:
        lines.append("### By Session\n")
        lines.append("| Session | Messages | Output tok | Cost |")
        lines.append("|---------|----------|-----------|------|")
        for session_id, msgs, out_tok, cost in session_rows:
            lines.append(f"| `{session_id}` | {msgs} | {out_tok:,} | ${cost:.4f} |")
        lines.append("")

    return "\n".join(lines)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Cost report from Claude Code session logs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("mode", choices=["session", "daily", "weekly"],
                        help="Reporting scope")
    parser.add_argument("--file", help="Specific JSONL file to report on (session mode only)")
    parser.add_argument("--append-to", help="Append report to this file instead of printing")
    args = parser.parse_args()

    project_dir = find_project_dir()

    if args.mode == "session":
        if args.file:
            jsonl = Path(args.file)
        elif project_dir:
            files = get_session_files(project_dir)
            jsonl = files[0] if files else None
        else:
            jsonl = None

        if not jsonl or not jsonl.exists():
            print("No session JSONL found.", file=sys.stderr)
            sys.exit(0)

        report = format_session_report(jsonl)

    elif args.mode == "daily":
        if not project_dir:
            print("Project directory not found.", file=sys.stderr)
            sys.exit(0)
        today_start = datetime.combine(date.today(), datetime.min.time())
        files = get_session_files(project_dir, since=today_start)
        report = format_multi_session_report(
            f"Daily Cost — {date.today().strftime('%Y-%m-%d')}", files
        )

    elif args.mode == "weekly":
        if not project_dir:
            print("Project directory not found.", file=sys.stderr)
            sys.exit(0)
        week_start = datetime.combine(date.today() - timedelta(days=7), datetime.min.time())
        files = get_session_files(project_dir, since=week_start)
        report = format_multi_session_report(
            f"Weekly Cost — last 7 days", files
        )

    if args.append_to:
        out_path = Path(args.append_to)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "a") as f:
            f.write("\n\n---\n\n")
            f.write(report)
        print(f"Cost report appended to {out_path}", file=sys.stderr)
    else:
        print(report)


if __name__ == "__main__":
    main()
