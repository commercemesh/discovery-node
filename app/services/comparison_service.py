"""Product comparison service"""
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from app.core.logging import get_logger
from app.services.cache_service import get_cache_service
from app.utils.request_id import generate_request_id

logger = get_logger(__name__)


class ComparisonService:
    """Service for comparing products from cached results"""
    
    def __init__(self):
        self.cache_service = get_cache_service()
    
    def compare_products(
        self,
        request_id: str,
        indices: List[int],
        comparison_aspects: Optional[List[str]] = None,
        format_type: str = "table"
    ) -> Dict[str, Any]:
        """
        Compare products from cached results.
        
        Args:
            request_id: Cache request ID
            indices: Product indices to compare (0-based)
            comparison_aspects: Specific aspects to compare
            format_type: Output format (table, narrative, pros_cons)
            
        Returns:
            Comparison results with new request ID
            
        Raises:
            ValueError: If indices are invalid or cache not found
        """
        # Retrieve cached data
        cached_data = self._get_cached_data(request_id)
        if not cached_data:
            raise ValueError(f"No cached results found for request ID: {request_id}")
        
        # Get items from cache
        items = cached_data.get("itemListElement", [])
        if not items:
            raise ValueError("No products found in cached results")
        
        # Validate indices
        self._validate_indices(indices, len(items))
        
        # Extract products at specified indices
        selected_products = []
        for idx in indices:
            list_item = items[idx]
            item = list_item.get("item", {})
            if item:
                selected_products.append(item)
        
        if not selected_products:
            raise ValueError("No valid products found at specified indices")
        
        # Auto-detect comparison aspects if not provided
        if not comparison_aspects:
            comparison_aspects = self._detect_comparison_aspects(selected_products)
        
        # Generate comparison matrix
        comparison_matrix = self._generate_comparison_matrix(
            selected_products,
            comparison_aspects
        )
        
        # Generate narrative summary
        narrative = self._generate_narrative(
            selected_products,
            comparison_matrix,
            comparison_aspects
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            selected_products,
            comparison_matrix,
            indices
        )
        
        # Create response
        new_request_id = generate_request_id()
        response = {
            "@context": {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            },
            "@type": "ComparisonResult",
            "cmp:requestId": new_request_id,
            "cmp:originalRequestId": request_id,
            "cmp:comparedIndices": indices,
            "cmp:comparisonAspects": comparison_aspects,
            "products": selected_products,
            "comparisonMatrix": comparison_matrix,
            "narrative": narrative,
            "recommendations": recommendations,
            "datePublished": datetime.utcnow().isoformat() + "Z"
        }
        
        # Cache the comparison result
        cache_key = f"compare:{new_request_id}"
        self.cache_service.cache_response(cache_key, response)
        
        logger.info(
            f"Compared {len(indices)} products from request {request_id}, "
            f"new request ID: {new_request_id}"
        )
        
        return response
    
    def _get_cached_data(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached data with different prefixes"""
        for prefix in ["search", "product", "mcp-search", "filter", "mcp-filter"]:
            cache_key = f"{prefix}:{request_id}"
            cached_data = self.cache_service.get_cached_response(cache_key)
            if cached_data:
                logger.info(f"Found cached data with key: {cache_key}")
                return cached_data
        return None
    
    def _validate_indices(self, indices: List[int], total_items: int):
        """Validate that indices are within bounds"""
        if not indices:
            raise ValueError("No indices provided")
        
        if len(indices) < 2:
            raise ValueError("At least 2 products required for comparison")
        
        if len(indices) > 5:
            raise ValueError(f"Maximum 5 products can be compared. Received {len(indices)} indices.")
        
        out_of_bounds = [idx for idx in indices if idx < 0 or idx >= total_items]
        if out_of_bounds:
            raise ValueError(
                f"Indices {out_of_bounds} are out of range. "
                f"Available products: 0-{total_items - 1}"
            )
    
    def _detect_comparison_aspects(self, products: List[Dict[str, Any]]) -> List[str]:
        """Auto-detect comparison aspects from products"""
        aspects = []
        
        # Always include price if available
        if any(self._get_product_price(p) is not None for p in products):
            aspects.append("price")
        
        # Check for brands
        brands = [self._get_product_brand(p) for p in products]
        if len(set(b for b in brands if b)) > 1:
            aspects.append("brand")
        
        # Check for categories
        categories = [p.get("category") for p in products]
        if any(categories):
            aspects.append("category")
        
        # Check for features
        if any(p.get("additionalProperty") for p in products):
            aspects.append("features")
        
        # Check for availability
        if any(self._get_product_availability(p) for p in products):
            aspects.append("availability")
        
        # Default aspects if none detected
        if not aspects:
            aspects = ["name", "description"]
        
        return aspects
    
    def _generate_comparison_matrix(
        self,
        products: List[Dict[str, Any]],
        aspects: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Generate comparison matrix for products"""
        matrix = {}
        
        for aspect in aspects:
            matrix[aspect] = {}
            
            if aspect == "price":
                prices = {}
                for i, product in enumerate(products):
                    name = self._get_product_name(product, i)
                    price = self._get_product_price(product)
                    prices[name] = price if price is not None else "N/A"
                
                # Find winner (lowest price)
                valid_prices = [(k, v) for k, v in prices.items() if v != "N/A"]
                if valid_prices:
                    winner = min(valid_prices, key=lambda x: x[1])[0]
                    prices["winner"] = winner
                
                matrix[aspect] = prices
            
            elif aspect == "brand":
                brands = {}
                for i, product in enumerate(products):
                    name = self._get_product_name(product, i)
                    brand = self._get_product_brand(product)
                    brands[name] = brand or "Unknown"
                
                matrix[aspect] = brands
            
            elif aspect == "features":
                features = {}
                for i, product in enumerate(products):
                    name = self._get_product_name(product, i)
                    product_features = self._extract_features(product)
                    features[name] = product_features
                
                # Add summary
                max_features = max(len(f) for f in features.values()) if features else 0
                product_with_most = [k for k, v in features.items() if len(v) == max_features]
                if product_with_most:
                    features["summary"] = f"{product_with_most[0]} has the most features ({max_features})"
                
                matrix[aspect] = features
            
            elif aspect == "availability":
                availability = {}
                for i, product in enumerate(products):
                    name = self._get_product_name(product, i)
                    avail = self._get_product_availability(product)
                    availability[name] = avail or "Unknown"
                
                matrix[aspect] = availability
            
            elif aspect == "category":
                categories = {}
                for i, product in enumerate(products):
                    name = self._get_product_name(product, i)
                    category = product.get("category", "Unknown")
                    categories[name] = category
                
                matrix[aspect] = categories
        
        return matrix
    
    def _generate_narrative(
        self,
        products: List[Dict[str, Any]],
        matrix: Dict[str, Dict[str, Any]],
        aspects: List[str]
    ) -> str:
        """Generate natural language comparison summary"""
        narrative_parts = []
        
        # Introduction
        product_names = [self._get_product_name(p, i) for i, p in enumerate(products)]
        narrative_parts.append(f"Comparing {len(products)} products: {', '.join(product_names)}.")
        
        # Price comparison
        if "price" in matrix:
            prices = matrix["price"]
            winner = prices.get("winner")
            if winner:
                price_summary = []
                for name, price in prices.items():
                    if name != "winner" and price != "N/A":
                        price_summary.append(f"{name} at ${price}")
                
                if price_summary:
                    narrative_parts.append(
                        f"In terms of pricing, {winner} offers the best value. "
                        f"Price comparison: {', '.join(price_summary)}."
                    )
        
        # Feature comparison
        if "features" in matrix:
            features = matrix["features"]
            summary = features.get("summary")
            if summary:
                narrative_parts.append(f"For features, {summary}.")
        
        # Brand comparison
        if "brand" in matrix:
            brands = matrix["brand"]
            unique_brands = set(v for k, v in brands.items() if k != "winner")
            if len(unique_brands) > 1:
                narrative_parts.append(
                    f"The products come from different brands: {', '.join(unique_brands)}."
                )
        
        # Availability
        if "availability" in matrix:
            availability = matrix["availability"]
            in_stock = [k for k, v in availability.items() if v == "InStock"]
            if in_stock:
                narrative_parts.append(
                    f"Currently in stock: {', '.join(in_stock)}."
                )
        
        return " ".join(narrative_parts)
    
    def _generate_recommendations(
        self,
        products: List[Dict[str, Any]],
        matrix: Dict[str, Dict[str, Any]],
        indices: List[int]
    ) -> Dict[str, int]:
        """Generate product recommendations based on comparison"""
        recommendations = {}
        
        # Find best value (good features at reasonable price)
        value_scores = []
        for i, (product, idx) in enumerate(zip(products, indices)):
            price = self._get_product_price(product)
            features = len(self._extract_features(product))
            
            # Calculate value score (features per dollar)
            if price and price > 0:
                score = features / price
            else:
                score = features  # If no price, use feature count
            
            value_scores.append((idx, score))
        
        # Sort by value score
        value_scores.sort(key=lambda x: x[1], reverse=True)
        recommendations["best_value"] = value_scores[0][0]
        
        # Find premium choice (most features/highest price)
        feature_counts = [(idx, len(self._extract_features(p))) 
                         for p, idx in zip(products, indices)]
        feature_counts.sort(key=lambda x: x[1], reverse=True)
        recommendations["premium_choice"] = feature_counts[0][0]
        
        # Find budget option (lowest price)
        prices = []
        for product, idx in zip(products, indices):
            price = self._get_product_price(product)
            if price is not None:
                prices.append((idx, price))
        
        if prices:
            prices.sort(key=lambda x: x[1])
            recommendations["budget_option"] = prices[0][0]
        else:
            # If no prices, use first product as budget option
            recommendations["budget_option"] = indices[0]
        
        return recommendations
    
    def _get_product_name(self, product: Dict[str, Any], index: int) -> str:
        """Get product name or generate one"""
        name = product.get("name", "")
        if name:
            # Truncate long names
            return name[:50] + "..." if len(name) > 50 else name
        return f"Product {index + 1}"
    
    def _get_product_price(self, product: Dict[str, Any]) -> Optional[float]:
        """Extract price from product offers"""
        offers = product.get("offers", [])
        if not isinstance(offers, list):
            offers = [offers]
        
        for offer in offers:
            if isinstance(offer, dict):
                price = offer.get("price")
                if price is not None:
                    try:
                        return float(price)
                    except (ValueError, TypeError):
                        pass
        
        return None
    
    def _get_product_brand(self, product: Dict[str, Any]) -> Optional[str]:
        """Extract brand name from product"""
        brand = product.get("brand")
        if isinstance(brand, dict):
            return brand.get("name")
        elif isinstance(brand, str):
            return brand
        return None
    
    def _get_product_availability(self, product: Dict[str, Any]) -> Optional[str]:
        """Extract availability from product offers"""
        offers = product.get("offers", [])
        if not isinstance(offers, list):
            offers = [offers]
        
        for offer in offers:
            if isinstance(offer, dict):
                availability = offer.get("availability")
                if availability:
                    # Extract last part of schema.org URL if present
                    if "/" in str(availability):
                        return str(availability).split("/")[-1]
                    return str(availability)
        
        return None
    
    def _extract_features(self, product: Dict[str, Any]) -> List[str]:
        """Extract features from product"""
        features = []
        
        # Extract from additionalProperty
        additional_props = product.get("additionalProperty", [])
        for prop in additional_props:
            if isinstance(prop, dict):
                name = prop.get("name", "")
                value = prop.get("value", "")
                if name and value:
                    features.append(f"{name}: {value}")
        
        # Extract from variant_attributes
        variant_attrs = product.get("variant_attributes", {})
        if isinstance(variant_attrs, dict):
            for key, value in variant_attrs.items():
                if key and value:
                    features.append(f"{key}: {value}")
        
        # Extract from variesBy (for ProductGroup)
        varies_by = product.get("variesBy", [])
        if varies_by:
            features.append(f"Varies by: {', '.join(varies_by)}")
        
        return features