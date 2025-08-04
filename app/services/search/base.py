from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class SearchResult:
    """Structured search result"""
    
    id: str
    score: float
    metadata: Dict[str, Any]
    dense_score: Optional[float] = None
    sparse_score: Optional[float] = None
    # Additional product information
    product_name: Optional[str] = None
    product_urn: Optional[str] = None
    product_brand: Optional[str] = None
    product_category: Optional[str] = None
    product_price: Optional[float] = None
    product_offers: Optional[List[Dict[str, Any]]] = None
    product_description: Optional[str] = None
    product_url: Optional[str] = None
    product_media: Optional[List[Dict[str, Any]]] = None


class BaseSearchService(ABC):
    """Abstract base class for search services"""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    @abstractmethod
    def search_products(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
        filters: Optional[Dict[str, Any]] = None,
        organization_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search for products"""
        pass