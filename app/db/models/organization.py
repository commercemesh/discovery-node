# app/db/models/organization.py
from sqlalchemy import Column, String, Text, JSON, UUID, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from app.db.base import Base
from app.db.models.associations import organization_category
import uuid


class Organization(Base):
    """
    Organization model representing a company or entity in the CMP Brand Registry.
    Based on the CMP Brand Registry specification.
    """

    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    subdomain = Column(String, unique=True, index=True, nullable=True, comment="Unique subdomain for multi-tenant access")
    domain = Column(String, nullable=True, comment="Custom domain configured by seller (e.g., agent.brand.com)")
    description = Column(Text)
    url = Column(String)
    logo_url = Column(String)
    urn = Column(
        String, unique=True, comment="CMP-specific organization identifier (URN format)"
    )
    social_links = Column(JSONB, default={}, comment="Array of social media URLs")
    feed_url = Column(String, comment="URL to the organization's product feed")
    raw_data = Column(JSONB, comment="Full JSON-LD representation of the organization")

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    brands = relationship(
        "Brand", back_populates="organization", cascade="all, delete-orphan"
    )

    # Many-to-many relationship with categories
    categories = relationship(
        "Category", secondary=organization_category, backref="organizations"
    )
    offers = relationship(
        "Offer", back_populates="organization", cascade="all, delete-orphan"
    )
    product_groups = relationship(
        "ProductGroup", back_populates="organization", cascade="all, delete-orphan"
    )
    products = relationship(
        "Product", back_populates="organization", cascade="all, delete-orphan"
    )
    api_keys = relationship(
        "APIKey", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}')>"
