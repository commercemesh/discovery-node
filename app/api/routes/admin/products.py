"""Admin API for product updates"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, timezone
import logging

from app.db.base import get_db_session
from app.services.product_service import ProductService
from app.services.product_group_service import ProductGroupService
from app.services.offer_service import OfferService
from app.core.dependencies import OrganizationId
from app.utils import formatters

logger = logging.getLogger(__name__)

# JSON-LD Schema Models
class BrandIdentifier(BaseModel):
    type_: str = Field(alias="@type", default="PropertyValue")
    propertyID: str
    value: str

class Brand(BaseModel):
    type_: str = Field(alias="@type", default="Brand")
    name: str
    identifier: Optional[BrandIdentifier] = None

class QuantitativeValue(BaseModel):
    type_: str = Field(alias="@type", default="QuantitativeValue")
    value: float

class PriceSpecification(BaseModel):
    type_: str = Field(alias="@type", default="PriceSpecification")
    price: float
    priceCurrency: str

class Offer(BaseModel):
    type_: str = Field(alias="@type", default="Offer")
    price: float
    priceCurrency: str
    availability: str
    inventoryLevel: QuantitativeValue
    priceValidUntil: Optional[datetime] = None
    priceSpecification: Optional[PriceSpecification] = None

    @field_validator('availability')
    def validate_availability(cls, v):
        valid = ["https://schema.org/InStock", "https://schema.org/OutOfStock"]
        if v not in valid:
            raise ValueError(f"availability must be one of {valid}")
        return v

class PropertyValue(BaseModel):
    type_: str = Field(alias="@type", default="PropertyValue")
    name: str
    value: Union[str, float, bool, Dict, List]

class MediaObject(BaseModel):
    type_: str = Field(alias="@type")
    url: str
    contentUrl: Optional[str] = None
    encodingFormat: Optional[str] = None
    thumbnailUrl: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[str] = None
    caption: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    uploadDate: Optional[str] = None

    @field_validator('type_')
    def validate_type(cls, v):
        valid = ["ImageObject", "VideoObject", "MediaObject"]
        if v not in valid:
            raise ValueError(f"@type must be one of {valid}")
        return v

class ProductGroupRef(BaseModel):
    type_: str = Field(alias="@type", default="ProductGroup")
    id_: str = Field(alias="@id")

    @field_validator('id_')
    def validate_product_group_id(cls, v):
        # Accept both :product: and :sku: patterns for ProductGroups
        # Some feeds use :sku: for product groups (e.g., :sku:tv-group-001)
        if not (v.startswith("urn:cmp:product:") or ":product:" in v or ":sku:" in v):
            raise ValueError("ProductGroup @id must contain ':product:' or ':sku:' in the URN")
        return v

class Product(BaseModel):
    context: Optional[Union[str, Dict[str, str]]] = Field(alias="@context", default=None)
    type_: Literal["Product"] = Field(alias="@type", default="Product")
    id_: Optional[str] = Field(alias="@id", default=None)  # Optional for creation
    name: str
    sku: str
    description: Optional[str] = None
    image: Optional[str] = None
    url: Optional[str] = None
    brand: Optional[Brand] = None
    category: Optional[str] = None
    offers: Offer
    additionalProperty: Optional[List[PropertyValue]] = None
    isVariantOf: Optional[ProductGroupRef] = None
    cmp_media: Optional[List[MediaObject]] = Field(alias="@cmp:media", default=None)

    @field_validator('context')
    def validate_context(cls, v):
        if v is None:
            return v
        if isinstance(v, str) and v != "https://schema.org":
            raise ValueError("@context string must be 'https://schema.org'")
        elif isinstance(v, dict):
            if v.get("schema") != "https://schema.org":
                raise ValueError("@context.schema must be 'https://schema.org'")
        return v

    @field_validator('id_')
    def validate_product_id(cls, v):
        if v is None:
            return v  # Allow None for creation
        # Accept both simple and complex URN formats
        if not (v.startswith("urn:cmp:sku:") or ":sku:" in v):
            raise ValueError("Product @id must contain ':sku:' in the URN")
        return v

class ProductGroup(BaseModel):
    context: Optional[Union[str, Dict[str, str]]] = Field(alias="@context", default=None)
    type_: Literal["ProductGroup"] = Field(alias="@type", default="ProductGroup")
    id_: Optional[str] = Field(alias="@id", default=None)  # Optional for creation
    name: str
    description: Optional[str] = None
    brand: Optional[Brand] = None
    category: Optional[str] = None
    productGroupID: str
    variesBy: Optional[List[str]] = None
    cmp_media: Optional[List[MediaObject]] = Field(alias="@cmp:media", default=None)

    @field_validator('context')
    def validate_context(cls, v):
        if v is None:
            return v
        if isinstance(v, str) and v != "https://schema.org":
            raise ValueError("@context string must be 'https://schema.org'")
        elif isinstance(v, dict):
            if v.get("schema") != "https://schema.org":
                raise ValueError("@context.schema must be 'https://schema.org'")
        return v

    @field_validator('id_')
    def validate_product_group_id(cls, v):
        if v is None:
            return v  # Allow None for creation
        # Log the value being validated
        logger.debug(f"Validating ProductGroup @id: {v}")
        # Accept both :product: and :sku: patterns for ProductGroups
        # Some feeds use :sku: for product groups (e.g., :sku:tv-group-001)
        if not (v.startswith("urn:cmp:product:") or ":product:" in v or ":sku:" in v):
            raise ValueError(f"ProductGroup @id must contain ':product:' or ':sku:' in the URN, got: {v}")
        return v

class ListItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    type_: str = Field(alias="@type", default="ListItem")
    position: int = Field(ge=1)
    item: Union[Product, ProductGroup] = Field(discriminator='type_')

class ItemListUpdate(BaseModel):
    context: Optional[Union[str, Dict[str, str]]] = Field(alias="@context", default=None)
    type_: str = Field(alias="@type", default="ItemList")
    itemListElement: List[ListItem] = Field(..., max_items=200, description="Maximum 200 items per request")

    @field_validator('context')
    def validate_context(cls, v):
        if v is None:
            return v
        if isinstance(v, str) and v != "https://schema.org":
            raise ValueError("@context string must be 'https://schema.org'")
        elif isinstance(v, dict):
            if v.get("schema") != "https://schema.org":
                raise ValueError("@context.schema must be 'https://schema.org'")
        return v

    @field_validator('itemListElement')
    def validate_item_list(cls, v):
        if len(v) == 0:
            raise ValueError("At least one item is required in itemListElement.")
        return v

# Router
products_admin_router = APIRouter()

@products_admin_router.put("/products")
async def update_products(
    data: ItemListUpdate,
    organization_id: OrganizationId,
    db: Session = Depends(get_db_session)
):
    """
    Upsert products using JSON-LD ItemList format
    
    This endpoint performs an upsert operation:
    - If a product/product group exists (by URN), it will be updated
    - If a product/product group doesn't exist, it will be created
    
    Organization context is determined by (in order of priority):
    1. X-Organization header (subdomain, e.g., "acme")
    2. Subdomain from Host header (e.g., "acme.discovery.com")
    
    Note: While we use organization URNs externally, the system internally
    uses UUIDs for database operations.
    """
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context is required. Use X-Organization header or subdomain."
        )
    
    product_service = ProductService(db)
    product_group_service = ProductGroupService(db)
    
    try:
        results = []
        
        for list_item in data.itemListElement:
            item = list_item.item
            
            try:
                if isinstance(item, ProductGroup):
                    # Check if product group exists
                    urn = item.id_
                    existing_pg = product_group_service.get_by_urn(urn)
                    
                    if existing_pg:
                        # UPDATE: Product group exists
                        # Verify organization ownership
                        if existing_pg.organization_id != organization_id:
                            raise ValueError("Product group belongs to different organization")
                        
                        # Parse JSON-LD to update schema
                        update_data = formatters.parse_jsonld_to_product_group_update(
                            item.model_dump(by_alias=True)
                        )
                        
                        # Update using service
                        updated = product_group_service.update_product_group(
                            existing_pg.id,
                            update_data
                        )
                        
                        results.append({
                            "type": "ProductGroup",
                            "urn": item.id_,
                            "action": "updated",
                            "id": str(updated.id)
                        })
                    else:
                        # CREATE: Product group doesn't exist
                        # Handle brand creation/lookup
                        from app.services.brand_service import BrandService
                        from app.core.urn_generator import generate_brand_urn
                        from app.services.organization_service import OrganizationService
                        
                        org_service = OrganizationService(db)
                        organization = org_service.get_organization(organization_id)
                        
                        brand_id = None
                        if item.brand:
                            brand_service = BrandService(db)
                            brand_urn = generate_brand_urn(item.brand.name, organization.urn)
                            existing_brand = brand_service.get_by_urn(brand_urn)
                            
                            if existing_brand:
                                brand_id = existing_brand.id
                            else:
                                from app.schemas.brand import BrandCreate
                                brand_create = BrandCreate(
                                    name=item.brand.name,
                                    urn=brand_urn,
                                    organization_id=organization_id
                                )
                                new_brand = brand_service.create_brand(brand_create)
                                brand_id = new_brand.id
                        
                        # Handle category
                        from app.services.category_service import CategoryService
                        category_service = CategoryService(db)
                        category = category_service.get_or_create_by_name(item.category or "uncategorized")
                        
                        # Parse JSON-LD to create schema
                        pg_create = formatters.parse_jsonld_to_product_group_create(
                            item.model_dump(by_alias=True),
                            organization_id,
                            brand_id,
                            category.id
                        )
                        
                        # Create using service
                        created = product_group_service.create_product_group(pg_create)
                        
                        results.append({
                            "type": "ProductGroup",
                            "urn": item.id_,
                            "action": "created",
                            "id": str(created.id)
                        })
                    
                elif isinstance(item, Product):
                    # Check if product exists
                    urn = item.id_
                    existing_product = product_service.get_by_urn(urn)
                    
                    if existing_product:
                        # UPDATE: Product exists
                        # Verify organization ownership
                        if existing_product.organization_id != organization_id:
                            raise ValueError("Product belongs to different organization")
                        
                        # Parse JSON-LD to update schema
                        update_data = formatters.parse_jsonld_to_product_update(
                            item.model_dump(by_alias=True)
                        )
                        
                        # Update using service
                        updated = product_service.update_product(
                            existing_product.id,
                            update_data
                        )
                        
                        # Handle offer updates if present
                        offer_data = item.offers
                        if offer_data:
                            offer_service = OfferService(db)
                            # Delete existing offers and create new one
                            existing_offers = offer_service.list_by_product(existing_product.id)
                            for offer in existing_offers:
                                offer_service.delete_offer(offer.id)
                            
                            # Create new offer
                            offer_create = formatters.parse_jsonld_offer(
                                offer_data.model_dump(by_alias=True),
                                existing_product.id,
                                organization_id
                            )
                            offer_service.create_offer(offer_create)
                        
                        results.append({
                            "type": "Product",
                            "urn": item.id_,
                            "action": "updated",
                            "id": str(updated.id)
                        })
                    else:
                        # CREATE: Product doesn't exist
                        # Handle brand creation/lookup
                        from app.services.brand_service import BrandService
                        from app.core.urn_generator import generate_brand_urn
                        from app.services.organization_service import OrganizationService
                        
                        org_service = OrganizationService(db)
                        organization = org_service.get_organization(organization_id)
                        
                        brand_id = None
                        if item.brand:
                            brand_service = BrandService(db)
                            brand_urn = generate_brand_urn(item.brand.name, organization.urn)
                            existing_brand = brand_service.get_by_urn(brand_urn)
                            
                            if existing_brand:
                                brand_id = existing_brand.id
                            else:
                                from app.schemas.brand import BrandCreate
                                brand_create = BrandCreate(
                                    name=item.brand.name,
                                    urn=brand_urn,
                                    organization_id=organization_id
                                )
                                new_brand = brand_service.create_brand(brand_create)
                                brand_id = new_brand.id
                        
                        # Handle category
                        from app.services.category_service import CategoryService
                        category_service = CategoryService(db)
                        category = category_service.get_or_create_by_name(item.category or "uncategorized")
                        
                        # Handle product group reference
                        product_group_id = None
                        if item.isVariantOf:
                            pg = product_group_service.get_by_urn(item.isVariantOf.id_)
                            if pg:
                                product_group_id = pg.id
                            else:
                                logger.warning(f"Product group {item.isVariantOf.id_} not found for product {urn}")
                        
                        # Parse JSON-LD to create schema
                        product_create = formatters.parse_jsonld_to_product_create(
                            item.model_dump(by_alias=True),
                            organization_id,
                            brand_id,
                            category.id,
                            product_group_id
                        )
                        
                        # Create using service
                        created = product_service.create_product(product_create)
                        
                        # Handle offer creation if present
                        if item.offers:
                            offer_create = formatters.parse_jsonld_offer(
                                item.offers.model_dump(by_alias=True),
                                created.id,
                                organization_id
                            )
                            offer_service.create_offer(offer_create)
                        
                        results.append({
                            "type": "Product",
                            "urn": item.id_,
                            "action": "created",
                            "id": str(created.id)
                        })
                    
            except ValueError as e:
                # Handle not found or ownership errors
                logger.warning(f"Update failed for {item.id_}: {str(e)}")
                results.append({
                    "type": type(item).__name__,
                    "urn": item.id_,
                    "action": "skipped",
                    "reason": str(e)
                })
            except Exception as e:
                # Handle other errors
                logger.error(f"Error updating {item.id_}: {str(e)}")
                results.append({
                    "type": type(item).__name__,
                    "urn": item.id_,
                    "action": "failed",
                    "error": str(e)
                })
        
        # Calculate summary
        summary = {
            "product_groups_created": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "created"),
            "product_groups_updated": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "updated"),
            "product_groups_skipped": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "skipped"),
            "product_groups_failed": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "failed"),
            "products_created": sum(1 for r in results if r["type"] == "Product" and r["action"] == "created"),
            "products_updated": sum(1 for r in results if r["type"] == "Product" and r["action"] == "updated"),
            "products_skipped": sum(1 for r in results if r["type"] == "Product" and r["action"] == "skipped"),
            "products_failed": sum(1 for r in results if r["type"] == "Product" and r["action"] == "failed"),
            "total_items_processed": len(data.itemListElement),
            "total_successful": sum(1 for r in results if r["action"] in ["created", "updated"]),
            "total_errors": sum(1 for r in results if r["action"] in ["skipped", "failed"])
        }
        
        # Queue embedding generation for created and updated products
        product_urns_for_embeddings = [
            r["urn"] for r in results 
            if r["type"] == "Product" and r["action"] in ["created", "updated"]
        ]
        
        if product_urns_for_embeddings:
            from app.worker.tasks.embeddings import generate_embedding_single, generate_embeddings_batch
            
            # Use single task for small batches, batch task for larger ones
            if len(product_urns_for_embeddings) <= 10:
                for urn in product_urns_for_embeddings:
                    generate_embedding_single.delay(urn)
                logger.info(f"Queued {len(product_urns_for_embeddings)} individual embedding generation tasks")
            else:
                # Process in chunks of 100
                chunk_size = 100
                for i in range(0, len(product_urns_for_embeddings), chunk_size):
                    chunk = product_urns_for_embeddings[i:i + chunk_size]
                    generate_embeddings_batch.delay(chunk)
                logger.info(f"Queued {(len(product_urns_for_embeddings) + chunk_size - 1) // chunk_size} batch embedding generation tasks")
        
        return {
            "status": "success",
            "summary": summary,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@products_admin_router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_products(
    data: ItemListUpdate,
    organization_id: OrganizationId,
    db: Session = Depends(get_db_session)
):
    """
    Create new products using JSON-LD ItemList format
    
    Organization context is determined by (in order of priority):
    1. X-Organization header (subdomain, e.g., "acme")
    2. Subdomain from Host header (e.g., "acme.discovery.com")
    """
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context is required. Use X-Organization header or subdomain."
        )
    
    product_service = ProductService(db)
    product_group_service = ProductGroupService(db)
    offer_service = OfferService(db)
    
    logger.info(f"Creating products for organization: {organization_id}")
    
    try:
        results = []
        
        for list_item in data.itemListElement:
            item = list_item.item
            
            try:
                if isinstance(item, ProductGroup):
                    # Generate URN if not provided
                    urn = item.id_
                    if not urn:
                        from app.core.urn_generator import generate_product_group_urn, generate_brand_urn
                        from app.services.organization_service import OrganizationService
                        
                        org_service = OrganizationService(db)
                        organization = org_service.get_organization(organization_id)
                        
                        # Need brand URN for generation
                        if item.brand:
                            brand_urn = generate_brand_urn(item.brand.name, organization.urn)
                        else:
                            # Use organization URN as fallback
                            brand_urn = organization.urn
                        
                        urn = generate_product_group_urn(item.productGroupID, organization.urn, brand_urn)
                        item.id_ = urn
                    
                    # Check if already exists
                    existing = product_group_service.get_by_urn(urn)
                    if existing:
                        raise ValueError(f"Product group with URN {urn} already exists")
                    
                    # Handle brand creation/lookup
                    from app.services.brand_service import BrandService
                    from app.core.urn_generator import generate_brand_urn
                    from app.services.organization_service import OrganizationService
                    
                    org_service = OrganizationService(db)
                    organization = org_service.get_organization(organization_id)
                    
                    brand_id = None
                    if item.brand:
                        brand_service = BrandService(db)
                        
                        # Use the URN from identifier if provided, otherwise generate one
                        if item.brand.identifier and item.brand.identifier.value:
                            brand_urn = item.brand.identifier.value
                        else:
                            brand_urn = generate_brand_urn(item.brand.name, organization.urn)
                        
                        existing_brand = brand_service.get_by_urn(brand_urn)
                        
                        if existing_brand:
                            brand_id = existing_brand.id
                        else:
                            from app.schemas.brand import BrandCreate
                            brand_create = BrandCreate(
                                name=item.brand.name,
                                urn=brand_urn,
                                organization_id=organization_id
                            )
                            new_brand = brand_service.create_brand(brand_create)
                            brand_id = new_brand.id
                    
                    # Handle category
                    from app.services.category_service import CategoryService
                    category_service = CategoryService(db)
                    category = category_service.get_or_create_by_name(item.category or "uncategorized")
                    
                    # Parse JSON-LD to create schema
                    pg_create = formatters.parse_jsonld_to_product_group_create(
                        item.model_dump(by_alias=True),
                        organization_id,
                        brand_id,
                        category.id
                    )
                    
                    # Create using service
                    created = product_group_service.create_product_group(pg_create)
                    
                    results.append({
                        "type": "ProductGroup",
                        "urn": urn,  # Use the generated/provided URN
                        "action": "created",
                        "id": str(created.id)
                    })
                    
                elif isinstance(item, Product):
                    # Convert to dict for the service method
                    jsonld_data = item.model_dump(by_alias=True)
                    
                    # Create product using service method that handles everything
                    try:
                        created = product_service.create_product_from_jsonld(jsonld_data, organization_id)
                        
                        # Handle offer creation if present
                        if item.offers:
                            offer_create = formatters.parse_jsonld_offer(
                                item.offers.model_dump(by_alias=True),
                                created.id,
                                organization_id
                            )
                            offer_service.create_offer(offer_create)
                        
                        results.append({
                            "type": "Product",
                            "urn": created.urn,
                            "action": "created",
                            "id": str(created.id)
                        })
                    except Exception as e:
                        if "already exists" in str(e):
                            raise ValueError(f"Product with URN {jsonld_data.get('@id', 'unknown')} already exists")
                        raise
                    
            except ValueError as e:
                # Handle already exists errors
                logger.warning(f"Creation failed for {urn if 'urn' in locals() else item.id_}: {str(e)}")
                results.append({
                    "type": type(item).__name__,
                    "urn": urn if 'urn' in locals() else item.id_,
                    "action": "skipped",
                    "reason": str(e)
                })
            except Exception as e:
                # Handle other errors
                logger.error(f"Error creating {urn if 'urn' in locals() else item.id_}: {str(e)}")
                results.append({
                    "type": type(item).__name__,
                    "urn": urn if 'urn' in locals() else item.id_,
                    "action": "failed",
                    "error": str(e)
                })
        
        # Calculate summary
        summary = {
            "product_groups_created": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "created"),
            "product_groups_updated": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "updated"),
            "product_groups_skipped": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "skipped"),
            "product_groups_failed": sum(1 for r in results if r["type"] == "ProductGroup" and r["action"] == "failed"),
            "products_created": sum(1 for r in results if r["type"] == "Product" and r["action"] == "created"),
            "products_updated": sum(1 for r in results if r["type"] == "Product" and r["action"] == "updated"),
            "products_skipped": sum(1 for r in results if r["type"] == "Product" and r["action"] == "skipped"),
            "products_failed": sum(1 for r in results if r["type"] == "Product" and r["action"] == "failed"),
            "total_items_processed": len(data.itemListElement),
            "total_successful": sum(1 for r in results if r["action"] in ["created", "updated"]),
            "total_errors": sum(1 for r in results if r["action"] in ["skipped", "failed"])
        }
        
        # Queue embedding generation for created products
        created_product_urns = [
            r["urn"] for r in results 
            if r["type"] == "Product" and r["action"] == "created"
        ]
        
        if created_product_urns:
            from app.worker.tasks.embeddings import generate_embedding_single, generate_embeddings_batch
            
            # Use single task for small batches, batch task for larger ones
            if len(created_product_urns) <= 10:
                for urn in created_product_urns:
                    generate_embedding_single.delay(urn)
                logger.info(f"Queued {len(created_product_urns)} individual embedding generation tasks")
            else:
                # Process in chunks of 100
                chunk_size = 100
                for i in range(0, len(created_product_urns), chunk_size):
                    chunk = created_product_urns[i:i + chunk_size]
                    generate_embeddings_batch.delay(chunk)
                logger.info(f"Queued {(len(created_product_urns) + chunk_size - 1) // chunk_size} batch embedding generation tasks")
        
        return {
            "status": "success",
            "summary": summary,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating products: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@products_admin_router.get("/products")
async def list_products(
    organization_id: OrganizationId,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_session)
):
    """
    List products in CMP-compliant JSON-LD format
    
    Returns products as an ItemList with ListItem elements following the CMP schema.
    
    Query parameters:
    - skip: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: 100, max: 1000)
    
    Organization context is determined by (in order of priority):
    1. X-Organization header (subdomain, e.g., "acme")
    2. Subdomain from Host header (e.g., "acme.discovery.com")
    """
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context is required. Use X-Organization header or subdomain."
        )
    
    # Enforce maximum limit
    if limit > 1000:
        limit = 1000
    
    product_service = ProductService(db)
    
    # Get products for the organization
    products = product_service.list_products_by_organization(organization_id, skip, limit)
    
    # Get total count for pagination
    total = product_service.count_products_by_organization(organization_id)
    
    # Get offers for products
    offer_service = OfferService(db)
    
    # Format each product into ItemList elements
    item_list_elements = []
    for i, product in enumerate(products):
        # Get offers for this product
        offers = offer_service.list_by_product(product.id)
        
        # Get product group if exists
        product_group = None
        if product.product_group_id:
            pg_service = ProductGroupService(db)
            product_group = pg_service.get_product_group(product.product_group_id)
        
        # Format product using existing formatter
        product_item = formatters.format_product_item(
            product=product,
            product_offers=offers,
            product_group=product_group
        )
        
        # Create list item
        list_item = {
            "@type": "ListItem",
            "position": i + 1,
            "item": product_item
        }
        item_list_elements.append(list_item)
    
    # Build response with pagination
    response = {
        "@context": {
            "schema": "https://schema.org",
            "cmp": "https://schema.commercemesh.ai/ns#"
        },
        "@type": "ItemList",
        "itemListElement": item_list_elements,
        "cmp:skip": skip,
        "cmp:limit": limit,
        "cmp:totalResults": total
    }
    
    # Add navigation helpers
    if skip + limit < total:
        response["cmp:hasNext"] = True
        response["cmp:nextSkip"] = skip + limit
    else:
        response["cmp:hasNext"] = False
    
    if skip > 0:
        response["cmp:hasPrevious"] = True
        response["cmp:previousSkip"] = max(0, skip - limit)
    else:
        response["cmp:hasPrevious"] = False
    
    return response

@products_admin_router.get("/products/{urn}")
async def get_product_admin(
    urn: str,
    organization_id: OrganizationId,
    db: Session = Depends(get_db_session)
):
    """
    Get product details in CMP-compliant JSON-LD format
    
    Returns a single product following the CMP schema structure.
    """
    if not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context is required. Use X-Organization header or subdomain."
        )
    
    product_service = ProductService(db)
    
    product = product_service.get_by_urn(urn)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with URN {urn} not found"
        )
    
    # Verify product belongs to organization
    if product.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Product belongs to different organization"
        )
    
    # Get offers for this product
    offer_service = OfferService(db)
    offers = offer_service.list_by_product(product.id)
    
    # Get product group if exists
    product_group = None
    if product.product_group_id:
        pg_service = ProductGroupService(db)
        product_group = pg_service.get_product_group(product.product_group_id)
    
    # Format product using existing formatter
    product_item = formatters.format_product_item(
        product=product,
        product_offers=offers,
        product_group=product_group
    )
    
    # The formatter already includes @context, so return directly
    return product_item