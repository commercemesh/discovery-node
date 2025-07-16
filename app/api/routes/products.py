from fastapi import APIRouter, HTTPException, Query, status, Depends, Path
from app.services.search_service import SearchService
from app.schemas.product import ProductSearchResponse, ProductDetailResponse
from app.db.base import get_db_session
from sqlalchemy.orm import Session, selectinload
from typing import List
from app.utils.formatters import format_product_search_response
import logging
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.offer_repository import OfferRepository
from app.db.repositories.product_group_repository import ProductGroupRepository
from app.db.models.product import Product
from fastapi.responses import JSONResponse
from fastapi import status

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