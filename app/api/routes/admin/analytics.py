"""Admin API endpoints for analytics and metrics."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Union
from datetime import date, datetime, timedelta
from uuid import UUID

from app.db.base import get_db_session
from app.services.analytics_service import AnalyticsService
from app.core.auth import api_key_auth_read

analytics_router = APIRouter()


@analytics_router.get("/analytics")
async def get_api_analytics(
    from_date: Optional[Union[date, datetime]] = Query(None, description="Start date (YYYY-MM-DD or ISO 8601 datetime with timezone)"),
    to_date: Optional[Union[date, datetime]] = Query(None, description="End date (YYYY-MM-DD or ISO 8601 datetime with timezone)"),
    timezone: Optional[str] = Query("UTC", description="Timezone for date interpretation (e.g., 'UTC', 'America/Los_Angeles')"),
    api_key = Depends(api_key_auth_read),
    db: Session = Depends(get_db_session)
):
    """
    Get API usage analytics broken down by endpoint categories.
    
    Returns metrics for:
    - Feed endpoints (/api/v1/feed/*)
    - Admin endpoints (/api/v1/admin/*)
    - Query endpoints (/api/v1/query/*)
    - Public endpoints (all other /api/v1/* endpoints)
    
    By default returns today's metrics. Can specify date range with from_date and to_date.
    
    If called with organization context (via subdomain or X-Organization header),
    returns metrics only for that organization.
    """
    analytics_service = AnalyticsService(db)
    
    # Validate date range
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="from_date must be before or equal to to_date"
        )
    
    # Limit date range to prevent excessive queries
    if from_date and to_date:
        date_diff = (to_date - from_date).days
        if date_diff > 90:
            raise HTTPException(
                status_code=400,
                detail="Date range cannot exceed 90 days"
            )
    
    # Get organization ID from authenticated API key
    organization_id = api_key.organization_id
    
    return analytics_service.get_api_analytics(
        from_date=from_date,
        to_date=to_date,
        organization_id=organization_id,  # Only show data for this organization
        tz=timezone
    )


@analytics_router.get("/analytics/health")
async def get_api_health(
    api_key = Depends(api_key_auth_read),
    db: Session = Depends(get_db_session)
):
    """
    Get current API health metrics for the last hour.
    
    Returns:
    - Request rate
    - Error rate
    - Average response time
    - Service status by category
    """
    analytics_service = AnalyticsService(db)
    
    # Get metrics for last hour
    now = datetime.now(timezone.utc)
    from_datetime = now - timedelta(hours=1)
    
    # Pass full datetime objects to get proper hourly metrics
    analytics = analytics_service.get_api_analytics(
        from_date=from_datetime,
        to_date=now,
        tz="UTC"  # Health metrics always in UTC
    )
    
    # Calculate health status
    overall = analytics["overall"]
    error_rate = overall["error_rate"]
    avg_response_time = overall["response_times"]["avg"]
    
    # Determine health status
    if error_rate > 10 or avg_response_time > 1000:
        status = "unhealthy"
    elif error_rate > 5 or avg_response_time > 500:
        status = "degraded"
    else:
        status = "healthy"
    
    # Service status by category
    services = {}
    for category in ["feed", "admin", "query", "public"]:
        cat_metrics = analytics["by_category"][category]["metrics"]
        cat_error_rate = cat_metrics["error_rate"]
        cat_avg_time = cat_metrics["avg_response_time"]
        
        if cat_error_rate > 10 or cat_avg_time > 1000:
            services[category] = "unhealthy"
        elif cat_error_rate > 5 or cat_avg_time > 500:
            services[category] = "degraded"
        else:
            services[category] = "healthy"
    
    return {
        "status": status,
        "timestamp": now.isoformat(),
        "metrics": {
            "request_rate": overall["total_requests"],
            "error_rate": error_rate,
            "avg_response_time": avg_response_time,
            "p95_response_time": overall["response_times"]["p95"]
        },
        "services": services,
        "last_hour_requests": overall["total_requests"],
        "last_hour_errors": overall["error_count"]
    }