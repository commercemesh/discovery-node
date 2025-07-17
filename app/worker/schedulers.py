# app/worker/schedulers.py
"""
Scheduled task definitions for Celery Beat.
"""
import logging
import yaml
import os
from pathlib import Path
from celery.schedules import crontab, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_beat_schedule():
    """
    Generate Celery Beat schedule from configuration.

    Returns:
        Dict of scheduled tasks
    """
    schedule = {
        # Default scheduled tasks
        "check-feed-updates": {
            "task": "ingest:check_feed_updates",
            "schedule": timedelta(seconds=settings.FEED_CHECK_INTERVAL),
            "options": {"expires": 3600},
        }
    }

    # Add ingestion tasks from configuration
    try:
        # Load ingestion configuration
        ingestion_config_path = settings.INGESTION_CONFIG_PATH

        if not os.path.exists(ingestion_config_path):
            logger.warning(
                f"Ingestion configuration file not found: {ingestion_config_path}"
            )
            return schedule

        with open(ingestion_config_path, "r") as f:
            config = yaml.safe_load(f)

        if not config or "ingestion" not in config:
            logger.warning("No ingestors defined in configuration")
            return schedule

        # Process each ingestor
        for ingestor in config["ingestion"]:
            name = ingestor.get("name", "unnamed")

            if "schedule" not in ingestor:
                logger.warning(f"No schedule defined for ingestor {name}")
                continue

            cron_schedule = ingestor["schedule"]

            # Parse cron schedule (format: "minute hour day month day_of_week")
            # Example: "0 */4 * * *" = every 4 hours
            try:
                parts = cron_schedule.split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    schedule_obj = crontab(
                        minute=minute,
                        hour=hour,
                        day_of_month=day,
                        month_of_year=month,
                        day_of_week=day_of_week,
                    )
                else:
                    # Fallback to every 4 hours if parsing fails
                    logger.warning(
                        f"Invalid cron schedule format: {cron_schedule}, using default"
                    )
                    schedule_obj = crontab(minute=0, hour="*/4")
            except Exception as e:
                logger.warning(
                    f"Error parsing cron schedule {cron_schedule}: {str(e)}, using default"
                )
                schedule_obj = crontab(minute=0, hour="*/4")

            # Schedule only the ingest:all task for this ingestor
            task_name = f"ingest-all-{name}"
            schedule[task_name] = {
                "task": "ingest:all",
                "schedule": schedule_obj,
                "args": (name, ingestor),
                "options": {"expires": 3600},
            }

    except Exception as e:
        logger.exception(f"Error loading ingestion configuration: {str(e)}")

    return schedule
