from typing import List, Dict, Any, Optional
import time
from app.core.logging import get_logger
from app.db.repositories.vector_repository import VectorRepository
from app.db.repositories.product_repository import ProductRepository
from .base import BaseSearchService, SearchResult

logger = get_logger(__name__)


class PineconeSearchService(BaseSearchService):
    """Handles hybrid search using Pinecone's Inference API"""

    def __init__(self, db_session):
        super().__init__(db_session)
        self.vector_repository = VectorRepository()
        self.product_repository = ProductRepository(db_session)

    def search_products(
        self,
        query: str,
        top_k: int = 20,
        alpha: float = 0.7,
        include_metadata: bool = True,
    ):
        """Search for products using Pinecone's dense and sparse indices"""

        try:
            # Reduced fetch multiplier since inference is faster
            fetch_k = min(top_k * 2, 50)
            logger.info(
                f"🔍 Querying Pinecone indices with Inference API (fetch_k={fetch_k})..."
            )
            start_time = time.time()
            dense_results = self.vector_repository._search_dense_index(
                query, fetch_k, alpha, include_metadata
            )
            sparse_results = self.vector_repository._search_sparse_index(
                query, fetch_k, alpha, include_metadata
            )

            logger.info(f"🔍 DEBUG: Dense results type: {type(dense_results)}")
            logger.info(f"🔍 DEBUG: Sparse results type: {type(sparse_results)}")

            dense_hits = self._hits(dense_results)
            sparse_hits = self._hits(sparse_results)
            
            logger.info(f"🔍 DEBUG: Dense hits count: {len(dense_hits)}")
            logger.info(f"🔍 DEBUG: Sparse hits count: {len(sparse_hits)}")
            merged_results = self.rrf_merge(dense_hits, sparse_hits, k=60, top_k=20)

            # #Optional database enrichment
            if merged_results:
                logger.info("🔗 Enriching with database data...")
                enrich_start = time.time()
                enriched_results = self._enrich_with_product_data(merged_results)
                enrich_time = time.time() - enrich_start
                logger.info(f"✅ Database enrichment completed in {enrich_time:.3f}s")
            else:
                enriched_results = merged_results
                enrich_time = 0

            total_time = time.time() - start_time
            logger.info(f"✅ Search completed in {total_time:.3f}s")
            return enriched_results
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ Search failed after {total_time:.3f}s: {str(e)}")
            raise

    def _hits(self, resp):
        """
        Return list of {'id', 'score', 'metadata'} with all product fields from Pinecone
        """
        logger.info(f"🔍 DEBUG: _hits input type: {type(resp)}")

        if hasattr(resp, "result") and hasattr(resp.result, "hits"):
            # SearchRecordsResponse object
            raw = resp.result.hits
            logger.info(
                f"🔍 DEBUG: Using SearchRecordsResponse format, raw hits: {len(raw) if raw else 0}"
            )
            # Log the first hit to see its structure
            if raw and len(raw) > 0:
                logger.info(f"🔍 DEBUG: First hit type: {type(raw[0])}")
                logger.info(f"🔍 DEBUG: First hit attrs: {dir(raw[0]) if hasattr(raw[0], '__dict__') else 'N/A'}")
                # Try to get the actual data
                first_hit = raw[0]
                if hasattr(first_hit, 'to_dict'):
                    logger.info(f"🔍 DEBUG: First hit as dict: {first_hit.to_dict()}")
                if hasattr(first_hit, '_data_store'):
                    logger.info(f"🔍 DEBUG: First hit data store: {first_hit._data_store}")
        elif hasattr(resp, "data") and hasattr(resp.data, "result"):
            # SearchResponse object
            raw = resp.data.result.hits
            logger.info(
                f"🔍 DEBUG: Using SearchResponse format, raw hits: {len(raw) if raw else 0}"
            )
        elif isinstance(resp, dict) and "results" in resp:
            # Dict response from Pinecone inference
            raw = resp.get("results", [])
            logger.info(
                f"🔍 DEBUG: Using dict response format, raw hits: {len(raw)}"
            )
        else:
            logger.warning(f"🔍 DEBUG: Unknown response format, resp attrs: {dir(resp) if hasattr(resp, '__dict__') else 'N/A'}")
            return []

        formatted = []
        for i, h in enumerate(raw):
            # Try direct attributes first
            if hasattr(h, "get"):
                # Use get method for Hit objects - they use _id and _score
                hit_id = h.get("_id") or h.get("id")
                hit_score = h.get("_score") or h.get("score")
                hit_fields = h.get("fields", {})
                
                if hit_id is not None:
                    formatted.append(
                        {
                            "id": hit_id,
                            "score": float(hit_score) if hit_score else 0.0,
                            "metadata": hit_fields,
                        }
                    )
                else:
                    logger.warning(f"🔍 DEBUG: Hit with null id at index {i}")
            elif hasattr(h, "hit"):
                # SearchResultHit object
                hit_data = h.hit
                if hit_data is not None:
                    formatted.append(
                        {
                            "id": hit_data.id,
                            "score": hit_data.score,
                            "metadata": getattr(hit_data, "metadata", {}),
                        }
                    )
                else:
                    logger.warning(f"🔍 DEBUG: Null hit data at index {i}")
            elif isinstance(h, dict):
                # Direct dict format
                if h.get("id") is not None:
                    formatted.append(
                        {
                            "id": h.get("id"),
                            "score": h.get("score", 0.0),
                            "metadata": h.get("metadata", {}),
                        }
                    )
                else:
                    logger.warning(f"🔍 DEBUG: Dict hit without id at index {i}")
            else:
                logger.warning(
                    f"🔍 DEBUG: Unknown hit format at index {i}: {type(h)}, attrs: {dir(h) if hasattr(h, '__dict__') else str(h)}"
                )

        logger.info(
            f"🔍 DEBUG: _hits returning {len(formatted)} formatted results"
        )
        # Extract just the first 3 IDs for logging
        sample_ids = [r["id"] for r in formatted[:3]]
        logger.info(f"🔍 DEBUG: Sample IDs: {sample_ids}")
        return formatted

    def rrf_merge(self, dense_hits, sparse_hits, k=60, top_k=20):
        """
        Reciprocal Rank Fusion to merge dense and sparse results
        """
        logger.info(f"Merging {len(dense_hits)} dense and {len(sparse_hits)} sparse hits")
        scores = {}

        # Score dense results
        for rank, hit in enumerate(dense_hits):
            id = hit["id"]
            if id is None:
                continue
            rrf_score = 1.0 / (k + rank + 1)
            
            if id not in scores:
                scores[id] = {
                    "rrf_score": 0,
                    "dense_score": hit["score"],
                    "sparse_score": 0,
                    "metadata": hit.get("metadata", {})
                }
            
            scores[id]["rrf_score"] += rrf_score
            scores[id]["dense_score"] = hit["score"]

        # Score sparse results
        for rank, hit in enumerate(sparse_hits):
            id = hit["id"]
            if id is None:
                continue
            rrf_score = 1.0 / (k + rank + 1)
            
            if id not in scores:
                scores[id] = {
                    "rrf_score": 0,
                    "dense_score": 0,
                    "sparse_score": hit["score"],
                    "metadata": hit.get("metadata", {})
                }
            
            scores[id]["rrf_score"] += rrf_score
            scores[id]["sparse_score"] = hit["score"]

        # Sort by RRF score
        sorted_items = sorted(
            [(id, score_data) for id, score_data in scores.items()],
            key=lambda x: x[1]["rrf_score"],
            reverse=True,
        )[:top_k]

        # Format results
        merged = []
        for id, score_data in sorted_items:
            if isinstance(score_data, dict):
                merged.append(
                    SearchResult(
                        id=id,
                        score=score_data.get("dense_score", 0)
                        + score_data.get("sparse_score", 0),
                        metadata=score_data.get("metadata", {}),
                        dense_score=score_data.get("dense_score", 0),
                        sparse_score=score_data.get("sparse_score", 0),
                    )
                )
            else:
                # Legacy format support
                merged.append(
                    SearchResult(id=id, score=score_data, metadata={})
                )

        logger.info(f"Merged into {len(merged)} final results")
        return merged

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

    def _enrich_with_product_data(self, search_results: List[SearchResult]) -> List[SearchResult]:
        """
        Enrich search results with database product information
        
        Args:
            search_results: List of SearchResult objects from vector search
            
        Returns:
            List of enriched SearchResult objects
        """
        # Extract URNs
        urns = [result.id for result in search_results]
        logger.info(f"🔍 Enriching {len(urns)} results, sample URNs: {urns[:3]}")
        
        # Batch fetch products by URN
        products = self.product_repository.get_products_by_urns(urns)
        logger.info(f"🔍 Found {len(products)} products in database")
        
        # Create URN to product mapping
        urn_to_product = {p.urn: p for p in products}
        
        # Enrich results
        enriched = []
        for result in search_results:
            product = urn_to_product.get(result.id)
            if product:
                # Extract media from raw_data if available
                media = []
                if product.raw_data:
                    media = self._extract_media_from_jsonld(product.raw_data)
                
                # Build enriched result
                result.product_name = product.name
                result.product_urn = product.urn
                result.product_brand = product.brand.name if product.brand else None
                result.product_category = product.category.name if product.category else None
                result.product_description = product.description
                result.product_url = product.url
                result.product_media = media
                
                # Add offer information
                if product.offers:
                    result.product_price = product.offers[0].price
                    result.product_offers = [
                        {
                            "price": offer.price,
                            "currency": offer.price_currency,
                            "availability": offer.availability,
                            "inventory_level": offer.inventory_level
                        }
                        for offer in product.offers
                    ]
                
                enriched.append(result)
            else:
                # Keep result even if product not found
                logger.warning(f"Product not found for URN: {result.id}")
                enriched.append(result)
        
        return enriched