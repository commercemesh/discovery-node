# app/mcp/resources/discovery_resources.py
import json
import logging
from typing import List, Union

import mcp.types as types
from mcp.server.lowlevel import Server
from pydantic import AnyUrl

from app.core.logging import get_logger
from app.core.dependencies import get_search_service
from app.db.base import SessionLocal

logger = get_logger(__name__)


def register_discovery_resources(app: Server) -> None:
    """Register discovery-related MCP resources based on current implementation"""
    
    @app.list_resources()
    async def list_resources() -> List[types.Resource]:
        """List available resources"""
        return [
            types.Resource(
                uri="cmp://products/sample",
                name="Product Sample",
                description="Sample of products from recent searches",
                mimeType="application/ld+json"
            ),
            types.Resource(
                uri="cmp://products/schema",
                name="Product Schema Documentation",
                description="Field definitions and schema for CMP product data",
                mimeType="application/json"
            ),
            types.Resource(
                uri="cmp://node/info",
                name="Discovery Node Info",
                description="Basic information about this discovery node",
                mimeType="application/json"
            )
        ]
    
    @app.read_resource()
    async def read_resource(uri: Union[str, AnyUrl]) -> str:
        """Read resource content"""
        logger.info(f"read_resource called with uri: {uri!r}")
        try:
            # Extract string from AnyUrl or use as-is
            uri_str = str(uri)
            
            if uri_str == "cmp://products/sample":
                logger.debug("Fetching product sample resource.")
                return await _get_product_sample()
            elif uri_str == "cmp://products/schema":
                logger.debug("Fetching product schema resource.")
                return await _get_product_schema()
            elif uri_str == "cmp://node/info":
                logger.debug("Fetching node info resource.")
                return await _get_node_info()
            else:
                logger.warning(f"Unknown resource requested: {uri_str}")
                raise ValueError(f"Unknown resource: {uri_str}")
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return json.dumps({"error": f"Failed to read resource: {str(e)}"})


async def _get_product_sample() -> str:
    """Get a sample of products using your existing search functionality"""
    try:
        logger.info("Fetching product sample using search service.")
        search_service = get_search_service()
        
        # Use a generic search term to get sample products
        logger.debug("Searching for products with query 'books' and top_k=5.")
        results = search_service.search_products(
            query="books", 
            top_k=5
        )
        logger.debug(f"Search results: {results}")
        
        if not results:
            logger.info("No products found for sample query.")
            return json.dumps({
                "@context": {
                    "schema": "https://schema.org",
                    "cmp": "https://schema.commercemesh.ai/ns#"
                },
                "@type": "ItemList",
                "name": "Product Sample",
                "description": "No products found",
                "itemListElement": []
            })
        
        # Use your existing formatter
        from app.utils.formatters import format_product_search_response
        logger.debug("Formatting product search response.")
        response_data = format_product_search_response(results)
        logger.debug(f"Formatted response data: {response_data}")
        
        # Wrap in proper CMP structure
        cmp_data = {
            "@context": {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            },
            "@type": "ItemList",
            "name": "Product Sample",
            "description": "Sample products from discovery node search",
            **response_data
        }
        logger.info("Returning product sample data.")
        
        return json.dumps(cmp_data, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting product sample: {e}")
        return json.dumps({
            "error": f"Failed to get product sample: {str(e)}"
        })


async def _get_product_schema() -> str:
    """Get complete field documentation for CMP product data based on actual schema"""
    schema_doc = {
        "@context": "https://schema.org",
        "@type": "Documentation",
        "name": "CMP Product Data Schema v0.1",
        "description": "Complete field definitions for CMP product search results",
        "about": {
            "@type": "DefinedTermSet",
            "name": "CMP Product Fields",
            "hasDefinedTerm": [
                # Top-level ItemList fields
                {
                    "@type": "DefinedTerm",
                    "termCode": "@context",
                    "name": "JSON-LD Context",
                    "description": "Defines vocabularies used - schema.org and CMP namespace"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@type",
                    "name": "Schema Type",
                    "description": "Always 'ItemList' for search results, 'Product' for individual products"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "itemListElement",
                    "name": "Result Items",
                    "description": "Array of ListItem objects containing the actual products"
                },
                  {
                    "@type": "DefinedTerm",
                    "termCode": "url",
                    "name": "Product URL",
                    "description": "Direct link to the product's website/PDP page - USE THIS for clickable product links"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "image",
                    "name": "Product Images",
                    "description": "Array of product images - RENDER THE FIRST IMAGE for visual appeal"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "image[0].url",
                    "name": "Primary Image URL", 
                    "description": "URL of the first/primary product image - use this for display"
                },
                
                # ListItem fields
                {
                    "@type": "DefinedTerm",
                    "termCode": "position",
                    "name": "Result Position",
                    "description": "1-based position of this item in search results"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "item",
                    "name": "Product Data",
                    "description": "The actual Product or ProductGroup object"
                },
                
                # Core Product fields
                {
                    "@type": "DefinedTerm", 
                    "termCode": "@id",
                    "name": "Product Identifier",
                    "description": "Unique CMP URN for the product, format: urn:cmp:sku:{product-id}"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "name", 
                    "name": "Product Name",
                    "description": "Display name of the product"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "sku",
                    "name": "Stock Keeping Unit",
                    "description": "Unique product identifier used by the seller (required)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "description",
                    "name": "Product Description", 
                    "description": "Detailed description of the product"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "category",
                    "name": "Product Category",
                    "description": "Category classification for the product"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "image",
                    "name": "Product Images",
                    "description": "Array of product images or single image URL"
                },
                
                # Brand object
                {
                    "@type": "DefinedTerm",
                    "termCode": "brand",
                    "name": "Brand Information",
                    "description": "Brand object with @type='Brand' and name"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "brand.@type",
                    "name": "Brand Type",
                    "description": "Always 'Brand' for brand objects"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "brand.name",
                    "name": "Brand Name",
                    "description": "Name of the brand that manufactures/sells this product"
                },
                
                # Offers object (required)
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers",
                    "name": "Product Offers",
                    "description": "Offer object with pricing and availability (required for products)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.@type",
                    "name": "Offer Type",
                    "description": "Always 'Offer' for offer objects"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.price",
                    "name": "Offer Price", 
                    "description": "Current selling price for this offer (required)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.priceCurrency",
                    "name": "Price Currency",
                    "description": "ISO 4217 currency code (e.g., USD, EUR) (required)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.availability",
                    "name": "Availability Status",
                    "description": "Schema.org URL: https://schema.org/InStock or https://schema.org/OutOfStock (required)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.inventoryLevel",
                    "name": "Inventory Level Object",
                    "description": "QuantitativeValue object with current stock quantity (required)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.inventoryLevel.@type",
                    "name": "Inventory Type",
                    "description": "Always 'QuantitativeValue' for inventory objects"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.inventoryLevel.value",
                    "name": "Inventory Quantity",
                    "description": "Current quantity available in inventory (number)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.priceValidUntil",
                    "name": "Price Expiration",
                    "description": "ISO 8601 datetime when price expires (optional)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "offers.priceSpecification",
                    "name": "Price Specification",
                    "description": "Additional price details object (optional)"
                },
                
                # Additional properties array
                {
                    "@type": "DefinedTerm",
                    "termCode": "additionalProperty",
                    "name": "Additional Properties",
                    "description": "Array of PropertyValue objects for variant attributes"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "additionalProperty[].@type",
                    "name": "Property Type",
                    "description": "Always 'PropertyValue' for property objects"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "additionalProperty[].name",
                    "name": "Property Name",
                    "description": "Name of the property (e.g., 'color', 'size')"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "additionalProperty[].value",
                    "name": "Property Value",
                    "description": "Value of the property (string, number, boolean, object, or array)"
                },
                
                # Product variant relationship
                {
                    "@type": "DefinedTerm",
                    "termCode": "isVariantOf",
                    "name": "Product Group Reference",
                    "description": "Reference to the ProductGroup this product is a variant of"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "isVariantOf.@type",
                    "name": "Variant Type",
                    "description": "Always 'ProductGroup' for group references"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "isVariantOf.@id",
                    "name": "Product Group ID",
                    "description": "URN of the product group, format: urn:cmp:product:{group-id}"
                },
                
                # CMP-specific media
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media",
                    "name": "CMP Media Objects",
                    "description": "Array of rich media objects (videos, 360° views, etc.)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media[].@type",
                    "name": "Media Type",
                    "description": "ImageObject, VideoObject, or MediaObject"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media[].url",
                    "name": "Media URL",
                    "description": "Direct URL to the media file (required)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media[].encodingFormat",
                    "name": "Media Format",
                    "description": "MIME type of the media (e.g., video/mp4, image/jpeg)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media[].width",
                    "name": "Media Width",
                    "description": "Width in pixels for images/videos"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media[].height",
                    "name": "Media Height", 
                    "description": "Height in pixels for images/videos"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media[].duration",
                    "name": "Media Duration",
                    "description": "Duration for videos in ISO 8601 format (e.g., PT2M45S)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "@cmp:media[].caption",
                    "name": "Media Caption",
                    "description": "Descriptive caption for the media"
                },
                
                # Search-specific fields
                {
                    "@type": "DefinedTerm",
                    "termCode": "cmp:searchScore",
                    "name": "Search Relevance Score",
                    "description": "Hybrid search relevance score (0.0 to 1.0, higher = more relevant)"
                },
                {
                    "@type": "DefinedTerm",
                    "termCode": "url",
                    "name": "Product URL",
                    "description": "Direct link to the product page"
                }
            ]
        },
        "cmp:schemaValidation": {
            "@type": "PropertyValue",
            "name": "JSON Schema",
            "description": "Products must validate against CMP JSON Schema",
            "value": "http://json-schema.org/draft-07/schema#"
        },
        "cmp:requiredFields": [
            "@context", "@type", "@id", "name", "sku", "offers", "offers.price", 
            "offers.priceCurrency", "offers.availability", "offers.inventoryLevel"
        ]
    }
    
    return json.dumps(schema_doc, indent=2)

async def _get_node_info() -> str:
    """Get basic discovery node information"""
    try:
        node_info = {
            "@context": "https://schema.org",
            "@type": "Service",
            "name": "CMP Discovery Node by Overway",
            "description": "Demo of Commerce Mesh Protocol compatible MCP discovery node by Overway",
            "provider": {
                "@type": "Organization",
                "name": "Overway"
            },
            "serviceType": "ProductDiscovery",
            "serviceProtocol": "MCP",
            "availableChannel": {
                "@type": "ServiceChannel",
                "serviceProtocol": "StreamableHTTP",
                "description": "MCP StreamableHTTP with Server-Sent Events"
            },
            "potentialAction": [
                {
                    "@type": "SearchAction",
                    "name": "search-products",
                    "description": "Search for products using hybrid vector search",
                    "target": {
                        "@type": "EntryPoint",
                        "actionPlatform": "MCP",
                        "description": "MCP tool for product search"
                    }
                },
                {
                    "@type": "ViewAction", 
                    "name": "get-product-details",
                    "description": "Get detailed information about a specific product or product group by URN",
                    "target": {
                        "@type": "EntryPoint",
                        "actionPlatform": "MCP",
                        "description": "MCP tool for product/product group details via URN lookup"
                    }
                }
            ],
            "cmp:capabilities": {
                "hybridSearch": True,
                "vectorSearch": True,
                "categoryFiltering": True,
                "productDetails": True
            },
            "cmp:protocol": "v0.1"
        }
        
        return json.dumps(node_info, indent=2)
        
    except Exception as e:
        logger.error(f"Error getting node info: {e}")
        return json.dumps({
            "error": f"Failed to get node info: {str(e)}"
        })
