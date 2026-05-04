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

## Pending (not yet set up)

| Integration | Target setup date | Blocker |
|-------------|------------------|---------|
| Google Calendar | | Need OAuth credentials |
| Gmail | | Depends on Google OAuth; work email may not be active |

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
