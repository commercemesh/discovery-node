import logging
import json
from typing import List

import mcp.types as types
from mcp.server.lowlevel import Server

from app.core.logging import get_logger
from app.core.dependencies import SearchServiceFactory, ProductServiceFactory
from app.utils.formatters import format_product_search_response
from app.services.cache_service import get_cache_service
from app.services.filter_service import FilterService
from app.services.comparison_service import ComparisonService
from app.utils.request_id import validate_request_id

logger = get_logger(__name__)


def register_discovery_tools(
    app: Server,
    search_service_factory: SearchServiceFactory,
    product_service_factory: ProductServiceFactory
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
            ),
            types.Tool(
                name="filter-products",
                description="Filter cached search results using natural language criteria and price filters",
                inputSchema={
                    "type": "object",
                    "required": ["request_id", "filter_criteria"],
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": "6-character cache request ID from previous search",
                            "pattern": "^[A-Z0-9]{6}$"
                        },
                        "filter_criteria": {
                            "type": "string",
                            "description": "Natural language filter criteria (e.g., 'waterproof', 'lightweight', 'eco friendly')"
                        },
                        "max_price": {
                            "type": "number",
                            "description": "Maximum price filter",
                            "minimum": 0
                        },
                        "min_price": {
                            "type": "number",
                            "description": "Minimum price filter",
                            "minimum": 0
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of results to return",
                            "minimum": 1,
                            "maximum": 100
                        }
                    }
                }
            ),
            types.Tool(
                name="compare-products",
                description="Compare specific products from cached results by their indices",
                inputSchema={
                    "type": "object",
                    "required": ["request_id", "indices"],
                    "properties": {
                        "request_id": {
                            "type": "string",
                            "description": "6-character cache request ID from previous search",
                            "pattern": "^[A-Z0-9]{6}$"
                        },
                        "indices": {
                            "type": "array",
                            "description": "Product indices to compare (0-based, min 2, max 5)",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 5
                        },
                        "comparison_aspects": {
                            "type": "array",
                            "description": "Specific aspects to compare (e.g., 'price', 'features'). Auto-detected if not provided.",
                            "items": {"type": "string"}
                        },
                        "format": {
                            "type": "string",
                            "description": "Output format: table (default), narrative, or pros_cons",
                            "enum": ["table", "narrative", "pros_cons"],
                            "default": "table"
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
                    search_service_factory, arguments, ctx
                )
            elif name == "get-product-details":
                return _handle_get_product_details(
                    product_service_factory, arguments, ctx
                )
            elif name == "get-products-by-category":
                return _handle_get_products_by_category(
                    product_service_factory, arguments, ctx
                )
            elif name == "filter-products":
                return _handle_filter_products(arguments, ctx)
            elif name == "compare-products":
                return _handle_compare_products(arguments, ctx)
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
    search_service_factory: SearchServiceFactory, 
    arguments: dict, 
    ctx
) -> List[types.TextContent]:
    """Handle product search requests"""
    query = arguments["query"]
    limit = arguments.get("limit", 10)
    
    # Get cache service
    cache_service = get_cache_service()
    
    # Generate cache key and request ID
    cache_key = cache_service.generate_cache_key("mcp-search")
    request_id = cache_key.split(":")[-1]
    
    # Send progress notification
    # Note: We can't use async ctx.session.send_log_message in sync function
    logger.info(f"Searching for products: '{query}'")
    
    # Create service with proper session management
    for search_service in search_service_factory.create_with_cleanup():
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
        
        # Add request ID to response
        response_data["cmp:requestId"] = request_id
        
        # Cache the response
        cache_service.cache_response(cache_key, response_data)
    
        # Convert dictionary to JSON string for MCP TextContent
        response_text = json.dumps(response_data, indent=2)
       
        return [
            types.TextContent(
                type="text",
                text=response_text
            )
        ]


def _handle_get_product_details(
    product_service_factory: ProductServiceFactory,
    arguments: dict,
    ctx
) -> List[types.TextContent]:
    """Handle product details requests by URN"""
    urn = arguments["urn"]
    
    logger.info(f"Fetching details for URN: {urn}")
    
    # Create service with proper session management
    for product_service in product_service_factory.create_with_cleanup():
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
    product_service_factory: ProductServiceFactory,
    arguments: dict,
    ctx
) -> List[types.TextContent]:
    """Handle category-based product requests"""
    category = arguments["category"]
    limit = arguments.get("limit", 20)
    
    logger.info(f"Fetching products in category: {category}")
    
    # Create service with proper session management
    for product_service in product_service_factory.create_with_cleanup():
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


def _handle_filter_products(
    arguments: dict,
    ctx
) -> List[types.TextContent]:
    """Handle product filtering requests"""
    request_id = arguments["request_id"]
    filter_criteria = arguments["filter_criteria"]
    max_price = arguments.get("max_price")
    min_price = arguments.get("min_price")
    limit = arguments.get("limit")
    
    logger.info(f"Filtering products from request {request_id} with criteria: '{filter_criteria}'")
    
    # Validate request ID
    if not validate_request_id(request_id):
        return [
            types.TextContent(
                type="text",
                text=f"Invalid request ID format: {request_id}"
            )
        ]
    
    # Validate price range
    if min_price is not None and max_price is not None and min_price > max_price:
        return [
            types.TextContent(
                type="text",
                text="Minimum price cannot be greater than maximum price"
            )
        ]
    
    # Create filter service
    filter_service = FilterService()
    
    # Get cached data and filter
    filtered_items, total_filtered = filter_service.filter_products(
        request_id=request_id,
        filter_criteria=filter_criteria,
        max_price=max_price,
        min_price=min_price,
        limit=limit
    )
    
    if total_filtered == 0:
        # Check if original data exists
        cache_service = get_cache_service()
        original_found = False
        for prefix in ["search", "product", "mcp-search"]:
            cache_key = f"{prefix}:{request_id}"
            if cache_service.get_cached_response(cache_key):
                original_found = True
                break
        
        if not original_found:
            return [
                types.TextContent(
                    type="text",
                    text=f"No cached results found for request ID: {request_id}"
                )
            ]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=f"No products found matching filter criteria: '{filter_criteria}'"
                )
            ]
    
    # Get original cached data for metadata
    cache_service = get_cache_service()
    cached_data = None
    for prefix in ["search", "product", "mcp-search"]:
        cache_key = f"{prefix}:{request_id}"
        cached_data = cache_service.get_cached_response(cache_key)
        if cached_data:
            break
    
    # Create filtered response
    filtered_response = filter_service.create_filtered_response(
        cached_data=cached_data or {},
        filtered_items=filtered_items,
        total_filtered=total_filtered,
        filter_criteria=filter_criteria,
        max_price=max_price,
        min_price=min_price
    )
    
    # Generate new cache key for filtered results
    new_cache_key = cache_service.generate_cache_key("mcp-filter")
    new_request_id = new_cache_key.split(":")[-1]
    
    # Add new request ID to response
    filtered_response["cmp:requestId"] = new_request_id
    
    # Cache the filtered results
    cache_service.cache_response(new_cache_key, filtered_response)
    
    # Convert to JSON string for MCP
    response_text = json.dumps(filtered_response, indent=2)
    
    logger.info(
        f"Filtered {total_filtered} results with new request ID: {new_request_id}"
    )
    
    return [
        types.TextContent(
            type="text",
            text=response_text
        )
    ]


def _handle_compare_products(
    arguments: dict,
    ctx
) -> List[types.TextContent]:
    """Handle product comparison requests"""
    request_id = arguments["request_id"]
    indices = arguments["indices"]
    comparison_aspects = arguments.get("comparison_aspects")
    format_type = arguments.get("format", "table")
    
    logger.info(f"Comparing products at indices {indices} from request {request_id}")
    
    # Validate request ID
    if not validate_request_id(request_id):
        return [
            types.TextContent(
                type="text",
                text=f"Invalid request ID format: {request_id}"
            )
        ]
    
    # Validate indices
    if not isinstance(indices, list):
        return [
            types.TextContent(
                type="text",
                text="Indices must be a list of numbers"
            )
        ]
    
    # Convert indices to integers
    try:
        indices = [int(idx) for idx in indices]
    except (ValueError, TypeError):
        return [
            types.TextContent(
                type="text",
                text="All indices must be valid integers"
            )
        ]
    
    # Create comparison service
    comparison_service = ComparisonService()
    
    try:
        # Perform comparison
        comparison_result = comparison_service.compare_products(
            request_id=request_id,
            indices=indices,
            comparison_aspects=comparison_aspects,
            format_type=format_type
        )
        
        # Convert to JSON string for MCP
        response_text = json.dumps(comparison_result, indent=2)
        
        logger.info(
            f"Compared {len(indices)} products with new request ID: {comparison_result['cmp:requestId']}"
        )
        
        return [
            types.TextContent(
                type="text",
                text=response_text
            )
        ]
        
    except ValueError as e:
        error_msg = str(e)
        
        # Format error messages
        if "No cached results found" in error_msg:
            return [
                types.TextContent(
                    type="text",
                    text=f"No cached results found for request ID: {request_id}"
                )
            ]
        elif "out of range" in error_msg:
            return [
                types.TextContent(
                    type="text",
                    text=error_msg
                )
            ]
        elif "Maximum 5 products" in error_msg:
            return [
                types.TextContent(
                    type="text",
                    text=error_msg
                )
            ]
        else:
            return [
                types.TextContent(
                    type="text",
                    text=f"Comparison error: {error_msg}"
                )
            ]
    
    except Exception as e:
        logger.error(f"Error comparing products: {str(e)}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=f"Error comparing products: {str(e)}"
            )
        ]