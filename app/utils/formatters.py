from typing import List, Dict, Any, Optional
from app.services.search_service import SearchResult
from datetime import datetime, timezone

import logging

logger = logging.getLogger(__name__)


def _extract_media_from_raw_data(raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract media information from raw JSON-LD data."""
    if not raw_data:
        return []
    
    media_items = []
    
    # Check for @cmp:media
    if "@cmp:media" in raw_data:
        media = raw_data["@cmp:media"]
        if isinstance(media, list):
            media_items.extend(media)
        elif isinstance(media, dict):
            media_items.append(media)
    
    # Check for image field
    if "image" in raw_data:
        images = raw_data["image"]
        if isinstance(images, list):
            for img in images:
                if isinstance(img, dict):
                    media_items.append(img)
                elif isinstance(img, str):
                    media_items.append({"@type": "ImageObject", "url": img})
        elif isinstance(images, dict):
            media_items.append(images)
        elif isinstance(images, str):
            media_items.append({"@type": "ImageObject", "url": images})
    
    return media_items


def format_product_group_item(
    product_group: Any,
    brand: Optional[Any] = None,
    category: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Format a product group into schema.org ProductGroup format.
    
    Args:
        product_group: ProductGroup object with attributes like urn, name, etc.
        brand: Brand object (optional)
        category: Category object (optional)
    
    Returns:
        Dict representing a schema.org ProductGroup
    """
    item = {
        "@context": "https://schema.org",
        "@type": "ProductGroup",
        "@id": product_group.urn,
        "name": product_group.name,
        "description": product_group.description or "",
        "url": product_group.url or "",
        "productGroupID": product_group.product_group_id or "",
        "variesBy": product_group.varies_by or []
    }
    
    # Add category
    if category:
        item["category"] = category.name
    elif hasattr(product_group, 'category') and product_group.category:
        item["category"] = product_group.category
    
    # Add brand
    if brand:
        item["brand"] = {
            "@type": "Brand",
            "name": brand.name
        }
    
    # Add media/images if available in raw_data
    if hasattr(product_group, 'raw_data') and product_group.raw_data:
        media = _extract_media_from_raw_data(product_group.raw_data)
        if media:
            # Separate images from other media
            images = []
            other_media = []
            for m in media:
                if isinstance(m, dict):
                    media_type = m.get("@type", "").lower()
                    encoding = m.get("encodingFormat", "").lower()
                    if media_type == "imageobject" or encoding.startswith("image/"):
                        images.append(m)
                    else:
                        other_media.append(m)
            
            if images:
                item["image"] = images
            if other_media:
                item["@cmp:media"] = other_media
    
    return item


def format_product_item(
    product: Any,
    product_urn: Optional[str] = None,
    product_name: Optional[str] = None,
    product_brand: Optional[str] = None,
    product_category: Optional[str] = None,
    product_offers: Optional[List[Dict[str, Any]]] = None,
    product_description: Optional[str] = None,
    product_url: Optional[str] = None,
    product_media: Optional[List[Dict[str, Any]]] = None,
    product_group: Optional[Any] = None,
    score: Optional[float] = None
) -> Dict[str, Any]:
    """
    Format a product into schema.org Product format.
    
    This function can handle both:
    1. Full product objects (from products API)
    2. Search result data (from search API)
    
    Args:
        product: Product object or None (for search results)
        product_urn: URN override (for search results)
        product_name: Name override (for search results)
        ... other overrides for search results
        product_group: ProductGroup object if available
        score: Search score if from search results
    
    Returns:
        Dict representing a schema.org Product
    """
    # Use provided values or extract from product object
    if product:
        urn = product.urn
        name = product.name
        description = product.description
        url = product.url or ""
        sku = product.sku or ""
        variant_attrs = product.variant_attributes if hasattr(product, 'variant_attributes') else {}
        raw_data = product.raw_data if hasattr(product, 'raw_data') else {}
    else:
        # Use provided values (from search results)
        urn = product_urn
        name = product_name
        description = product_description
        url = product_url or ""
        sku = ""
        variant_attrs = {}
        raw_data = {}
    
    item = {
        "@type": "Product",
        "@id": urn,
        "name": name,
        "url": url,
    }
    
    # Add SKU
    if sku:
        item["sku"] = sku
    elif url and "variant=" in url:
        # Extract SKU from URL if available
        item["sku"] = url.split("variant=")[1].split("&")[0]
    
    # Add description
    if description:
        item["description"] = description
    
    # Add category
    if product_category:
        item["category"] = product_category
    elif product and hasattr(product, 'category') and product.category:
        item["category"] = product.category.name
    
    # Add brand
    if product_brand:
        item["brand"] = {"@type": "Brand", "name": product_brand}
    elif product and hasattr(product, 'brand') and product.brand:
        item["brand"] = {"@type": "Brand", "name": product.brand.name}
    
    # Add isVariantOf reference
    if product_group:
        item["isVariantOf"] = {
            "@type": "ProductGroup",
            "@id": product_group.urn
        }
    
    # Add offers
    if product_offers and len(product_offers) > 0:
        formatted_offers = []
        for offer in product_offers:
            if isinstance(offer, dict):
                # From search results
                offer_obj = {
                    "@type": "Offer",
                    "price": offer["price"],
                    "priceCurrency": offer["currency"],
                    "availability": f"https://schema.org/{offer['availability']}",
                }
                
                # Add seller if available
                if offer.get('seller_id'):
                    offer_obj["seller"] = {
                        "@type": "Organization",
                        "@id": f"urn:cmp:brand:{offer['seller_id']}",
                    }
                # Add optional fields
                for key in ["inventory_level", "price_valid_until", "shipping_speed_tier"]:
                    if key in offer:
                        if key == "inventory_level":
                            offer_obj["inventoryLevel"] = {
                                "@type": "QuantitativeValue",
                                "value": offer[key]
                            }
                        else:
                            offer_obj[key] = offer[key]
            else:
                # From product object
                offer_obj = {
                    "@type": "Offer",
                    "price": float(offer.price) if offer.price else 0.0,
                    "priceCurrency": offer.price_currency or "USD",
                    "availability": f"https://schema.org/{offer.availability}" if offer.availability else "https://schema.org/OutOfStock"
                }
                if hasattr(offer, 'inventory_level') and offer.inventory_level is not None:
                    offer_obj["inventoryLevel"] = {
                        "@type": "QuantitativeValue",
                        "value": offer.inventory_level
                    }
                if hasattr(offer, 'price_valid_until') and offer.price_valid_until:
                    offer_obj["priceValidUntil"] = offer.price_valid_until.isoformat()
            
            formatted_offers.append(offer_obj)
        
        item["offers"] = formatted_offers[0] if len(formatted_offers) == 1 else formatted_offers
    
    # Add media/images
    media_to_process = product_media or []
    if not media_to_process and product and hasattr(product, 'raw_data') and product.raw_data:
        media_to_process = _extract_media_from_raw_data(product.raw_data)
    
    if media_to_process:
        images = []
        cmp_media = []
        
        for media in media_to_process:
            if isinstance(media, dict) and media.get("url"):
                # Determine if it's an image or other media
                encoding_format = media.get("encodingFormat", "").lower()
                media_type = media.get("@type", media.get("type", "ImageObject"))
                
                if encoding_format.startswith("image/") or media_type == "ImageObject":
                    image_obj = {"@type": "ImageObject", "url": media["url"]}
                    if "width" in media:
                        image_obj["width"] = media["width"]
                    if "height" in media:
                        image_obj["height"] = media["height"]
                    if "encodingFormat" in media:
                        image_obj["encodingFormat"] = media["encodingFormat"]
                    images.append(image_obj)
                else:
                    # Non-image media
                    media_obj = {"@type": media_type, "url": media["url"]}
                    if "encodingFormat" in media:
                        media_obj["encodingFormat"] = media["encodingFormat"]
                    cmp_media.append(media_obj)
        
        if images:
            item["image"] = images
        if cmp_media:
            item["@cmp:media"] = cmp_media
    
    # Add additional properties from variant attributes
    if variant_attrs:
        additional_properties = []
        for key, value in variant_attrs.items():
            additional_properties.append({
                "@type": "PropertyValue",
                "name": key,
                "value": value
            })
        if additional_properties:
            item["additionalProperty"] = additional_properties
    
    # Add search score if available
    if score is not None:
        item["cmp:searchScore"] = score
    
    return item


def format_product_search_response(products: List[SearchResult]) -> Dict[str, Any]:
    """
    Format product search results into standardized JSON response.
    Uses the modular format_product_item function.
    """
    item_list_elements = []
    
    for i, result in enumerate(products):
        logger.info(f"🔍 DEBUG: Processing result {i}: type={type(result)}")
        
        # Extract product data
        if hasattr(result, "id"):
            # SearchResult object
            product_item = format_product_item(
                product=None,  # Search results don't have full product objects
                product_urn=result.product_urn,
                product_name=result.product_name,
                product_brand=result.product_brand,
                product_category=result.product_category,
                product_offers=result.product_offers,
                product_description=result.product_description,
                product_url=result.product_url,
                product_media=result.product_media,
                score=result.score
            )
        else:
            # Dictionary
            product_item = format_product_item(
                product=None,
                product_urn=result.get("product_urn"),
                product_name=result.get("product_name"),
                product_brand=result.get("product_brand"),
                product_category=result.get("product_category"),
                product_offers=result.get("product_offers"),
                product_description=result.get("product_description"),
                product_url=result.get("product_url"),
                product_media=result.get("product_media"),
                score=result.get("score")
            )
        
        # Create list item
        list_item = {"@type": "ListItem", "position": i + 1, "item": product_item}
        item_list_elements.append(list_item)
    
    # Create the final response
    response_data = {
        "itemListElement": item_list_elements,
        "cmp_totalResults": len(products),
        "cmp_nodeVersion": "v1.0.0",
        "datePublished": datetime.now(timezone.utc).isoformat(),
    }
    
    return response_data


def format_product_by_urn_response(product_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format product details by URN into schema.org ItemList response.
    Uses the modular format_product_item and format_product_group_item functions.
    
    Handles both product and product group searches:
    - Product with ProductGroup: Returns ProductGroup + Product as ListItems
    - Product without ProductGroup: Returns only Product as ListItem
    - ProductGroup: Returns ProductGroup + all linked Products as ListItems
    """
    result_type = product_details.get("type", "product")
    brand = product_details["brand"]
    category = product_details["category"]
    offers = product_details.get("offers", [])
    
    item_list_elements = []
    
    if result_type == "product":
        # Found as product - return ONLY the product (no product group)
        product = product_details["product"]
        
        # Format product with all details (no product group reference)
        product_item = format_product_item(
            product=product,
            product_offers=offers,
            product_group=None  # Don't include product group for direct product matches
        )
        
        # Add context since this is a top-level item
        product_item["@context"] = "https://schema.org"
        
        # Add Product as the only ListItem
        product_list_item = {
            "@type": "ListItem",
            "position": 1,
            "item": product_item
        }
        item_list_elements.append(product_list_item)
    
    elif result_type == "product_group":
        # Found as product group
        product_group = product_details["product_group"]
        linked_products = product_details.get("linked_products", [])
        
        # 1. ProductGroup as first ListItem (position 1)
        product_group_item = format_product_group_item(
            product_group=product_group,
            brand=brand,
            category=category
        )
        
        # Add ProductGroup as first ListItem
        product_group_list_item = {
            "@type": "ListItem",
            "position": 1,
            "item": product_group_item
        }
        item_list_elements.append(product_group_list_item)
        
        # 2. Add all linked products as subsequent ListItems
        for idx, product in enumerate(linked_products):
            # Format each linked product
            product_item = format_product_item(
                product=product,
                product_offers=None,  # Individual offers would need to be fetched per product
                product_group=product_group
            )
            
            # Add context since this is a top-level item
            product_item["@context"] = "https://schema.org"
            
            # Add Product as ListItem
            product_list_item = {
                "@type": "ListItem",
                "position": idx + 2,  # Start from position 2 since ProductGroup is at position 1
                "item": product_item
            }
            item_list_elements.append(product_list_item)
    
    # Create the final response
    response_data = {
        "itemListElement": item_list_elements
    }
    
    return response_data


