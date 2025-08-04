from contextlib import contextmanager
from typing import Optional, Annotated
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.db.base import SessionLocal, get_db_session
from app.services.search.factory import SearchServiceFactory as SearchFactory
from app.services.product_service import ProductService
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.vector_repository import VectorRepository
from app.db.repositories.organization_repository import OrganizationRepository

logger = get_logger(__name__)

@contextmanager
def get_db_session():
    """Create a database session with proper cleanup"""
    db_session = SessionLocal()
    try:
        yield db_session
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()

def get_db():
    """FastAPI dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# For MCP server, we need to create services per request to avoid stale sessions
class SearchServiceFactory:
    """Factory for creating SearchService instances with fresh DB sessions"""
    
    def create(self):
        """Create a new SearchService instance with a fresh DB session"""
        db_session = SessionLocal()
        return SearchFactory.create(db_session)
    
    def create_with_cleanup(self):
        """Create SearchService with automatic session cleanup"""
        with get_db_session() as db_session:
            yield SearchFactory.create(db_session)

class ProductServiceFactory:
    """Factory for creating ProductService instances with fresh DB sessions"""
    
    def create(self) -> ProductService:
        """Create a new ProductService instance with a fresh DB session"""
        db_session = SessionLocal()
        return ProductService(db_session=db_session)
    
    def create_with_cleanup(self):
        """Create ProductService with automatic session cleanup"""
        with get_db_session() as db_session:
            yield ProductService(db_session=db_session)

# Keep the original functions for backward compatibility
def get_search_service():
    """Get search service instance with DB session"""
    factory = SearchServiceFactory()
    return factory.create()

def get_product_service() -> ProductService:
    """Get product service instance with dependencies"""
    factory = ProductServiceFactory()
    return factory.create()


async def get_organization_context(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[UUID]:
    """
    Extract organization context from request.
    
    First checks if API key authentication has set organization_id in request state.
    
    Otherwise, in multi-tenant mode:
    - Extract subdomain from Host header
    - Look up organization by subdomain
    - Return organization_id
    
    In single-tenant mode:
    - Return configured DEFAULT_ORGANIZATION_ID
    - If not configured, return None (no filtering)
    """
    # Check if organization_id was set by API key authentication
    if hasattr(request.state, 'organization_id'):
        return request.state.organization_id
    if not settings.MULTI_TENANT_MODE:
        # Single-tenant mode
        if settings.DEFAULT_ORGANIZATION_ID:
            return UUID(settings.DEFAULT_ORGANIZATION_ID)
        return None
    
    # Multi-tenant mode - extract subdomain from Host header or X-Organization header
    
    # First check for X-Organization header (for proxied requests)
    org_header = request.headers.get("x-organization", "")
    if org_header:
        subdomain = org_header.lower()
        logger.info(f"Using organization from X-Organization header: {subdomain}")
    else:
        # Fall back to Host header
        host = request.headers.get("host", "")
        
        if not host:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Host header is required in multi-tenant mode"
            )
        
        # Extract subdomain (first part before first dot)
        # Handle cases like: subdomain.overway.net, subdomain.overway.net:8000
        host_parts = host.split(':')[0].split('.')  # Remove port if present
        
        if len(host_parts) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid host format - subdomain required"
            )
        
        subdomain = host_parts[0].lower()
    
    # Look up organization by subdomain
    org_repo = OrganizationRepository(db)
    organization = org_repo.get_by_subdomain(subdomain)
    
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization not found for subdomain: {subdomain}"
        )
    
    logger.info(f"Organization context resolved: {organization.name} (ID: {organization.id})")
    return organization.id


# Type alias for dependency injection
OrganizationId = Annotated[Optional[UUID], Depends(get_organization_context)]