# app/worker/celery_app.py
"""
Celery application configuration for the CMP discovery node.
"""
from celery import Celery
from celery.signals import worker_ready
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "cmp_discovery",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.worker.tasks.ingest",
        "app.worker.tasks.cleanup",
        "app.worker.tasks.embeddings",
    ],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_time_limit=3600,  # 1 hour time limit per task
    task_soft_time_limit=3300,  # 55 minutes soft time limit
    # Queue configuration
    task_routes={
        "embeddings:generate_single": {"queue": "embeddings_high"},
        "embeddings:generate_batch": {"queue": "embeddings_bulk"},
        "embeddings:regenerate_organization": {"queue": "embeddings_bulk"},
        "ingest:*": {"queue": "celery"},  # Default queue for ingestion tasks
        "cleanup:*": {"queue": "celery"},  # Default queue for cleanup tasks
    },
    # Define queues
    task_queues={
        "celery": {
            "exchange": "celery",
            "routing_key": "celery",
        },
        "embeddings_high": {
            "exchange": "embeddings",
            "routing_key": "embeddings.high",
            "priority": 10,  # Higher priority
        },
        "embeddings_bulk": {
            "exchange": "embeddings",
            "routing_key": "embeddings.bulk",
            "priority": 5,  # Lower priority
        },
    },
)

# Load periodic tasks from scheduler
celery_app.conf.beat_schedule = {}

# Load beat schedule from scheduler module
from app.worker.schedulers import get_beat_schedule

celery_app.conf.beat_schedule.update(get_beat_schedule())


@worker_ready.connect
def at_worker_ready(sender, **kwargs):
    """Log when worker is ready and schedule initial tasks."""
    logger.info("Celery worker is ready.")

    # Import here to avoid circular imports
    from app.worker.tasks.ingest import schedule_all_ingestors

    # Schedule initial ingestion
    print(f"TRIGGER_INGESTION_ON_STARTUP: {settings.TRIGGER_INGESTION_ON_STARTUP}")
    if settings.TRIGGER_INGESTION_ON_STARTUP:
        logger.info("Scheduling initial ingestion tasks...")
        schedule_all_ingestors.delay()


if __name__ == "__main__":
    celery_app.start()
