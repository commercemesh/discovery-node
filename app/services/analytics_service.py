"""Service for API analytics and metrics aggregation."""
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, date, time, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from uuid import UUID
import pytz

from app.db.models.api_usage_metric import APIUsageMetric
from app.db.repositories.api_usage_metric_repository import APIUsageMetricRepository
from app.schemas.api_usage_metric import APIAnalyticsResponse


class AnalyticsService:
    """Service for retrieving and aggregating API usage analytics."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.metrics_repo = APIUsageMetricRepository(db_session)
    
    def get_api_analytics(
        self,
        from_date: Optional[Union[date, datetime]] = None,
        to_date: Optional[Union[date, datetime]] = None,
        organization_id: Optional[UUID] = None,
        tz: str = "UTC"
    ) -> Dict[str, Any]:
        """
        Get comprehensive API analytics broken down by endpoint categories.
        
        Args:
            from_date: Start date/datetime (defaults to today in specified timezone)
            to_date: End date/datetime (defaults to today in specified timezone)
            organization_id: Optional filter by organization
            tz: Timezone for date interpretation (default: UTC)
            
        Returns:
            Dictionary with analytics broken down by feed, admin, query, and public endpoints
        """
        # Get timezone object
        try:
            timezone_obj = pytz.timezone(tz)
        except pytz.exceptions.UnknownTimeZoneError:
            timezone_obj = pytz.UTC
        
        # Default to today in the specified timezone if no dates provided
        now_in_tz = datetime.now(timezone_obj)
        if not from_date:
            from_date = now_in_tz.date()
        if not to_date:
            to_date = now_in_tz.date()
        
        # Convert to timezone-aware datetime objects
        if isinstance(from_date, date) and not isinstance(from_date, datetime):
            # Convert date to datetime at start of day in specified timezone
            start_datetime = timezone_obj.localize(datetime.combine(from_date, time.min))
        elif isinstance(from_date, datetime):
            # If datetime is naive, localize it to the specified timezone
            if from_date.tzinfo is None:
                start_datetime = timezone_obj.localize(from_date)
            else:
                # Already timezone-aware, use as is
                start_datetime = from_date
        
        if isinstance(to_date, date) and not isinstance(to_date, datetime):
            # Convert date to datetime at end of day in specified timezone
            end_datetime = timezone_obj.localize(datetime.combine(to_date, time.max))
        elif isinstance(to_date, datetime):
            # If datetime is naive, localize it to the specified timezone
            if to_date.tzinfo is None:
                end_datetime = timezone_obj.localize(to_date)
            else:
                # Already timezone-aware, use as is
                end_datetime = to_date
        
        # Base query - since timestamps are already timezone-aware, 
        # we can compare them directly with our timezone-aware bounds
        base_query = self.db.query(APIUsageMetric).filter(
            and_(
                APIUsageMetric.timestamp >= start_datetime,
                APIUsageMetric.timestamp <= end_datetime
            )
        )
        
        # Apply organization filter if provided
        if organization_id:
            base_query = base_query.filter(APIUsageMetric.organization_id == organization_id)
        
        # Get overall metrics  
        overall_metrics = self._get_overall_metrics(base_query)
        
        # Get metrics by category
        feed_metrics = self._get_category_metrics(base_query, '/feed')
        admin_metrics = self._get_category_metrics(base_query, '/admin')
        query_metrics = self._get_category_metrics(base_query, '/query')
        public_metrics = self._get_root_path_metrics(base_query)  # Metrics for root / path
        
        # Get top endpoints by category
        feed_top = self._get_top_endpoints(base_query, '/feed')
        admin_top = self._get_top_endpoints(base_query, '/admin')
        query_top = self._get_top_endpoints(base_query, '/query')
        public_top = self._get_top_root_endpoints(base_query)  # Top endpoints for root path
        
        # Get error breakdown
        errors_by_category = self._get_errors_by_category(base_query)
        
        return {
            "period": {
                "from": from_date.isoformat(),
                "to": to_date.isoformat()
            },
            "overall": overall_metrics,
            "by_category": {
                "feed": {
                    "metrics": feed_metrics,
                    "top_endpoints": feed_top
                },
                "admin": {
                    "metrics": admin_metrics,
                    "top_endpoints": admin_top
                },
                "query": {
                    "metrics": query_metrics,
                    "top_endpoints": query_top
                },
                "public": {
                    "metrics": public_metrics,
                    "top_endpoints": public_top
                }
            },
            "errors": errors_by_category,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _get_overall_metrics(self, base_query) -> Dict[str, Any]:
        """Get overall metrics across all endpoints."""
        metrics = base_query.with_entities(
            func.count(APIUsageMetric.id).label('total_requests'),
            func.avg(APIUsageMetric.response_time_ms).label('avg_response_time'),
            func.min(APIUsageMetric.response_time_ms).label('min_response_time'),
            func.max(APIUsageMetric.response_time_ms).label('max_response_time'),
            func.percentile_cont(0.5).within_group(APIUsageMetric.response_time_ms).label('p50_response_time'),
            func.percentile_cont(0.95).within_group(APIUsageMetric.response_time_ms).label('p95_response_time'),
            func.percentile_cont(0.99).within_group(APIUsageMetric.response_time_ms).label('p99_response_time'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code >= 400).label('error_count'),
            func.count(func.distinct(APIUsageMetric.organization_id)).label('unique_organizations'),
            func.count(func.distinct(APIUsageMetric.api_key_id)).label('unique_api_keys')
        ).first()
        
        total_requests = metrics.total_requests or 0
        error_count = metrics.error_count or 0
        
        return {
            "total_requests": total_requests,
            "error_count": error_count,
            "error_rate": round(error_count / total_requests * 100, 2) if total_requests > 0 else 0,
            "response_times": {
                "avg": round(metrics.avg_response_time or 0, 2),
                "min": metrics.min_response_time or 0,
                "max": metrics.max_response_time or 0,
                "p50": round(metrics.p50_response_time or 0, 2),
                "p95": round(metrics.p95_response_time or 0, 2),
                "p99": round(metrics.p99_response_time or 0, 2)
            },
            "unique_organizations": metrics.unique_organizations or 0,
            "unique_api_keys": metrics.unique_api_keys or 0
        }
    
    def _get_category_metrics(self, base_query, path_prefix: str) -> Dict[str, Any]:
        """Get metrics for a specific category of endpoints."""
        category_query = base_query.filter(APIUsageMetric.path.like(f'/api/v1{path_prefix}%'))
        
        metrics = category_query.with_entities(
            func.count(APIUsageMetric.id).label('total_requests'),
            func.avg(APIUsageMetric.response_time_ms).label('avg_response_time'),
            func.percentile_cont(0.95).within_group(APIUsageMetric.response_time_ms).label('p95_response_time'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code >= 400).label('error_count'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code == 200).label('success_count'),
            func.count(func.distinct(APIUsageMetric.route_pattern)).label('unique_endpoints')
        ).first()
        
        total_requests = metrics.total_requests or 0
        error_count = metrics.error_count or 0
        
        # Get status code breakdown
        status_breakdown = category_query.with_entities(
            APIUsageMetric.status_code,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.status_code).all()
        
        # Get method breakdown
        method_breakdown = category_query.with_entities(
            APIUsageMetric.method,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.method).all()
        
        return {
            "total_requests": total_requests,
            "error_rate": round(error_count / total_requests * 100, 2) if total_requests > 0 else 0,
            "success_rate": round((metrics.success_count or 0) / total_requests * 100, 2) if total_requests > 0 else 0,
            "avg_response_time": round(metrics.avg_response_time or 0, 2),
            "p95_response_time": round(metrics.p95_response_time or 0, 2),
            "unique_endpoints": metrics.unique_endpoints or 0,
            "status_codes": {str(code): count for code, count in status_breakdown},
            "methods": {method: count for method, count in method_breakdown}
        }
    
    def _get_public_metrics(self, base_query) -> Dict[str, Any]:
        """Get metrics for public endpoints (excluding feed, admin, query)."""
        public_query = base_query.filter(
            and_(
                APIUsageMetric.path.like('/api/v1%'),
                ~APIUsageMetric.path.like('/api/v1/feed%'),
                ~APIUsageMetric.path.like('/api/v1/admin%'),
                ~APIUsageMetric.path.like('/api/v1/query%')
            )
        )
        
        metrics = public_query.with_entities(
            func.count(APIUsageMetric.id).label('total_requests'),
            func.avg(APIUsageMetric.response_time_ms).label('avg_response_time'),
            func.percentile_cont(0.95).within_group(APIUsageMetric.response_time_ms).label('p95_response_time'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code >= 400).label('error_count'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code == 200).label('success_count'),
            func.count(func.distinct(APIUsageMetric.route_pattern)).label('unique_endpoints')
        ).first()
        
        total_requests = metrics.total_requests or 0
        error_count = metrics.error_count or 0
        
        # Get status code breakdown
        status_breakdown = public_query.with_entities(
            APIUsageMetric.status_code,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.status_code).all()
        
        # Get method breakdown
        method_breakdown = public_query.with_entities(
            APIUsageMetric.method,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.method).all()
        
        return {
            "total_requests": total_requests,
            "error_rate": round(error_count / total_requests * 100, 2) if total_requests > 0 else 0,
            "success_rate": round((metrics.success_count or 0) / total_requests * 100, 2) if total_requests > 0 else 0,
            "avg_response_time": round(metrics.avg_response_time or 0, 2),
            "p95_response_time": round(metrics.p95_response_time or 0, 2),
            "unique_endpoints": metrics.unique_endpoints or 0,
            "status_codes": {str(code): count for code, count in status_breakdown},
            "methods": {method: count for method, count in method_breakdown}
        }
    
    def _get_top_endpoints(self, base_query, path_prefix: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top endpoints by request count for a category."""
        top_endpoints = base_query.filter(
            APIUsageMetric.path.like(f'/api/v1{path_prefix}%')
        ).with_entities(
            APIUsageMetric.route_pattern,
            APIUsageMetric.method,
            func.count(APIUsageMetric.id).label('request_count'),
            func.avg(APIUsageMetric.response_time_ms).label('avg_response_time'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code >= 400).label('error_count')
        ).group_by(
            APIUsageMetric.route_pattern,
            APIUsageMetric.method
        ).order_by(
            func.count(APIUsageMetric.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "endpoint": f"{method} {pattern}",
                "request_count": request_count,
                "avg_response_time": round(avg_time or 0, 2),
                "error_rate": round(error_count / request_count * 100, 2) if request_count > 0 else 0
            }
            for pattern, method, request_count, avg_time, error_count in top_endpoints
        ]
    
    def _get_top_public_endpoints(self, base_query, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top public endpoints by request count."""
        top_endpoints = base_query.filter(
            and_(
                APIUsageMetric.path.like('/api/v1%'),
                ~APIUsageMetric.path.like('/api/v1/feed%'),
                ~APIUsageMetric.path.like('/api/v1/admin%'),
                ~APIUsageMetric.path.like('/api/v1/query%')
            )
        ).with_entities(
            APIUsageMetric.route_pattern,
            APIUsageMetric.method,
            func.count(APIUsageMetric.id).label('request_count'),
            func.avg(APIUsageMetric.response_time_ms).label('avg_response_time'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code >= 400).label('error_count')
        ).group_by(
            APIUsageMetric.route_pattern,
            APIUsageMetric.method
        ).order_by(
            func.count(APIUsageMetric.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "endpoint": f"{method} {pattern}",
                "request_count": request_count,
                "avg_response_time": round(avg_time or 0, 2),
                "error_rate": round(error_count / request_count * 100, 2) if request_count > 0 else 0
            }
            for pattern, method, request_count, avg_time, error_count in top_endpoints
        ]
    
    def _get_errors_by_category(self, base_query) -> Dict[str, Any]:
        """Get error breakdown by category."""
        errors_query = base_query.filter(APIUsageMetric.status_code >= 400)
        
        # Get errors by category
        feed_errors = errors_query.filter(APIUsageMetric.path.like('/api/v1/feed%')).count()
        admin_errors = errors_query.filter(APIUsageMetric.path.like('/api/v1/admin%')).count()
        query_errors = errors_query.filter(APIUsageMetric.path.like('/api/v1/query%')).count()
        public_errors = errors_query.filter(
            and_(
                APIUsageMetric.path.like('/api/v1%'),
                ~APIUsageMetric.path.like('/api/v1/feed%'),
                ~APIUsageMetric.path.like('/api/v1/admin%'),
                ~APIUsageMetric.path.like('/api/v1/query%')
            )
        ).count()
        
        # Get top error messages
        top_errors = errors_query.with_entities(
            APIUsageMetric.status_code,
            func.jsonb_extract_path_text(APIUsageMetric.metrics, 'error_message').label('error_message'),
            func.count(APIUsageMetric.id).label('count')
        ).group_by(
            APIUsageMetric.status_code,
            func.jsonb_extract_path_text(APIUsageMetric.metrics, 'error_message')
        ).order_by(
            func.count(APIUsageMetric.id).desc()
        ).limit(10).all()
        
        return {
            "by_category": {
                "feed": feed_errors,
                "admin": admin_errors,
                "query": query_errors,
                "public": public_errors
            },
            "top_errors": [
                {
                    "status_code": status,
                    "message": message or "No error message",
                    "count": count
                }
                for status, message, count in top_errors
            ]
        }
    
    def _get_root_path_metrics(self, base_query) -> Dict[str, Any]:
        """Get metrics for root / path (brand registry endpoint)."""
        root_query = base_query.filter(
            APIUsageMetric.path == '/'
        )
        
        metrics = root_query.with_entities(
            func.count(APIUsageMetric.id).label('total_requests'),
            func.avg(APIUsageMetric.response_time_ms).label('avg_response_time'),
            func.percentile_cont(0.95).within_group(APIUsageMetric.response_time_ms).label('p95_response_time'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code >= 400).label('error_count'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code == 200).label('success_count'),
            func.count(func.distinct(APIUsageMetric.host)).label('unique_hosts')
        ).first()
        
        total_requests = metrics.total_requests or 0
        error_count = metrics.error_count or 0
        
        # Get status code breakdown
        status_breakdown = root_query.with_entities(
            APIUsageMetric.status_code,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.status_code).all()
        
        # Get method breakdown
        method_breakdown = root_query.with_entities(
            APIUsageMetric.method,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.method).all()
        
        return {
            "total_requests": total_requests,
            "error_rate": round(error_count / total_requests * 100, 2) if total_requests > 0 else 0,
            "success_rate": round((metrics.success_count or 0) / total_requests * 100, 2) if total_requests > 0 else 0,
            "avg_response_time": round(metrics.avg_response_time or 0, 2),
            "p95_response_time": round(metrics.p95_response_time or 0, 2),
            "unique_hosts": metrics.unique_hosts or 0,
            "status_codes": {str(code): count for code, count in status_breakdown},
            "methods": {method: count for method, count in method_breakdown}
        }
    
    def _get_top_root_endpoints(self, base_query, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top root path access patterns."""
        # For root path, we'll show breakdown by host if available
        top_patterns = base_query.filter(
            APIUsageMetric.path == '/'
        ).with_entities(
            APIUsageMetric.host,
            APIUsageMetric.method,
            func.count(APIUsageMetric.id).label('request_count'),
            func.avg(APIUsageMetric.response_time_ms).label('avg_response_time'),
            func.count(APIUsageMetric.id).filter(APIUsageMetric.status_code >= 400).label('error_count')
        ).group_by(
            APIUsageMetric.host,
            APIUsageMetric.method
        ).order_by(
            func.count(APIUsageMetric.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "endpoint": f"{method} / (host: {host or 'direct'})",
                "request_count": request_count,
                "avg_response_time": round(avg_time or 0, 2),
                "error_rate": round(error_count / request_count * 100, 2) if request_count > 0 else 0
            }
            for host, method, request_count, avg_time, error_count in top_patterns
        ]