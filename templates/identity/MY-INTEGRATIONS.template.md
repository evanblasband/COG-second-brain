---
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: reference
tags: [integrations, config]
status: active
source: internal
---

# My Integrations

Skills check this file before using any external service. Do not attempt to call tools for disabled integrations.

## Active

| Integration | Auth method | Scope | Notes |
|-------------|-------------|-------|-------|
| GitHub | `gh` CLI | | username: [from GITHUB_USER in .env] |

## Active via MCP (connected through claude.ai — no extra setup)

| Integration | MCP tool prefix | Notes |
|-------------|----------------|-------|
| Google Calendar | `mcp__claude_ai_Google_Calendar__` | Use in interactive Claude sessions |
| Gmail | `mcp__claude_ai_Gmail__` | Use in interactive Claude sessions |

## Pending (Python CLI — needed for background agents only)

| Integration | Blocker | Notes |
|-------------|---------|-------|
| Google Calendar CLI | Need Google Cloud credentials JSON | Only required for heartbeat/cron — not for interactive sessions |
| Gmail CLI | Same as above | Week 2 |

## Disabled

| Integration | Reason |
|-------------|--------|
| Slack | No workspace access yet |
| Confluence | No account yet |
| Foundry | No access yet |

## Notes

- Emails and usernames come from `.env` — never hardcode them here
- When work email is provisioned, re-run Google OAuth and update the Active table
- For any integration not listed, ask before attempting to call it
