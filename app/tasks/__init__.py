# Import celery app first
from app.infra.celery_app import celery_app

# Initialize logging configuration for Celery workers
from app.infra.logging_config import LoggingConfig
from app.tasks.process_nats_event_task import process_nats_event_task

LoggingConfig()  # Initialize logging

__all__ = ["celery_app", "process_nats_event_task"]
