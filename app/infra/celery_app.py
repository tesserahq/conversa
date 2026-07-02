# pyright: reportMissingTypeStubs=false
from celery import Celery
from celery.schedules import schedule

from app.config import get_settings

settings = get_settings()

celery_app = Celery("conversa-worker")

celery_app.conf.update(
    broker_url=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    result_backend=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    task_default_queue="conversa",  # Use dedicated queue for conversa tasks
    task_routes={
        "app.tasks.*": {"queue": "conversa"},  # Route all app.tasks.* to conversa queue
    },
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Required for celery-exporter (listens to the Celery event bus on the
    # broker) to see this worker's tasks at all — without these, task events
    # are off by default and the exporter has nothing to report.
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Beat schedule for context sync
celery_app.conf.beat_schedule = {
    "sync-context-all-due": {
        "task": "app.tasks.context_sync_task.sync_context_all_due_task",
        "schedule": schedule(run_every=settings.context_sync_interval_seconds),
    },
}

celery_app.autodiscover_tasks(["app.tasks"])  # ensure tasks are registered explicitly

from celery.signals import worker_process_init  # noqa: E402


@worker_process_init.connect
def _on_worker_process_init(sender, **kwargs):
    # Fires once per (post-fork) worker child process, unlike worker_init which
    # runs pre-fork in the parent — the OTLP gRPC exporter connection is not
    # fork-safe, so tracing must be set up here.
    from app.infra.logging_config import get_logger

    logger = get_logger("celery_app")

    if not settings.otel_enabled:
        logger.info("OTel tracing disabled for worker (OTEL_ENABLED is not set)")
        return
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from app.telemetry import setup_tracing

        tracer_provider = setup_tracing()
        CeleryInstrumentor().instrument(tracer_provider=tracer_provider)
        logger.info(
            "OTel tracing enabled for worker "
            f"(endpoint={settings.otel_exporter_otlp_endpoint}, "
            f"service={settings.otel_service_name})"
        )
    except Exception:
        logger.exception("Failed to set up OTel tracing for worker")


# # Explicitly register tasks to ensure they're available
# def register_tasks():
#     """Explicitly import tasks to ensure registration."""
#     try:
#         from app.tasks.process_import_items import process_import_items  # noqa: F401
#         from app.tasks.backfill_digests import backfill_digests_task  # noqa: F401
#         print(f"✅ Tasks registered: process_import_items, backfill_digests_task")
#     except ImportError as e:
#         print(f"⚠️  Warning: Could not import tasks: {e}")

# # Register tasks when this module is imported
# register_tasks()
