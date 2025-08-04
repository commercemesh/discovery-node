"""Product comparison request and response schemas"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Literal
from enum import Enum


class ComparisonFormat(str, Enum):
    """Output format for comparison results"""
    TABLE = "table"
    NARRATIVE = "narrative"
    PROS_CONS = "pros_cons"


class CompareRequest(BaseModel):
    """Request model for product comparison"""
    
    request_id: str = Field(
        ...,
        description="6-character cache request ID",
        min_length=6,
        max_length=6,
        pattern="^[A-Z0-9]{6}$",
        example="K3M9X2"
    )
    indices: List[int] = Field(
        ...,
        description="Product indices to compare (0-based)",
        min_items=2,
        max_items=5,
        example=[0, 1, 2]
    )
    comparison_aspects: Optional[List[str]] = Field(
        None,
        description="Specific aspects to compare. If not provided, auto-detected from products",
        example=["price", "features", "brand"]
    )
    format: Optional[ComparisonFormat] = Field(
        ComparisonFormat.TABLE,
        description="Output format for comparison",
        example="table"
    )
    
    @validator('indices')
    def validate_indices(cls, v):
        """Ensure indices are non-negative and unique"""
        if any(idx < 0 for idx in v):
            raise ValueError("Indices must be non-negative")
        if len(set(v)) != len(v):
            raise ValueError("Indices must be unique")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "K3M9X2",
                "indices": [0, 1, 2],
                "comparison_aspects": ["price", "features"],
                "format": "table"
            }
        }


class Recommendations(BaseModel):
    """Product recommendations based on comparison"""
    
    best_value: int = Field(..., description="Index of best value product")
    premium_choice: int = Field(..., description="Index of premium option")
    budget_option: int = Field(..., description="Index of budget choice")


class ComparisonError(BaseModel):
    """Error response for comparison failures"""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Human-readable error message")
    available_range: Optional[List[int]] = Field(
        None,
        description="Available index range when indices are out of bounds"
    )


class CompareResponse(BaseModel):
    """Response model for product comparison in JSON-LD format"""
    
    context: Dict[str, str] = Field(
        default={
            "schema": "https://schema.org",
            "cmp": "https://schema.commercemesh.ai/ns#",
        },
        alias="@context",
        description="JSON-LD context",
    )
    type: str = Field(
        default="ComparisonResult",
        alias="@type",
        description="Schema.org type"
    )
    cmp_requestId: str = Field(
        ...,
        alias="cmp:requestId",
        description="New request ID for comparison results"
    )
    cmp_originalRequestId: str = Field(
        ...,
        alias="cmp:originalRequestId",
        description="Reference to source results"
    )
    cmp_comparedIndices: List[int] = Field(
        ...,
        alias="cmp:comparedIndices",
        description="Which products were compared"
    )
    cmp_comparisonAspects: List[str] = Field(
        ...,
        alias="cmp:comparisonAspects",
        description="Aspects used for comparison"
    )
    products: List[Dict[str, Any]] = Field(
        ...,
        description="Full product details for compared items"
    )
    comparisonMatrix: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Detailed comparison matrix across aspects"
    )
    narrative: str = Field(
        ...,
        description="Natural language summary of comparison"
    )
    recommendations: Recommendations = Field(
        ...,
        description="Product recommendations based on comparison"
    )
    datePublished: Optional[str] = Field(
        None,
        description="Publication date in ISO format"
    )
    
    class Config:
        populate_by_name = True