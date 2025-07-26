"""Product filtering service with regex and price filtering"""
import re
from typing import List, Dict, Any, Optional, Tuple
from app.core.logging import get_logger
from app.services.cache_service import get_cache_service

logger = get_logger(__name__)


class FilterService:
    """Service for filtering cached product results"""
    
    # Common filter patterns
    FILTER_PATTERNS = {
        "waterproof": r"water[-\s]?(proof|resistant|repellent)",
        "water resistant": r"water[-\s]?(proof|resistant|repellent)",
        "weatherproof": r"weather[-\s]?(proof|resistant)",
        "dustproof": r"dust[-\s]?(proof|resistant)",
        "shockproof": r"shock[-\s]?(proof|resistant)",
        "lightweight": r"(light[-\s]?weight|ultra[-\s]?light)",
        "heavy duty": r"heavy[-\s]?duty",
        "portable": r"portable",
        "wireless": r"wireless|wi[-\s]?fi|bluetooth",
        "rechargeable": r"rechargeable|battery",
        "eco friendly": r"eco[-\s]?friendly|sustainable|green|environmentally",
        "organic": r"organic|natural",
        "vegan": r"vegan|plant[-\s]?based",
        "gluten free": r"gluten[-\s]?free",
        "biodegradable": r"bio[-\s]?degradable",
        "recyclable": r"recyclable|recycled",
        "premium": r"premium|luxury|high[-\s]?end",
        "budget": r"budget|affordable|cheap|economy",
        "bestseller": r"best[-\s]?seller|popular|top[-\s]?rated",
        "new": r"new|latest|recent",
        "vintage": r"vintage|retro|classic",
        "limited edition": r"limited[-\s]?edition|exclusive",
        "handmade": r"hand[-\s]?made|artisan|craft",
        "professional": r"professional|pro[-\s]?grade",
        "beginner": r"beginner|entry[-\s]?level|starter",
        "compact": r"compact|small|mini",
        "large": r"large|big|jumbo|xl",
        "durable": r"durable|long[-\s]?lasting|robust",
        "fast": r"fast|quick|rapid|speedy",
        "quiet": r"quiet|silent|noise[-\s]?less",
        "smart": r"smart|intelligent|ai[-\s]?powered",
    }
    
    def __init__(self):
        self.cache_service = get_cache_service()
    
    def keyword_match(self, text: str, criteria: str) -> bool:
        """
        Check if text matches the filter criteria using regex.
        
        Args:
            text: Text to search in
            criteria: Filter criteria
            
        Returns:
            True if match found, False otherwise
        """
        if not text or not criteria:
            return False
        
        # Convert to lowercase for case-insensitive matching
        text_lower = text.lower()
        criteria_lower = criteria.lower()
        
        # Check if we have a predefined pattern
        if criteria_lower in self.FILTER_PATTERNS:
            pattern = self.FILTER_PATTERNS[criteria_lower]
        else:
            # Create a basic pattern for the criteria
            # Escape special regex characters and allow word boundaries
            escaped = re.escape(criteria_lower)
            # Allow hyphens and spaces between words
            pattern = escaped.replace(r'\ ', r'[-\s]?')
        
        try:
            return bool(re.search(pattern, text_lower))
        except re.error as e:
            logger.error(f"Regex error for pattern '{pattern}': {e}")
            # Fallback to simple substring search
            return criteria_lower in text_lower
    
    def filter_products(
        self,
        request_id: str,
        filter_criteria: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        limit: Optional[int] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filter products from cached results.
        
        Args:
            request_id: Cache request ID
            filter_criteria: Natural language filter criteria
            max_price: Maximum price filter
            min_price: Minimum price filter
            limit: Maximum results to return
            
        Returns:
            Tuple of (filtered items, total filtered count)
        """
        # Try to retrieve cached data with different prefixes
        cached_data = None
        for prefix in ["search", "product", "mcp-search"]:
            cache_key = f"{prefix}:{request_id}"
            cached_data = self.cache_service.get_cached_response(cache_key)
            if cached_data:
                logger.info(f"Found cached data with key: {cache_key}")
                break
        
        if not cached_data:
            logger.warning(f"No cached data found for request ID: {request_id}")
            return [], 0
        
        # Extract items from the cached response
        items = cached_data.get("itemListElement", [])
        if not items:
            logger.info("No items found in cached data")
            return [], 0
        
        # Filter the items
        filtered_items = []
        
        for list_item in items:
            item = list_item.get("item", {})
            if not item:
                continue
            
            # Check if item matches filter criteria
            matches_criteria = False
            
            # Search in various fields
            searchable_text = " ".join([
                str(item.get("name", "")),
                str(item.get("description", "")),
                str(item.get("category", "")),
                str(item.get("brand", {}).get("name", "") if isinstance(item.get("brand"), dict) else ""),
                # Include additional properties
                " ".join([
                    f"{prop.get('name', '')} {prop.get('value', '')}"
                    for prop in item.get("additionalProperty", [])
                ])
            ])
            
            if self.keyword_match(searchable_text, filter_criteria):
                matches_criteria = True
            
            # Check variant attributes for Product type
            if item.get("@type") == "Product" and not matches_criteria:
                variant_attrs = item.get("variant_attributes", {})
                if variant_attrs:
                    variant_text = " ".join([f"{k} {v}" for k, v in variant_attrs.items()])
                    if self.keyword_match(variant_text, filter_criteria):
                        matches_criteria = True
            
            # Check product group variesBy for ProductGroup type
            if item.get("@type") == "ProductGroup" and not matches_criteria:
                varies_by = item.get("variesBy", [])
                if varies_by:
                    varies_text = " ".join(varies_by)
                    if self.keyword_match(varies_text, filter_criteria):
                        matches_criteria = True
            
            if not matches_criteria:
                continue
            
            # Apply price filters
            if max_price is not None or min_price is not None:
                # Check offers for price
                offers = item.get("offers", [])
                if not isinstance(offers, list):
                    offers = [offers]
                
                # Filter by price
                price_match = False
                for offer in offers:
                    if isinstance(offer, dict):
                        price = offer.get("price")
                        if price is not None:
                            if min_price is not None and price < min_price:
                                continue
                            if max_price is not None and price > max_price:
                                continue
                            price_match = True
                            break
                
                if not price_match and offers:
                    continue
            
            # Add to filtered results
            filtered_items.append(list_item)
        
        # Apply limit if specified
        total_filtered = len(filtered_items)
        if limit and limit > 0:
            filtered_items = filtered_items[:limit]
        
        logger.info(f"Filtered {total_filtered} items from {len(items)} total items")
        
        return filtered_items, total_filtered
    
    def create_filtered_response(
        self,
        cached_data: Dict[str, Any],
        filtered_items: List[Dict[str, Any]],
        total_filtered: int,
        filter_criteria: str,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a filtered response maintaining the original structure.
        
        Args:
            cached_data: Original cached response
            filtered_items: Filtered items
            total_filtered: Total count before limit
            filter_criteria: Applied filter criteria
            max_price: Applied max price filter
            min_price: Applied min price filter
            
        Returns:
            Filtered response in the same format as original
        """
        # Copy the original structure
        filtered_response = {
            "@context": cached_data.get("@context", "https://schema.org"),
            "@type": cached_data.get("@type", "ItemList"),
            "itemListElement": filtered_items,
            "cmp:totalResults": total_filtered,
            "cmp:nodeVersion": cached_data.get("cmp:nodeVersion", "v1.0.0"),
            "datePublished": cached_data.get("datePublished"),
            # Add filter metadata
            "cmp:filterApplied": {
                "criteria": filter_criteria,
                "maxPrice": max_price,
                "minPrice": min_price,
                "originalTotal": cached_data.get("cmp:totalResults", len(cached_data.get("itemListElement", [])))
            }
        }
        
        # Ensure we have the cmp namespace in context if using cmp: properties
        if isinstance(filtered_response.get("@context"), str):
            filtered_response["@context"] = {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            }
        
        return filtered_response