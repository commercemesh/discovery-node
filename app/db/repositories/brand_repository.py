# app/db/repositories/brand_repository.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.brand import Brand
from app.db.models.category import Category
from app.schemas.brand import BrandCreate, BrandUpdate


class BrandRepository:
    """Repository for CRUD operations on Brand model"""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_by_id(self, brand_id: UUID) -> Optional[Brand]:
        """Get brand by ID"""
        return self.db_session.query(Brand).filter(Brand.id == brand_id).first()

    def get_by_urn(self, urn: str) -> Optional[Brand]:
        """Get brand by CMP URN"""
        return self.db_session.query(Brand).filter(Brand.urn == urn).first()

    def get_by_name_and_org(self, name: str, organization_id: UUID) -> Optional[Brand]:
        """Get brand by name and organization ID"""
        return (
            self.db_session.query(Brand)
            .filter(Brand.name == name, Brand.organization_id == organization_id)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 100, organization_id: Optional[UUID] = None) -> List[Brand]:
        """List brands with pagination, optionally filtered by organization"""
        query = self.db_session.query(Brand)
        if organization_id:
            query = query.filter(Brand.organization_id == organization_id)
        return query.offset(skip).limit(limit).all()

    def list_by_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Brand]:
        """List brands by organization"""
        return (
            self.db_session.query(Brand)
            .filter(Brand.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, brand_data: BrandCreate) -> Brand:
        """Create a new brand"""
        # Handle categories separately
        category_ids = brand_data.category_ids or []

        # Create dict without category_ids for SQLAlchemy model
        brand_dict = brand_data.model_dump(exclude={"category_ids"})

        # Create new Brand model instance
        db_brand = Brand(**brand_dict)

        # Add to session
        self.db_session.add(db_brand)

        # Add categories if provided
        if category_ids:
            categories = (
                self.db_session.query(Category)
                .filter(Category.id.in_(category_ids))
                .all()
            )
            db_brand.categories = categories

        # Commit changes
        self.db_session.commit()
        self.db_session.refresh(db_brand)

        return db_brand

    def update(self, brand_id: UUID, brand_data: BrandUpdate) -> Optional[Brand]:
        """Update an existing brand"""
        db_brand = self.get_by_id(brand_id)

        if not db_brand:
            return None

        # Handle categories separately
        category_ids = None
        if "category_ids" in brand_data.model_dump(exclude_unset=True):
            category_ids = brand_data.category_ids

        # Update model with data from Pydantic model (excluding category_ids)
        brand_data_dict = brand_data.model_dump(
            exclude={"category_ids"}, exclude_unset=True
        )
        for key, value in brand_data_dict.items():
            setattr(db_brand, key, value)

        # Update categories if provided
        if category_ids is not None:
            categories = (
                self.db_session.query(Category)
                .filter(Category.id.in_(category_ids))
                .all()
            )
            db_brand.categories = categories

        # Commit changes
        self.db_session.commit()
        self.db_session.refresh(db_brand)

        return db_brand

    def delete(self, brand_id: UUID) -> bool:
        """Delete a brand by ID"""
        db_brand = self.get_by_id(brand_id)

        if not db_brand:
            return False

        self.db_session.delete(db_brand)
        self.db_session.commit()

        return True

    def list_by_category(
        self, category_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Brand]:
        """List brands by category"""
        return (
            self.db_session.query(Brand)
            .join(Brand.categories)
            .filter(Category.id == category_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
