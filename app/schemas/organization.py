# app/schemas/organization.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from app.schemas.category import CategoryResponse


class OrganizationBase(BaseModel):
    """Base Pydantic model for Organization data"""

    name: str
    subdomain: Optional[str] = Field(None, description="Unique subdomain for multi-tenant access")
    domain: Optional[str] = Field(None, description="Custom domain configured by seller (e.g., agent.brand.com)")
    description: Optional[str] = None
    url: Optional[str] = Field(None, description="Organization's canonical URL")
    logo_url: Optional[str] = Field(None, description="URL to organization logo")
    urn: Optional[str] = Field(
        None, description="CMP Organization identifier (URN format)"
    )
    social_links: Optional[List[str]] = Field(None, description="Social media URLs")
    feed_url: Optional[str] = Field(
        None, description="URL to organization's product feed"
    )


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new Organization"""

    raw_data: Optional[Dict[str, Any]] = Field(
        None, description="Full JSON-LD representation"
    )
    category_ids: Optional[List[UUID]] = Field(None, description="List of category IDs")


class OrganizationUpdate(BaseModel):
    """Schema for updating an Organization (all fields optional)"""

    name: Optional[str] = None
    subdomain: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    logo_url: Optional[str] = None
    urn: Optional[str] = None
    social_links: Optional[List[str]] = None
    feed_url: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    category_ids: Optional[List[UUID]] = None


class OrganizationInDB(OrganizationBase):
    """Schema for Organization as stored in DB (includes DB fields)"""

    id: UUID
    created_at: datetime
    updated_at: datetime
    raw_data: Optional[Dict[str, Any]] = None
    categories: List[CategoryResponse] = []

    model_config = {"from_attributes": True}


class OrganizationResponse(OrganizationInDB):
    """Schema for API responses"""

    pass
