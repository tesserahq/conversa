"""Celery task for syncing context packs from sources."""

from __future__ import annotations

from uuid import UUID

from app.commands.sync_context_for_user_command import SyncContextForUserCommand
from app.services.context_source_state_service import ContextSourceStateService
from app.infra.celery_app import celery_app
from app.infra.logging_config import get_logger
from app.utils.db.db_session_helper import db_session
from tessera_sdk.utils.m2m_token import M2MTokenClient

logger = get_logger("context_sync")


def _get_m2m_token() -> str | None:
    """Get M2M token for source auth. Returns None if unavailable."""
    try:
        return M2MTokenClient().get_token_sync().access_token
    except Exception:
        return None


@celery_app.task(name="app.tasks.context_sync_task.sync_context_for_user_task")
def sync_context_for_user_task(user_id_str: str) -> str | None:
    """
    Sync context from all enabled sources for one user, merge, and store snapshot.
    """
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        logger.warning("Invalid user_id for context sync: %s", user_id_str)
        return None

    m2m_token = _get_m2m_token()
    with db_session() as db:
        command = SyncContextForUserCommand(db, m2m_token=m2m_token)
        result = command.execute(user_id)

    return str(result) if result is not None else user_id_str


@celery_app.task(name="app.tasks.context_sync_task.sync_context_all_due_task")
def sync_context_all_due_task(limit: int = 500) -> int:
    """
    Enumerate (source, user) pairs due for sync and enqueue per-user tasks.
    One task per user (debounced).
    """
    with db_session() as db:
        state_svc = ContextSourceStateService(db)
        pairs = state_svc.get_due_user_source_pairs(limit=limit)

    user_ids = {str(u.id) for _, u in pairs}
    for uid in user_ids:
        sync_context_for_user_task.delay(uid)

    logger.info("Enqueued context sync for %d users", len(user_ids))
    return len(user_ids)
