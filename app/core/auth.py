"""Authentication middleware for API key authentication."""
from typing import Optional, List
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from sqlalchemy.orm import Session
import logging

from app.db.base import get_db_session
from app.services.api_key_service import APIKeyService
from app.schemas.api_key import APIKeyInDB, APIKeyAuditLogCreate

logger = logging.getLogger(__name__)


class APIKeyAuth(HTTPBearer):
    """API key authentication using Bearer token scheme."""
    
    def __init__(self, permissions: Optional[List[str]] = None, auto_error: bool = True):
        """
        Initialize API key authentication.
        
        Args:
            permissions: Required permissions (e.g., ["admin:read", "admin:write"])
            auto_error: Whether to automatically raise HTTPException on failure
        """
        super().__init__(auto_error=auto_error)
        self.required_permissions = permissions or []
    
    async def __call__(
        self, 
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
        db: Session = Depends(get_db_session)
    ) -> APIKeyInDB:
        """
        Validate API key and check permissions.
        
        Args:
            request: FastAPI request object
            credentials: Bearer token credentials
            db: Database session
            
        Returns:
            APIKeyInDB object if authentication succeeds
            
        Raises:
            HTTPException: If authentication fails
        """
        # Extract the API key from Bearer token
        api_key = credentials.credentials
        
        # Validate the API key
        api_key_service = APIKeyService(db)
        api_key_data = api_key_service.validate_api_key(api_key)
        
        if not api_key_data:
            # Log failed authentication attempt
            logger.warning(f"Invalid API key attempted from {request.client.host}")
            
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Check permissions if required
        if self.required_permissions:
            if not self._check_permissions(api_key_data.permissions, self.required_permissions):
                # Log permission failure
                api_key_service.log_api_key_usage(APIKeyAuditLogCreate(
                    api_key_id=api_key_data.id,
                    action="permission_denied",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("User-Agent"),
                    request_path=str(request.url.path),
                    response_status=403
                ))
                
                raise HTTPException(
                    status_code=HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {self.required_permissions}"
                )
        
        # Log successful authentication
        api_key_service.log_api_key_usage(APIKeyAuditLogCreate(
            api_key_id=api_key_data.id,
            action="authenticated",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            request_path=str(request.url.path),
            response_status=200
        ))
        
        # Store API key data in request state for later use
        request.state.api_key = api_key_data
        request.state.organization_id = api_key_data.organization_id
        
        return api_key_data
    
    def _check_permissions(self, user_permissions: dict, required_permissions: List[str]) -> bool:
        """
        Check if user has required permissions.
        
        Permission format: "resource:action" (e.g., "admin:read", "admin:write")
        
        Args:
            user_permissions: User's permissions dict
            required_permissions: List of required permissions
            
        Returns:
            True if user has all required permissions
        """
        for required in required_permissions:
            if ":" in required:
                resource, action = required.split(":", 1)
                if resource not in user_permissions:
                    return False
                if action not in user_permissions[resource]:
                    return False
            else:
                # Simple permission check
                if required not in user_permissions:
                    return False
        
        return True


# Pre-configured auth dependencies for common use cases
api_key_auth_read = APIKeyAuth(permissions=["admin:read"])
api_key_auth_write = APIKeyAuth(permissions=["admin:write"])
api_key_auth_admin = APIKeyAuth(permissions=["admin:read", "admin:write"])


def get_current_organization_from_api_key(
    request: Request,
    api_key: APIKeyInDB = Depends(api_key_auth_read)
) -> str:
    """
    Get the current organization ID from the authenticated API key.
    
    This is a dependency that can be used in routes to get the organization context.
    """
    return str(api_key.organization_id)