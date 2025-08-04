"""SQLAlchemy model for API keys."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey, JSON, Integer, UUID, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class APIKey(Base):
    """API Key model for authentication."""
    
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    permissions = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, server_default="true", nullable=False, default=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="api_keys")
    audit_logs = relationship("APIKeyAuditLog", back_populates="api_key", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_api_keys_organization_id", "organization_id"),
    )


class APIKeyAuditLog(Base):
    """Audit log for API key usage."""
    
    __tablename__ = "api_key_audit_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(50), nullable=False)  # e.g., "authenticated", "failed", "rate_limited"
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_path = Column(String(500), nullable=True)
    response_status = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    api_key = relationship("APIKey", back_populates="audit_logs")
    
    __table_args__ = (
        Index("ix_api_key_audit_log_api_key_id", "api_key_id"),
        Index("ix_api_key_audit_log_created_at", "created_at"),
    )