"""Pydantic schemas for API usage metrics."""
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class APIUsageMetricBase(BaseModel):
    """Base schema for API usage metrics."""
    request_id: UUID = Field(..., description="Unique request identifier")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
    method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Request path")
    host: Optional[str] = Field(None, description="Request hostname including subdomain")
    route_pattern: Optional[str] = Field(None, description="Parameterized route pattern")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Query parameters")
    status_code: int = Field(..., description="HTTP status code")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Additional metrics")


class APIUsageMetricCreate(APIUsageMetricBase):
    """Schema for creating API usage metrics."""
    organization_id: Optional[UUID] = Field(None, description="Organization ID")
    api_key_id: Optional[UUID] = Field(None, description="API key ID")


class APIUsageMetricUpdate(BaseModel):
    """Schema for updating API usage metrics."""
    metrics: Optional[Dict[str, Any]] = None


class APIUsageMetricInDB(APIUsageMetricBase):
    """Schema for API usage metrics in database."""
    id: UUID
    timestamp: datetime
    organization_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class APIUsageMetricResponse(APIUsageMetricInDB):
    """Schema for API usage metric response."""
    pass


# Analytics response schemas
class ResponseTimeMetrics(BaseModel):
    """Response time metrics."""
    avg: float = Field(..., description="Average response time")
    min: int = Field(..., description="Minimum response time")
    max: int = Field(..., description="Maximum response time")
    p50: float = Field(..., description="50th percentile response time")
    p95: float = Field(..., description="95th percentile response time")
    p99: float = Field(..., description="99th percentile response time")


class OverallMetrics(BaseModel):
    """Overall API metrics."""
    total_requests: int = Field(..., description="Total number of requests")
    error_count: int = Field(..., description="Number of error responses")
    error_rate: float = Field(..., description="Error rate as percentage")
    response_times: ResponseTimeMetrics
    unique_organizations: int = Field(..., description="Number of unique organizations")
    unique_api_keys: int = Field(..., description="Number of unique API keys")


class CategoryMetrics(BaseModel):
    """Metrics for a specific category of endpoints."""
    total_requests: int = Field(..., description="Total requests in category")
    error_rate: float = Field(..., description="Error rate as percentage")
    success_rate: float = Field(..., description="Success rate as percentage")
    avg_response_time: float = Field(..., description="Average response time")
    p95_response_time: float = Field(..., description="95th percentile response time")
    unique_endpoints: int = Field(..., description="Number of unique endpoints")
    status_codes: Dict[str, int] = Field(..., description="Breakdown by status code")
    methods: Dict[str, int] = Field(..., description="Breakdown by HTTP method")


class TopEndpoint(BaseModel):
    """Top endpoint metrics."""
    endpoint: str = Field(..., description="Endpoint (method + path)")
    request_count: int = Field(..., description="Number of requests")
    avg_response_time: float = Field(..., description="Average response time")
    error_rate: float = Field(..., description="Error rate as percentage")


class CategoryAnalytics(BaseModel):
    """Analytics for a category of endpoints."""
    metrics: CategoryMetrics
    top_endpoints: List[TopEndpoint]


class TopError(BaseModel):
    """Top error information."""
    status_code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Error message")
    count: int = Field(..., description="Number of occurrences")


class ErrorAnalytics(BaseModel):
    """Error analytics."""
    by_category: Dict[str, int] = Field(..., description="Error count by category")
    top_errors: List[TopError] = Field(..., description="Most common errors")


class AnalyticsPeriod(BaseModel):
    """Analytics time period."""
    from_: str = Field(..., alias="from", description="Start date")
    to: str = Field(..., description="End date")


class APIAnalyticsResponse(BaseModel):
    """Complete API analytics response."""
    period: AnalyticsPeriod
    overall: OverallMetrics
    by_category: Dict[str, CategoryAnalytics] = Field(
        ..., 
        description="Metrics by category (feed, admin, query, public)"
    )
    errors: ErrorAnalytics
    generated_at: str = Field(..., description="When analytics were generated")


class HealthMetrics(BaseModel):
    """API health metrics."""
    request_rate: int = Field(..., description="Requests in time period")
    error_rate: float = Field(..., description="Error rate as percentage")
    avg_response_time: float = Field(..., description="Average response time")
    p95_response_time: float = Field(..., description="95th percentile response time")


class APIHealthResponse(BaseModel):
    """API health response."""
    status: str = Field(..., description="Overall health status")
    timestamp: str = Field(..., description="Timestamp of health check")
    metrics: HealthMetrics
    services: Dict[str, str] = Field(..., description="Status by service category")
    last_hour_requests: int = Field(..., description="Requests in last hour")
    last_hour_errors: int = Field(..., description="Errors in last hour")