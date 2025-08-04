from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Union
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.db.base import get_db_session
from app.services.organization_service import OrganizationService
from app.services.brand_service import BrandService
from app.schemas.organization import OrganizationCreate as OrganizationSchema
from app.schemas.brand import BrandCreate
from app.core.urn_generator import generate_urn_from_url, generate_brand_urn, generate_org_urn
from app.utils.formatters import format_organization_registry_response
from app.services.api_key_service import APIKeyService

# Request models
class BrandData(BaseModel):
    name: str
    url: str
    logo: Optional[str] = None
    urn: Optional[str] = None  # Optional, will be generated if not provided

class OrganizationData(BaseModel):
    name: str
    url: str
    logo: Optional[str] = None
    description: Optional[str] = None
    category: Optional[Union[List[str], str]] = None
    urn: Optional[str] = None  # Optional, will be generated if not provided
    domain: Optional[str] = None  # Custom domain configured by seller
    brand: BrandData

class NestedOrganizationCreate(BaseModel):
    organization: OrganizationData
    session: Optional[dict] = None

organization_router = APIRouter()

@organization_router.post("/organizations")
async def create_organization(
    data: NestedOrganizationCreate,
    db: Session = Depends(get_db_session)
):
    """Create a new organization with brand information"""
    org_service = OrganizationService(db)
    brand_service = BrandService(db)
    
    try:
        # Extract organization data
        org_data = data.organization
        
        # Handle category - ensure it's always a list
        category_list = None
        if org_data.category:
            if isinstance(org_data.category, list):
                category_list = org_data.category
            else:
                # Convert string to list (handle comma-separated or single value)
                category_str = str(org_data.category)
                # Handle PostgreSQL array format like "{books,gifts}"
                if category_str.startswith('{') and category_str.endswith('}'):
                    category_str = category_str[1:-1]
                # Split by comma and clean up
                category_list = [cat.strip() for cat in category_str.split(',') if cat.strip()]
        
        # Generate URNs if not provided
        # Use organization URL domain for consistent URN generation
        org_urn = org_data.urn if org_data.urn else generate_org_urn(org_data.url)
        brand_urn = org_data.brand.urn if org_data.brand.urn else generate_brand_urn(org_data.brand.name, org_urn)
        
        # Check if organization with this URN already exists
        existing_org = org_service.get_organization_by_urn(org_urn)
        
        if existing_org:
            # Update existing organization
            from app.schemas.organization import OrganizationUpdate
            org_update = OrganizationUpdate(
                name=org_data.name,
                url=org_data.url,
                logo_url=org_data.logo,
                description=org_data.description,
                domain=org_data.domain,
                raw_data={"category": category_list} if category_list else None
            )
            organization = org_service.update_organization(existing_org.id, org_update)
        else:
            # Create new organization
            org_create = OrganizationSchema(
                name=org_data.name,
                url=org_data.url,
                logo_url=org_data.logo,
                description=org_data.description,
                domain=org_data.domain,
                urn=org_urn,
                raw_data={"category": category_list} if category_list else None
            )
            organization = org_service.create(org_create)
        
        # Handle brand creation/update
        existing_brand = brand_service.get_by_urn(brand_urn)
        
        if existing_brand:
            # Update existing brand
            from app.schemas.brand import BrandUpdate
            brand_update = BrandUpdate(
                name=org_data.brand.name,
                logo_url=org_data.brand.logo
            )
            brand = brand_service.update_brand(existing_brand.id, brand_update)
        else:
            # Create new brand
            brand_create = BrandCreate(
                name=org_data.brand.name,
                logo_url=org_data.brand.logo,
                urn=brand_urn,
                organization_id=organization.id
            )
            brand = brand_service.create_brand(brand_create)
        
        # Generate API key for the organization
        api_key_service = APIKeyService(db)
        api_key_response = api_key_service.generate_api_key(
            org_id=organization.id,
            name=f"{organization.name} Admin API Key",
            permissions={"admin": ["read", "write"]}
        )
        
        # Get the actual database model with brands relationship
        db_organization = org_service.organization_repo.get_by_id(organization.id)
        
        # Format using CMP brand-registry format
        formatted_response = format_organization_registry_response(db_organization)
        
        # Add the brand URL from request data since it's not stored in DB
        if "brand" in formatted_response and org_data.brand.url:
            formatted_response["brand"]["url"] = org_data.brand.url
        
        # Add API key to the cmp:services structure
        if "cmp:services" in formatted_response and "cmp:adminAPI" in formatted_response["cmp:services"]:
            formatted_response["cmp:services"]["cmp:adminAPI"]["cmp:authentication"] = {
                "@type": "PropertyValue",
                "name": "API Key Authentication",
                "description": "Use Bearer token in Authorization header",
                "cmp:keys": [
                    {
                        "@type": "cmp:APIKey",
                        "name": api_key_response.name,
                        "key": api_key_response.key,  # Only shown once!
                        "permissions": api_key_response.permissions,
                        "expiresAt": api_key_response.expires_at.isoformat() if api_key_response.expires_at else None
                    }
                ]
            }
        
        # Return the formatted response directly
        return formatted_response
        
    except Exception as e:
        import traceback
        error_details = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating organization: {error_details}")
        raise HTTPException(status_code=500, detail=str(e))

@organization_router.get("/organizations/{org_urn}")
async def get_organization(
    org_urn: str,
    db: Session = Depends(get_db_session)
):
    """Get organization by URN"""
    org_service = OrganizationService(db)
    
    # Get the actual database model instead of the Pydantic schema
    organization = org_service.organization_repo.get_by_urn(org_urn)
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Format using CMP brand-registry format
    formatted_response = format_organization_registry_response(organization)
    
    # Add the brand URL as org URL since it's not stored in DB
    if "brand" in formatted_response and organization.url:
        formatted_response["brand"]["url"] = organization.url
    
    # Return the formatted response directly
    return formatted_response