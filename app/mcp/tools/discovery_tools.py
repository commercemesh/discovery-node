import logging
import json
from typing import List

import mcp.types as types
from mcp.server.lowlevel import Server

from app.core.logging import get_logger
from app.services.search_service import SearchService
from app.services.product_service import ProductService
from app.utils.formatters import format_product_search_response

logger = get_logger(__name__)


def register_discovery_tools(
    app: Server,
    search_service: SearchService,
    product_service: ProductService
) -> None:
    """Register all discovery-related MCP tools"""
    
    @app.list_tools()
    async def list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name="search-products",
                description="Search for products using hybrid vector search",
                inputSchema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for products"
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of results (default: 10)",
                            "default": 10
                        }
                    }
                }
            ),
            types.Tool(
                name="get-product-details",
                description="Get detailed information about a specific product or product group by URN",
                inputSchema={
                    "type": "object",
                    "required": ["urn"],
                    "properties": {
                        "urn": {
                            "type": "string",
                            "description": "Product or ProductGroup URN to retrieve details for"
                        }
                    }
                }
            ),
            types.Tool(
                name="get-products-by-category",
                description="Get products filtered by category",
                inputSchema={
                    "type": "object",
                    "required": ["category"],
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Product category to filter by"
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of results (default: 20)",
                            "default": 20
                        }
                    }
                }
            )
        ]
    
    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
        """Handle tool calls"""
        ctx = app.request_context
        
        try:
            if name == "search-products":
                return _handle_search_products(
                    search_service, arguments, ctx
                )
            elif name == "get-product-details":
                return _handle_get_product_details(
                    product_service, arguments, ctx
                )
            elif name == "get-products-by-category":
                return _handle_get_products_by_category(
                    product_service, arguments, ctx
                )
            else:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )
                ]
        except Exception as e:
            logger.error(f"Error handling tool {name}: {e}")
            return [
                types.TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )
            ]


def _handle_search_products(
    search_service: SearchService, 
    arguments: dict, 
    ctx
) -> List[types.TextContent]:
    """Handle product search requests"""
    query = arguments["query"]
    limit = arguments.get("limit", 10)
    
    # Send progress notification
    # Note: We can't use async ctx.session.send_log_message in sync function
    logger.info(f"Searching for products: '{query}'")
    
    # Perform search
    results = search_service.search_products(
        query=query,
        top_k=limit
    )
    
    # Format results
    if not results:
        return [
            types.TextContent(
                type="text",
                text=f"No products found for query: '{query}'"
            )
        ]
    
    response_data = format_product_search_response(results)
    
    # Convert dictionary to JSON string for MCP TextContent
    response_text = json.dumps(response_data, indent=2)
   
    return [
        types.TextContent(
            type="text",
            text=response_text
        )
    ]


def _handle_get_product_details(
    product_service: ProductService,
    arguments: dict,
    ctx
) -> List[types.TextContent]:
    """Handle product details requests by URN"""
    urn = arguments["urn"]
    
    logger.info(f"Fetching details for URN: {urn}")
    
    # Use the same service method as the products API
    product_details = product_service.get_product_with_details_by_urn(urn)
    
    if not product_details:
        return [
            types.TextContent(
                type="text",
                text=f"Product or ProductGroup not found: {urn}"
            )
        ]
    
    result_type = product_details.get("type")
    brand = product_details.get("brand")
    category = product_details.get("category")
    offers = product_details.get("offers", [])
    
    if result_type == "product":
        # Format product details
        product = product_details["product"]
        details = f"**Product Details**\n\n"
        details += f"**URN:** {product.urn}\n"
        details += f"**Name:** {product.name}\n"
        details += f"**SKU:** {product.sku or 'N/A'}\n"
        details += f"**Brand:** {brand.name if brand else 'Unknown'}\n"
        details += f"**Category:** {category.name if category else 'Unknown'}\n"
        details += f"**Description:** {product.description or 'No description available'}\n"
        
        # Add offer information
        if offers:
            details += f"**Offers:** {len(offers)} available\n"
            for i, offer in enumerate(offers[:3], 1):  # Show first 3 offers
                details += f"  {i}. ${offer.price} {offer.price_currency} - {offer.availability}\n"
        
        # Add more details if available
        if product.url:
            details += f"**URL:** {product.url}\n"
            
    elif result_type == "product_group":
        # Format product group details
        product_group = product_details["product_group"]
        linked_products = product_details.get("linked_products", [])
        
        details = f"**ProductGroup Details**\n\n"
        details += f"**URN:** {product_group.urn}\n"
        details += f"**Name:** {product_group.name}\n"
        details += f"**Brand:** {brand.name if brand else 'Unknown'}\n"
        details += f"**Category:** {category.name if category else 'Unknown'}\n"
        details += f"**Description:** {product_group.description or 'No description available'}\n"
        details += f"**Product Group ID:** {product_group.product_group_id or 'N/A'}\n"
        details += f"**Varies By:** {', '.join(product_group.varies_by) if product_group.varies_by else 'N/A'}\n"
        
        # Add linked products
        if linked_products:
            details += f"\n**Linked Products ({len(linked_products)}):**\n"
            for i, product in enumerate(linked_products[:5], 1):  # Show first 5 products
                details += f"  {i}. {product.name} (URN: {product.urn})\n"
            if len(linked_products) > 5:
                details += f"  ... and {len(linked_products) - 5} more\n"
        
        # Add URL if available
        if product_group.url:
            details += f"**URL:** {product_group.url}\n"
    
    return [
        types.TextContent(
            type="text",
            text=details
        )
    ]


def _handle_get_products_by_category(
    product_service: ProductService,
    arguments: dict,
    ctx
) -> List[types.TextContent]:
    """Handle category-based product requests"""
    category = arguments["category"]
    limit = arguments.get("limit", 20)
    
    logger.info(f"Fetching products in category: {category}")
    
    products = product_service.get_products_by_category(
        category=category,
        limit=limit
    )
    
    if not products:
        return [
            types.TextContent(
                type="text",
                text=f"No products found in category: '{category}'"
            )
        ]
    
    # Format category results
    response_text = f"Found {len(products)} products in category '{category}':\n\n"
    for i, product in enumerate(products, 1):
        response_text += f"{i}. **{product.name}**\n"
        response_text += f"   Brand: {product.brand.name if product.brand else 'Unknown'}\n"
        response_text += f"   Price: ${product.price or 'N/A'}\n"
        response_text += f"   ID: {product.id}\n\n"
    
    return [
        types.TextContent(
            type="text",
            text=response_text
        )
    ]