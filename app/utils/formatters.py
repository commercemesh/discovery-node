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
    # Start with basic context
    context = "https://schema.org"
    
    item = {
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
                # Update context to include cmp namespace
                context = {
                    "schema": "https://schema.org",
                    "cmp": "https://schema.commercemesh.ai/ns#"
                }
    
    # Set the context
    item["@context"] = context
    
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
    
    # Start with basic context
    context = "https://schema.org"
    
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
                
                # Add organization if available
                if offer.get('organization_id'):
                    offer_obj["seller"] = {
                        "@type": "Organization",
                        "@id": f"urn:cmp:brand:{offer['organization_id']}",
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
            # Update context to include cmp namespace
            context = {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            }
    
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
        # Update context to include cmp namespace if not already
        if isinstance(context, str):
            context = {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            }
    
    # Set the context
    item["@context"] = context
    
    return item


def format_product_search_response(products: List[SearchResult]) -> Dict[str, Any]:
    """
    Format product search results into standardized JSON response.
    Uses the modular format_product_item function.
    """
    item_list_elements = []
    has_cmp_namespace = False
    
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
        
        # Check if we need the cmp namespace
        if "@cmp:media" in product_item or "cmp:searchScore" in product_item:
            has_cmp_namespace = True
        
        # Create list item
        list_item = {"@type": "ListItem", "position": i + 1, "item": product_item}
        item_list_elements.append(list_item)
    
    # Set appropriate context
    if has_cmp_namespace:
        context = {
            "@context": {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            }
        }
    else:
        context = {"@context": "https://schema.org"}
    
    # Create the final response
    response_data = {
        **context,
        "@type": "ItemList",
        "itemListElement": item_list_elements,
        "cmp:totalResults": len(products),
        "cmp:nodeVersion": "v1.0.0",
        "datePublished": datetime.now(timezone.utc).isoformat(),
    }
    
    return response_data


def parse_jsonld_to_product_create(jsonld_data: Dict[str, Any], organization_id: Any, brand_id: Any, category_id: Any, product_group_id: Optional[Any] = None) -> "ProductCreate":
    """
    Parse JSON-LD product data into ProductCreate schema.
    
    Args:
        jsonld_data: JSON-LD product data
        organization_id: Organization UUID
        brand_id: Brand UUID (must be resolved before calling)
        category_id: Category UUID (must be resolved before calling)
        product_group_id: Optional ProductGroup UUID (must be resolved before calling)
        
    Returns:
        ProductCreate object ready for service
    """
    from app.schemas.product import ProductCreate, PropertyValueBase
    import json
    
    # Create a deep copy to avoid modifying the original and serialize datetime objects
    jsonld_copy = json.loads(json.dumps(jsonld_data, default=str))
    
    # Extract variant attributes from additionalProperty
    variant_attrs = {}
    additional_props = []
    additional_property = jsonld_data.get("additionalProperty", [])
    if additional_property:
        for prop in additional_property:
            if isinstance(prop, dict) and "name" in prop and "value" in prop:
                variant_attrs[prop["name"]] = prop["value"]
                additional_props.append(PropertyValueBase(
                    name=prop["name"],
                    value=prop["value"]
                ))
    
    # Create ProductCreate object
    return ProductCreate(
        name=jsonld_data.get("name", ""),
        sku=jsonld_data.get("sku", ""),
        description=jsonld_data.get("description"),
        url=jsonld_data.get("url"),
        product_group_id=product_group_id,
        brand_id=brand_id,
        urn=jsonld_data.get("@id", ""),
        variant_attributes=variant_attrs,
        organization_id=organization_id,
        category_id=category_id,
        additional_properties=additional_props if additional_props else None,
        raw_data=jsonld_copy  # Use the copy with serialized datetime
    )


def parse_jsonld_to_product_update(jsonld_data: Dict[str, Any]) -> "ProductUpdate":
    """
    Parse JSON-LD product data into ProductUpdate schema.
    
    Args:
        jsonld_data: JSON-LD product data
        
    Returns:
        ProductUpdate object ready for service
    """
    from app.schemas.product import ProductUpdate, PropertyValueBase
    import json
    from datetime import datetime
    
    # Create a deep copy to avoid modifying the original
    jsonld_copy = json.loads(json.dumps(jsonld_data, default=str))
    
    # Extract variant attributes from additionalProperty
    variant_attrs = {}
    additional_props = []
    additional_property = jsonld_data.get("additionalProperty", [])
    if additional_property:
        for prop in additional_property:
            if isinstance(prop, dict) and "name" in prop and "value" in prop:
                variant_attrs[prop["name"]] = prop["value"]
                additional_props.append(PropertyValueBase(
                    name=prop["name"],
                    value=prop["value"]
                ))
    
    # Create ProductUpdate object
    return ProductUpdate(
        name=jsonld_data.get("name"),
        sku=jsonld_data.get("sku"),
        description=jsonld_data.get("description"),
        url=jsonld_data.get("url"),
        variant_attributes=variant_attrs,
        additional_properties=additional_props if additional_props else None,
        raw_data=jsonld_copy  # Use the copy with serialized datetime
    )


def parse_jsonld_offer(offer_data: Dict[str, Any], product_id: Any, organization_id: Any) -> "OfferCreate":
    """
    Parse JSON-LD offer data into OfferCreate schema.
    
    Args:
        offer_data: JSON-LD offer data
        product_id: Product UUID
        organization_id: Organization UUID
        
    Returns:
        OfferCreate object ready for service
    """
    from app.schemas.offer import OfferCreate
    import json
    
    # Create a deep copy to avoid modifying the original and serialize datetime objects
    offer_data_copy = json.loads(json.dumps(offer_data, default=str))
    
    inventory = offer_data.get("inventoryLevel", {})
    
    return OfferCreate(
        product_id=product_id,
        organization_id=organization_id,
        price=offer_data.get("price", 0.0),
        price_currency=offer_data.get("priceCurrency", "USD"),
        availability=offer_data.get("availability", "").replace("https://schema.org/", ""),
        inventory_level=int(inventory.get("value", 0)) if inventory else None,
        price_valid_until=offer_data.get("priceValidUntil"),
        raw_data=offer_data_copy  # Use the copy with serialized datetime
    )


def parse_jsonld_to_product_group_create(jsonld_data: Dict[str, Any], organization_id: Any, brand_id: Any, category_id: Any) -> "ProductGroupCreate":
    """
    Parse JSON-LD product group data into ProductGroupCreate schema.
    
    Args:
        jsonld_data: JSON-LD product group data
        organization_id: Organization UUID
        brand_id: Brand UUID (must be resolved before calling)
        category_id: Category UUID (must be resolved before calling)
        
    Returns:
        ProductGroupCreate object ready for service
    """
    from app.schemas.product_group import ProductGroupCreate
    import json
    
    # Create a deep copy to avoid modifying the original and serialize datetime objects
    jsonld_copy = json.loads(json.dumps(jsonld_data, default=str))
    
    # Extract varies_by and ensure it's a list
    varies_by = jsonld_data.get("variesBy", [])
    if isinstance(varies_by, str):
        varies_by = [varies_by]
    
    return ProductGroupCreate(
        name=jsonld_data.get("name", ""),
        description=jsonld_data.get("description"),
        brand_id=brand_id,
        urn=jsonld_data.get("@id", ""),
        product_group_id=jsonld_data.get("productGroupID", ""),
        varies_by=varies_by,
        organization_id=organization_id,
        category_id=category_id,
        raw_data=jsonld_copy  # Use the copy with serialized datetime
    )


def parse_jsonld_to_product_group_update(jsonld_data: Dict[str, Any]) -> "ProductGroupUpdate":
    """
    Parse JSON-LD product group data into ProductGroupUpdate schema.
    
    Args:
        jsonld_data: JSON-LD product group data
        
    Returns:
        ProductGroupUpdate object ready for service
    """
    from app.schemas.product_group import ProductGroupUpdate
    import json
    
    # Create a deep copy to avoid modifying the original and serialize datetime objects
    jsonld_copy = json.loads(json.dumps(jsonld_data, default=str))
    
    return ProductGroupUpdate(
        name=jsonld_data.get("name"),
        description=jsonld_data.get("description"),
        raw_data=jsonld_copy  # Use the copy with serialized datetime
    )


def format_organization_registry_response(organization: Any) -> Dict[str, Any]:
    """
    Format organization data into CMP brand-registry format.
    
    Args:
        organization: Organization object with attributes like urn, name, url, etc.
        
    Returns:
        Dict representing a CMP brand-registry response
    """
    # Extract brand information if available
    brand_data = None
    if hasattr(organization, 'brands') and organization.brands:
        # Assuming the first brand is the primary one
        brand = organization.brands[0] if isinstance(organization.brands, list) else organization.brands
        brand_data = {
            "@type": "Brand",
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:brandId",
                "value": brand.urn
            },
            "name": brand.name,
            "url": getattr(brand, 'url', organization.url),
            "logo": brand.logo_url if hasattr(brand, 'logo_url') else None
        }
    
    # Extract category from raw_data if available
    category = None
    if hasattr(organization, 'raw_data') and organization.raw_data:
        category = organization.raw_data.get('category')
    
    # Build the organization response
    response = {
        "@context": {
            "schema": "https://schema.org",
            "cmp": "https://cmp.commercemesh.com/ns#"
        },
        "@type": "Organization",
        "identifier": {
            "@type": "PropertyValue",
            "propertyID": "cmp:orgId",
            "value": organization.urn
        },
        "name": organization.name,
        "url": organization.url,
        "logo": organization.logo_url if hasattr(organization, 'logo_url') else None,
        "description": organization.description if hasattr(organization, 'description') else None,
        "category": category
    }
    
    # Add CMP services structure
    # Determine base URL using domain or subdomain
    base_url = None
    if hasattr(organization, 'domain') and organization.domain:
        # Use custom domain if configured
        base_url = f"https://{organization.domain}"
    elif hasattr(organization, 'subdomain') and organization.subdomain:
        # Use subdomain with HOST from config
        from app.core.config import settings
        base_url = f"https://{organization.subdomain}.{settings.HOST}"
    
    if base_url:
        response["cmp:services"] = {
            "@type": "StructuredValue",
            "name": "CommerceMesh Services",
            "cmp:productFeed": {
                "@type": "DataFeed",
                "name": "Product Feed",
                "url": f"{base_url}/feed/feed.json",
                "encodingFormat": "application/json"
            },
            "cmp:queryAPI": {
                "@type": "WebAPI",
                "name": "Query API",
                "url": f"{base_url}/api/v1/query",
                "documentation": f"{base_url}/api/v1/query/docs"
            },
            "cmp:adminAPI": {
                "@type": "WebAPI",
                "name": "Admin API",
                "url": f"{base_url}/api/v1/admin",
                "documentation": f"{base_url}/api/v1/admin/docs"
            },
            "cmp:MCP": {
                "@type": "SSE",
                "name": "MCP (Sunset)",
                "url": f"{base_url}/sse",
                "encodingFormat": "text/event-stream"
            }
        }
    
    # Add brand if available
    if brand_data:
        response["brand"] = brand_data
    
    # Remove None values for cleaner response
    response = {k: v for k, v in response.items() if v is not None}
    
    return response


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
    
    # Check if we need cmp namespace
    has_cmp_namespace = False
    for list_item in item_list_elements:
        item = list_item.get("item", {})
        if "@cmp:media" in item or "cmp:searchScore" in item:
            has_cmp_namespace = True
            break
    
    # Set appropriate context
    if has_cmp_namespace:
        context = {
            "@context": {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            }
        }
    else:
        context = {"@context": "https://schema.org"}
    
    # Create the final response
    response_data = {
        **context,
        "@type": "ItemList",
        "itemListElement": item_list_elements
    }
    
    return response_data


