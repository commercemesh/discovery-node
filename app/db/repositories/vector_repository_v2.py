import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.vectors import VectorProviderFactory, VectorProvider
from app.vectors.types import VectorRecord, SearchResult, IndexConfig, SearchType

logger = logging.getLogger(__name__)


class VectorRepositoryV2:
    """Vector repository using the provider abstraction pattern."""
    
    def __init__(self):
        """Initialize with configured vector provider."""
        self.provider = self._create_provider()
        self.namespace = settings.PINECONE_NAMESPACE  # Keep for backward compatibility
        
    def _create_provider(self) -> VectorProvider:
        """Create vector provider based on configuration."""
        provider_name = settings.VECTOR_PROVIDER
        
        if provider_name == "pinecone":
            config = {
                "api_key": settings.PINECONE_API_KEY,
                "batch_size": settings.PINECONE_BATCH_SIZE,
                "namespace": settings.PINECONE_NAMESPACE,
                "dense_index_name": settings.PINECONE_DENSE_INDEX,
                "sparse_index_name": settings.PINECONE_SPARSE_INDEX,
                "cloud": settings.PINECONE_CLOUD,
                "region": settings.PINECONE_REGION
            }
        elif provider_name == "pgvector":
            config = {
                "connection_string": settings.PGVECTOR_CONNECTION_STRING,
                "table_prefix": settings.PGVECTOR_TABLE_PREFIX,
                "pool_min_size": settings.PGVECTOR_POOL_MIN_SIZE,
                "pool_max_size": settings.PGVECTOR_POOL_MAX_SIZE,
                "embedding_service_url": settings.PGVECTOR_EMBEDDING_SERVICE_URL
            }
        else:
            raise ValueError(f"Unknown vector provider: {provider_name}")
            
        return VectorProviderFactory.create(provider_name, config)
    
    def upsert_products_into_dense_index(self, records: List[Dict[str, Any]]):
        """Upsert products into dense vector index."""
        # Convert to VectorRecord format
        vector_records = []
        for record in records:
            vector_record = VectorRecord(
                id=record["id"],
                values=record.get("values"),
                metadata=record.get("metadata")
            )
            vector_records.append(vector_record)
        
        index_name = (settings.PINECONE_DENSE_INDEX if settings.VECTOR_PROVIDER == "pinecone" 
                     else "dense")
        
        success = self.provider.batch_upsert_vectors(
            index_name=index_name,
            records=vector_records,
            batch_size=settings.PINECONE_BATCH_SIZE,
            namespace=self.namespace
        )
        
        if not success:
            raise Exception("Failed to upsert products to dense index")
    
    def upsert_products_into_sparse_index(self, records: List[Dict[str, Any]]):
        """Upsert products into sparse vector index."""
        # Convert to VectorRecord format
        vector_records = []
        for record in records:
            # Convert sparse values format if needed
            sparse_values = None
            if "sparse_values" in record:
                if isinstance(record["sparse_values"], dict):
                    if "indices" in record["sparse_values"] and "values" in record["sparse_values"]:
                        # Convert from Pinecone format to dict format
                        sparse_values = dict(zip(
                            record["sparse_values"]["indices"],
                            record["sparse_values"]["values"]
                        ))
                    else:
                        sparse_values = record["sparse_values"]
            
            vector_record = VectorRecord(
                id=record["id"],
                sparse_values=sparse_values,
                metadata=record.get("metadata")
            )
            vector_records.append(vector_record)
        
        index_name = (settings.PINECONE_SPARSE_INDEX if settings.VECTOR_PROVIDER == "pinecone" 
                     else "sparse")
        
        success = self.provider.batch_upsert_vectors(
            index_name=index_name,
            records=vector_records,
            batch_size=settings.PINECONE_BATCH_SIZE,
            namespace=self.namespace
        )
        
        if not success:
            raise Exception("Failed to upsert products to sparse index")
    
    def _search_dense_index(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Search dense vector index."""
        index_name = (settings.PINECONE_DENSE_INDEX if settings.VECTOR_PROVIDER == "pinecone" 
                     else "dense")
        
        results = self.provider.search(
            index_name=index_name,
            query=query,
            top_k=top_k,
            search_type=SearchType.DENSE,
            namespace=self.namespace
        )
        
        # Convert to expected format
        return self._format_search_results(results)
    
    def _search_sparse_index(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Search sparse vector index."""
        index_name = (settings.PINECONE_SPARSE_INDEX if settings.VECTOR_PROVIDER == "pinecone" 
                     else "sparse")
        
        results = self.provider.search(
            index_name=index_name,
            query=query,
            top_k=top_k,
            search_type=SearchType.SPARSE,
            namespace=self.namespace
        )
        
        # Convert to expected format
        return self._format_search_results(results)
    
    def _format_search_results(self, results: List[SearchResult]) -> Dict[str, Any]:
        """Format search results to match expected output format."""
        # Convert to match the existing format
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "metadata": result.metadata or {}
            })
        
        return {
            "results": formatted_results
        }
    
    def create_indexes(self):
        """Create necessary indexes if they don't exist."""
        if settings.VECTOR_PROVIDER == "pinecone":
            # Pinecone indexes are created via the setup script
            logger.info("Pinecone indexes should be created via setup_pinecone.py")
        else:
            # Create dense index
            dense_config = IndexConfig(
                name="dense",
                dimension=1024,  # llama-text-embed-v2 dimension
                metric="cosine",
                index_type="dense"
            )
            self.provider.create_index(dense_config)
            
            # Create sparse index
            sparse_config = IndexConfig(
                name="sparse",
                metric="dotproduct",
                index_type="sparse"
            )
            self.provider.create_index(sparse_config)
    
    def health_check(self) -> bool:
        """Check if vector provider is healthy."""
        return self.provider.health_check()
    
    # Backward compatibility methods
    def _retry_with_backoff(self, func, max_retries=3):
        """Backward compatibility - providers handle retries internally."""
        return func()
    
    def _batch_upsert(self, index, records: List[Dict]):
        """Backward compatibility - redirects to new methods."""
        if "dense" in str(index):
            self.upsert_products_into_dense_index(records)
        else:
            self.upsert_products_into_sparse_index(records)