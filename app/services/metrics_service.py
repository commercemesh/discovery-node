"""Service for logging API usage metrics asynchronously."""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import SessionLocal
from app.db.repositories.api_usage_metric_repository import APIUsageMetricRepository
from app.schemas.api_usage_metric import APIUsageMetricCreate

logger = logging.getLogger(__name__)

# Thread pool for async database operations
executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="metrics_")


class MetricsService:
    """Service for logging API usage metrics."""
    
    @staticmethod
    def log_api_usage_sync(
        request_id: UUID,
        response_time_ms: int,
        method: str,
        path: str,
        host: Optional[str],
        route_pattern: Optional[str],
        query_params: Optional[Dict[str, Any]],
        status_code: int,
        organization_id: Optional[UUID],
        api_key_id: Optional[UUID],
        ip_address: Optional[str],
        user_agent: Optional[str],
        metrics: Dict[str, Any]
    ) -> None:
        """
        Synchronously log API usage metrics to database.
        This is called from the async wrapper.
        """
        db = None
        try:
            db = SessionLocal()
            metrics_repo = APIUsageMetricRepository(db)
            
            # Create metric record using schema
            metric_create = APIUsageMetricCreate(
                request_id=request_id,
                response_time_ms=response_time_ms,
                method=method,
                path=path,
                host=host,
                route_pattern=route_pattern,
                query_params=query_params,
                status_code=status_code,
                organization_id=organization_id,
                api_key_id=api_key_id,
                ip_address=ip_address,
                user_agent=user_agent,
                metrics=metrics
            )
            
            metrics_repo.create(metric_create)
            
            logger.debug(f"Logged API usage metric for {method} {path} - {status_code}")
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to log API usage metric: {str(e)}")
            if db:
                db.rollback()
        except Exception as e:
            logger.error(f"Unexpected error logging API usage metric: {str(e)}")
        finally:
            if db:
                db.close()
    
    @staticmethod
    async def log_api_usage(
        request_id: UUID,
        response_time_ms: int,
        method: str,
        path: str,
        host: Optional[str],
        route_pattern: Optional[str],
        query_params: Optional[Dict[str, Any]],
        status_code: int,
        organization_id: Optional[UUID],
        api_key_id: Optional[UUID],
        ip_address: Optional[str],
        user_agent: Optional[str],
        metrics: Dict[str, Any]
    ) -> None:
        """
        Asynchronously log API usage metrics.
        Runs in background without blocking the response.
        """
        loop = asyncio.get_event_loop()
        
        # Run the sync database operation in a thread pool
        await loop.run_in_executor(
            executor,
            MetricsService.log_api_usage_sync,
            request_id,
            response_time_ms,
            method,
            path,
            host,
            route_pattern,
            query_params,
            status_code,
            organization_id,
            api_key_id,
            ip_address,
            user_agent,
            metrics
        )
    
    @staticmethod
    def extract_route_pattern(path: str, matched_route: Optional[str] = None) -> Optional[str]:
        """
        Extract the route pattern from the actual path.
        
        Examples:
        - /api/v1/products/123 -> /api/v1/products/{id}
        - /api/v1/organizations/urn:cmp:org:test -> /api/v1/organizations/{org_urn}
        """
        if matched_route:
            return matched_route
        
        # Common patterns to detect
        patterns = [
            # UUID pattern
            (r'/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', '/{id}'),
            # URN pattern
            (r'/(urn:[^/]+)', '/{urn}'),
            # Numeric ID
            (r'/(\d+)$', '/{id}'),
            # Specific endpoints
            (r'/products/[^/]+$', '/products/{urn}'),
            (r'/organizations/[^/]+$', '/organizations/{org_urn}'),
        ]
        
        import re
        for pattern, replacement in patterns:
            if re.search(pattern, path):
                return re.sub(pattern, replacement, path)
        
        return path
    
    @staticmethod
    def parse_custom_headers(headers: dict) -> Dict[str, Any]:
        """Extract custom headers that should be logged."""
        custom_headers = {}
        
        # Headers to capture
        headers_to_capture = [
            'x-request-id',
            'x-correlation-id',
            'x-request-source',
            'x-api-version',
            'x-client-version',
        ]
        
        for header in headers_to_capture:
            if header in headers:
                custom_headers[header] = headers[header]
        
        return custom_headers