from typing import List, Dict, Any, Optional
import time
import logging
from sqlalchemy import text
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.db.repositories.product_repository import ProductRepository
from .base import BaseSearchService, SearchResult

logger = get_logger(__name__)


class PgVectorSearchService(BaseSearchService):
    """Handles similarity search using pgvector"""
    
    def __init__(self, db_session):
        super().__init__(db_session)
        self.product_repository = ProductRepository(db_session)
    
    def search_products(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
    ) -> List[SearchResult]:
        """Search for products using pgvector similarity search"""
        
        try:
            start_time = time.time()
            logger.info(f"🔍 Searching pgvector for query: '{query}'")
            
            # Get embedding for query
            query_embedding = self._get_query_embedding(query)
            
            # Perform similarity search
            results = self._search_by_embedding(query_embedding, top_k)
            
            total_time = time.time() - start_time
            logger.info(f"✅ Search completed in {total_time:.3f}s, found {len(results)} results")
            
            return results
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ Search failed after {total_time:.3f}s: {str(e)}")
            raise
    
    def _get_query_embedding(self, query: str) -> List[float]:
        """Get embedding for query text using OpenAI"""
        if not settings.EMBEDDING_API_KEY:
            logger.warning("No embedding API key, using random embedding for testing")
            return np.random.rand(settings.EMBEDDING_DIMENSION).tolist()
        
        try:
            import openai
            client = openai.OpenAI(api_key=settings.EMBEDDING_API_KEY)
            
            logger.info(f"Getting embedding for query: '{query}' using {settings.EMBEDDING_MODEL_NAME}")
            
            response = client.embeddings.create(
                model=settings.EMBEDDING_MODEL_NAME,
                input=query
            )
            
            embedding = response.data[0].embedding
            logger.info(f"Successfully got embedding with dimension: {len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to get query embedding: {e}")
            # Fallback to random for testing
            return np.random.rand(settings.EMBEDDING_DIMENSION).tolist()
    
    def _search_by_embedding(self, embedding: List[float], top_k: int) -> List[SearchResult]:
        """Search products by embedding similarity"""
        
        logger.info(f"Searching with embedding dimension: {len(embedding)}, top_k: {top_k}")
        
        # First check if we have any products with embeddings
        count_query = text("SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL")
        count = self.db_session.execute(count_query).scalar()
        logger.info(f"Total products with embeddings: {count}")
        
        # Build the similarity search query
        query_sql = text("""
            SELECT 
                p.urn as id,
                p.id as product_id,
                1 - (p.embedding <=> CAST(:embedding AS vector)) as score,
                p.name,
                p.description,
                p.url,
                b.name as brand_name,
                c.name as category_name,
                o.price,
                o.price_currency,
                o.availability,
                o.inventory_level,
                o.seller_id,
                p.raw_data
            FROM products p
            JOIN brands b ON p.brand_id = b.id
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN offers o ON o.product_id = p.id
            WHERE p.embedding IS NOT NULL
            ORDER BY p.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)
        
        rows = self.db_session.execute(
            query_sql,
            {"embedding": embedding, "limit": top_k}
        ).fetchall()
        
        logger.info(f"Found {len(rows)} results from pgvector search")
        
        # Convert to SearchResult objects
        results = []
        for row in rows:
            # Extract media from raw_data
            media = []
            if row.raw_data:
                media = self._extract_media_from_jsonld(row.raw_data)
            
            result = SearchResult(
                id=row.id,
                score=float(row.score),
                metadata={
                    "brand": row.brand_name,
                    "category": row.category_name,
                    "price": float(row.price) if row.price else None,
                    "availability": row.availability
                },
                product_name=row.name,
                product_urn=row.id,
                product_brand=row.brand_name,
                product_category=row.category_name,
                product_description=row.description,
                product_url=row.url,
                product_media=media
            )
            
            # Add offer information
            if row.price:
                result.product_price = float(row.price)
                result.product_offers = [{
                    "price": float(row.price),
                    "currency": row.price_currency,
                    "availability": row.availability,
                    "inventory_level": row.inventory_level,
                    "seller_id": str(row.seller_id) if row.seller_id else None
                }]
            
            results.append(result)
        
        return results
    
    def _extract_media_from_jsonld(self, jsonld: dict) -> List[Dict[str, Any]]:
        """Extract media information from JSON-LD raw_data"""
        media = []
        
        # Check for @cmp:media field
        if "@cmp:media" in jsonld:
            cmp_media = jsonld["@cmp:media"]
            if isinstance(cmp_media, list):
                for item in cmp_media:
                    if isinstance(item, dict) and item.get("@type") == "ImageObject":
                        media.append({
                            "type": "image",
                            "url": item.get("url"),
                            "caption": item.get("caption", ""),
                            "width": item.get("width"),
                            "height": item.get("height")
                        })
            elif isinstance(cmp_media, dict) and cmp_media.get("@type") == "ImageObject":
                media.append({
                    "type": "image",
                    "url": cmp_media.get("url"),
                    "caption": cmp_media.get("caption", ""),
                    "width": cmp_media.get("width"),
                    "height": cmp_media.get("height")
                })
        
        # Also check for direct image field
        if "image" in jsonld and isinstance(jsonld["image"], str):
            media.append({
                "type": "image",
                "url": jsonld["image"],
                "caption": "",
                "width": None,
                "height": None
            })
        
        return media