from fastapi import APIRouter, HTTPException, Query, status, Depends, Path
from app.services.search import SearchServiceFactory
from app.services.product_service import ProductService
from app.schemas.product import ProductSearchResponse, ProductByUrnResponse
from app.db.base import get_db_session
from app.services.cache_service import get_cache_service
from app.core.dependencies import OrganizationId
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from uuid import UUID
from app.utils.formatters import format_product_search_response, format_product_by_urn_response
import logging
import urllib.parse

logger = logging.getLogger(__name__)


search_router = APIRouter(
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)


@search_router.get(
    "/search",
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
    limit: int = Query(
        default=20,
        description="Maximum number of results to return",
        ge=1,
        le=100,
        example=20,
    ),
    category: Optional[str] = Query(
        default=None,
        description="Filter results by category name",
        example="books",
    ),
    price_max: Optional[float] = Query(
        default=None,
        description="Maximum price filter",
        ge=0,
        example=100.0,
    ),
    organization_id: OrganizationId = None,
    db: Session = Depends(get_db_session),
) -> ProductSearchResponse:
    """
    Search for products using natural language queries.

    The search uses hybrid search combining dense and sparse vectors for optimal results.

    - **q**: The search query (e.g., "gaming laptop", "wireless earbuds", "running shoes")
    - **limit**: Maximum number of results to return (1-100, default: 20)
    - **category**: Optional category filter (e.g., "books", "electronics")
    - **price_max**: Optional maximum price filter

    Returns a list of products sorted by relevance score.
    """
    try:
        if not q or not q.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty",
            )

        # Get cache service
        cache_service = get_cache_service()
        
        # Generate cache key and add to response
        cache_key = cache_service.generate_cache_key("search")
        request_id = cache_key.split(":")[-1]  # Extract request ID from key
        
        # Build filters
        filters = {}
        if category:
            filters["category"] = category
        if price_max is not None:
            filters["price_max"] = price_max
            
        search_service = SearchServiceFactory.create(db)
        results = search_service.search_products(
            q, 
            top_k=limit, 
            filters=filters,
            organization_id=organization_id
        )

        response_data = format_product_search_response(results)
        
        # Add request ID to response
        response_data["cmp:requestId"] = request_id

        # Create the ProductSearchResponse object
        response = ProductSearchResponse(**response_data)
        
        # Cache the response
        cache_service.cache_response(cache_key, response_data)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during product search: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search service error",
        )
