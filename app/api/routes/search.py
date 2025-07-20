from fastapi import APIRouter, HTTPException, Query, status, Depends, Path
from app.services.search import SearchServiceFactory
from app.services.product_service import ProductService
from app.schemas.product import ProductSearchResponse, ProductByUrnResponse
from app.db.base import get_db_session
from sqlalchemy.orm import Session
from typing import List
from app.utils.formatters import format_product_search_response, format_product_by_urn_response
import logging
import urllib.parse

logger = logging.getLogger(__name__)


search_router = APIRouter(
    prefix="/v1",
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

        search_service = SearchServiceFactory.create(db)
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
