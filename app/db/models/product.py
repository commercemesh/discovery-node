# app/db/models/product.py (update this file to add the Product model)
from sqlalchemy import Column, String, Text, ForeignKey, UUID, Float, Integer, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from pgvector.sqlalchemy import Vector
from app.db.base import Base
import uuid

# Keep the existing ProductGroup class


class Product(Base):
    """
    Product model representing a specific product variant in the CMP Product Feed specification.
    Products are variants of a ProductGroup.
    """

    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    urn = Column(
        String,
        unique=True,
        nullable=False,
        comment="CMP-specific product identifier (URN format)",
    )
    name = Column(String, nullable=False, index=True)
    url = Column(String)
    sku = Column(String, index=True, comment="Stock keeping unit")
    description = Column(Text)
    product_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_groups.id", ondelete="CASCADE"),
        nullable=True,
    )
    brand_id = Column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_attributes = Column(
        JSONB, default={}, comment="Attributes that differentiate this variant"
    )
    raw_data = Column(JSONB, comment="Full JSON-LD representation of the product")
    
    # Vector embedding for similarity search
    embedding = Column(
        Vector(1536),  # text-embedding-3-small dimension (configurable)
        comment="Dense embedding vector for semantic search"
    )

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    product_group = relationship("ProductGroup", back_populates="products")
    brand = relationship("Brand", back_populates="products")
    category = relationship("Category", backref="products", foreign_keys=[category_id])
    organization = relationship("Organization", back_populates="products")
    offers = relationship(
        "Offer", back_populates="product", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Product(id={self.id}, name='{self.name}', sku='{self.sku}')>"
