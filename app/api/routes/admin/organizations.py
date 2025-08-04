"""Admin API for organization management"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Union, List, Optional
from pydantic import BaseModel

from app.db.base import get_db_session
from app.services.organization_service import OrganizationService
from app.services.brand_service import BrandService
from app.schemas.organization import OrganizationUpdate
from app.schemas.brand import BrandCreate, BrandUpdate
from app.core.urn_generator import generate_brand_urn
from app.utils.formatters import format_organization_registry_response
from app.core.auth import get_current_organization_from_api_key

# Request models
class BrandData(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    logo: Optional[str] = None
    urn: Optional[str] = None

class OrganizationUpdateData(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    category: Optional[Union[List[str], str]] = None
    domain: Optional[str] = None
    brand: Optional[BrandData] = None

class NestedOrganizationUpdate(BaseModel):
    organization: OrganizationUpdateData

organizations_admin_router = APIRouter()

@organizations_admin_router.patch("/organizations/{org_urn}")
async def update_organization(
    org_urn: str,
    data: NestedOrganizationUpdate,
    authenticated_org_id: str = Depends(get_current_organization_from_api_key),
    db: Session = Depends(get_db_session)
):
    """
    Update an existing organization (requires authentication)
    
    Only the organization that owns the API key can update itself.
    """
    org_service = OrganizationService(db)
    brand_service = BrandService(db)
    
    try:
        # Get existing organization
        existing_org = org_service.organization_repo.get_by_urn(org_urn)
        if not existing_org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        # Verify the authenticated org matches the org being updated
        if str(existing_org.id) != authenticated_org_id:
            raise HTTPException(
                status_code=403, 
                detail="You can only update your own organization"
            )
        
        # Extract organization data
        org_data = data.organization
        
        # Build update dict with only provided fields
        update_dict = {}
        
        if org_data.name is not None:
            update_dict["name"] = org_data.name
        if org_data.url is not None:
            update_dict["url"] = org_data.url
        if org_data.logo is not None:
            update_dict["logo_url"] = org_data.logo
        if org_data.description is not None:
            update_dict["description"] = org_data.description
        if org_data.domain is not None:
            update_dict["domain"] = org_data.domain
        
        # Handle category - ensure it's always a list
        if org_data.category is not None:
            category_list = None
            if isinstance(org_data.category, list):
                category_list = org_data.category
            else:
                # Convert string to list
                category_str = str(org_data.category)
                # Handle PostgreSQL array format
                if category_str.startswith('{') and category_str.endswith('}'):
                    category_str = category_str[1:-1]
                category_list = [cat.strip() for cat in category_str.split(',') if cat.strip()]
            
            if category_list:
                update_dict["raw_data"] = {"category": category_list}
        
        # Update organization if there are changes
        if update_dict:
            org_update = OrganizationUpdate(**update_dict)
            organization = org_service.update_organization(existing_org.id, org_update)
        else:
            organization = existing_org
        
        # Handle brand update if provided
        if org_data.brand and any(v is not None for v in [org_data.brand.name, org_data.brand.logo]):
            # Generate brand URN if not provided
            brand_urn = org_data.brand.urn if org_data.brand.urn else generate_brand_urn(
                org_data.brand.name or "default", existing_org.urn
            )
            
            existing_brand = brand_service.get_by_urn(brand_urn)
            
            if existing_brand:
                # Update existing brand
                brand_update_dict = {}
                if org_data.brand.name is not None:
                    brand_update_dict["name"] = org_data.brand.name
                if org_data.brand.logo is not None:
                    brand_update_dict["logo_url"] = org_data.brand.logo
                
                if brand_update_dict:
                    brand_update = BrandUpdate(**brand_update_dict)
                    brand = brand_service.update_brand(existing_brand.id, brand_update)
            else:
                # Create new brand for this organization
                brand_create = BrandCreate(
                    name=org_data.brand.name or "Default Brand",
                    logo_url=org_data.brand.logo,
                    urn=brand_urn,
                    organization_id=organization.id
                )
                brand = brand_service.create_brand(brand_create)
        
        # Get the actual database model with brands relationship
        db_organization = org_service.organization_repo.get_by_id(organization.id)
        
        # Format using CMP brand-registry format
        formatted_response = format_organization_registry_response(db_organization)
        
        # Add the brand URL from request data since it's not stored in DB
        if "brand" in formatted_response and org_data.brand and org_data.brand.url:
            formatted_response["brand"]["url"] = org_data.brand.url
        
        return formatted_response
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating organization: {error_details}")
        raise HTTPException(status_code=500, detail=str(e))

@organizations_admin_router.delete("/organizations/{org_urn}")
async def delete_organization(
    org_urn: str,
    authenticated_org_id: str = Depends(get_current_organization_from_api_key),
    db: Session = Depends(get_db_session)
):
    """
    Delete an organization (requires authentication)
    
    Only the organization that owns the API key can delete itself.
    """
    org_service = OrganizationService(db)
    
    # Get existing organization
    existing_org = org_service.organization_repo.get_by_urn(org_urn)
    if not existing_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Verify the authenticated org matches the org being deleted
    if str(existing_org.id) != authenticated_org_id:
        raise HTTPException(
            status_code=403, 
            detail="You can only delete your own organization"
        )
    
    # Delete the organization (cascade will handle related records)
    org_service.delete_organization(existing_org.id)
    
    return {"message": "Organization deleted successfully", "urn": org_urn}