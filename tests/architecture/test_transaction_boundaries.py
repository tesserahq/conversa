"""Architecture guards for transaction ownership, provided by
tessera_sdk.testing.transaction_guards (see docs/managed-transactions.md in
tessera-sdk-py).

Every transaction rule is fully enforced, so any violation fails. The only
exceptions are the reasoned early commits in ``early_commit_allowlist``.

``async_database_access`` (synchronous database access inside ``async def``,
linden-api SDD 0012) starts from the violations listed in
``transaction_baseline.json``; each fix removes its entry. Regenerate it with
``UPDATE_TRANSACTION_BASELINE=1 pytest tests/architecture``.
"""

from pathlib import Path

import pytest
from tessera_sdk.testing.transaction_guards import (
    DEFAULT_TRANSACTION_DIRS,
    EVENT_LOOP_RULE_NAMES,
    RULE_NAMES,
    TransactionGuardConfig,
    assert_matches_baseline,
)

CONFIG = TransactionGuardConfig(
    app_root=Path(__file__).parents[2] / "app",
    baseline_path=Path(__file__).with_name("transaction_baseline.json"),
    transaction_dirs=(
        *DEFAULT_TRANSACTION_DIRS,
        "middleware",
        "core",
        "messaging",
        "workers",
        "channels",
        "adapters",
        "gateway",
    ),
    session_modules=("db.py", "services/sdk_user_service.py"),
    repository_base_modules=(),
    # Allowlisted top-level workflows that commit early around external I/O:
    # (path relative to app/, function name) -> reason.
    early_commit_allowlist={
        ("commands/sync_context_for_user_command.py", "_fetch_packs_from_sources"): (
            "context sources are fetched over HTTP: commit the new sync states "
            "first, then checkpoint each source's state after its fetch"
        ),
    },
)


@pytest.mark.parametrize("rule", RULE_NAMES)
def test_transaction_rule_matches_baseline(rule):
    assert_matches_baseline(CONFIG, rule)


@pytest.mark.parametrize("rule", EVENT_LOOP_RULE_NAMES)
def test_event_loop_rule_matches_baseline(rule):
    """Synchronous database access in ``async def`` blocks the event loop
    (linden-api SDD 0012)."""
    assert_matches_baseline(CONFIG, rule)
