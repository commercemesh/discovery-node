# Standard library
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

# Third party
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text

# Local imports
from app.core.config import settings
from app.core.logging import get_logger
from app.core.auth import api_key_auth_admin
from app.middleware import MetricsMiddleware
import app.api as api


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application startup and shutdown events"""
    # Startup
    logger.info("🚀 Discovery API starting up...")

    # Test database connection
    try:
        from app.db.base import get_db_session

        session_gen = get_db_session()
        session = next(session_gen)
        session.execute(text("SELECT 1")).fetchone()
        session.close()
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise

    yield  # This is where FastAPI serves the application

    # Shutdown
    logger.info("🛑 Openfeed API shutting down...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title="Overway Discovery",
        description="Overway Discovery is a product discovery engine that uses AI to find products that match your search query.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Mount Query APIs (semantic search, read-only)
    for name, router in api.query_routers:
        if name == "feed":
            # Feed router needs to be at root level
            app.include_router(router, prefix="", tags=["feed"])
        elif name == "cache":
            # Cache router stays at /api/v1/cache
            app.include_router(router, prefix="/api/v1", tags=["cache"])
        else:
            app.include_router(
                router, 
                prefix="/api/v1/query",
                tags=[f"query-{name}"]
            )

    # Mount Admin APIs (CRUD operations) with authentication
    for name, router in api.admin_routers:
        app.include_router(
            router,
            prefix="/api/v1/admin", 
            tags=[f"admin-{name}"],
            dependencies=[Depends(api_key_auth_admin)]
        )

    # Mount Public APIs
    for name, router in api.public_routers:
        app.include_router(router, prefix="/api/v1", tags=[name])

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add metrics middleware to track API usage
    app.add_middleware(MetricsMiddleware)

    # Add detailed request/response logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = str(uuid.uuid4())
        print(f"[{request_id}] Incoming request: {request.method} {request.url}")
        logger.info(f"[{request_id}] {'='*60}")
        logger.info(f"[{request_id}] REQUEST START")
        logger.info(f"[{request_id}] Method: {request.method}")
        logger.info(f"[{request_id}] URL: {request.url}")

        # Log headers (filter sensitive ones in production)
        headers = dict(request.headers)
        # Remove sensitive headers in non-debug mode
        sensitive_headers = ["authorization", "cookie", "x-api-key"]
        for header in sensitive_headers:
            if header in headers:
                headers[header] = "[REDACTED]"
        logger.info(f"[{request_id}] Headers: {headers}")
        logger.info(f"[{request_id}] Query Params: {dict(request.query_params)}")

        # Log request body for POST/PUT/PATCH requests
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # Try to decode as JSON for better readability
                    try:
                        import json

                        body_json = json.loads(body.decode())
                        logger.info(
                            f"[{request_id}] Request Body: {json.dumps(body_json, indent=2)}"
                        )
                    except:
                        logger.info(f"[{request_id}] Request Body: {body.decode()}")
                else:
                    logger.info(f"[{request_id}] Request Body: (empty)")

                # Recreate the request body since we consumed it
                from starlette.requests import Request as StarletteRequest

                request._body = body
            except Exception as e:
                logger.warning(f"[{request_id}] Could not read request body: {e}")

        start_time = time.time()

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response details

            logger.info(f"[{request_id}] RESPONSE")
            logger.info(f"[{request_id}] Status Code: {response.status_code}")
            logger.info(f"[{request_id}] Response Headers: {dict(response.headers)}")
            logger.info(f"[{request_id}] Process Time: {process_time:.4f}s")

            # Log response body for error status codes or in debug mode
            if response.status_code >= 400:
                try:
                    # For streaming responses, we can't easily read the body
                    if hasattr(response, "body"):
                        response_body = response.body
                        if response_body:
                            try:
                                import json

                                body_json = json.loads(response_body.decode())
                                logger.info(
                                    f"[{request_id}] Response Body: {json.dumps(body_json, indent=2)}"
                                )
                            except:
                                logger.info(
                                    f"[{request_id}] Response Body: {response_body.decode()}"
                                )
                        else:
                            logger.info(f"[{request_id}] Response Body: (empty)")
                    else:
                        logger.info(
                            f"[{request_id}] Response Body: (streaming response)"
                        )
                except Exception as e:
                    logger.warning(f"[{request_id}] Could not read response body: {e}")

            logger.info(f"[{request_id}] REQUEST END")
            logger.info(f"[{request_id}] {'='*60}")

            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"[{request_id}] Request failed after {process_time:.4f}s: {str(e)}",
                exc_info=True,
            )
            logger.info(f"[{request_id}] REQUEST END (ERROR)")
            logger.info(f"[{request_id}] {'='*60}")
            raise  # Re-raise the exception so it's handled properly

    # Add request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint for load balancers and monitoring"""
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Helper function to filter routes by path prefix
    def filter_routes_by_prefix(routes, prefixes):
        """Filter routes that match any of the given prefixes"""
        filtered = []
        for route in routes:
            if hasattr(route, 'path'):
                # Check if route path starts with any of the prefixes
                if any(route.path.startswith(prefix) for prefix in prefixes):
                    filtered.append(route)
                # Also include root health check
                elif route.path in ["/health", "/openapi.yaml", "/openapi.json"]:
                    filtered.append(route)
        return filtered

    # OpenAPI specification endpoints - Full API
    @app.get("/openapi.yaml")
    async def get_openapi_yaml():
        """Serve full OpenAPI specification in YAML format"""
        from fastapi.openapi.utils import get_openapi
        from yaml import dump

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Convert to YAML
        yaml_content = dump(openapi_schema, default_flow_style=False, sort_keys=False)

        from fastapi.responses import Response

        return Response(content=yaml_content, media_type="application/x-yaml")

    @app.get("/openapi.json")
    async def get_openapi_json():
        """Serve full OpenAPI specification in JSON format"""
        from fastapi.openapi.utils import get_openapi
        import json

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Convert to JSON
        json_content = json.dumps(openapi_schema, indent=2)

        from fastapi.responses import Response

        return Response(content=json_content, media_type="application/json")

    # Query API OpenAPI specification
    @app.get("/api/v1/query/openapi.yaml")
    async def get_query_openapi_yaml():
        """Serve Query API OpenAPI specification in YAML format"""
        from fastapi.openapi.utils import get_openapi
        from yaml import dump

        # Filter routes for query APIs
        query_prefixes = ["/api/v1/query/", "/api/v1/cache", "/api/v1/health", "/feed"]
        filtered_routes = filter_routes_by_prefix(app.routes, query_prefixes)

        openapi_schema = get_openapi(
            title=f"{app.title} - Query API",
            version=app.version,
            description="Query and search endpoints for product discovery",
            routes=filtered_routes,
        )

        # Convert to YAML
        yaml_content = dump(openapi_schema, default_flow_style=False, sort_keys=False)

        from fastapi.responses import Response

        return Response(content=yaml_content, media_type="application/x-yaml")

    # Admin API OpenAPI specification
    @app.get("/api/v1/admin/openapi.yaml")
    async def get_admin_openapi_yaml():
        """Serve Admin API OpenAPI specification in YAML format"""
        from fastapi.openapi.utils import get_openapi
        from yaml import dump

        # Filter routes for admin APIs
        admin_prefixes = ["/api/v1/admin/", "/api/v1/health"]
        filtered_routes = filter_routes_by_prefix(app.routes, admin_prefixes)

        openapi_schema = get_openapi(
            title=f"{app.title} - Admin API",
            version=app.version,
            description="Administrative endpoints for managing organizations, brands, and products",
            routes=filtered_routes,
        )

        # Convert to YAML
        yaml_content = dump(openapi_schema, default_flow_style=False, sort_keys=False)

        from fastapi.responses import Response

        return Response(content=yaml_content, media_type="application/x-yaml")

    # Root route to serve brand-registry.json based on subdomain
    @app.get("/")
    async def get_brand_registry(request: Request):
        """Serve brand-registry.json based on subdomain"""
        from app.db.base import get_db_session
        from app.services.organization_service import OrganizationService
        from app.services.brand_service import BrandService
        
        # Extract subdomain from host header
        host = request.headers.get("host", "")
        subdomain = None
        
        # Parse subdomain from host (e.g., "brand.discovery.com" -> "brand")
        if host:
            # Remove port if present
            host_without_port = host.split(":")[0]
            parts = host_without_port.split(".")
            
            # For localhost development (e.g., "insight-editions.localhost")
            if len(parts) >= 2 and parts[-1] == "localhost":
                subdomain = parts[0]
            # For production domains (e.g., "brand.discovery.com")
            elif len(parts) > 2:  # At least subdomain.domain.tld
                subdomain = parts[0]
        
        if not subdomain:
            return JSONResponse(
                status_code=404,
                content={"error": "No subdomain found in request"}
            )
        
        # Get organization by subdomain
        db_gen = get_db_session()
        db = next(db_gen)
        try:
            org_service = OrganizationService(db)
            organization = org_service.get_by_subdomain(subdomain)
            
            if not organization:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Organization not found for subdomain: {subdomain}"}
                )
            
            # Get brand for the organization
            brand_service = BrandService(db)
            brand = brand_service.get_by_organization_id(organization.id)
            
            # Build brand-registry.json response
            brand_registry = {
                "@context": {
                    "schema": "https://schema.org",
                    "cmp": "https://schema.commercemesh.ai/ns#"
                },
                "@type": "Organization",
                "name": organization.name,
                "description": organization.description,
                "url": organization.url,
                "logo": organization.logo_url,
                "brand": {
                    "@type": "Brand",
                    "name": brand.name if brand else organization.name,
                    "logo": brand.logo_url if brand and brand.logo_url else organization.logo_url,
                    "identifier": {
                        "@type": "PropertyValue",
                        "propertyID": "cmp:brandId",
                        "value": brand.urn if brand else organization.urn
                    }
                } if brand else None,
                "sameAs": organization.social_links if organization.social_links else [],
                "cmp:category": [cat.slug for cat in organization.categories] if organization.categories else [],
                "cmp:links": [
                    {
                        "@type": "catalogue",
                        "url": f"https://{host}/feed/feed.json"
                    },
                    {
                        "@type": "api",
                        "url": f"https://{host}/api/v1/query/openapi.yaml"
                    },
                    {
                        "@type": "mcp",
                        "url": f"https://{host}/sse"
                    }
                ],
                "identifier": {
                    "@type": "PropertyValue",
                    "propertyID": "cmp:orgId",
                    "value": organization.urn
                }
            }
            
            return JSONResponse(content=brand_registry)
            
        finally:
            db.close()

    # ValueError handler (before global handler)
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.error(f"ValueError: {str(exc)}")
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )

    # Validation error handler for detailed logging
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        # Clean up the errors to remove non-serializable objects
        errors = []
        
        # Try to extract identifying information from the request body
        identifying_info = {}
        try:
            if exc.body and isinstance(exc.body, dict):
                # Extract top-level identifiers
                if "@id" in exc.body:
                    identifying_info["@id"] = exc.body["@id"]
                if "sku" in exc.body:
                    identifying_info["sku"] = exc.body["sku"]
                    
                # For ItemList requests, try to extract identifiers from items
                if exc.body.get("@type") == "ItemList" and "itemListElement" in exc.body:
                    items_info = []
                    for idx, item in enumerate(exc.body["itemListElement"]):
                        if isinstance(item, dict) and "item" in item:
                            item_data = item["item"]
                            if isinstance(item_data, dict):
                                item_info = {"position": item.get("position", idx + 1)}
                                if "@id" in item_data:
                                    item_info["@id"] = item_data["@id"]
                                if "sku" in item_data:
                                    item_info["sku"] = item_data["sku"]
                                if "name" in item_data:
                                    item_info["name"] = item_data["name"]
                                if "@type" in item_data:
                                    item_info["@type"] = item_data["@type"]
                                items_info.append(item_info)
                    if items_info:
                        identifying_info["items"] = items_info
        except Exception as e:
            logger.warning(f"Could not extract identifying info from request: {e}")
        
        for error in exc.errors():
            clean_error = {
                "type": error.get("type"),
                "loc": error.get("loc"),
                "msg": error.get("msg")
            }
            # Remove the ctx field which contains non-serializable ValueError objects
            if 'ctx' in error:
                if 'error' in error['ctx']:
                    # Convert the error to string
                    clean_error['ctx'] = {"error": str(error['ctx']['error'])}
            errors.append(clean_error)
        
        logger.error(f"Validation error: {errors}")
        logger.error(f"Request body identifiers: {identifying_info}")
        
        response_content = {
            "detail": "Validation error", 
            "errors": errors
        }
        
        if identifying_info:
            response_content["request_identifiers"] = identifying_info
            
        return JSONResponse(
            status_code=422,
            content=response_content,
        )

    @app.exception_handler(ValidationError)
    async def pydantic_validation_exception_handler(
        request: Request, exc: ValidationError
    ):
        # Clean up the errors to remove non-serializable objects
        errors = []
        for error in exc.errors():
            if isinstance(error, dict):
                clean_error = {
                    "type": error.get("type"),
                    "loc": error.get("loc"),
                    "msg": error.get("msg")
                }
                # Remove the ctx field which contains non-serializable ValueError objects
                if 'ctx' in error and isinstance(error['ctx'], dict):
                    if 'error' in error['ctx']:
                        # Convert the error to string
                        clean_error['ctx'] = {"error": str(error['ctx']['error'])}
            else:
                clean_error = {'msg': str(error)}
            errors.append(clean_error)
        
        logger.error(f"Pydantic validation error: {errors}")
        return JSONResponse(
            status_code=422,
            content={"detail": "Validation error", "errors": errors},
        )

    return app


# Create the app instance
app = create_app()
