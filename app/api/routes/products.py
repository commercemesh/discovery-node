from fastapi import APIRouter, HTTPException, Query, status, Depends, Path, Body
from app.services.search_service import SearchService
from app.schemas.product import ProductSearchResponse, ProductDetailResponse
from app.db.base import get_db_session
from sqlalchemy.orm import Session, selectinload
from typing import List, Dict, Any, Optional
from app.utils.formatters import format_product_search_response
import logging
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.offer_repository import OfferRepository
from app.db.repositories.product_group_repository import ProductGroupRepository
from app.db.models.product import Product
from fastapi.responses import JSONResponse
from fastapi import status
from app.services.product_service import ProductService
from app.services.product_group_service import ProductGroupService
from  app.services.organization_service import OrganizationService
from app.services.brand_service import BrandService
from uuid import UUID

logger = logging.getLogger(__name__)


products_router = APIRouter(
    prefix="/v1",
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)


@products_router.get(
    "/products",
    response_model=ProductSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search for products",
    description="Search for products using a natural language query. Returns a list of relevant products ranked by similarity score.",
    response_description="List of products matching the search query",
    responses={
        200: {
            "description": "Successful product search",
            "model": ProductSearchResponse,
        },
        400: {
            "description": "Invalid search query",
            "content": {
                "application/json": {
                    "example": {"detail": "Search query cannot be empty"}
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {"example": {"detail": "Search service error"}}
            },
        },
    },
)
async def get_products(
    q: str = Query(
        default="James Cameron",
        description="Search query for finding products",
        min_length=1,
        max_length=500,
        example="wireless headphones",
    ),
    db: Session = Depends(get_db_session),
) -> ProductSearchResponse:
    """
    Search for products using natural language queries.

    The search uses hybrid search combining dense and sparse vectors for optimal results.

    - **q**: The search query (e.g., "gaming laptop", "wireless earbuds", "running shoes")

    Returns a list of products sorted by relevance score.
    """
    try:
        if not q or not q.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty",
            )

        search_service = SearchService(db)
        results = search_service.search_products(q)

        response_data = format_product_search_response(results)

        # Create the ProductSearchResponse object
        response = ProductSearchResponse(**response_data)


        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during product search: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search service error",
        )


@products_router.get(
    "/products/{sku_urn}",
    response_model=ProductDetailResponse,
    responses={
        200: {
            "description": "Product details retrieved successfully",
            "model": ProductDetailResponse,
        },
        404: {
            "description": "Product not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Product with URN 'urn:cmp:sku:1234567890' not found"
                    }
                }
            }
        },
        500: {
            "description": "Database or Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Database or internal error"
                    }
                }
            }
        }
    },
    summary="Get product details by SKU URN",
    description="Returns detailed information for a product given its unique SKU URN."
)
async def get_product(
    sku_urn: str = Path(..., description="Unique URN for product"),
    db: Session = Depends(get_db_session)
):
    """Get product details by SKU URN."""
    logger.info(f"Request received to fetch product details with SKU URN: {sku_urn}")
    try:
        product_repository = ProductRepository(db_session=db)
        product = product_repository.get_by_urn(sku_urn)

        if not product:
            not_found_msg = f"Product with URN '{sku_urn}' not found"
            logger.debug(not_found_msg)
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": not_found_msg}
            )

        try:
            # Format offers in the required JSON-LD format
            product_offers = []
            min_price = None
            
            for offer in product.offers:
                try:
                    if offer.raw_data:
                        product_offers.append(offer.raw_data)
                        
                        # Track minimum price from offers
                        if "price" in offer.raw_data and offer.raw_data["price"] is not None:
                            offer_price = float(offer.raw_data["price"])
                            if min_price is None or offer_price < min_price:
                                min_price = offer_price
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Error processing offer {offer.id}: {str(e)}")
                    continue

            # Get product media from raw_data - combine from both product and product group
            product_media = []
            
            try:
                # Extract media from product raw_data
                if product.raw_data and "@cmp:media" in product.raw_data:
                    media = product.raw_data["@cmp:media"]
                    if isinstance(media, list):
                        product_media.extend(media)
                    elif isinstance(media, dict):
                        product_media.append(media)
                
                # Extract media from product group raw_data
                if product.product_group and product.product_group.raw_data and "@cmp:media" in product.product_group.raw_data:
                    media = product.product_group.raw_data["@cmp:media"]
                    if isinstance(media, list):
                        product_media.extend(media)
                    elif isinstance(media, dict):
                        product_media.append(media)
            except (KeyError, TypeError) as e:
                logger.warning(f"Error extracting media: {str(e)}")
                product_media = []

            # Get product group info
            product_group = None
            try:
                group = product.product_group
                if group:
                    product_group = {
                        "id": str(group.id),
                        "urn": group.urn,
                        "name": group.name,
                        "category": group.category.id if group.category else ""
                    }
            except (AttributeError, TypeError) as e:
                logger.warning(f"Error processing product group: {str(e)}")
                product_group = None

            # Get product category
            product_category = None
            try:
                if product.category:
                    product_category = product.category.name
            except (AttributeError, TypeError) as e:
                logger.warning(f"Error getting product category: {str(e)}")
                product_category = None

            return ProductDetailResponse(
                id=str(product.id),
                name=product.name,
                description=product.description,
                category=product_category,
                price=min_price,
                offers=product_offers,
                media=product_media,
                group=product_group,
            )
        except (AttributeError, TypeError, KeyError) as e:
            logger.error(f"Error while processing product data: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail="Error processing product data"
            )
    except Exception as e:
        logger.error(f"Unexpected error while fetching product details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching product details"
        )


@products_router.post(
    "/product",
    status_code=status.HTTP_200_OK,
    summary="Upsert product group and/or product",
    description="Upsert a product group and/or product from a JSON-LD ItemList body. Returns the IDs of upserted objects.",
    response_description="IDs of upserted product group and/or product",
)
async def upsert_product_group_and_product(
    body: Dict[str, Any] = Body(..., description="JSON-LD ItemList with product group and/or product"),
    db: Session = Depends(get_db_session),
):
    """
    Upsert a product group and/or product from a JSON-LD ItemList body.
    Returns the IDs of upserted objects.
    """
    logger.info(f"Upsert request received: {body}")
    try:
        # Validate top-level structure
        item_list = body.get("itemListElement")
        identifier = body.get("identifier")
        if not item_list or not isinstance(item_list, list):
            raise HTTPException(status_code=400, detail="itemListElement must be a non-empty list")
        if not identifier or not isinstance(identifier, dict) or not identifier.get("value"):
            raise HTTPException(status_code=400, detail="identifier.value (organization_id) is required")
        organization_urn = identifier["value"]
        organization_service = OrganizationService(db)
        organization = organization_service.get_organization_by_urn(organization_urn)
        if not organization:
            raise  HTTPException(status_code=400, detail=f"Organization does not exist with urn {organization_urn}")
        organization_id = organization.id

        # Find product group and all product JSONs
        product_group_json = None
        product_jsons = []
        for el in item_list:
            item = el.get("item")
            if not item or not item.get("@id"):
                continue
            if item.get("@type") == "ProductGroup":
                product_group_json = item
            elif item.get("@type") == "Product":
                product_jsons.append(item)

        if not product_group_json and not product_jsons:
            raise HTTPException(status_code=400, detail="At least one of ProductGroup or Product type object must be present in itemListElement")

        # Prepare services
        product_group_service = ProductGroupService(db)
        product_service = ProductService(db)
        brand_service = BrandService(db)

        upserted = {"product_group_id": None, "successful_products": [], "errors": []}

        # --- Product Group Handling ---
        brand_id: Optional[UUID] = None
        category_name: Optional[str] = None
        if product_group_json:
            urn = product_group_json.get("@id")
            if not urn:
                logger.error("ProductGroup missing @id field")
                upserted["errors"].append({
                    "position": 0,  # Product group doesn't have position in the same way
                    "type": "ProductGroup",
                    "urn": urn or "missing",
                    "error": "ProductGroup missing @id field"
                })
                raise HTTPException(status_code=400, detail="ProductGroup missing @id field")
            # Check for brand dict
            brand_dict = product_group_json.get("brand")
            if not brand_dict or not brand_dict.get("name"):
                logger.error(f"ProductGroup {urn} missing brand dict or brand name")
                upserted["errors"].append({
                    "position": 0,
                    "type": "ProductGroup",
                    "urn": urn,
                    "error": "ProductGroup missing brand dict or brand name"
                })
                raise HTTPException(status_code=400, detail="ProductGroup missing brand dict or brand name")
            brand_name = brand_dict["name"]
            # Try to fetch brand by name
            brand = brand_service.get_by_name(brand_name)
            if not brand:
                # Create brand using process_brand
                try:
                    brand_data = {"name": brand_name, "identifier": {"value": None}}
                    brand_id_val = brand_service.process_brand(brand_data, organization_id)
                    brand = brand_service.get_brand(brand_id_val)
                except Exception as e:
                    logger.error(f"Failed to create brand {brand_name} for product group {urn}: {str(e)}")
                    upserted["errors"].append({
                        "position": 0,
                        "type": "ProductGroup",
                        "urn": urn,
                        "error": f"Failed to create brand {brand_name}: {str(e)}"
                    })
                    raise HTTPException(status_code=500, detail=f"Failed to create brand: {str(e)}")
            if not brand or not brand.id:
                logger.error(f"Failed to resolve or create brand {brand_name} for product group {urn}")
                upserted["errors"].append({
                    "position": 0,
                    "type": "ProductGroup",
                    "urn": urn,
                    "error": f"Failed to resolve or create brand {brand_name}"
                })
                raise HTTPException(status_code=500, detail="Failed to resolve or create brand")
            brand_id = brand.id
            # Upsert product group
            try:
                pg_id = product_group_service.process_product_group(product_group_json, brand_id, organization_id)
                if pg_id:
                    logger.info(f"Successfully processed product group {urn}")
                    upserted["product_group_id"] = str(pg_id)
                else:
                    logger.error(f"Failed to process product group {urn} - no ID returned")
                    upserted["errors"].append({
                        "position": 0,
                        "type": "ProductGroup",
                        "urn": urn,
                        "error": "Failed to process product group - no ID returned"
                    })
            except Exception as e:
                logger.error(f"Failed to process product group {urn}: {str(e)}")
                upserted["errors"].append({
                    "position": 0,
                    "type": "ProductGroup",
                    "urn": urn,
                    "error": f"Failed to process product group: {str(e)}"
                })
                raise HTTPException(status_code=500, detail=f"Failed to process product group: {str(e)}")
            category_name = product_group_json.get("category")

        # Need to test product scenario's, product group related working as expected.
        # --- Product Handling ---
        for product_json in product_jsons:
            # Get position from the product JSON object itself
            position = product_json.get("position", 0)
            urn = product_json.get("@id")
            if not urn:
                logger.error(f"Product at position {position} missing @id field")
                upserted["errors"].append({
                    "position": position,
                    "type": "Product",
                    "urn": urn or "missing",
                    "error": "Product missing @id field"
                })
                continue  # skip invalid product
            is_variant_of = product_json.get("isVariantOf")
            if not product_group_json:
                # Product ONLY cases
                if not is_variant_of:
                    # Upsert product without product group and isVariantOf reference
                    # We need a brand and category
                    # Extract URN
                    urn = product_json.get("@id", "")

                    if not urn:
                        logger.error(f"Product at position {position} missing required @id field")
                        upserted["errors"].append({
                            "position": position,
                            "type": "Product",
                            "urn": urn or "missing",
                            "error": "Product data missing required @id field"
                        })
                        continue

                    # Check if product already exists
                    existing_product = product_service.get_by_urn(urn)
                    if not existing_product:
                        logger.error(f"Cannot process product {urn} at position {position} without product group or isVariantOf reference")
                        upserted["errors"].append({
                            "position": position,
                            "type": "Product",
                            "urn": urn,
                            "error": "Cannot process product without product group or isVariantOf reference"
                        })
                        continue  # skip invalid product

                    brand_id = existing_product.brand_id
                    category_name = existing_product.category.name if existing_product.category else ""
                    try:
                        prod_id = product_service.process_product(product_json, brand_id, category_name)
                        if prod_id:
                            logger.info(f"Successfully processed product {urn} at position {position}")
                            upserted["successful_products"].append({
                                "position": position,
                                "type": "Product",
                                "urn": urn,
                                "product_id": str(prod_id)
                            })
                    except Exception as e:
                        logger.error(f"Failed to process product {urn} at position {position}: {str(e)}")
                        upserted["errors"].append({
                            "position": position,
                            "type": "Product",
                            "urn": urn,
                            "error": f"Failed to process product: {str(e)}"
                        })
                else:
                    # Product ONLY WITH isVariantOf
                    variant_urn = is_variant_of.get("@id") if isinstance(is_variant_of, dict) else None
                    if not variant_urn:
                        logger.error(f"Product {urn} at position {position} isVariantOf missing @id")
                        upserted["errors"].append({
                            "position": position,
                            "type": "Product",
                            "urn": urn,
                            "error": "Product isVariantOf missing @id"
                        })
                        continue  # skip invalid variant
                    # Check if product group exists
                    pg = product_group_service.get_by_urn(variant_urn)
                    if not pg:
                        logger.error(f"Cannot process product {urn} at position {position} without product group, invalid product group reference: {variant_urn}")
                        upserted["errors"].append({
                            "position": position,
                            "type": "Product",
                            "urn": urn,
                            "error": f"Cannot process product without product group, invalid product group reference: {variant_urn}"
                        })
                        continue  # skip invalid product
                    
                    brand_id = pg.brand_id
                    category_name = pg.category.name if pg.category else ""
                    try:
                        prod_id = product_service.process_product(product_json, brand_id, category_name)
                        if prod_id:
                            logger.info(f"Successfully processed product {urn} at position {position} with variant reference")
                            upserted["successful_products"].append({
                                "position": position,
                                "type": "Product",
                                "urn": urn,
                                "product_id": str(prod_id)
                            })
                    except Exception as e:
                        logger.error(f"Failed to process product {urn} at position {position}: {str(e)}")
                        upserted["errors"].append({
                            "position": position,
                            "type": "Product",
                            "urn": urn,
                            "error": f"Failed to process product: {str(e)}"
                        })
            else:
                # Both product group and product present
                if not brand_id or not category_name:
                    logger.error(f"Cannot process product {urn} at position {position} without brand or category from product group")
                    upserted["errors"].append({
                        "position": position,
                        "type": "Product",
                        "urn": urn,
                        "error": "Cannot process product without brand or category from product group"
                    })
                    continue  # skip if not resolved
                try:
                    prod_id = product_service.process_product(product_json, brand_id, category_name)
                    if prod_id:
                        logger.info(f"Successfully processed product {urn} at position {position} with product group")
                        upserted["successful_products"].append({
                            "position": position,
                            "type": "Product",
                            "urn": urn,
                            "product_id": str(prod_id)
                        })
                except Exception as e:
                    logger.error(f"Failed to process product {urn} at position {position}: {str(e)}")
                    upserted["errors"].append({
                        "position": position,
                        "type": "Product",
                        "urn": urn,
                        "error": f"Failed to process product: {str(e)}"
                    })
        return upserted
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during upsert: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")