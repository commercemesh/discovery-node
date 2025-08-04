"""Service for managing API keys."""
import secrets
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import logging
from sqlalchemy.orm import Session

from app.db.models.api_key import APIKey, APIKeyAuditLog
from app.schemas.api_key import (
    APIKeyCreate, APIKeyUpdate, APIKeyInDB, APIKeyResponse, 
    APIKeyAuditLogCreate, APIKeyAuditLogInDB
)

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service for API key management."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def generate_api_key(self, org_id: UUID, name: str, permissions: Optional[Dict[str, Any]] = None) -> APIKeyResponse:
        """
        Generate a new API key for an organization.
        
        Args:
            org_id: Organization UUID
            name: Human-readable name for the API key
            permissions: Optional permissions dict (defaults to admin read/write)
            
        Returns:
            APIKeyResponse with the raw key (only time it's visible)
        """
        # Generate a secure random API key
        raw_key = f"cmp_{secrets.token_urlsafe(32)}"
        
        # Hash the key for storage
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Create the API key record
        api_key = APIKey(
            organization_id=org_id,
            name=name,
            key_hash=key_hash,
            permissions=permissions or {"admin": ["read", "write"]},
            is_active=True
        )
        
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        
        logger.info(f"Generated API key '{name}' for organization {org_id}")
        
        # Return response with raw key
        return APIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key=raw_key,  # Only time we return the raw key
            permissions=api_key.permissions,
            created_at=api_key.created_at,
            expires_at=api_key.expires_at,
            is_active=api_key.is_active,
            organization_id=api_key.organization_id
        )
    
    def validate_api_key(self, raw_key: str) -> Optional[APIKeyInDB]:
        """
        Validate an API key and return its details if valid.
        
        Args:
            raw_key: The raw API key to validate
            
        Returns:
            APIKeyInDB if valid, None otherwise
        """
        # Hash the provided key
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Look up the key by hash
        api_key = self.db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key:
            return None
        
        # Check if expired
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            logger.warning(f"API key {api_key.id} has expired")
            return None
        
        # Update last used timestamp
        api_key.last_used_at = datetime.utcnow()
        self.db.commit()
        
        return APIKeyInDB.model_validate(api_key)
    
    def get_api_key(self, api_key_id: UUID) -> Optional[APIKeyInDB]:
        """Get API key by ID."""
        api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            return None
        return APIKeyInDB.model_validate(api_key)
    
    def list_api_keys(self, organization_id: UUID) -> List[APIKeyInDB]:
        """List all API keys for an organization."""
        api_keys = self.db.query(APIKey).filter(
            APIKey.organization_id == organization_id
        ).all()
        return [APIKeyInDB.model_validate(key) for key in api_keys]
    
    def update_api_key(self, api_key_id: UUID, update_data: APIKeyUpdate) -> Optional[APIKeyInDB]:
        """Update an API key."""
        api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(api_key, field, value)
        
        self.db.commit()
        self.db.refresh(api_key)
        
        return APIKeyInDB.model_validate(api_key)
    
    def delete_api_key(self, api_key_id: UUID) -> bool:
        """Delete an API key."""
        api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            return False
        
        self.db.delete(api_key)
        self.db.commit()
        
        logger.info(f"Deleted API key {api_key_id}")
        return True
    
    def deactivate_api_key(self, api_key_id: UUID) -> Optional[APIKeyInDB]:
        """Deactivate an API key without deleting it."""
        api_key = self.db.query(APIKey).filter(APIKey.id == api_key_id).first()
        if not api_key:
            return None
        
        api_key.is_active = False
        self.db.commit()
        self.db.refresh(api_key)
        
        logger.info(f"Deactivated API key {api_key_id}")
        return APIKeyInDB.model_validate(api_key)
    
    def log_api_key_usage(self, audit_log: APIKeyAuditLogCreate) -> APIKeyAuditLogInDB:
        """Log API key usage for auditing."""
        log_entry = APIKeyAuditLog(**audit_log.model_dump())
        
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        
        return APIKeyAuditLogInDB.model_validate(log_entry)
    
    def get_api_key_audit_logs(
        self, 
        api_key_id: UUID, 
        limit: int = 100,
        offset: int = 0
    ) -> List[APIKeyAuditLogInDB]:
        """Get audit logs for an API key."""
        logs = self.db.query(APIKeyAuditLog).filter(
            APIKeyAuditLog.api_key_id == api_key_id
        ).order_by(
            APIKeyAuditLog.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [APIKeyAuditLogInDB.model_validate(log) for log in logs]