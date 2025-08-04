from fastapi import APIRouter, HTTPException, status, Depends, Path
from app.services.product_service import ProductService
from app.schemas.product import ProductByUrnResponse
from app.db.base import get_db_session
from app.services.cache_service import get_cache_service
from app.core.dependencies import OrganizationId
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from app.utils.formatters import format_product_by_urn_response
import logging
import urllib.parse

logger = logging.getLogger(__name__)


products_router = APIRouter(
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)


@products_router.get(
    "/products/{urn}",
    response_model=ProductByUrnResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product or product group by URN",
    description="Search for a URN in both products and product groups tables. Returns different structures based on what's found: ProductGroup URN returns ProductGroup + all linked products; Product URN with ProductGroup returns both; Product URN without ProductGroup returns only the product.",
    response_description="Product and ProductGroup data in ItemList format",
    responses={
        200: {
            "description": "Product found successfully",
            "model": ProductByUrnResponse,
        },
        400: {
            "description": "Invalid URN format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid URN format"}
                }
            },
        },
        404: {
            "description": "Product not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Product not found"}
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {"example": {"detail": "Product service error"}}
            },
        },
    },
)
async def get_product_by_urn(
    urn: str = Path(
        ...,
        description="Product URN (Uniform Resource Name)",
        example="urn:cmp:sku:12345-abcde",
        min_length=1,
        max_length=500,
    ),
    organization_id: OrganizationId = None,
    db: Session = Depends(get_db_session),
) -> ProductByUrnResponse:
    """
    Search for a URN in both products and product groups tables.

    **Behavior depends on what's found:**
    
    1. **ProductGroup URN**: Returns ProductGroup + all linked Products
       - ProductGroup as first ListItem (position 1)
       - All linked Products as subsequent ListItems (positions 2, 3, etc.)
    
    2. **Product URN with ProductGroup**: Returns ProductGroup + Product
       - ProductGroup as first ListItem (position 1)
       - Product as second ListItem (position 2)
    
    3. **Product URN without ProductGroup**: Returns only Product
       - Product as first ListItem (position 1)

    The URN should be URL-encoded if it contains special characters.

    - **urn**: The URN to search for (e.g., "urn:cmp:sku:12345-abcde" or "urn:cmp:product:product-group-name")

    Returns the data in schema.org ItemList format with proper JSON-LD context.
    """
    try:
        # URL decode the URN in case it was encoded
        decoded_urn = urllib.parse.unquote(urn)
        
        # Basic URN validation
        if not decoded_urn or not decoded_urn.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URN cannot be empty",
            )

        # Validate URN format (basic check)
        if not decoded_urn.startswith("urn:"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URN format - must start with 'urn:'",
            )

        # Get cache service
        cache_service = get_cache_service()
        
        # Generate cache key and add to response
        cache_key = cache_service.generate_cache_key("product")
        request_id = cache_key.split(":")[-1]  # Extract request ID from key
        
        product_service = ProductService(db)
        product_details = product_service.get_product_with_details_by_urn(decoded_urn, organization_id)

        if not product_details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )

        response_data = format_product_by_urn_response(product_details)
        
        # Add request ID to response
        response_data["cmp:requestId"] = request_id

        # Create the ProductByUrnResponse object
        response = ProductByUrnResponse(**response_data)
        
        # Cache the response
        cache_service.cache_response(cache_key, response_data)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving product by URN {urn}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Product service error",
        )