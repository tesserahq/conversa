"""Identies event names follow the configured EVENT_TYPE_PREFIX."""

import pytest

from app.core.identies_events import IdentiesEventNames


@pytest.mark.parametrize("prefix", ["com.identies", "com.mylinden"])
def test_event_names_are_namespaced_by_the_prefix(prefix):
    names = IdentiesEventNames(prefix)

    assert names.subscription == f"{prefix}.>"
    assert names.user_created == f"{prefix}.user.created"
    assert names.user_updated == f"{prefix}.user.updated"
    assert names.external_account_linked == f"{prefix}.external_account.linked"


def test_default_prefix_matches_production():
    from app.config import get_settings

    assert get_settings().identies_event_prefix == "com.identies"
