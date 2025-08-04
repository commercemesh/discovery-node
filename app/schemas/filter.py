"""Filter request and response schemas"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class FilterRequest(BaseModel):
    """Request model for filtering cached results"""
    
    request_id: str = Field(
        ...,
        description="6-character cache request ID",
        min_length=6,
        max_length=6,
        pattern="^[A-Z0-9]{6}$",
        example="K3M9X2"
    )
    filter_criteria: Optional[str] = Field(
        None,
        description="Natural language filter criteria (optional when using price filters)",
        min_length=1,
        max_length=200,
        example="waterproof"
    )
    max_price: Optional[float] = Field(
        None,
        description="Maximum price filter",
        ge=0,
        example=100.0
    )
    min_price: Optional[float] = Field(
        None,
        description="Minimum price filter",
        ge=0,
        example=20.0
    )
    limit: Optional[int] = Field(
        None,
        description="Maximum number of results to return",
        ge=1,
        le=100,
        example=10
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "K3M9X2",
                "filter_criteria": "waterproof",
                "max_price": 100.0,
                "min_price": 20.0,
                "limit": 10
            }
        }


class FilterMetadata(BaseModel):
    """Metadata about applied filters"""
    
    criteria: Optional[str] = Field(None, description="Applied filter criteria")
    maxPrice: Optional[float] = Field(None, description="Applied maximum price filter")
    minPrice: Optional[float] = Field(None, description="Applied minimum price filter")
    originalTotal: int = Field(..., description="Total results before filtering")


class FilterResponse(BaseModel):
    """Response model for filtered results in JSON-LD format"""
    
    context: Dict[str, str] = Field(
        default={
            "schema": "https://schema.org",
            "cmp": "https://schema.commercemesh.ai/ns#",
        },
        alias="@context",
        description="JSON-LD context",
    )
    type: str = Field(
        default="ItemList",
        alias="@type",
        description="Schema.org type"
    )
    itemListElement: List[Dict[str, Any]] = Field(
        ...,
        description="Filtered list of products"
    )
    cmp_totalResults: int = Field(
        ...,
        alias="cmp:totalResults",
        description="Total number of filtered results"
    )
    cmp_nodeVersion: str = Field(
        default="v1.0.0",
        alias="cmp:nodeVersion",
        description="Node version"
    )
    cmp_requestId: str = Field(
        ...,
        alias="cmp:requestId",
        description="New request ID for filtered results"
    )
    cmp_filterApplied: FilterMetadata = Field(
        ...,
        alias="cmp:filterApplied",
        description="Information about applied filters"
    )
    datePublished: Optional[str] = Field(
        None,
        description="Publication date in ISO format"
    )
    
    class Config:
        populate_by_name = True