# app/services/brand_service.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from app.db.repositories.brand_repository import BrandRepository
from app.services.category_service import CategoryService
from app.schemas.brand import BrandCreate, BrandUpdate, BrandInDB
from app.services.organization_service import OrganizationService
import logging

logger = logging.getLogger(__name__)


class BrandService:
    """Service for brand-related business logic"""

    def __init__(self, db_session):
        self.brand_repo = BrandRepository(db_session)
        self.category_service = CategoryService(db_session)
        self.organization_service = OrganizationService(db_session)

    def get_brand(self, brand_id: UUID) -> Optional[BrandInDB]:
        """Get brand by ID"""
        brand = self.brand_repo.get_by_id(brand_id)
        if not brand:
            return None
        return BrandInDB.model_validate(brand)

    def get_by_urn(self, urn: str) -> Optional[BrandInDB]:
        """Get brand by URN"""
        brand = self.brand_repo.get_by_urn(urn)
        if not brand:
            return None
        return BrandInDB.model_validate(brand)

    def get_by_name(self, name: str) -> Optional[BrandInDB]:
        """Get brand by name (searches across all organizations)"""
        # Search across all brands for the given name
        brands = self.brand_repo.list(
            0, 1000
        )  # Get all brands (adjust limit as needed)
        for brand in brands:
            if brand.name == name:
                return BrandInDB.model_validate(brand)
        return None

    def get_or_create_by_name(self, brand_name: str, organization_id: UUID = None):
        """
        Get or create a brand by name. If brand doesn't exist, creates it.
        Returns the BrandInDB object.
        """
        brand = self.get_by_name(brand_name)
        if not brand:
            # Create the brand if it doesn't exist
            # Note: We need organization_id to create a brand
            if not organization_id:
                logger.warning(f"Cannot create brand '{brand_name}' without organization_id")
                return None
            
            brand_create_data = BrandCreate(
                name=brand_name,
                organization_id=organization_id,
                urn=f"urn:cmp:brand:{brand_name.lower().replace(' ', '-')}"
            )
            brand = self.create_brand(brand_create_data)
            logger.info(f"Created new brand '{brand_name}' with ID {brand.id}")
        
        return brand

    def get_or_create_by_urn(self, brand_data: Dict[str, Any], org_urn: str = None):
        """
        Get or create a brand from feed data using the identifier.value.
        Returns the BrandInDB object.
        """
        # Extract brand identifier from feed data
        identifier = brand_data.get('identifier', {}).get('value')
        brand_name = brand_data.get('name')
        
        if not identifier:
            logger.warning(f"Brand data missing identifier.value: {brand_data}")
            return None
            
        # Try to find existing brand by identifier
        brand = self.brand_repo.get_by_urn(identifier)
        
        if not brand:
            # Create the brand if it doesn't exist
            if not org_urn:
                logger.warning(f"Cannot create brand '{brand_name}' without org_urn")
                return None
            
            logger.debug(f"Looking up organization by URN: {org_urn}")
            organization = self.organization_service.get_organization_by_urn(org_urn)
            if not organization:
                # Let's check what organizations exist in the database
                all_orgs = self.organization_service.list_organizations(0, 1000)
                logger.warning(f"Cannot create brand '{brand_name}' without organization. URN: {org_urn}")
                logger.warning(f"Available organizations: {[org.urn for org in all_orgs]}")
                return None
          
            
            brand_create_data = BrandCreate(
                name=brand_name,
                organization_id=organization.id,
                urn=identifier,
                logo_url=brand_data.get('logo', ''),
                raw_data=brand_data
            )
            brand = self.create_brand(brand_create_data)
            logger.info(f"Created new brand '{brand_name}' with ID {brand.id} from feed data")
        else:
            logger.debug(f"Found existing brand '{brand_name}' with ID {brand.id}")
        
        return brand

    def list_brands(self, skip: int = 0, limit: int = 100) -> List[BrandInDB]:
        """List brands with pagination"""
        brands = self.brand_repo.list(skip, limit)
        return [BrandInDB.model_validate(brand) for brand in brands]

    def list_by_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[BrandInDB]:
        """List brands by organization"""
        brands = self.brand_repo.list_by_organization(organization_id, skip, limit)
        return [BrandInDB.model_validate(brand) for brand in brands]

    def create_brand(self, brand_data: BrandCreate) -> BrandInDB:
        """Create a new brand"""
        # Additional business logic/validation could go here
        brand = self.brand_repo.create(brand_data)
        return BrandInDB.model_validate(brand)

    def update_brand(
        self, brand_id: UUID, brand_data: BrandUpdate
    ) -> Optional[BrandInDB]:
        """Update an existing brand"""
        brand = self.brand_repo.update(brand_id, brand_data)
        if not brand:
            return None
        return BrandInDB.model_validate(brand)

    def delete_brand(self, brand_id: UUID) -> bool:
        """Delete a brand by ID"""
        return self.brand_repo.delete(brand_id)

    def process_brand(self, brand_data: Dict[str, Any], organization_id: UUID) -> UUID:
        """
        Process brand data from the CMP brand registry.
        Creates or updates the brand in the database.
        Returns the brand ID.
        """
        # Extract brand ID from the identifier
        brand_id = None
        brand_urn = None
        if "identifier" in brand_data and "value" in brand_data["identifier"]:
            brand_urn = brand_data["identifier"]["value"]
            existing_brand = self.brand_repo.get_by_urn(brand_urn)
            if existing_brand:
                brand_id = existing_brand.id

        # Process categories if included
        category_ids = []
        if "cmp:category" in brand_data and brand_data["cmp:category"]:
            category_slugs = brand_data["cmp:category"]
            category_ids = self.category_service.get_or_create_categories(
                category_slugs
            )

        # Prepare brand data
        brand_create_data = BrandCreate(
            name=brand_data.get("name", ""),
            logo_url=brand_data.get("logo", ""),
            urn=brand_urn,
            organization_id=organization_id,
            raw_data=brand_data,  # Store the full JSON for reference
            category_ids=category_ids,
        )

        # Create or update the brand
        if brand_id:
            brand_update = BrandUpdate(**brand_create_data.model_dump())
            updated_brand = self.brand_repo.update(brand_id, brand_update)
            return updated_brand.id
        else:
            new_brand = self.brand_repo.create(brand_create_data)
            return new_brand.id

    def list_by_category(
        self, category_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[BrandInDB]:
        """List brands by category"""
        brands = self.brand_repo.list_by_category(category_id, skip, limit)
        return [BrandInDB.model_validate(brand) for brand in brands]
