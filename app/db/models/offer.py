# app/db/models/offer.py
from sqlalchemy import Column, String, ForeignKey, UUID, Float, Integer, Boolean, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from app.db.base import Base
import uuid


class Offer(Base):
    """
    Offer model representing a specific offering of a product by a seller
    in the CMP Product Feed specification.
    """

    __tablename__ = "offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        comment="Organization offering the product",
    )

    # Pricing information
    price = Column(Float, nullable=False, comment="Current price of the product")
    price_currency = Column(
        String(3), nullable=False, comment="Currency code (e.g., 'USD')"
    )
    price_valid_until = Column(
        TIMESTAMP(timezone=True), comment="Expiration date for the current price"
    )

    # Availability information
    availability = Column(
        String,
        nullable=False,
        comment="Availability status (e.g., 'InStock', 'OutOfStock')",
    )
    inventory_level = Column(Integer, comment="Current inventory quantity")

    # Shipping information
    shipping_cost = Column(Float, comment="Cost of shipping")
    shipping_currency = Column(String(3), comment="Currency code for shipping cost")
    shipping_destination = Column(String, comment="Destination region for shipping")

    # Service level information
    shipping_speed_tier = Column(
        String, comment="Shipping speed tier (e.g., 'Standard', 'Express')"
    )
    est_delivery_min_days = Column(
        Integer, comment="Minimum expected delivery time in days"
    )
    est_delivery_max_days = Column(
        Integer, comment="Maximum expected delivery time in days"
    )
    warranty_months = Column(Integer, comment="Duration of warranty in months")
    warranty_type = Column(String, comment="Type of warranty")
    return_window_days = Column(Integer, comment="Number of days allowed for returns")
    restocking_fee_pct = Column(Float, comment="Restocking fee as percentage")

    # Additional flags
    gift_wrap = Column(
        Boolean, default=False, comment="Whether gift wrapping is available"
    )

    # Raw data
    raw_data = Column(JSONB, comment="Full JSON-LD representation of the offer")

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    product = relationship("Product", back_populates="offers")
    organization = relationship("Organization", back_populates="offers")

    def __repr__(self):
        return f"<Offer(id={self.id}, price={self.price} {self.price_currency}, organization_id={self.organization_id})>"
