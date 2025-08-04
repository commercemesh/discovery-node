"""Middleware for collecting API usage metrics."""
import time
import json
import asyncio
import uuid
from typing import Callable, Optional, Dict, Any
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.services.metrics_service import MetricsService
from app.core.dependencies import get_organization_context, get_db


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect and log API usage metrics."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.metrics_service = MetricsService()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        # Skip metrics for non-API endpoints
        if not self._should_track_endpoint(request.url.path):
            return await call_next(request)
        
        # Generate request ID if not present
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        
        # Start timing
        start_time = time.time()
        
        # Store request body for size calculation
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                request_body = await request.body()
                # Recreate request with body since we consumed it
                from starlette.datastructures import Headers
                from starlette.requests import Request as StarletteRequest
                
                async def receive():
                    return {"type": "http.request", "body": request_body}
                
                request = StarletteRequest(
                    request.scope,
                    receive=receive,
                    send=request._send
                )
            except:
                pass
        
        # Process request
        response = await call_next(request)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Collect response body for size calculation
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Create new response with the collected body
        response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
        
        # Extract route pattern from matched route
        route_pattern = None
        if hasattr(request, "scope") and "route" in request.scope:
            route = request.scope["route"]
            if hasattr(route, "path"):
                route_pattern = route.path
        
        # Build metrics
        metrics = self._build_metrics(
            request=request,
            response=response,
            request_body=request_body,
            response_body=response_body,
            request_id=request_id
        )
        
        # Get organization and API key info from request state
        organization_id = None
        api_key_id = None
        if hasattr(request.state, "organization_id"):
            organization_id = request.state.organization_id
        if hasattr(request.state, "api_key") and request.state.api_key:
            api_key_id = request.state.api_key.id
        
        # If no organization_id from auth, try to extract from subdomain/header
        if not organization_id:
            try:
                # Create a simple DB session for the dependency
                db = next(get_db())
                try:
                    organization_id = await get_organization_context(request, db)
                finally:
                    db.close()
            except Exception:
                # If organization context fails (e.g., not in multi-tenant mode), that's ok
                pass
        
        # Extract query params
        query_params = dict(request.query_params) if request.query_params else None
        
        # Log metrics asynchronously (fire and forget)
        asyncio.create_task(
            self.metrics_service.log_api_usage(
                request_id=uuid.UUID(request_id) if isinstance(request_id, str) else request_id,
                response_time_ms=response_time_ms,
                method=request.method,
                path=str(request.url.path),
                host=request.headers.get("host") or str(request.url.hostname),
                route_pattern=MetricsService.extract_route_pattern(str(request.url.path), route_pattern),
                query_params=query_params,
                status_code=response.status_code,
                organization_id=organization_id,
                api_key_id=api_key_id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
                metrics=metrics
            )
        )
        
        return response
    
    def _should_track_endpoint(self, path: str) -> bool:
        """Determine if endpoint should be tracked."""
        # Track all API endpoints
        if path.startswith("/api/"):
            return True
        
        # Track root path (brand registry)
        if path == "/":
            return True
        
        # Skip static files, health checks, etc.
        skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/openapi.yaml",
            "/favicon.ico",
            "/static/",
            "/_health",
        ]
        
        for skip_path in skip_paths:
            if path.startswith(skip_path):
                return False
        
        return False
    
    def _build_metrics(
        self,
        request: Request,
        response: Response,
        request_body: Optional[bytes],
        response_body: bytes,
        request_id: str
    ) -> Dict[str, Any]:
        """Build metrics dictionary."""
        metrics = {
            "request_id": request_id,
            "api_version": "v1",  # Extract from path if needed
            "host": request.headers.get("host", ""),
        }
        
        # Add request/response sizes
        if request_body:
            metrics["request_size_bytes"] = len(request_body)
        metrics["response_size_bytes"] = len(response_body)
        
        # Add referer if present
        if "referer" in request.headers:
            metrics["referer"] = request.headers["referer"]
        
        # Add custom headers
        custom_headers = MetricsService.parse_custom_headers(dict(request.headers))
        if custom_headers:
            metrics["custom_headers"] = custom_headers
        
        # Add tags based on path
        tags = []
        path = str(request.url.path)
        
        if "/admin/" in path:
            tags.append("admin")
        if "/query/" in path:
            tags.append("query")
        if "/public/" in path or not ("/admin/" in path or "/query/" in path):
            tags.append("public")
        
        # Add operation type
        if request.method == "GET":
            if path.endswith("/") or "?" in str(request.url):
                tags.append("list")
            else:
                tags.append("read")
        elif request.method == "POST":
            tags.append("create")
        elif request.method in ["PUT", "PATCH"]:
            tags.append("update")
        elif request.method == "DELETE":
            tags.append("delete")
        
        # Add resource type
        if "/products" in path:
            tags.append("products")
        elif "/organizations" in path:
            tags.append("organizations")
        elif "/search" in path or "/query" in path:
            tags.append("search")
        
        metrics["tags"] = tags
        
        # Add error info if applicable
        if response.status_code >= 400:
            try:
                error_body = json.loads(response_body)
                if "detail" in error_body:
                    metrics["error_message"] = str(error_body["detail"])[:500]
                if "errors" in error_body:
                    metrics["error_type"] = "ValidationError"
            except:
                pass
        
        # Parse response for item counts (for list/bulk endpoints)
        try:
            if response.status_code == 200 and response_body:
                response_json = json.loads(response_body)
                
                # For list endpoints
                if "itemListElement" in response_json:
                    metrics["items_returned"] = len(response_json["itemListElement"])
                elif "results" in response_json:
                    metrics["items_returned"] = len(response_json["results"])
                
                # For bulk create/update endpoints
                if "summary" in response_json:
                    summary = response_json["summary"]
                    if "products_created" in summary:
                        metrics["items_created"] = summary.get("products_created", 0) + summary.get("product_groups_created", 0)
                    if "products_updated" in summary:
                        metrics["items_updated"] = summary.get("products_updated", 0) + summary.get("product_groups_updated", 0)
                    if "total_errors" in summary:
                        metrics["items_failed"] = summary["total_errors"]
        except:
            pass
        
        return metrics