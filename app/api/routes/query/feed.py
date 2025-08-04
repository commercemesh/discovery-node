from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote

from app.storage.s3_reader import S3Reader
from app.core.dependencies import get_organization_context
from app.core.config import settings
from app.db.base import get_db_session
from app.services.organization_service import OrganizationService
from app.db.repositories.product_repository import ProductRepository
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

feed_router = APIRouter()

async def generate_dynamic_feed(
    organization,
    request: Request,
    db: Session
) -> dict:
    """
    Generate feed.json dynamically for an organization.
    
    Args:
        organization: Organization model instance
        request: FastAPI request object
        db: Database session
        
    Returns:
        Dict containing the feed structure
    """
    # Get host for URL generation
    host = request.headers.get("host", "")
    protocol = "https" if request.url.scheme == "https" else "http"
    base_url = f"{protocol}://{host}"
    
    # Get organization's categories directly from the relationship
    category_names = [cat.name for cat in organization.categories]
    
    # Get unique product attributes and values
    product_repo = ProductRepository(db)
    attributes = get_unique_attributes(product_repo, organization.id)
    
    # Generate search examples
    examples = generate_search_examples(base_url, category_names)
    
    # Build the feed structure
    feed = {
        "schema": "cmp.feed.index.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "organization": {
            "name": organization.name,
            "url": organization.url or base_url
        },
        "openapi_spec": f"{base_url}/api/v1/openapi.json",
        "search_template": f"{base_url}/api/v1/query/search?q={{query}}&category={{category}}&price_max={{price_max}}&attributes={{attributes}}&limit=20",
        "search_parameters": {
            "query": "REQUIRED: Natural-language search terms.",
            "category": "OPTIONAL: see facets.categories",
            "price_max": "OPTIONAL: Number",
            "attributes": "OPTIONAL: see facets.attributes",
            "limit": "OPTIONAL: Max rows; default 20"
        },
        "facets": {
            "categories": category_names,
            "attributes": attributes
        },
        "examples": examples,
        "quick_access": {
            "bestsellers": f"{base_url}/api/v1/query/search?attributes=popularity:true&limit=20",
            "deals": f"{base_url}/api/v1/query/search?attributes=on_sale:true&attributes=discount_desc:true&limit=50",
            "new": f"{base_url}/api/v1/query/search?attributes=days_new:30&attributes=newest:true&limit=20"
        }
    }
    
    return feed


def get_unique_attributes(product_repo: ProductRepository, organization_id: str) -> List[Dict[str, Any]]:
    """
    Extract unique attributes and their values from all products.
    
    Returns:
        List of dicts with 'name' and 'values' keys
    """
    # Get all products for the organization
    products = product_repo.list_by_organization(organization_id, limit=1000)
    
    # Extract attributes from raw_data
    attribute_map = {}
    
    for product in products:
        if product.raw_data and isinstance(product.raw_data, dict):
            # Look for common attribute fields
            for key in ['attributes', 'additionalProperty', 'properties', 'specifications']:
                if key in product.raw_data:
                    attrs = product.raw_data[key]
                    if isinstance(attrs, dict):
                        for attr_name, attr_value in attrs.items():
                            if attr_name not in attribute_map:
                                attribute_map[attr_name] = set()
                            if isinstance(attr_value, (str, int, float)):
                                attribute_map[attr_name].add(str(attr_value))
                    elif isinstance(attrs, list):
                        for attr in attrs:
                            if isinstance(attr, dict) and 'name' in attr and 'value' in attr:
                                attr_name = attr['name']
                                attr_value = attr['value']
                                if attr_name not in attribute_map:
                                    attribute_map[attr_name] = set()
                                if isinstance(attr_value, (str, int, float)):
                                    attribute_map[attr_name].add(str(attr_value))
    
    # Convert to required format
    attributes = []
    for name, values in attribute_map.items():
        if values:  # Only include attributes that have values
            attributes.append({
                "name": name,
                "values": sorted(list(values))[:20]  # Limit to top 20 values per attribute
            })
    
    # Sort by attribute name
    attributes.sort(key=lambda x: x['name'])
    
    # Return top 10 most common attributes
    return attributes[:10]


def generate_search_examples(base_url: str, categories: List[str]) -> List[Dict[str, str]]:
    """
    Generate example search queries based on available categories.
    
    Returns:
        List of example queries with intent and ready_link
    """
    examples = []
    
    # Basic product search example
    examples.append({
        "intent": "comfortable walking shoes under $100",
        "ready_link": f"{base_url}/api/v1/query/search?q={quote('comfortable walking shoes')}&price_max=100&limit=20"
    })
    
    # Category-based example if categories exist
    if categories:
        category = categories[0]
        category_encoded = quote(category)
        examples.append({
            "intent": f"best products in {category}",
            "ready_link": f"{base_url}/api/v1/query/search?q={quote('best products')}&category={category_encoded}&limit=20"
        })
    
    # Attribute-based example
    examples.append({
        "intent": "eco-friendly products with free shipping",
        "ready_link": f"{base_url}/api/v1/query/search?q={quote('eco-friendly')}&attributes={quote('shipping:free')}&limit=20"
    })
    
    return examples


@feed_router.get("/feed/{filename:path}")
async def serve_feed(
    filename: str,
    request: Request,
    db: Session = Depends(get_db_session)
):
    """
    Serve feed files. For feed.json, generate dynamically. For other files, serve from S3.
    
    Args:
        filename: Feed filename (e.g., feed.json, feed-001.json)
        request: FastAPI request object
        db: Database session
        
    Returns:
        JSON content of the feed file
    """
    logger.info(f"Serving feed file: {filename}")
    logger.info(f"Request host: {request.headers.get('host', 'no host header')}")
    
    # Validate filename - must be JSON
    if not filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON feed files are supported")
    
    # Extract subdomain from host header
    host = request.headers.get("host", "")
    if not host:
        raise HTTPException(status_code=400, detail="Host header not found")
    
    # Remove port if present
    host_without_port = host.split(':')[0]
    
    # First, check if this is a custom domain
    org_service = OrganizationService(db)
    
    # Try to find organization by custom domain
    from app.db.models.organization import Organization
    organization = db.query(Organization).filter(Organization.domain == host_without_port).first()
    
    if not organization:
        # Not a custom domain, extract subdomain
        host_parts = host_without_port.split('.')
        
        if len(host_parts) >= 2:
            # Take the first part as subdomain
            subdomain = host_parts[0]
            logger.info(f"Extracted subdomain: {subdomain}")
            
            # Get organization by subdomain
            organization = org_service.get_by_subdomain(subdomain)
        else:
            raise HTTPException(status_code=400, detail="Invalid host format - subdomain not found")
    
    if not organization:
        logger.warning(f"Organization not found for host: {host_without_port}")
        raise HTTPException(status_code=404, detail=f"Organization not found for host: {host_without_port}")
    
    # Get URN from organization
    if not organization.urn:
        logger.error(f"Organization {organization.name} has no URN")
        raise HTTPException(status_code=500, detail="Organization URN not found")
    
    logger.info(f"Found organization URN: {organization.urn}")
    
    # Check if this is feed.json - if so, generate dynamically
    if filename == "feed.json":
        logger.info(f"Generating dynamic feed.json for organization {organization.name}")
        feed_data = await generate_dynamic_feed(organization, request, db)
        
        # Return with appropriate headers for crawlers/bots
        return JSONResponse(
            content=feed_data,
            headers={
                # Allow all origins for feed access
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, User-Agent",
                
                # Cache for 1 hour
                "Cache-Control": "public, max-age=3600",
                
                # Indicate content type
                "Content-Type": "application/json; charset=utf-8",
                
                # Allow robots
                "X-Robots-Tag": "all",
                
                # No authentication required
                "X-Content-Type-Options": "nosniff",
            }
        )
    
    # For other feed files, continue with S3 retrieval
    # Use the full URN as the S3 folder path
    # S3 path format: urn:cmp:org:6794c67d-8258-5273-a8f7-612f3bfdfe79/feed.json
    org_urn = organization.urn
    logger.info(f"Using full URN for S3 path: {org_urn}")
    
    # Initialize S3 reader
    s3_reader = S3Reader()
    
    if not s3_reader.bucket_name:
        raise HTTPException(status_code=503, detail="S3 storage not configured")
    
    try:
        # Construct S3 key using URN/filename pattern (matching OpenFeed's storage)
        s3_key = f"{org_urn}/{filename}"
        logger.info(f"Reading from S3: s3://{s3_reader.bucket_name}/{s3_key}")
        
        # Get object from S3
        response = s3_reader.s3_client.get_object(
            Bucket=s3_reader.bucket_name,
            Key=s3_key
        )
        
        # Read content
        content = response['Body'].read()
        
        # Parse JSON to validate it
        import json
        feed_data = json.loads(content)
        
        # Return with appropriate headers for crawlers/bots
        return JSONResponse(
            content=feed_data,
            headers={
                # Allow all origins for feed access
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, User-Agent",
                
                # Cache for 1 hour
                "Cache-Control": "public, max-age=3600",
                
                # Indicate content type
                "Content-Type": "application/json; charset=utf-8",
                
                # Allow robots
                "X-Robots-Tag": "all",
                
                # No authentication required
                "X-Content-Type-Options": "nosniff",
            }
        )
        
    except s3_reader.s3_client.exceptions.NoSuchKey:
        logger.warning(f"Feed file not found in S3: {s3_key}")
        # Try with feeds/ prefix as fallback (some feeds might be stored with prefix)
        try:
            s3_key_with_prefix = f"feeds/{org_urn}/{filename}"
            logger.info(f"Trying with feeds/ prefix: s3://{s3_reader.bucket_name}/{s3_key_with_prefix}")
            
            response = s3_reader.s3_client.get_object(
                Bucket=s3_reader.bucket_name,
                Key=s3_key_with_prefix
            )
            
            content = response['Body'].read()
            import json
            feed_data = json.loads(content)
            
            return JSONResponse(
                content=feed_data,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, User-Agent",
                    "Cache-Control": "public, max-age=3600",
                    "Content-Type": "application/json; charset=utf-8",
                    "X-Robots-Tag": "all",
                    "X-Content-Type-Options": "nosniff",
                }
            )
        except s3_reader.s3_client.exceptions.NoSuchKey:
            logger.warning(f"Feed file not found with or without prefix: {s3_key}")
            raise HTTPException(status_code=404, detail="Feed file not found")
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in feed file: {s3_key}")
        raise HTTPException(status_code=500, detail="Invalid feed format")
    except Exception as e:
        logger.error(f"Error serving feed {filename}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving feed: {str(e)}")

@feed_router.options("/feed/{filename:path}")
async def feed_options(filename: str):
    """
    Handle OPTIONS requests for CORS preflight.
    This ensures crawlers and bots can access the feed.
    """
    # filename parameter is required for route matching but not used
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, User-Agent",
            "Access-Control-Max-Age": "86400",  # 24 hours
        }
    )