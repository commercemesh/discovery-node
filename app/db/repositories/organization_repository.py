# app/db/repositories/organization_repository.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.organization import Organization
from app.db.models.category import Category
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
import re
import unicodedata


class OrganizationRepository:
    """Repository for CRUD operations on Organization model"""

    def __init__(self, db_session: Session):
        self.db_session = db_session
    
    def _generate_web_friendly_subdomain(self, name: str, exclude_id: Optional[UUID] = None) -> str:
        """
        Generate a web-friendly subdomain from organization name.
        
        Args:
            name: Organization name to convert
            exclude_id: Organization ID to exclude when checking uniqueness (for updates)
            
        Returns:
            Web-friendly subdomain that is unique and DNS-compliant
        """
        # First, normalize unicode characters
        subdomain = unicodedata.normalize('NFKD', name)
        subdomain = subdomain.encode('ascii', 'ignore').decode('ascii')
        
        # Convert to lowercase
        subdomain = subdomain.lower()
        
        # Replace spaces and special characters with hyphens
        subdomain = re.sub(r'[^a-z0-9]+', '-', subdomain)
        
        # Remove leading/trailing hyphens and collapse multiple hyphens
        subdomain = re.sub(r'-+', '-', subdomain)
        subdomain = subdomain.strip('-')
        
        # Ensure it starts with a letter or number (DNS requirement)
        if subdomain and not re.match(r'^[a-z0-9]', subdomain):
            subdomain = 'org-' + subdomain
        
        # Truncate to 63 characters (DNS label limit)
        subdomain = subdomain[:63]
        
        # Ensure it doesn't end with a hyphen after truncation
        subdomain = subdomain.rstrip('-')
        
        # If empty or invalid, use a default
        if not subdomain or not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$', subdomain):
            subdomain = 'org'
        
        # Ensure uniqueness
        counter = 0
        base_subdomain = subdomain
        while True:
            existing = self.get_by_subdomain(subdomain)
            if not existing or (exclude_id and existing.id == exclude_id):
                break
            counter += 1
            subdomain = f"{base_subdomain}-{counter}"
        
        return subdomain

    def get_by_id(self, org_id: UUID) -> Optional[Organization]:
        """Get organization by ID"""
        return (
            self.db_session.query(Organization)
            .filter(Organization.id == org_id)
            .first()
        )

    def get_by_urn(self, urn: str) -> Optional[Organization]:
        """Get organization by CMP URN"""
        return (
            self.db_session.query(Organization).filter(Organization.urn == urn).first()
        )

    def get_by_name(self, name: str) -> Optional[Organization]:
        """Get organization by name"""
        return (
            self.db_session.query(Organization)
            .filter(Organization.name == name)
            .first()
        )
    
    def get_by_subdomain(self, subdomain: str) -> Optional[Organization]:
        """Get organization by subdomain"""
        return (
            self.db_session.query(Organization)
            .filter(Organization.subdomain == subdomain)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 100) -> List[Organization]:
        """List organizations with pagination"""
        return self.db_session.query(Organization).offset(skip).limit(limit).all()

    def create(self, org_data: OrganizationCreate) -> Organization:
        """Create a new organization"""
        # Handle categories separately
        category_ids = org_data.category_ids or []

        # Create dict without category_ids for SQLAlchemy model
        org_dict = org_data.model_dump(exclude={"category_ids"})

        # Generate subdomain if not provided
        if not org_dict.get("subdomain") and org_dict.get("name"):
            org_dict["subdomain"] = self._generate_web_friendly_subdomain(org_dict["name"])

        # Create new Organization model instance
        db_org = Organization(**org_dict)

        # Add to session
        self.db_session.add(db_org)

        # Add categories if provided
        if category_ids:
            categories = (
                self.db_session.query(Category)
                .filter(Category.id.in_(category_ids))
                .all()
            )
            db_org.categories = categories

        # Commit changes
        self.db_session.commit()
        self.db_session.refresh(db_org)

        return db_org

    def update(
        self, org_id: UUID, org_data: OrganizationUpdate
    ) -> Optional[Organization]:
        """Update an existing organization"""
        db_org = self.get_by_id(org_id)

        if not db_org:
            return None

        # Handle categories separately
        category_ids = None
        if "category_ids" in org_data.model_dump(exclude_unset=True):
            category_ids = org_data.category_ids

        # Update model with data from Pydantic model (excluding category_ids)
        org_data_dict = org_data.model_dump(
            exclude={"category_ids"}, exclude_unset=True
        )
        
        # Generate subdomain if organization doesn't have one and name is being updated
        if not db_org.subdomain and ("name" in org_data_dict or db_org.name):
            # Use updated name if provided, otherwise use existing name
            name = org_data_dict.get("name", db_org.name)
            org_data_dict["subdomain"] = self._generate_web_friendly_subdomain(name, exclude_id=org_id)
        
        for key, value in org_data_dict.items():
            setattr(db_org, key, value)

        # Update categories if provided
        if category_ids is not None:
            categories = (
                self.db_session.query(Category)
                .filter(Category.id.in_(category_ids))
                .all()
            )
            db_org.categories = categories

        # Commit changes
        self.db_session.commit()
        self.db_session.refresh(db_org)

        return db_org

    def delete(self, org_id: UUID) -> bool:
        """Delete an organization by ID"""
        db_org = self.get_by_id(org_id)

        if not db_org:
            return False

        self.db_session.delete(db_org)
        self.db_session.commit()

        return True

    def list_by_category(
        self, category_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Organization]:
        """List organizations by category"""
        return (
            self.db_session.query(Organization)
            .join(Organization.categories)
            .filter(Category.id == category_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
