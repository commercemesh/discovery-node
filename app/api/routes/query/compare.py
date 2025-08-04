"""Product comparison endpoint"""
from fastapi import APIRouter, HTTPException, status
from app.services.comparison_service import ComparisonService
from app.schemas.compare import CompareRequest, CompareResponse, ComparisonError
from app.utils.request_id import validate_request_id
import logging

logger = logging.getLogger(__name__)

compare_router = APIRouter(
    tags=["compare"],
    responses={
        404: {"description": "Cached results not found"},
        400: {"description": "Invalid request"},
    },
)


@compare_router.post(
    "/compare",
    response_model=CompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare products from cached results",
    description="Compare specific products from cached search results by their indices. Supports comparing 2-5 products across multiple aspects like price, features, and brand.",
    response_description="Product comparison results",
    responses={
        200: {
            "description": "Successfully compared products",
            "model": CompareResponse,
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
                                "loc": ["body", "indices"],
                                "msg": "Indices must be unique",
                                "type": "value_error"
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def compare_products(
    compare_request: CompareRequest
) -> CompareResponse:
    """
    Compare products from cached search results.
    
    This endpoint retrieves previously cached search results and compares
    the products at the specified indices. The comparison analyzes multiple
    aspects like price, features, brand, and availability.
    
    **Index specification:**
    - Indices are 0-based (first product is index 0)
    - Must specify 2-5 unique indices
    - Indices must be within the range of available products
    
    **Comparison aspects:**
    - If not specified, aspects are auto-detected from products
    - Common aspects: price, brand, features, availability, category
    
    **Output formats:**
    - "table": Structured comparison matrix (default)
    - "narrative": Natural language summary
    - "pros_cons": Pros and cons format (future enhancement)
    
    The comparison results are cached with a new request ID for 15 minutes.
    """
    try:
        # Validate request ID
        if not validate_request_id(compare_request.request_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid request ID format",
            )
        
        # Create comparison service
        comparison_service = ComparisonService()
        
        # Perform comparison
        try:
            comparison_result = comparison_service.compare_products(
                request_id=compare_request.request_id,
                indices=compare_request.indices,
                comparison_aspects=compare_request.comparison_aspects,
                format_type=compare_request.format.value if compare_request.format else "table"
            )
            
            # Create response object
            response = CompareResponse(**comparison_result)
            
            logger.info(
                f"Compared {len(compare_request.indices)} products from request {compare_request.request_id}, "
                f"new request ID: {comparison_result['cmp:requestId']}"
            )
            
            return response
            
        except ValueError as e:
            error_msg = str(e)
            
            # Handle specific error cases
            if "No cached results found" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No cached results found for request ID",
                )
            elif "out of range" in error_msg:
                # Extract available range from error message
                import re
                match = re.search(r"Available products: (\d+)-(\d+)", error_msg)
                if match:
                    start, end = int(match.group(1)), int(match.group(2))
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "Invalid indices",
                            "message": error_msg,
                            "available_range": list(range(start, end + 1))
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg,
                    )
            elif "Maximum 5 products" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Too many products",
                        "message": error_msg
                    }
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg,
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing products: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comparison service error",
        )