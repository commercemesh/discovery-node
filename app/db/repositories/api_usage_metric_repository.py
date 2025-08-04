"""Repository for API usage metrics data access."""
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.db.models.api_usage_metric import APIUsageMetric
from app.schemas.api_usage_metric import APIUsageMetricCreate, APIUsageMetricInDB


class APIUsageMetricRepository:
    """Repository for API usage metrics operations."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create(self, metric_data: APIUsageMetricCreate) -> APIUsageMetric:
        """Create a new API usage metric record."""
        db_metric = APIUsageMetric(**metric_data.model_dump())
        self.db.add(db_metric)
        self.db.commit()
        self.db.refresh(db_metric)
        return db_metric
    
    def get_by_id(self, metric_id: UUID) -> Optional[APIUsageMetric]:
        """Get API usage metric by ID."""
        return self.db.query(APIUsageMetric).filter(APIUsageMetric.id == metric_id).first()
    
    def get_by_request_id(self, request_id: UUID) -> Optional[APIUsageMetric]:
        """Get API usage metric by request ID."""
        return self.db.query(APIUsageMetric).filter(APIUsageMetric.request_id == request_id).first()
    
    def list_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        organization_id: Optional[UUID] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[APIUsageMetric]:
        """List API usage metrics within a date range."""
        query = self.db.query(APIUsageMetric).filter(
            and_(
                APIUsageMetric.timestamp >= start_date,
                APIUsageMetric.timestamp <= end_date
            )
        )
        
        if organization_id:
            query = query.filter(APIUsageMetric.organization_id == organization_id)
        
        return query.order_by(desc(APIUsageMetric.timestamp)).offset(offset).limit(limit).all()
    
    def list_by_organization(
        self, 
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[APIUsageMetric]:
        """List API usage metrics for a specific organization."""
        return self.db.query(APIUsageMetric).filter(
            APIUsageMetric.organization_id == organization_id
        ).order_by(desc(APIUsageMetric.timestamp)).offset(offset).limit(limit).all()
    
    def list_by_api_key(
        self, 
        api_key_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[APIUsageMetric]:
        """List API usage metrics for a specific API key."""
        return self.db.query(APIUsageMetric).filter(
            APIUsageMetric.api_key_id == api_key_id
        ).order_by(desc(APIUsageMetric.timestamp)).offset(offset).limit(limit).all()
    
    def list_by_path_prefix(
        self, 
        path_prefix: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[APIUsageMetric]:
        """List API usage metrics for endpoints with specific path prefix."""
        query = self.db.query(APIUsageMetric).filter(
            APIUsageMetric.path.like(f'{path_prefix}%')
        )
        
        if start_date:
            query = query.filter(APIUsageMetric.timestamp >= start_date)
        if end_date:
            query = query.filter(APIUsageMetric.timestamp <= end_date)
        
        return query.order_by(desc(APIUsageMetric.timestamp)).offset(offset).limit(limit).all()
    
    def list_errors(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        organization_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[APIUsageMetric]:
        """List API usage metrics with error status codes (>= 400)."""
        query = self.db.query(APIUsageMetric).filter(
            APIUsageMetric.status_code >= 400
        )
        
        if start_date:
            query = query.filter(APIUsageMetric.timestamp >= start_date)
        if end_date:
            query = query.filter(APIUsageMetric.timestamp <= end_date)
        if organization_id:
            query = query.filter(APIUsageMetric.organization_id == organization_id)
        
        return query.order_by(desc(APIUsageMetric.timestamp)).offset(offset).limit(limit).all()
    
    def count_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        organization_id: Optional[UUID] = None
    ) -> int:
        """Count API usage metrics within a date range."""
        query = self.db.query(APIUsageMetric).filter(
            and_(
                APIUsageMetric.timestamp >= start_date,
                APIUsageMetric.timestamp <= end_date
            )
        )
        
        if organization_id:
            query = query.filter(APIUsageMetric.organization_id == organization_id)
        
        return query.count()
    
    def get_response_time_percentiles(
        self,
        start_date: datetime,
        end_date: datetime,
        organization_id: Optional[UUID] = None,
        path_prefix: Optional[str] = None
    ) -> Dict[str, float]:
        """Get response time percentiles for a date range."""
        query = self.db.query(APIUsageMetric).filter(
            and_(
                APIUsageMetric.timestamp >= start_date,
                APIUsageMetric.timestamp <= end_date
            )
        )
        
        if organization_id:
            query = query.filter(APIUsageMetric.organization_id == organization_id)
        if path_prefix:
            query = query.filter(APIUsageMetric.path.like(f'{path_prefix}%'))
        
        result = query.with_entities(
            func.percentile_cont(0.5).within_group(APIUsageMetric.response_time_ms).label('p50'),
            func.percentile_cont(0.95).within_group(APIUsageMetric.response_time_ms).label('p95'),
            func.percentile_cont(0.99).within_group(APIUsageMetric.response_time_ms).label('p99'),
            func.avg(APIUsageMetric.response_time_ms).label('avg'),
            func.min(APIUsageMetric.response_time_ms).label('min'),
            func.max(APIUsageMetric.response_time_ms).label('max')
        ).first()
        
        return {
            "p50": float(result.p50 or 0),
            "p95": float(result.p95 or 0),
            "p99": float(result.p99 or 0),
            "avg": float(result.avg or 0),
            "min": float(result.min or 0),
            "max": float(result.max or 0)
        }
    
    def get_top_endpoints(
        self,
        start_date: datetime,
        end_date: datetime,
        organization_id: Optional[UUID] = None,
        path_prefix: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top endpoints by request count."""
        query = self.db.query(APIUsageMetric).filter(
            and_(
                APIUsageMetric.timestamp >= start_date,
                APIUsageMetric.timestamp <= end_date
            )
        )
        
        if organization_id:
            query = query.filter(APIUsageMetric.organization_id == organization_id)
        if path_prefix:
            query = query.filter(APIUsageMetric.path.like(f'{path_prefix}%'))
        
        results = query.with_entities(
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
                "route_pattern": pattern,
                "method": method,
                "request_count": request_count,
                "avg_response_time": float(avg_time or 0),
                "error_count": error_count,
                "error_rate": float(error_count / request_count * 100) if request_count > 0 else 0
            }
            for pattern, method, request_count, avg_time, error_count in results
        ]
    
    def get_status_code_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
        organization_id: Optional[UUID] = None,
        path_prefix: Optional[str] = None
    ) -> Dict[int, int]:
        """Get breakdown of requests by status code."""
        query = self.db.query(APIUsageMetric).filter(
            and_(
                APIUsageMetric.timestamp >= start_date,
                APIUsageMetric.timestamp <= end_date
            )
        )
        
        if organization_id:
            query = query.filter(APIUsageMetric.organization_id == organization_id)
        if path_prefix:
            query = query.filter(APIUsageMetric.path.like(f'{path_prefix}%'))
        
        results = query.with_entities(
            APIUsageMetric.status_code,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.status_code).all()
        
        return {status_code: count for status_code, count in results}
    
    def get_method_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
        organization_id: Optional[UUID] = None,
        path_prefix: Optional[str] = None
    ) -> Dict[str, int]:
        """Get breakdown of requests by HTTP method."""
        query = self.db.query(APIUsageMetric).filter(
            and_(
                APIUsageMetric.timestamp >= start_date,
                APIUsageMetric.timestamp <= end_date
            )
        )
        
        if organization_id:
            query = query.filter(APIUsageMetric.organization_id == organization_id)
        if path_prefix:
            query = query.filter(APIUsageMetric.path.like(f'{path_prefix}%'))
        
        results = query.with_entities(
            APIUsageMetric.method,
            func.count(APIUsageMetric.id).label('count')
        ).group_by(APIUsageMetric.method).all()
        
        return {method: count for method, count in results}
    
    def delete_old_metrics(self, older_than: datetime) -> int:
        """Delete metrics older than specified date. Returns count of deleted records."""
        deleted_count = self.db.query(APIUsageMetric).filter(
            APIUsageMetric.timestamp < older_than
        ).delete()
        self.db.commit()
        return deleted_count