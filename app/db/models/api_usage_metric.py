"""SQLAlchemy model for API usage metrics."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import (
    Column, String, DateTime, Integer, ForeignKey, UUID, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.db.base import Base


class APIUsageMetric(Base):
    """Model for tracking API usage metrics."""
    
    __tablename__ = "api_usage_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Timing
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    response_time_ms = Column(Integer, nullable=False)
    
    # Request details
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    host = Column(String(255))  # Hostname including subdomain
    route_pattern = Column(String(500))  # Parameterized route like /api/v1/products/{id}
    query_params = Column(JSONB)
    
    # Response details
    status_code = Column(Integer, nullable=False)
    
    # Authentication & Organization
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"))
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="SET NULL"))
    
    # Client information
    ip_address = Column(String(45))  # Supports IPv6
    user_agent = Column(String(1000))
    
    # Flexible metrics storage
    metrics = Column(JSONB, nullable=False, default=dict)
    """
    Example metrics content:
    {
        "request_size_bytes": 1024,
        "response_size_bytes": 2048,
        "db_query_count": 5,
        "db_query_time_ms": 45,
        "cache_hits": 2,
        "cache_misses": 1,
        "error_type": "ValidationError",
        "error_message": "Invalid SKU format",
        "tags": ["admin", "products", "create"],
        "api_version": "v1",
        "host": "acme.discovery.com",
        "referer": "https://dashboard.example.com",
        "items_returned": 25,  # For list endpoints
        "items_created": 10,   # For bulk create
        "items_updated": 5,    # For bulk update
        "vector_search_time_ms": 120,  # For search endpoints
        "embedding_time_ms": 50,  # If embeddings were generated
        "rate_limit_remaining": 950,
        "custom_headers": {
            "x-request-source": "dashboard",
            "x-correlation-id": "abc-123"
        }
    }
    """
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    organization = relationship("Organization")
    api_key = relationship("APIKey")
    
    __table_args__ = (
        # Indexes for common queries
        Index("idx_api_usage_timestamp", "timestamp", postgresql_using="btree"),
        Index("idx_api_usage_org_timestamp", "organization_id", "timestamp", 
              postgresql_where="organization_id IS NOT NULL"),
        Index("idx_api_usage_path_timestamp", "path", "timestamp"),
        Index("idx_api_usage_host_timestamp", "host", "timestamp"),
        Index("idx_api_usage_status_timestamp", "status_code", "timestamp"),
        Index("idx_api_usage_route_pattern", "route_pattern", "timestamp"),
        Index("idx_api_usage_api_key", "api_key_id", 
              postgresql_where="api_key_id IS NOT NULL"),
        # GIN index for JSONB queries
        Index("idx_api_usage_metrics_gin", "metrics", postgresql_using="gin"),
    )
    
    def __repr__(self):
        return f"<APIUsageMetric(id={self.id}, path={self.path}, status={self.status_code})>"