from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.core.logging import get_logger
from app.db.repositories.vector_repository import VectorRepository
from app.db.repositories.product_repository import ProductRepository
import time

logger = get_logger(__name__)


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


class SearchService:
    """Handles hybrid search using Pinecone's Inference API"""

    def __init__(self, db_session):
        self.db_session = db_session
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

            # logger.debug(f"🔍 DEBUG: Dense results: {dense_results}")
            # logger.debug(f"🔍 DEBUG: Sparse results: {sparse_results}")

            dense_hits = self._hits(dense_results)
            sparse_hits = self._hits(sparse_results)
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
            logger.debug(
                f"🔍 DEBUG: Using SearchRecordsResponse format, raw hits: {len(raw)}"
            )
        elif isinstance(resp, dict):
            if "matches" in resp:
                raw = resp["matches"]
                logger.debug(f"🔍 DEBUG: Using 'matches' format, raw hits: {len(raw)}")
            elif "result" in resp and "hits" in resp["result"]:
                raw = resp["result"]["hits"]
                logger.debug(
                    f"🔍 DEBUG: Using 'result.hits' format, raw hits: {len(raw)}"
                )
            else:
                logger.error(
                    f"🔍 DEBUG: Unexpected response shape: {resp.keys() if isinstance(resp, dict) else 'Not a dict'}"
                )
                raise ValueError("Unexpected response shape")
        else:
            logger.error(f"🔍 DEBUG: Unexpected response type: {type(resp)}")
            raise ValueError("Unexpected response type")

        hits = []
        for h in raw:
            # Get metadata from either fields or metadata
            metadata = h.get("fields", {}) or h.get("metadata", {})

            hit_data = {
                "id": h.get("_id") or h.get("id"),
                "score": h.get("_score") or h.get("score"),
                "metadata": {
                    "price": metadata.get("price"),
                    "availability": metadata.get("availability"),
                    "brand": metadata.get("brand"),
                    "category": metadata.get("category"),
                },
            }
            hits.append(hit_data)

        logger.info(f"🔍 DEBUG: _hits output: {len(hits)} hits")
        logger.info(f"🔍 DEBUG: First hit: {hits[0] if hits else 'None'}")

        return hits

    def rrf_merge(self, dense_hits, sparse_hits, k=60, top_k=20):
        """
        Merge via RRF: score = Σ 1/(k + rank)
        """
        logger.debug(
            f"🔍 DEBUG: RRF merge input - dense_hits: {len(dense_hits)}, sparse_hits: {len(sparse_hits)}"
        )
        logger.debug(
            f"🔍 DEBUG: First dense hit: {dense_hits[0] if dense_hits else 'None'}"
        )
        logger.debug(
            f"🔍 DEBUG: First sparse hit: {sparse_hits[0] if sparse_hits else 'None'}"
        )

        fused = {}
        for rank, hit in enumerate(dense_hits, 1):
            fused.setdefault(hit["id"], {"metadata": hit["metadata"], "score": 0})
            fused[hit["id"]]["score"] += 1 / (k + rank)
        for rank, hit in enumerate(sparse_hits, 1):
            fused.setdefault(hit["id"], {"metadata": hit["metadata"], "score": 0})
            fused[hit["id"]]["score"] += 1 / (k + rank)

        # Convert to SearchResult objects
        search_results = []
        for hit_id, hit_data in sorted(
            fused.items(), key=lambda x: x[1]["score"], reverse=True
        )[:top_k]:
            search_results.append(
                SearchResult(
                    id=hit_id,
                    score=hit_data["score"],
                    metadata=hit_data["metadata"],
                    dense_score=None,  # RRF doesn't preserve individual scores
                    sparse_score=None,
                )
            )

        logger.info(f"🔍 DEBUG: RRF merge output - {len(search_results)} results")
        logger.info(
            f"🔍 DEBUG: First merged result: {search_results[0] if search_results else 'None'}"
        )

        return search_results

    def _enrich_with_product_data(
        self, search_results: List[SearchResult]
    ) -> List[SearchResult]:
        """Enrich search results with product information from database"""
        if not search_results:
            return search_results

        try:
            logger.info(f"🔍 DEBUG: Enriching {len(search_results)} results")

            # Extract product IDs - handle both SearchResult objects and dictionaries
            product_ids = []
            for result in search_results:
                if hasattr(result, "id"):
                    # SearchResult object
                    product_ids.append(result.id)
                else:
                    # Dictionary
                    product_ids.append(result.get("id"))

            logger.info(
                f"🔍 DEBUG: Extracted product IDs: {product_ids[:5]}..."
            )  # Show first 5

            products = self.product_repository.get_products_with_relations(product_ids)

            logger.info(f"🔍 DEBUG: Found {len(products)} products in database")

            # Check if offers are being loaded
            total_offers = 0
            for product in products:
                if hasattr(product, "offers") and product.offers:
                    total_offers += len(product.offers)
                    logger.info(
                        f"🔍 DEBUG: Product {product.id} has {len(product.offers)} offers"
                    )
                else:
                    logger.info(
                        f"🔍 DEBUG: Product {product.id} has no offers (offers attribute: {hasattr(product, 'offers')})"
                    )

            logger.info(f"🔍 DEBUG: Total offers found: {total_offers}")

            # Create mapping
            product_map = {}
            for product in products:
                # Extract media from product JSON-LD first, then fallback to product group
                media = self._extract_media_from_jsonld(product.raw_data)
                if not media and product.product_group:
                    media = self._extract_media_from_jsonld(
                        product.product_group.raw_data
                    )

                # Get brand name from the loaded brand relationship
                brand_name = product.brand.name if product.brand else None

                # Extract prices from offers
                prices = []
                logger.info(
                    f"🔍 DEBUG: Product {product.id} has {len(product.offers) if product.offers else 0} offers"
                )
                if product.offers:
                    # Use a set to track unique offers to avoid duplicates
                    seen_offers = set()
                    for offer in product.offers:
                        # Create a unique key for this offer
                        offer_key = (
                            offer.price,
                            offer.price_currency,
                            offer.availability,
                            offer.seller_id,
                        )
                        if offer_key not in seen_offers:
                            seen_offers.add(offer_key)
                            logger.info(
                                f"🔍 DEBUG: Offer: price={offer.price}, currency={offer.price_currency}, availability={offer.availability}"
                            )
                            offer_data = {
                                "price": offer.price,
                                "currency": offer.price_currency,
                                "availability": offer.availability,
                                "seller_id": str(offer.seller_id),
                            }

                            # Add optional offer fields
                            if offer.price_valid_until:
                                offer_data["price_valid_until"] = (
                                    offer.price_valid_until.isoformat()
                                )
                            if offer.inventory_level is not None:
                                offer_data["inventory_level"] = offer.inventory_level
                            if offer.shipping_speed_tier:
                                offer_data["shipping_speed_tier"] = (
                                    offer.shipping_speed_tier
                                )
                            if offer.est_delivery_min_days is not None:
                                offer_data["est_delivery_min_days"] = (
                                    offer.est_delivery_min_days
                                )
                            if offer.est_delivery_max_days is not None:
                                offer_data["est_delivery_max_days"] = (
                                    offer.est_delivery_max_days
                                )
                            if offer.warranty_months is not None:
                                offer_data["warranty_months"] = offer.warranty_months
                            if offer.return_window_days is not None:
                                offer_data["return_window_days"] = (
                                    offer.return_window_days
                                )
                            if offer.gift_wrap is not None:
                                offer_data["gift_wrap"] = offer.gift_wrap

                            prices.append(offer_data)
                        else:
                            logger.info(
                                f"🔍 DEBUG: Skipping duplicate offer: price={offer.price}, currency={offer.price_currency}, availability={offer.availability}"
                            )
                else:
                    logger.info(f"🔍 DEBUG: No offers found for product {product.id}")

                product_map[str(product.id)] = {
                    "name": product.name,
                    "urn": product.urn,  # Add the URN from the product
                    "brand": brand_name,
                    "category": product.category.name if product.category else None,
                    "prices": prices,
                    "description": product.description,
                    "url": product.raw_data.get("url") if product.raw_data else None,
                    "media": media,
                }

            logger.info(
                f"🔍 DEBUG: Product map keys: {list(product_map.keys())[:5]}..."
            )  # Show first 5

            # Enrich results
            for result in search_results:
                result_id = result.id if hasattr(result, "id") else result.get("id")
                logger.info(f"🔍 DEBUG: Processing result ID: {result_id}")
                if result_id in product_map:
                    data = product_map[result_id]
                    logger.info(
                        f"🔍 DEBUG: Found product data for {result_id}: {data['name']}"
                    )
                    logger.info(f"🔍 DEBUG: Offers data: {data.get('prices', [])}")
                    if hasattr(result, "product_name"):
                        # SearchResult object
                        result.product_name = data["name"]
                        result.product_urn = data["urn"]
                        result.product_brand = data["brand"]
                        result.product_category = data["category"]
                        result.product_price = (
                            data["prices"][0]["price"] if data["prices"] else None
                        )
                        result.product_offers = data["prices"]  # Add all offers
                        result.product_description = data["description"]
                        result.product_url = data["url"]
                        result.product_media = data["media"]
                        logger.info(
                            f"🔍 DEBUG: Set product_offers to: {result.product_offers}"
                        )
                    else:
                        # Dictionary
                        result["product_name"] = data["name"]
                        result["product_urn"] = data["urn"]
                        result["product_brand"] = data["brand"]
                        result["product_category"] = data["category"]
                        result["product_price"] = (
                            data["prices"][0]["price"] if data["prices"] else None
                        )
                        result["product_offers"] = data["prices"]  # Add all offers
                        result["product_description"] = data["description"]
                        result["product_url"] = data["url"]
                        result["product_media"] = data["media"]
                        logger.info(
                            f"🔍 DEBUG: Set product_offers to: {result.get('product_offers')}"
                        )
                else:
                    logger.info(f"🔍 DEBUG: No product data found for {result_id}")

                # Also extract fields from Pinecone metadata as fallback if database enrichment failed
                if hasattr(result, "metadata") and result.metadata:
                    metadata = result.metadata
                    if hasattr(result, "product_brand") and not result.product_brand:
                        result.product_brand = metadata.get("brand")
                    if (
                        hasattr(result, "product_category")
                        and not result.product_category
                    ):
                        result.product_category = metadata.get("category")
                    if hasattr(result, "product_price") and not result.product_price:
                        result.product_price = metadata.get("price")
                elif isinstance(result, dict) and result.get("metadata"):
                    metadata = result["metadata"]
                    if not result.get("product_brand"):
                        result["product_brand"] = metadata.get("brand")
                    if not result.get("product_category"):
                        result["product_category"] = metadata.get("category")
                    if not result.get("product_price"):
                        result["product_price"] = metadata.get("price")

            return search_results

        except Exception as e:
            logger.error(f"Error enriching product data: {str(e)}")
            return search_results

    def _extract_media_from_jsonld(
        self, jsonld: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract media information from JSON-LD data"""
        try:
            if not jsonld:
                return []

            # Check for @cmp:media in the main JSON-LD
            if "@cmp:media" in jsonld:
                media = jsonld["@cmp:media"]
                if isinstance(media, list):
                    return media
                elif isinstance(media, dict):
                    return [media]

            # Check for @cmp:media in offers
            offers = jsonld.get("offers", {})
            if isinstance(offers, dict) and "@cmp:media" in offers:
                media = offers["@cmp:media"]
                if isinstance(media, list):
                    return media
                elif isinstance(media, dict):
                    return [media]

            # Check for @cmp:media in nested structures
            for key, value in jsonld.items():
                if isinstance(value, dict) and "@cmp:media" in value:
                    media = value["@cmp:media"]
                    if isinstance(media, list):
                        return media
                    elif isinstance(media, dict):
                        return [media]

            return []

        except Exception as e:
            logger.error(f"Error extracting media from JSON-LD: {str(e)}")
            return []
