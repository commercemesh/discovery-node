"""Filter endpoint for filtering cached search results"""
from fastapi import APIRouter, HTTPException, status, Depends
from app.services.filter_service import FilterService
from app.services.cache_service import get_cache_service
from app.schemas.filter import FilterRequest, FilterResponse, FilterMetadata
from app.utils.request_id import validate_request_id
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

filter_router = APIRouter(
    tags=["filter"],
    responses={
        404: {"description": "Cached results not found"},
        400: {"description": "Invalid request"},
    },
)


@filter_router.post(
    "/filter",
    response_model=FilterResponse,
    status_code=status.HTTP_200_OK,
    summary="Filter cached search results",
    description="Filter previously cached search results using natural language criteria and optional price filters. Results are cached with a new request ID.",
    response_description="Filtered product list",
    responses={
        200: {
            "description": "Successfully filtered results",
            "model": FilterResponse,
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid request ID format"}
                }
            },
        },
        404: {
            "description": "Cached results not found",
            "content": {
                "application/json": {
                    "example": {"detail": "No cached results found for request ID"}
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Validation error",
                        "errors": [
                            {
                                "loc": ["body", "request_id"],
                                "msg": "String should match pattern '^[A-Z0-9]{6}$'",
                                "type": "string_pattern_mismatch"
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def filter_products(
    filter_request: FilterRequest
) -> FilterResponse:
    """
    Filter cached search results using natural language criteria.
    
    This endpoint retrieves previously cached search results and applies filtering
    based on the provided criteria. The filtering uses regex pattern matching
    to find products that match the natural language filter criteria.
    
    **Common filter criteria examples:**
    - "waterproof" - matches water-proof, water resistant, water-repellent
    - "lightweight" - matches light-weight, ultra-light
    - "wireless" - matches wireless, wi-fi, bluetooth
    - "eco friendly" - matches eco-friendly, sustainable, green
    - "premium" - matches premium, luxury, high-end
    
    **Price filtering:**
    - Use `min_price` and `max_price` to filter by offer prices
    - Products without offers will be excluded when price filters are applied
    
    The filtered results are cached with a new request ID for 15 minutes.
    """
    try:
        # Validate request ID
        if not validate_request_id(filter_request.request_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request ID format",
            )
        
        # Validate price range
        if (filter_request.min_price is not None and 
            filter_request.max_price is not None and 
            filter_request.min_price > filter_request.max_price):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum price cannot be greater than maximum price",
            )
        
        # Create filter service
        filter_service = FilterService()
        
        # Validate that at least one filter is provided
        if not filter_request.filter_criteria and filter_request.max_price is None and filter_request.min_price is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one filter criteria must be provided (text filter or price range)",
            )
        
        # Get cached data and filter
        filtered_items, total_filtered = filter_service.filter_products(
            request_id=filter_request.request_id,
            filter_criteria=filter_request.filter_criteria,
            max_price=filter_request.max_price,
            min_price=filter_request.min_price,
            limit=filter_request.limit
        )
        
        if total_filtered == 0:
            # Check if original data was found
            cache_service = get_cache_service()
            original_found = False
            for prefix in ["search", "product", "mcp-search"]:
                cache_key = f"{prefix}:{filter_request.request_id}"
                if cache_service.get_cached_response(cache_key):
                    original_found = True
                    break
            
            if not original_found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No cached results found for request ID",
                )
            # If original was found but no results after filtering, continue with empty results
        
        # Get original cached data for metadata
        cache_service = get_cache_service()
        cached_data = None
        for prefix in ["search", "product", "mcp-search"]:
            cache_key = f"{prefix}:{filter_request.request_id}"
            cached_data = cache_service.get_cached_response(cache_key)
            if cached_data:
                break
        
        # Create filtered response
        filtered_response_data = filter_service.create_filtered_response(
            cached_data=cached_data or {},
            filtered_items=filtered_items,
            total_filtered=total_filtered,
            filter_criteria=filter_request.filter_criteria,
            max_price=filter_request.max_price,
            min_price=filter_request.min_price
        )
        
        # Generate new cache key for filtered results
        new_cache_key = cache_service.generate_cache_key("filter")
        new_request_id = new_cache_key.split(":")[-1]
        
        # Add new request ID to response
        filtered_response_data["cmp:requestId"] = new_request_id
        
        # Cache the filtered results
        cache_service.cache_response(new_cache_key, filtered_response_data)
        
        # Create response object
        response = FilterResponse(**filtered_response_data)
        
        logger.info(
            f"Filtered {total_filtered} results from request {filter_request.request_id} "
            f"with criteria '{filter_request.filter_criteria}', "
            f"new request ID: {new_request_id}"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error filtering products: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Filter service error",
        )