# app/worker/tasks/embeddings.py
"""
Celery tasks for generating product embeddings in real-time.
"""
import logging
from typing import List
from celery import shared_task
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.services.vector_service import VectorService
from app.core.config import settings

logger = logging.getLogger(__name__)


@shared_task(
    name="embeddings:generate_single",
    bind=True,
    queue="embeddings_high",
    rate_limit="1000/m",
    max_retries=3,
    default_retry_delay=60,  # 1 minute
)
def generate_embedding_single(self, product_urn: str):
    """
    Generate embeddings for a single product.
    Used for real-time updates when products are created/updated via API.
    
    Args:
        product_urn: The URN of the product to process
    """
    try:
        logger.info(f"Starting embedding generation for product: {product_urn}")
        
        db_session = SessionLocal()
        try:
            vector_service = VectorService(db_session)
            result = vector_service.upsert_product_by_urn(product_urn)
            
            if result.successful_records > 0:
                logger.info(f"Successfully generated embeddings for product: {product_urn}")
                return {
                    "status": "success",
                    "product_urn": product_urn,
                    "dense_index": result.dense_index_success,
                    "sparse_index": result.sparse_index_success,
                }
            else:
                logger.error(f"Failed to generate embeddings for product: {product_urn}")
                return {
                    "status": "failed",
                    "product_urn": product_urn,
                    "errors": result.errors,
                }
                
        finally:
            db_session.close()
            
    except Exception as e:
        logger.exception(f"Error generating embedding for {product_urn}: {str(e)}")
        
        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                f"Retrying embedding generation for {product_urn} (attempt {retry_count + 1})"
            )
            self.retry(exc=e, countdown=60 * (retry_count + 1))  # Exponential backoff
        
        return {
            "status": "error",
            "product_urn": product_urn,
            "error": str(e),
        }


@shared_task(
    name="embeddings:generate_batch",
    bind=True,
    queue="embeddings_bulk",
    rate_limit="10000/h",
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    time_limit=3600,  # 1 hour hard limit
    soft_time_limit=3300,  # 55 minutes soft limit
)
def generate_embeddings_batch(self, product_urns: List[str]):
    """
    Generate embeddings for a batch of products.
    Used for bulk imports where many products are created at once.
    
    Args:
        product_urns: List of product URNs to process
    """
    try:
        logger.info(f"Starting batch embedding generation for {len(product_urns)} products")
        
        db_session = SessionLocal()
        try:
            vector_service = VectorService(db_session)
            result = vector_service.upsert_products_by_urns(product_urns)
            
            logger.info(
                f"Batch embedding generation completed: "
                f"{result.successful_records}/{result.total_products} successful"
            )
            
            return {
                "status": "completed" if not result.errors else "partial_failure",
                "total_products": result.total_products,
                "successful_records": result.successful_records,
                "failed_records": result.failed_records,
                "dense_index_success": result.dense_index_success,
                "sparse_index_success": result.sparse_index_success,
                "errors": result.errors[:10] if result.errors else [],  # Limit errors in response
                "processing_time_seconds": result.processing_time,
            }
            
        finally:
            db_session.close()
            
    except Exception as e:
        logger.exception(f"Error in batch embedding generation: {str(e)}")
        
        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                f"Retrying batch embedding generation (attempt {retry_count + 1})"
            )
            self.retry(exc=e, countdown=300 * (retry_count + 1))  # Exponential backoff
        
        return {
            "status": "error",
            "total_products": len(product_urns),
            "error": str(e),
        }


@shared_task(
    name="embeddings:regenerate_organization",
    bind=True,
    queue="embeddings_bulk",
    rate_limit="1/h",  # Limit to prevent accidental overuse
    max_retries=3,
    default_retry_delay=600,  # 10 minutes
    time_limit=7200,  # 2 hours hard limit
    soft_time_limit=6600,  # 1.75 hours soft limit
)
def regenerate_organization_embeddings(self, organization_id: str):
    """
    Regenerate all embeddings for an organization.
    Useful for bulk updates or when switching embedding models.
    
    Args:
        organization_id: UUID of the organization
    """
    try:
        logger.info(f"Starting embedding regeneration for organization: {organization_id}")
        
        db_session = SessionLocal()
        try:
            from uuid import UUID
            org_uuid = UUID(organization_id)
            
            vector_service = VectorService(db_session)
            result = vector_service.upsert_products(org_uuid)
            
            logger.info(
                f"Organization embedding regeneration completed: "
                f"{result.successful_records}/{result.total_products} successful"
            )
            
            return {
                "status": "completed" if not result.errors else "partial_failure",
                "organization_id": organization_id,
                "total_products": result.total_products,
                "successful_records": result.successful_records,
                "failed_records": result.failed_records,
                "dense_index_success": result.dense_index_success,
                "sparse_index_success": result.sparse_index_success,
                "errors": result.errors[:10] if result.errors else [],  # Limit errors
                "processing_time_seconds": result.processing_time,
            }
            
        finally:
            db_session.close()
            
    except Exception as e:
        logger.exception(f"Error regenerating embeddings for org {organization_id}: {str(e)}")
        
        # Retry with exponential backoff
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            logger.info(
                f"Retrying organization embedding regeneration (attempt {retry_count + 1})"
            )
            self.retry(exc=e, countdown=600 * (retry_count + 1))
        
        return {
            "status": "error",
            "organization_id": organization_id,
            "error": str(e),
        }