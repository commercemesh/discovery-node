import json
import logging
from typing import List, Dict, Any, Optional
import asyncpg
from pgvector.asyncpg import register_vector
import numpy as np

from ..base import VectorProvider
from ..types import VectorRecord, SearchResult, IndexConfig, SearchType

logger = logging.getLogger(__name__)


class PgVectorProvider(VectorProvider):
    """PostgreSQL pgvector implementation of the VectorProvider interface."""
    
    def _setup(self):
        """Initialize connection pool and settings."""
        self.connection_string = self.config["connection_string"]
        self.pool = None
        self.table_prefix = self.config.get("table_prefix", "vectors")
        self.embedding_service_url = self.config.get("embedding_service_url")
        
    async def _get_pool(self):
        """Get or create connection pool."""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=self.config.get("pool_min_size", 2),
                max_size=self.config.get("pool_max_size", 10),
                setup=self._setup_connection
            )
        return self.pool
    
    async def _setup_connection(self, conn):
        """Setup pgvector extension for a connection."""
        await register_vector(conn)
        
    async def _close_pool(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    def create_index(self, index_config: IndexConfig) -> bool:
        """Create tables and indexes for vector storage."""
        import asyncio
        return asyncio.run(self._create_index_async(index_config))
    
    async def _create_index_async(self, index_config: IndexConfig) -> bool:
        """Async implementation of create_index."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                table_name = f"{self.table_prefix}_{index_config.name}"
                
                # Create pgvector extension if not exists
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                if index_config.index_type == "dense":
                    # Create table for dense vectors
                    await conn.execute(f"""
                        CREATE TABLE IF NOT EXISTS {table_name} (
                            id TEXT PRIMARY KEY,
                            vector vector({index_config.dimension}),
                            metadata JSONB,
                            namespace TEXT DEFAULT '__default__',
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    
                    # Create HNSW index for fast similarity search
                    index_method = "hnsw" if index_config.metric == "cosine" else "ivfflat"
                    ops = "vector_cosine_ops" if index_config.metric == "cosine" else "vector_l2_ops"
                    
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS {table_name}_vector_idx 
                        ON {table_name} 
                        USING {index_method} (vector {ops})
                    """)
                    
                else:  # sparse
                    # Create table for sparse vectors (stored as JSONB)
                    await conn.execute(f"""
                        CREATE TABLE IF NOT EXISTS {table_name} (
                            id TEXT PRIMARY KEY,
                            sparse_vector JSONB,
                            metadata JSONB,
                            namespace TEXT DEFAULT '__default__',
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    
                    # Create GIN index for JSONB
                    await conn.execute(f"""
                        CREATE INDEX IF NOT EXISTS {table_name}_sparse_idx 
                        ON {table_name} 
                        USING GIN (sparse_vector)
                    """)
                
                # Create indexes for common queries
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS {table_name}_namespace_idx 
                    ON {table_name} (namespace)
                """)
                
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS {table_name}_metadata_idx 
                    ON {table_name} 
                    USING GIN (metadata)
                """)
                
                logger.info(f"Successfully created table and indexes for {table_name}")
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
        """Upsert vectors to PostgreSQL."""
        import asyncio
        return asyncio.run(self._upsert_vectors_async(index_name, records, namespace))
    
    async def _upsert_vectors_async(
        self,
        index_name: str,
        records: List[VectorRecord],
        namespace: Optional[str] = None
    ) -> bool:
        """Async implementation of upsert_vectors."""
        try:
            pool = await self._get_pool()
            table_name = f"{self.table_prefix}_{index_name}"
            namespace = namespace or "__default__"
            
            async with pool.acquire() as conn:
                # Determine if this is dense or sparse based on first record
                if records and records[0].values is not None:
                    # Dense vectors
                    values = []
                    for record in records:
                        values.append((
                            record.id,
                            record.values,
                            json.dumps(record.metadata) if record.metadata else None,
                            namespace
                        ))
                    
                    await conn.executemany(f"""
                        INSERT INTO {table_name} (id, vector, metadata, namespace)
                        VALUES ($1, $2, $3::jsonb, $4)
                        ON CONFLICT (id) DO UPDATE SET
                            vector = EXCLUDED.vector,
                            metadata = EXCLUDED.metadata,
                            namespace = EXCLUDED.namespace
                    """, values)
                    
                else:
                    # Sparse vectors
                    values = []
                    for record in records:
                        sparse_json = json.dumps(record.sparse_values) if record.sparse_values else None
                        values.append((
                            record.id,
                            sparse_json,
                            json.dumps(record.metadata) if record.metadata else None,
                            namespace
                        ))
                    
                    await conn.executemany(f"""
                        INSERT INTO {table_name} (id, sparse_vector, metadata, namespace)
                        VALUES ($1, $2::jsonb, $3::jsonb, $4)
                        ON CONFLICT (id) DO UPDATE SET
                            sparse_vector = EXCLUDED.sparse_vector,
                            metadata = EXCLUDED.metadata,
                            namespace = EXCLUDED.namespace
                    """, values)
                
                logger.info(f"Successfully upserted {len(records)} records to {table_name}")
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
        """Search vectors using text query."""
        import asyncio
        return asyncio.run(self._search_async(
            index_name, query, top_k, search_type, filter, namespace
        ))
    
    async def _search_async(
        self,
        index_name: str,
        query: str,
        top_k: int = 10,
        search_type: SearchType = SearchType.HYBRID,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Async implementation of search."""
        try:
            # Get embedding for query
            query_vector = await self._get_embedding(query, search_type)
            
            if search_type == SearchType.DENSE or search_type == SearchType.HYBRID:
                return await self._search_by_vector_async(
                    index_name, query_vector, top_k, filter, namespace
                )
            else:
                # For sparse search, we'd need a sparse embedding service
                logger.warning("Sparse search not fully implemented for pgvector")
                return []
                
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
        """Search using pre-computed vector."""
        import asyncio
        return asyncio.run(self._search_by_vector_async(
            index_name, vector, top_k, filter, namespace
        ))
    
    async def _search_by_vector_async(
        self,
        index_name: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[SearchResult]:
        """Async implementation of vector search."""
        try:
            pool = await self._get_pool()
            table_name = f"{self.table_prefix}_{index_name}"
            namespace = namespace or "__default__"
            
            # Build query with optional filters
            where_clauses = [f"namespace = ${2}"]
            params = [vector, namespace]
            param_count = 3
            
            if filter:
                for key, value in filter.items():
                    where_clauses.append(f"metadata->>${key}::text = ${param_count}")
                    params.append(str(value))
                    param_count += 1
            
            where_clause = " AND ".join(where_clauses)
            
            query = f"""
                SELECT id, metadata, 
                       1 - (vector <=> $1::vector) as score
                FROM {table_name}
                WHERE {where_clause}
                ORDER BY vector <=> $1::vector
                LIMIT {top_k}
            """
            
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                
                results = []
                for row in rows:
                    results.append(SearchResult(
                        id=row['id'],
                        score=float(row['score']),
                        metadata=json.loads(row['metadata']) if row['metadata'] else {}
                    ))
                    
                return results
                
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
        import asyncio
        return asyncio.run(self._delete_vectors_async(index_name, ids, namespace))
    
    async def _delete_vectors_async(
        self,
        index_name: str,
        ids: List[str],
        namespace: Optional[str] = None
    ) -> bool:
        """Async implementation of delete_vectors."""
        try:
            pool = await self._get_pool()
            table_name = f"{self.table_prefix}_{index_name}"
            namespace = namespace or "__default__"
            
            async with pool.acquire() as conn:
                result = await conn.execute(f"""
                    DELETE FROM {table_name}
                    WHERE id = ANY($1::text[]) AND namespace = $2
                """, ids, namespace)
                
                deleted_count = int(result.split()[-1])
                logger.info(f"Deleted {deleted_count} vectors from {table_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete vectors: {e}")
            return False
    
    def delete_index(self, index_name: str) -> bool:
        """Delete table and indexes."""
        import asyncio
        return asyncio.run(self._delete_index_async(index_name))
    
    async def _delete_index_async(self, index_name: str) -> bool:
        """Async implementation of delete_index."""
        try:
            pool = await self._get_pool()
            table_name = f"{self.table_prefix}_{index_name}"
            
            async with pool.acquire() as conn:
                await conn.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                logger.info(f"Deleted table {table_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check PostgreSQL connection health."""
        import asyncio
        return asyncio.run(self._health_check_async())
    
    async def _health_check_async(self) -> bool:
        """Async implementation of health_check."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def _get_embedding(self, text: str, search_type: SearchType) -> List[float]:
        """Get embedding for text using external service."""
        # This would call your embedding service
        # For now, returning a placeholder
        # In production, this would make an HTTP request to your embedding service
        
        if self.embedding_service_url:
            # Make request to embedding service
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.embedding_service_url}/embed",
                    json={"text": text, "type": search_type.value}
                ) as resp:
                    result = await resp.json()
                    return result["embedding"]
        else:
            # Placeholder - in production, use actual embedding service
            logger.warning("No embedding service configured, using random vector")
            return np.random.rand(1024).tolist()
    
    def __del__(self):
        """Cleanup connection pool on deletion."""
        if hasattr(self, 'pool') and self.pool:
            import asyncio
            try:
                asyncio.run(self._close_pool())
            except:
                pass