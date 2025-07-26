# app/schemas/product.py
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from datetime import datetime
from app.schemas.category import CategoryResponse
from app.schemas.offer import OfferResponse


class OfferBase(BaseModel):
    """Base Pydantic model for Offer data"""

    price: float
    price_currency: str = Field(..., description="Currency code (e.g., 'USD')")
    availability: str = Field(
        ..., description="Availability status (e.g., 'InStock', 'OutOfStock')"
    )
    inventory_level: Optional[int] = Field(
        None, description="Current inventory quantity"
    )
    price_valid_until: Optional[datetime] = Field(
        None, description="Expiration date for the current price"
    )


class PropertyValueBase(BaseModel):
    """Base Pydantic model for PropertyValue data"""

    name: str
    value: Union[str, int, float, bool, Dict[str, Any]]


class ProductBase(BaseModel):
    """Base Pydantic model for Product data"""

    name: str
    url: Optional[str] = Field(None, description="URL to the product page")
    sku: Optional[str] = Field(None, description="Stock keeping unit")
    description: Optional[str] = Field(None, description="Product description")
    product_group_id: Optional[UUID] = Field(
        None, description="ProductGroup this product belongs to"
    )
    brand_id: UUID = Field(..., description="Brand this product belongs to")
    urn: str = Field(..., description="CMP product identifier (URN format)")
    variant_attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Attributes that differentiate this variant"
    )
    category_id: Optional[UUID] = Field(
        None, description="Category ID for this product"
    )
    organization_id: UUID = Field(
        ..., description="Organization this product belongs to"
    )


class ProductCreate(ProductBase):
    """Schema for creating a new Product"""

    raw_data: Optional[Dict[str, Any]] = Field(
        None, description="Full JSON-LD representation"
    )
    offers: Optional[OfferBase] = Field(None, description="Offer information")
    additional_properties: Optional[List[PropertyValueBase]] = Field(
        None, description="Additional product properties"
    )


class ProductUpdate(BaseModel):
    """Schema for updating a Product (all fields optional)"""

    name: Optional[str] = None
    url: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    product_group_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None
    urn: Optional[str] = None
    variant_attributes: Optional[Dict[str, Any]] = None
    raw_data: Optional[Dict[str, Any]] = None
    offers: Optional[OfferBase] = None
    additional_properties: Optional[List[PropertyValueBase]] = None
    category_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None


class ProductInDB(ProductBase):
    """Schema for Product as stored in DB (includes DB fields)"""

    id: UUID
    created_at: datetime
    updated_at: datetime
    raw_data: Optional[Dict[str, Any]] = None
    category: Optional[CategoryResponse] = None
    offers: List[OfferResponse] = []

    model_config = {"from_attributes": True}


class ProductResponse(ProductInDB):
    """Schema for API responses"""

    pass


class ProductForVector(BaseModel):
    """Schema for products specifically formatted for vector processing"""

    id: str = Field(..., description="Product ID as string")
    urn: str = Field(..., description="Product URN")
    name: str = Field(..., description="Product name")
    description: Optional[str] = Field(None, description="Product description")
    brand_name: Optional[str] = Field(None, description="Brand name")
    category_name: Optional[str] = Field(None, description="Category name")
    price: Optional[float] = Field(None, description="Product price")
    availability: Optional[str] = Field(None, description="Availability status")
    product_group_id: Optional[str] = Field(
        None, description="Product group ID as string"
    )
    variant_attrs: Dict[str, Any] = Field(
        default_factory=dict, description="Variant attributes"
    )

    @classmethod
    def from_product_with_relations(cls, product) -> "ProductForVector":
        """Create ProductForVector from a Product model with loaded relations"""
        return cls(
            id=str(product.id),
            urn=product.urn,
            name=product.name,
            description=product.description,
            brand_name=product.brand.name if product.brand else None,
            category_name=product.category.name if product.category else None,
            price=product.offers[0].price if product.offers else None,
            availability=product.offers[0].availability if product.offers else None,
            product_group_id=(
                str(product.product_group_id) if product.product_group_id else None
            ),
            variant_attrs=product.variant_attributes or {},
        )


class ProductSearchResponse(BaseModel):
    """Product search result response model in JSON-LD format"""

    context: Dict[str, str] = Field(
        default={
            "schema": "https://schema.org",
            "cmp": "https://schema.commercemesh.ai/ns#",
        },
        alias="@context",
        description="JSON-LD context",
    )
    type: str = Field(default="ItemList", alias="@type", description="Schema.org type")
    itemListElement: List[Dict[str, Any]] = Field(..., description="List of products")
    cmp_totalResults: Optional[int] = Field(
        None, alias="cmp:totalResults", description="Total number of results"
    )
    cmp_nodeVersion: Optional[str] = Field(
        None, alias="cmp:nodeVersion", description="Node version"
    )
    cmp_requestId: Optional[str] = Field(
        None, alias="cmp:requestId", description="Request ID for caching"
    )
    datePublished: Optional[str] = Field(
        None, description="Publication date in ISO format"
    )


class ProductByUrnResponse(BaseModel):
    """Product by URN response model in JSON-LD ItemList format"""

    context: Union[str, Dict[str, str]] = Field(
        default="https://schema.org",
        alias="@context",
        description="JSON-LD context",
    )
    type: str = Field(default="ItemList", alias="@type", description="Schema.org type")
    itemListElement: List[Dict[str, Any]] = Field(..., description="List containing ProductGroup and Product")
    cmp_requestId: Optional[str] = Field(
        None, alias="cmp:requestId", description="Request ID for caching"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "item": {
                            "@context": "https://schema.org",
                            "@type": "ProductGroup",
                            "@id": "urn:cmp:product:the-journey-within",
                            "name": "The Journey Within",
                            "description": "",
                            "url": "https://insight-editions.myshopify.com/products/the-journey-within",
                            "brand": {
                                "@type": "Brand",
                                "name": "FutureFabrik"
                            },
                            "category": "Books",
                            "productGroupID": "the-journey-within",
                            "variesBy": ["title"]
                        }
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "item": {
                            "@context": "https://schema.org",
                            "@type": "Product",
                            "@id": "urn:cmp:sku:",
                            "name": "The Journey Within (Default Title)",
                            "url": "https://insight-editions.myshopify.com/products/the-journey-within?variant=",
                            "sku": "",
                            "isVariantOf": {
                                "@type": "ProductGroup",
                                "@id": "urn:cmp:product:the-journey-within"
                            },
                            "offers": {
                                "@type": "Offer",
                                "price": 0.0,
                                "priceCurrency": "USD",
                                "availability": "https://schema.org/OutOfStock",
                                "inventoryLevel": {
                                    "@type": "QuantitativeValue",
                                    "value": 0
                                },
                                "priceValidUntil": "2026-06-19T15:07:18.333109"
                            },
                            "additionalProperty": [
                                {
                                    "@type": "PropertyValue",
                                    "name": "title",
                                    "value": "Default Title"
                                }
                            ]
                        }
                    }
                ]
            }
        }

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "@context": {
                    "schema": "https://schema.org",
                    "cmp": "https://schema.commercemesh.ai/ns#",
                },
                "@type": "ItemList",
                "cmp:totalResults": 1,
                "cmp:nodeVersion": "v1.0.0",
                "datePublished": "2025-07-15T00:00:00Z",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "item": {
                            "@type": "Product",
                            "@id": "urn:cmp:sku:7eff4c52-5d03-4770-863d-c795327109fe",
                            "sku": "9781683836919",
                            "name": "Spacepedia",
                            "description": "Humans have always sought to push the boundaries of discovery...",
                            "category": "books",
                            "url": "https://insight-editions.myshopify.com/products/spacepedia?variant=9781683836919",
                            "brand": {"@type": "Brand", "name": "WidgetCo"},
                            "image": [
                                {
                                    "@type": "ImageObject",
                                    "url": "https://cdn.shopify.com/s/files/1/0421/4502/2103/products/77659-77574-cover.jpg?v=1597701326",
                                    "width": 684,
                                    "height": 810,
                                    "encodingFormat": "image/jpeg",
                                }
                            ],
                            "isVariantOf": {
                                "@type": "ProductGroup",
                                "@id": "urn:cmp:product:spacepedia",
                                "name": "Spacepedia – All Editions",
                            },
                            "additionalProperty": [
                                {
                                    "@type": "PropertyValue",
                                    "name": "readerAgeMin",
                                    "value": 8,
                                },
                                {
                                    "@type": "PropertyValue",
                                    "name": "readerAgeMax",
                                    "value": 14,
                                },
                            ],
                            "@cmp:media": [
                                {
                                    "@type": "VideoObject",
                                    "url": "https://cdn.shopify.com/s/files/intro.mp4",
                                    "encodingFormat": "video/mp4",
                                }
                            ],
                            "offers": [
                                {
                                    "@type": "Offer",
                                    "price": 24.99,
                                    "priceCurrency": "USD",
                                    "priceValidUntil": "2025-12-31T23:59:59Z",
                                    "availability": "https://schema.org/OutOfStock",
                                    "inventoryLevel": {
                                        "@type": "QuantitativeValue",
                                        "value": 0,
                                    },
                                    "seller": {
                                        "@type": "Organization",
                                        "@id": "urn:cmp:brand:21c7e663-a5be-4778-8bde-b224f55c11ad",
                                    },
                                }
                            ],
                            "cmp:searchScore": 0.03278688524590164,
                        },
                    }
                ],
            }
        }
