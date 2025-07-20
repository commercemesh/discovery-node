from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import logging

from .types import VectorRecord, SearchResult, IndexConfig, SearchType

logger = logging.getLogger(__name__)


class VectorProvider(ABC):
    """Abstract base class for vector storage providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the vector provider with configuration."""
        self.config = config
        self._setup()
    
    @abstractmethod
    def _setup(self):
        """Setup provider-specific resources."""
        pass
    
    @abstractmethod
    def create_index(self, index_config: IndexConfig) -> bool:
        """Create a new index/collection for storing vectors.
        
        Args:
            index_config: Configuration for the index
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def upsert_vectors(
        self,
        index_name: str,
        records: List[VectorRecord],
        namespace: Optional[str] = None
    ) -> bool:
        """Insert or update vectors in the specified index.
        
        Args:
            index_name: Name of the index to upsert into
            records: List of vector records to upsert
            namespace: Optional namespace for organization
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def search(
        self,
        index_name: str,
        query: str,
        top_k: int = 10,
        search_type: SearchType = SearchType.HYBRID,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search for similar vectors.
        
        Args:
            index_name: Name of the index to search
            query: Search query text
            top_k: Number of results to return
            search_type: Type of search (dense, sparse, hybrid)
            filter: Optional metadata filters
            namespace: Optional namespace for organization
            
        Returns:
            List of search results
        """
        pass
    
    @abstractmethod
    def search_by_vector(
        self,
        index_name: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search using a pre-computed vector.
        
        Args:
            index_name: Name of the index to search
            vector: Query vector
            top_k: Number of results to return
            filter: Optional metadata filters
            namespace: Optional namespace for organization
            
        Returns:
            List of search results
        """
        pass
    
    @abstractmethod
    def delete_vectors(
        self,
        index_name: str,
        ids: List[str],
        namespace: Optional[str] = None
    ) -> bool:
        """Delete vectors by their IDs.
        
        Args:
            index_name: Name of the index
            ids: List of vector IDs to delete
            namespace: Optional namespace
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_index(self, index_name: str) -> bool:
        """Delete an entire index.
        
        Args:
            index_name: Name of the index to delete
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is healthy and accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def batch_upsert_vectors(
        self,
        index_name: str,
        records: List[VectorRecord],
        batch_size: int = 100,
        namespace: Optional[str] = None
    ) -> bool:
        """Batch upsert vectors for better performance.
        
        Default implementation uses sequential batching.
        Providers can override for optimized implementations.
        
        Args:
            index_name: Name of the index
            records: List of vector records
            batch_size: Size of each batch
            namespace: Optional namespace
            
        Returns:
            True if all batches successful, False otherwise
        """
        success = True
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            if not self.upsert_vectors(index_name, batch, namespace):
                success = False
                logger.error(f"Failed to upsert batch {i//batch_size + 1}")
        return success
    
    def hybrid_search(
        self,
        index_name: str,
        query: str,
        dense_index: Optional[str] = None,
        sparse_index: Optional[str] = None,
        top_k: int = 10,
        alpha: float = 0.5,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Perform hybrid search combining dense and sparse results.
        
        Default implementation for providers that don't have native hybrid search.
        Uses Reciprocal Rank Fusion (RRF) to merge results.
        
        Args:
            index_name: Primary index name
            query: Search query
            dense_index: Name of dense index (if different)
            sparse_index: Name of sparse index (if different)
            top_k: Number of results to return
            alpha: Weight for dense results (1-alpha for sparse)
            filter: Optional metadata filters
            namespace: Optional namespace
            
        Returns:
            Merged search results
        """
        # Get dense results
        dense_results = self.search(
            dense_index or index_name,
            query,
            top_k=top_k * 2,  # Get more for merging
            search_type=SearchType.DENSE,
            filter=filter,
            namespace=namespace
        )
        
        # Get sparse results
        sparse_results = self.search(
            sparse_index or index_name,
            query,
            top_k=top_k * 2,
            search_type=SearchType.SPARSE,
            filter=filter,
            namespace=namespace
        )
        
        # Merge using RRF
        return self._rrf_merge(dense_results, sparse_results, top_k, alpha)
    
    def _rrf_merge(
        self,
        dense_results: List[SearchResult],
        sparse_results: List[SearchResult],
        top_k: int,
        alpha: float = 0.5,
        k: int = 60
    ) -> List[SearchResult]:
        """Reciprocal Rank Fusion to merge dense and sparse results.
        
        Args:
            dense_results: Results from dense search
            sparse_results: Results from sparse search
            top_k: Number of results to return
            alpha: Weight for dense results
            k: RRF constant (typically 60)
            
        Returns:
            Merged results
        """
        scores = {}
        
        # Score dense results
        for rank, result in enumerate(dense_results):
            rrf_score = alpha / (k + rank + 1)
            scores[result.id] = scores.get(result.id, 0) + rrf_score
            
        # Score sparse results  
        for rank, result in enumerate(sparse_results):
            rrf_score = (1 - alpha) / (k + rank + 1)
            scores[result.id] = scores.get(result.id, 0) + rrf_score
            
        # Sort by combined score
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Build merged results
        id_to_result = {r.id: r for r in dense_results + sparse_results}
        merged_results = []
        
        for id, score in sorted_items[:top_k]:
            if id in id_to_result:
                result = id_to_result[id]
                result.score = score  # Update with RRF score
                merged_results.append(result)
                
        return merged_results