"""Tests for scripts/people_updater.py — home-org (internal vs external) tagging.

Locks in the config-driven behavior that replaced the hardcoded employer name:
the internal tag is applied only when a person's org matches the configured
home org (VAULT_HOME_ORG, gitignored); otherwise "external". No employer name
lives in tracked code.
"""

import people_updater as pu


def test_matching_home_org_gets_internal_tag():
    assert pu._org_tag("Acme Corp", home_org="Acme Corp", home_tag="internal") == "internal"


def test_non_matching_org_is_external():
    assert pu._org_tag("Other Inc", home_org="Acme Corp", home_tag="internal") == "external"


def test_unset_home_org_tags_everyone_external():
    # When VAULT_HOME_ORG is blank, nobody is internal.
    assert pu._org_tag("Acme Corp", home_org="", home_tag="internal") == "external"


def test_custom_home_tag_is_honored():
    assert pu._org_tag("Acme Corp", home_org="Acme Corp", home_tag="staff") == "staff"


def test_no_employer_name_hardcoded_in_source():
    # Regression guard for the PII/company scrub: the literal must not return.
    src = (pu.__file__)
    with open(src) as f:
        text = f.read()
    assert "Sage Health" not in text
