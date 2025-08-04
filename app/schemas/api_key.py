"""Pydantic schemas for API keys."""
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class APIKeyBase(BaseModel):
    """Base API key schema."""
    name: str = Field(..., description="Human-readable name for the API key")
    permissions: Dict[str, Any] = Field(
        default_factory=lambda: {"admin": ["read", "write"]},
        description="Permissions granted to this API key"
    )
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class APIKeyCreate(APIKeyBase):
    """Schema for creating an API key."""
    organization_id: UUID = Field(..., description="Organization this key belongs to")


class APIKeyUpdate(BaseModel):
    """Schema for updating an API key."""
    name: Optional[str] = None
    permissions: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class APIKeyInDB(APIKeyBase):
    """Schema for API key in database."""
    id: UUID
    organization_id: UUID
    key_hash: str
    created_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class APIKeyResponse(BaseModel):
    """Schema for API key response (includes raw key only on creation)."""
    id: UUID
    name: str
    key: Optional[str] = Field(None, description="Raw API key - only provided on creation")
    permissions: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    organization_id: UUID

    class Config:
        from_attributes = True


class APIKeyAuditLogCreate(BaseModel):
    """Schema for creating an audit log entry."""
    api_key_id: UUID
    action: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    response_status: Optional[int] = None


class APIKeyAuditLogInDB(APIKeyAuditLogCreate):
    """Schema for audit log in database."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True