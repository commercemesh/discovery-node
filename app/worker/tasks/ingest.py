# app/worker/tasks/ingest.py
"""
Celery tasks for ingesting CMP brand registry and product feed data.
"""
import logging
import json
import os
from datetime import datetime
from celery import shared_task
from app.worker.celery_app import celery_app
from app.ingestors.manager import IngestorManager
from app.core.config import settings

logger = logging.getLogger(__name__)


@shared_task(
    name="ingest:all", bind=True, max_retries=3, default_retry_delay=300  # 5 minutes
)
def ingest_all(self, ingestor_name, ingestor_config):
    """
    Sequentially ingest registry, feed, and vector for a given ingestor.
    Each step only runs if the previous one succeeded.
    """
    try:
        logger.info(f"Starting full ingestion for {ingestor_name}")
        manager = IngestorManager()
        results = {}

        # 1. Registry

        try:
            registry_result = manager.ingest_registry(ingestor_config)
            results["registry"] = {"status": "success", "result": registry_result}
            logger.info(f"Registry ingestion successful for {ingestor_name}")
        except Exception as e:
            logger.exception(
                f"Error in registry ingestion for {ingestor_name}: {e}"
            )
            results["registry"] = {"status": "error", "error": str(e)}
            return {"status": "error", "step": "registry", "results": results}


        # 2. Feed
      
        try:
            feed_result = manager.ingest_feed(ingestor_config)
            results["feed"] = {"status": "success", "result": feed_result}
            logger.info(f"Feed ingestion successful for {ingestor_name}")
        except Exception as e:
            logger.exception(f"Error in feed ingestion for {ingestor_name}: {e}")
            results["feed"] = {"status": "error", "error": str(e)}
            return {"status": "error", "step": "feed", "results": results}
      
        # 3. Vector

        try:
            vector_result = manager.ingest_vector(ingestor_config)
            results["vector"] = {"status": "success", "result": vector_result}
            logger.info(f"Vector ingestion successful for {ingestor_name}")
        except Exception as e:
            logger.exception(f"Error in vector ingestion for {ingestor_name}: {e}")
            results["vector"] = {"status": "error", "error": str(e)}
            return {"status": "error", "step": "vector", "results": results}


        return {"status": "success", "results": results}
    except Exception as e:
        logger.exception(f"Error in full ingestion for {ingestor_name}: {e}")
        return {"status": "error", "step": "unknown", "error": str(e)}


@shared_task(name="ingest:schedule_all")
def schedule_all_ingestors():
    """
    Schedule ingestion tasks for all configured ingestors.
    This task reads the configuration and creates individual tasks.
    This task is called by celery beat to schedule ingestion tasks for all configured ingestors also called on startup if set to true in the config.
    """
    try:
        logger.info("Scheduling ingestion tasks for all configured ingestors")
        manager = IngestorManager()
        ingestors = manager.get_ingestors()
        for ingestor in ingestors:
            logger.info(f"Scheduling full ingestion for {ingestor['name']}")
            ingest_all.delay(ingestor["name"], ingestor)
        return {"status": "success", "message": f"Scheduled {len(ingestors)} ingestors"}
    except Exception as e:
        logger.exception(f"Error scheduling ingestors: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task(
    name="ingest:registry",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def ingest_registry(self, ingestor_name, ingestor_config):
    """
    Ingest a brand registry from the specified source.

    Args:
        ingestor_name: Name of the ingestor (for logging)
        ingestor_config: Full ingestor configuration dictionary
    """
    try:
        source_type = ingestor_config.get("source_type")
        registry_path = ingestor_config.get("registry")
        
        logger.info(
            f"Starting brand registry ingestion for {ingestor_name} from {registry_path}"
        )

        # Create ingestor manager
        manager = IngestorManager()

        # Run registry ingestion
        result = manager.ingest_registry(ingestor_config)

        logger.info(f"Completed brand registry ingestion for {ingestor_name}: {result}")
        return {
            "status": "success",
            "ingestor": ingestor_name,
            "type": "registry",
            "source_type": source_type,
            "path": registry_path,
            "result": result,
        }
    except Exception as e:
        logger.exception(f"Error ingesting registry for {ingestor_name}: {str(e)}")

        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                f"Retrying registry ingestion for {ingestor_name} (attempt {retry_count + 1})"
            )
            self.retry(exc=e)

        return {
            "status": "error",
            "ingestor": ingestor_name,
            "type": "registry",
            "source_type": source_type,
            "path": registry_path,
            "error": str(e),
        }


@shared_task(
    name="ingest:feed", 
    bind=True, 
    max_retries=3, 
    default_retry_delay=300,  # 5 minutes
    time_limit=7200,  # 2 hours hard limit
    soft_time_limit=6600  # 1.75 hours soft limit
)
def ingest_feed(self, ingestor_name, ingestor_config):
    """
    Ingest a product feed from the specified source.
    """
    try:
        source_type = ingestor_config.get("source_type")
        feed_path = ingestor_config.get("feed_path")
        
        logger.info(
            f"Starting product feed ingestion for {ingestor_name} from {feed_path}"
        )
        manager = IngestorManager()
        result = manager.ingest_feed(ingestor_config)
        logger.info(f"Completed product feed ingestion for {ingestor_name}: {result}")


        return {
            "status": "success",
            "ingestor": ingestor_name,
            "type": "feed",
            "source_type": source_type,
            "path": feed_path,
            "result": result,
        }
    except Exception as e:
        logger.exception(f"Error ingesting feed for {ingestor_name}: {str(e)}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                f"Retrying feed ingestion for {ingestor_name} (attempt {retry_count + 1})"
            )
            self.retry(exc=e)
        return {
            "status": "error",
            "ingestor": ingestor_name,
            "type": "feed",
            "source_type": source_type,
            "path": feed_path,
            "error": str(e),
        }


@shared_task(
    name="ingest:vector", bind=True, max_retries=3, default_retry_delay=300  # 5 minutes
)
def ingest_vector(self, ingestor_name, ingestor_config):
    """
    Ingest a vector from the specified source.
    """
    try:
        source_type = ingestor_config.get("source_type")
        registry_path = ingestor_config.get("registry")
        
        logger.info(
            f"Starting vector ingestion for {ingestor_name} from {registry_path}"
        )
        manager = IngestorManager()

        # Run feed ingestion
        result = manager.ingest_vector(ingestor_config)

        logger.info(f"Completed vector ingestion for {ingestor_name}: {result}")

        return {
            "status": "success",
            "ingestor": ingestor_name,
            "type": "vector",
            "source_type": source_type,
            "path": registry_path,
            "result": result,
        }
    except Exception as e:
        logger.exception(f"Error ingesting vector for {ingestor_name}: {str(e)}")

        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                f"Retrying vector ingestion for {ingestor_name} (attempt {retry_count + 1})"
            )
            self.retry(exc=e)


@shared_task(name="ingest:check_feed_updates")
def check_feed_updates():
    """
    Check for updates to product feeds based on timestamps or change detection.
    This task checks for changes and triggers ingestion if updates are detected.
    """
    try:
        logger.info("Checking for feed updates")

        # Create ingestor manager
        manager = IngestorManager()

        # Get all ingestors from configuration
        ingestors = manager.get_ingestors()

        updated_feeds = []

        # Check each feed for updates
        for ingestor in ingestors:
            if not ingestor.get("feed_path"):
                continue

            logger.info(f"Checking for updates to {ingestor['name']} feed")

            # Check if feed has been updated
            if manager.has_feed_updates(ingestor["source_type"], ingestor["feed_path"]):
                logger.info(f"Updates detected for {ingestor['name']} feed")

                # Schedule feed ingestion
                ingest_feed.delay(
                    ingestor["name"], ingestor
                )

                updated_feeds.append(ingestor["name"])

        if updated_feeds:
            return {"status": "success", "updated_feeds": updated_feeds}
        else:
            return {"status": "success", "message": "No feed updates detected"}
    except Exception as e:
        logger.exception(f"Error checking feed updates: {str(e)}")
        return {"status": "error", "message": str(e)}
