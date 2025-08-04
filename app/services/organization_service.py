# app/services/organization_service.py
from typing import List, Optional, Dict, Any
from uuid import UUID
import json
from app.db.repositories.organization_repository import OrganizationRepository
from app.services.category_service import CategoryService
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationInDB,
)


class OrganizationService:
    """Service for organization-related business logic"""

    def __init__(self, db_session):
        self.organization_repo = OrganizationRepository(db_session)
        self.category_service = CategoryService(db_session)

    def get_organization(self, org_id: UUID) -> Optional[OrganizationInDB]:
        """Get organization by ID"""
        org = self.organization_repo.get_by_id(org_id)
        if not org:
            return None
        return OrganizationInDB.model_validate(org)

    def get_organization_by_urn(self, urn: str) -> Optional[OrganizationInDB]:
        """Get organization by URN"""
        org = self.organization_repo.get_by_urn(urn)
        if not org:
            return None
        return OrganizationInDB.model_validate(org)
    
    def get_by_subdomain(self, subdomain: str) -> Optional[OrganizationInDB]:
        """Get organization by subdomain"""
        org = self.organization_repo.get_by_subdomain(subdomain)
        if not org:
            return None
        return OrganizationInDB.model_validate(org)

    def list_organizations(
        self, skip: int = 0, limit: int = 100
    ) -> List[OrganizationInDB]:
        """List organizations with pagination"""
        orgs = self.organization_repo.list(skip, limit)
        return [OrganizationInDB.model_validate(org) for org in orgs]
    
    def get_by_urn(self, urn: str) -> Optional[OrganizationInDB]:
        """Get organization by URN (alias for get_organization_by_urn)"""
        return self.get_organization_by_urn(urn)
    
    def create(self, org_data: OrganizationCreate) -> OrganizationInDB:
        """Create a new organization (alias for create_organization)"""
        return self.create_organization(org_data)

    def create_organization(self, org_data: OrganizationCreate) -> OrganizationInDB:
        """Create a new organization"""
        # Additional business logic/validation could go here
        org = self.organization_repo.create(org_data)
        return OrganizationInDB.model_validate(org)

    def update_organization(
        self, org_id: UUID, org_data: OrganizationUpdate
    ) -> Optional[OrganizationInDB]:
        """Update an existing organization"""
        org = self.organization_repo.update(org_id, org_data)
        if not org:
            return None
        return OrganizationInDB.model_validate(org)

    def delete_organization(self, org_id: UUID) -> bool:
        """Delete an organization by ID"""
        return self.organization_repo.delete(org_id)

    def process_organization(self, org_data: Dict[str, Any]) -> UUID:
        """
        Process organization data from the CMP brand registry.
        Creates or updates the organization in the database.
        Returns the organization ID.
        """
        # Extract org ID from the identifier
        org_id = None
        if "identifier" in org_data and "value" in org_data["identifier"]:
            urn = org_data["identifier"]["value"]
            existing_org = self.organization_repo.get_by_urn(urn)
            if existing_org:
                org_id = existing_org.id

        # Prepare organization data
        social_links = org_data.get("sameAs", [])
        if isinstance(social_links, str):
            try:
                social_links = json.loads(social_links)
            except json.JSONDecodeError:
                social_links = [social_links]

        # Process categories
        category_ids = []
        if "cmp:category" in org_data and org_data["cmp:category"]:
            category_slugs = org_data["cmp:category"]
            category_ids = self.category_service.get_or_create_categories(
                category_slugs
            )

        # Create the organization data object
        org_create_data = OrganizationCreate(
            name=org_data.get("name", ""),
            description=org_data.get("description", ""),
            url=org_data.get("url", ""),
            logo_url=org_data.get("logo", ""),
            urn=org_data.get("identifier", {}).get("value", ""),
            social_links=social_links,
            feed_url=org_data.get("cmp:productFeed", {}).get("url", ""),
            raw_data=org_data,  # Store the full JSON for reference
            category_ids=category_ids,
        )

        # Create or update the organization
        if org_id:
            org_update = OrganizationUpdate(**org_create_data.model_dump())
            updated_org = self.organization_repo.update(org_id, org_update)
            return updated_org.id
        else:
            new_org = self.organization_repo.create(org_create_data)
            return new_org.id

    def list_by_category(
        self, category_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[OrganizationInDB]:
        """List organizations by category"""
        orgs = self.organization_repo.list_by_category(category_id, skip, limit)
        return [OrganizationInDB.model_validate(org) for org in orgs]
