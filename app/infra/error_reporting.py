"""Rollbar error reporting shared by the API and the Celery workers."""

from __future__ import annotations

import rollbar

from app.config import get_settings


def init_rollbar() -> None:
    """Initialize the Rollbar SDK with the configured server-side token."""
    settings = get_settings()
    rollbar.init(settings.rollbar_access_token, environment=settings.environment)


def init_rollbar_for_worker(**kwargs) -> None:
    """Initialize Rollbar in each post-fork Celery worker process (production only)."""
    if get_settings().is_production:
        init_rollbar()


def report_task_failure(sender=None, exception=None, traceback=None, **kwargs) -> None:
    """Report a failed Celery task to Rollbar (production only)."""
    if not get_settings().is_production or exception is None:
        return
    rollbar.report_exc_info(
        (type(exception), exception, traceback),
        extra_data={"task": getattr(sender, "name", None)},
    )
