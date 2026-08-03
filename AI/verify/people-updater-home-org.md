# Verify — people_updater home-org config-driven (PII follow-up)

**Branch:** `cog/people-updater-home-org` · **Date:** 2026-08-03 · **Result:** ✅ PASS

## What / why
Follow-up to the 2026-08-03 public-repo PII scrub. `scripts/people_updater.py:518` hardcoded
`org_tag = "sage" if org == "Sage Health" else "external"` — an employer name in tracked
(public) code. Made it config-driven, matching the existing `VAULT_DOMAIN_ORG_MAP` convention
(org data in gitignored `.env`).

## Changes
- `scripts/people_updater.py`: added `_HOME_ORG`/`_HOME_ORG_TAG` (from env `VAULT_HOME_ORG` /
  `VAULT_HOME_ORG_TAG`) + a testable `_org_tag(org, home_org=, home_tag=)` helper; replaced the
  hardcoded line with `_org_tag(org)`. No employer literal remains.
- `.env.example`: documented `VAULT_HOME_ORG` / `VAULT_HOME_ORG_TAG` (generic placeholders).
- `tests/test_people_updater.py` (NEW): 5 tests — match→internal, non-match→external,
  unset-home-org→external, custom tag honored, and a regression guard asserting "Sage Health"
  is not in the source.

## Verification
```
grep '"sage"|Sage Health' scripts/people_updater.py  -> none ✓
.venv/bin/pytest -q  -> 14 passed  (9 prior + 5 new)
```

## Operational note (behavior change)
Internal tagging now requires `VAULT_HOME_ORG` in `.env` (gitignored). Until it's set, new CRM
stubs tag everyone `external`. To preserve prior behavior set:
`VAULT_HOME_ORG=Sage Health` and (to keep the old "sage" tag) `VAULT_HOME_ORG_TAG=sage`.
