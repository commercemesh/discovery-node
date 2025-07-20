from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SearchType(Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


@dataclass
class VectorRecord:
    """Represents a vector record to be stored."""
    id: str
    values: Optional[List[float]] = None  # Dense vector
    sparse_values: Optional[Dict[int, float]] = None  # Sparse vector
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    """Represents a search result."""
    id: str
    score: float
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class IndexConfig:
    """Configuration for creating an index."""
    name: str
    dimension: Optional[int] = None  # For dense vectors
    metric: str = "cosine"  # cosine, euclidean, dotproduct
    index_type: str = "dense"  # dense, sparse
    additional_config: Optional[Dict[str, Any]] = None