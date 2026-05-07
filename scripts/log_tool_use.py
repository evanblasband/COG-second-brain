#!/usr/bin/env python3
"""
log_tool_use.py — Tool-use logger called by post-tool-use.sh.

Reads Claude Code's tool JSON from stdin, extracts name and content sizes,
appends a JSONL record to the daily tool log.

Usage (called by hook, not directly):
    CLAUDE_TOOL_NAME=Bash python scripts/log_tool_use.py AI/sessions/YYYY-MM-DD-tool-log.jsonl
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

log_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/tool-log.jsonl")
tool_name_env = os.environ.get("CLAUDE_TOOL_NAME", "unknown")

try:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
    tool_name = data.get("tool_name", tool_name_env)
    input_chars = len(json.dumps(data.get("tool_input", {})))
    output_chars = len(str(data.get("tool_output", "")))
    is_error = bool(data.get("is_error", False))
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "input_chars": input_chars,
        "output_chars": output_chars,
        "is_error": is_error,
    }
except Exception:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name_env,
        "input_chars": 0,
        "output_chars": 0,
        "is_error": False,
    }

log_file.parent.mkdir(parents=True, exist_ok=True)
with open(log_file, "a") as f:
    f.write(json.dumps(record) + "\n")
