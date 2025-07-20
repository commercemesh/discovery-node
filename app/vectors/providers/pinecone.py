import time
import random
import logging
from typing import List, Dict, Any, Optional
from pinecone import Pinecone, ServerlessSpec

from ..base import VectorProvider
from ..types import VectorRecord, SearchResult, IndexConfig, SearchType

logger = logging.getLogger(__name__)


class PineconeProvider(VectorProvider):
    """Pinecone implementation of the VectorProvider interface."""
    
    def _setup(self):
        """Initialize Pinecone client and indexes."""
        self.client = Pinecone(api_key=self.config["api_key"])
        self.batch_size = self.config.get("batch_size", 96)
        self.namespace = self.config.get("namespace", "__default__")
        
        # Initialize indexes if they exist
        self.indexes = {}
        if "dense_index_name" in self.config:
            self.indexes["dense"] = self.client.Index(self.config["dense_index_name"])
        if "sparse_index_name" in self.config:
            self.indexes["sparse"] = self.client.Index(self.config["sparse_index_name"])
    
    def create_index(self, index_config: IndexConfig) -> bool:
        """Create a new Pinecone index."""
        try:
            existing_indexes = [idx.name for idx in self.client.list_indexes()]
            
            if index_config.name in existing_indexes:
                logger.info(f"Index {index_config.name} already exists")
                return True
            
            # Determine spec based on index type
            if index_config.index_type == "dense":
                spec = ServerlessSpec(
                    cloud=self.config.get("cloud", "aws"),
                    region=self.config.get("region", "us-east-1")
                )
                
                self.client.create_index(
                    name=index_config.name,
                    metric=index_config.metric,
                    dimension=index_config.dimension,
                    spec=spec
                )
            else:  # sparse
                spec = ServerlessSpec(
                    cloud=self.config.get("cloud", "aws"),
                    region=self.config.get("region", "us-east-1")
                )
                
                self.client.create_index(
                    name=index_config.name,
                    metric=index_config.metric,
                    spec=spec
                )
            
            # Wait for index to be ready
            while not self.client.describe_index(index_config.name).status['ready']:
                time.sleep(1)
            
            # Cache the index
            self.indexes[index_config.index_type] = self.client.Index(index_config.name)
            
            logger.info(f"Successfully created index {index_config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False
    
    def upsert_vectors(
        self,
        index_name: str,
        records: List[VectorRecord],
        namespace: Optional[str] = None
    ) -> bool:
        """Upsert vectors to Pinecone index."""
        try:
            index = self._get_index(index_name)
            namespace = namespace or self.namespace
            
            # Convert VectorRecord to Pinecone format
            pinecone_records = []
            for record in records:
                pc_record = {"id": record.id}
                
                if record.values:
                    pc_record["values"] = record.values
                    
                if record.sparse_values:
                    pc_record["sparse_values"] = {
                        "indices": list(record.sparse_values.keys()),
                        "values": list(record.sparse_values.values())
                    }
                    
                if record.metadata:
                    pc_record["metadata"] = record.metadata
                    
                pinecone_records.append(pc_record)
            
            # Batch upsert with retry logic
            self._batch_upsert_with_retry(index, pinecone_records, namespace)
            return True
            
        except Exception as e:
            logger.error(f"Failed to upsert vectors: {e}")
            return False
    
    def search(
        self,
        index_name: str,
        query: str,
        top_k: int = 10,
        search_type: SearchType = SearchType.HYBRID,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search using Pinecone's Inference API."""
        try:
            if search_type == SearchType.HYBRID:
                # Use the hybrid search method
                return self.hybrid_search(
                    index_name=index_name,
                    query=query,
                    dense_index=self.config.get("dense_index_name"),
                    sparse_index=self.config.get("sparse_index_name"),
                    top_k=top_k,
                    filter=filter,
                    namespace=namespace
                )
            
            index = self._get_index(index_name)
            namespace = namespace or self.namespace
            
            # Use Pinecone's inference API for text queries
            query_params = {
                "namespace": namespace,
                "query": {
                    "top_k": top_k,
                    "inputs": {"text": query},
                    "include_metadata": True
                }
            }
            
            if filter:
                query_params["query"]["filter"] = filter
                
            results = index.search(**query_params)
            
            # Convert to SearchResult format
            search_results = []
            for match in results.get("results", []):
                search_results.append(SearchResult(
                    id=match["id"],
                    score=match.get("score", 0.0),
                    metadata=match.get("metadata", {})
                ))
                
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_by_vector(
        self,
        index_name: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Search using a pre-computed vector."""
        try:
            index = self._get_index(index_name)
            namespace = namespace or self.namespace
            
            query_params = {
                "namespace": namespace,
                "vector": vector,
                "top_k": top_k,
                "include_metadata": True
            }
            
            if filter:
                query_params["filter"] = filter
                
            results = index.query(**query_params)
            
            # Convert to SearchResult format
            search_results = []
            for match in results.matches:
                search_results.append(SearchResult(
                    id=match.id,
                    score=match.score,
                    metadata=match.metadata if hasattr(match, 'metadata') else {}
                ))
                
            return search_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def delete_vectors(
        self,
        index_name: str,
        ids: List[str],
        namespace: Optional[str] = None
    ) -> bool:
        """Delete vectors by IDs."""
        try:
            index = self._get_index(index_name)
            namespace = namespace or self.namespace
            
            index.delete(ids=ids, namespace=namespace)
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            return False
    
    def delete_index(self, index_name: str) -> bool:
        """Delete a Pinecone index."""
        try:
            self.client.delete_index(index_name)
            
            # Remove from cache
            for key, idx in list(self.indexes.items()):
                if idx._config.host.split('.')[0] == index_name:
                    del self.indexes[key]
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check Pinecone connection health."""
        try:
            # Try to list indexes as a health check
            indexes = list(self.client.list_indexes())
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def _get_index(self, index_name: str):
        """Get index by name, checking cache first."""
        # Check if it's a type reference (dense/sparse)
        if index_name in self.indexes:
            return self.indexes[index_name]
            
        # Otherwise try to get by name
        try:
            index = self.client.Index(index_name)
            return index
        except Exception as e:
            raise ValueError(f"Index {index_name} not found: {e}")
    
    def _retry_with_backoff(self, func, max_retries=3):
        """Retry function with exponential backoff for rate limits."""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (2**attempt) + random.uniform(0, 1)
                        logger.warning(
                            f"Rate limit hit, retrying in {wait_time:.2f} seconds "
                            f"(attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                raise e
        return func()
    
    def _batch_upsert_with_retry(self, index, records: List[dict], namespace: str):
        """Batch upsert with retry logic."""
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]
            self._retry_with_backoff(
                lambda b=batch: index.upsert(vectors=b, namespace=namespace)
            )