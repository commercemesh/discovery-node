"""Cache retrieval endpoint"""
from fastapi import APIRouter, HTTPException, status, Path
from app.services.cache_service import get_cache_service
from app.utils.request_id import validate_request_id
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

cache_router = APIRouter(
    prefix="/v1/cache",
    tags=["cache"],
    responses={
        404: {"description": "Cached response not found"},
        400: {"description": "Invalid request ID"},
    },
)


@cache_router.get(
    "/{request_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Retrieve cached response by request ID",
    description="Retrieve a previously cached API response using its request ID. Cache entries expire after 15 minutes.",
    response_description="The cached response data",
    responses={
        200: {
            "description": "Cached response found",
            "content": {
                "application/json": {
                    "example": {
                        "@context": "https://schema.org",
                        "@type": "ItemList",
                        "cmp:requestId": "ABC123",
                        "itemListElement": []
                    }
                }
            },
        },
        400: {
            "description": "Invalid request ID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid request ID format"}
                }
            },
        },
        404: {
            "description": "Cached response not found or expired",
            "content": {
                "application/json": {
                    "example": {"detail": "Cached response not found"}
                }
            },
        },
    },
)
async def get_cached_response(
    request_id: str = Path(
        ...,
        description="6-character request ID",
        example="ABC123",
        min_length=6,
        max_length=6,
        regex="^[A-Z0-9]{6}$",
    ),
) -> Dict[str, Any]:
    """
    Retrieve a cached response by its request ID.
    
    Request IDs are 6-character alphanumeric codes (uppercase letters and digits)
    that are returned in API responses. Cache entries have a 15-minute TTL.
    
    - **request_id**: The 6-character request ID from a previous API response
    
    Returns the original cached response if found and not expired.
    """
    try:
        # Validate request ID format
        if not validate_request_id(request_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request ID format",
            )
        
        # Get cache service
        cache_service = get_cache_service()
        
        # Try different cache key prefixes
        prefixes = ["search", "product", "mcp-search"]
        cached_data = None
        
        for prefix in prefixes:
            cache_key = f"{prefix}:{request_id}"
            cached_data = cache_service.get_cached_response(cache_key)
            if cached_data:
                logger.info(f"Cache hit for request ID {request_id} with prefix {prefix}")
                break
        
        if not cached_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cached response not found",
            )
        
        return cached_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving cached response for {request_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache service error",
        )