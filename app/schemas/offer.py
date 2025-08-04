# app/schemas/offer.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class OfferBase(BaseModel):
    """Base Pydantic model for Offer data"""

    product_id: UUID = Field(..., description="Product this offer is for")
    organization_id: UUID = Field(..., description="Organization offering the product")
    price: float = Field(..., description="Current price of the product")
    price_currency: str = Field(..., description="Currency code (e.g., 'USD')")
    availability: str = Field(
        ..., description="Availability status (e.g., 'InStock', 'OutOfStock')"
    )

    # Optional fields
    inventory_level: Optional[int] = Field(
        None, description="Current inventory quantity"
    )
    price_valid_until: Optional[datetime] = Field(
        None, description="Expiration date for the current price"
    )
    shipping_cost: Optional[float] = Field(None, description="Cost of shipping")
    shipping_currency: Optional[str] = Field(
        None, description="Currency code for shipping cost"
    )
    shipping_destination: Optional[str] = Field(
        None, description="Destination region for shipping"
    )
    shipping_speed_tier: Optional[str] = Field(
        None, description="Shipping speed tier (e.g., 'Standard', 'Express')"
    )
    est_delivery_min_days: Optional[int] = Field(
        None, description="Minimum expected delivery time in days"
    )
    est_delivery_max_days: Optional[int] = Field(
        None, description="Maximum expected delivery time in days"
    )
    warranty_months: Optional[int] = Field(
        None, description="Duration of warranty in months"
    )
    warranty_type: Optional[str] = Field(None, description="Type of warranty")
    return_window_days: Optional[int] = Field(
        None, description="Number of days allowed for returns"
    )
    restocking_fee_pct: Optional[float] = Field(
        None, description="Restocking fee as percentage"
    )
    gift_wrap: Optional[bool] = Field(
        None, description="Whether gift wrapping is available"
    )


class OfferCreate(OfferBase):
    """Schema for creating a new Offer"""

    raw_data: Optional[Dict[str, Any]] = Field(
        None, description="Full JSON-LD representation"
    )


class OfferUpdate(BaseModel):
    """Schema for updating an Offer (all fields optional)"""

    product_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    price: Optional[float] = None
    price_currency: Optional[str] = None
    availability: Optional[str] = None
    inventory_level: Optional[int] = None
    price_valid_until: Optional[datetime] = None
    shipping_cost: Optional[float] = None
    shipping_currency: Optional[str] = None
    shipping_destination: Optional[str] = None
    shipping_speed_tier: Optional[str] = None
    est_delivery_min_days: Optional[int] = None
    est_delivery_max_days: Optional[int] = None
    warranty_months: Optional[int] = None
    warranty_type: Optional[str] = None
    return_window_days: Optional[int] = None
    restocking_fee_pct: Optional[float] = None
    gift_wrap: Optional[bool] = None
    raw_data: Optional[Dict[str, Any]] = None


class OfferInDB(OfferBase):
    """Schema for Offer as stored in DB (includes DB fields)"""

    id: UUID
    created_at: datetime
    updated_at: datetime
    raw_data: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class OfferResponse(OfferInDB):
    """Schema for API responses"""

    pass
