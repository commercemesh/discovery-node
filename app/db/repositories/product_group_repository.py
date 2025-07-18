# app/db/repositories/product_group_repository.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func
from app.db.models.product_group import ProductGroup
from app.db.models.category import Category
from app.schemas.product_group import ProductGroupCreate, ProductGroupUpdate


class ProductGroupRepository:
    """Repository for CRUD operations on ProductGroup model"""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_by_id(self, product_group_id: UUID) -> Optional[ProductGroup]:
        """Get product group by ID"""
        return (
            self.db_session.query(ProductGroup)
            .filter(ProductGroup.id == product_group_id)
            .first()
        )

    def get_by_urn(self, urn: str) -> Optional[ProductGroup]:
        """Get product group by CMP URN"""
        return (
            self.db_session.query(ProductGroup).filter(ProductGroup.urn == urn).first()
        )

    def get_by_product_group_id(self, product_group_id: str) -> Optional[ProductGroup]:
        """Get product group by external product group ID"""
        return (
            self.db_session.query(ProductGroup)
            .filter(ProductGroup.product_group_id == product_group_id)
            .first()
        )

    def list(self, skip: int = 0, limit: int = 100) -> List[ProductGroup]:
        """List product groups with pagination"""
        return self.db_session.query(ProductGroup).offset(skip).limit(limit).all()

    def list_by_brand(
        self, brand_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ProductGroup]:
        """List product groups by brand"""
        return (
            self.db_session.query(ProductGroup)
            .filter(ProductGroup.brand_id == brand_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_category(
        self, category: str, skip: int = 0, limit: int = 100
    ) -> List[ProductGroup]:
        """List product groups by category string"""
        return (
            self.db_session.query(ProductGroup)
            .filter(ProductGroup.category == category)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ProductGroup]:
        """List product groups by organization"""
        return (
            self.db_session.query(ProductGroup)
            .filter(ProductGroup.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, product_group_data: ProductGroupCreate) -> ProductGroup:
        """Create a new product group"""
        # No more category_ids or association table logic needed
        product_group_dict = product_group_data.model_dump(exclude={"category"})
        db_product_group = ProductGroup(**product_group_dict)
        self.db_session.add(db_product_group)
        self.db_session.commit()
        self.db_session.refresh(db_product_group)
        return db_product_group

    def update(
        self, product_group_id: UUID, product_group_data: ProductGroupUpdate
    ) -> Optional[ProductGroup]:
        """Update an existing product group"""
        db_product_group = self.get_by_id(product_group_id)
        if not db_product_group:
            return None
        product_group_data_dict = product_group_data.model_dump(
            exclude_unset=True, exclude={"category"}
        )
        for key, value in product_group_data_dict.items():
            setattr(db_product_group, key, value)
        self.db_session.commit()
        self.db_session.refresh(db_product_group)
        return db_product_group

    def delete(self, product_group_id: UUID) -> bool:
        """Delete a product group by ID"""
        db_product_group = self.get_by_id(product_group_id)

        if not db_product_group:
            return False

        self.db_session.delete(db_product_group)
        self.db_session.commit()

        return True

    def list_by_category_id(
        self, category_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ProductGroup]:
        """List product groups by category ID (using category_id column)"""
        return (
            self.db_session.query(ProductGroup)
            .filter(ProductGroup.category_id == category_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def bulk_upsert(self, product_groups: List[ProductGroupCreate], batch_size: int = 1000) -> List[ProductGroup]:
        """
        Bulk upsert (insert or update) product groups using SQLAlchemy's bulk_save_objects.
        Processes in batches to handle large datasets efficiently.
        Returns list of upserted ProductGroup objects.
        """
        from sqlalchemy.dialects.postgresql import insert
        import logging
        
        logger = logging.getLogger(__name__)
        upserted_groups = []
        
        for i in range(0, len(product_groups), batch_size):
            batch = product_groups[i:i + batch_size]
            
            try:
                # Prepare data with deduplication - exclude "category" since it's not a direct field in the model
                mappings = []
                seen_urns = set()
                
                for pg in batch:
                    # Check for duplicate URNs within this batch
                    urn = pg.urn
                    if urn in seen_urns:
                        logger.warning(f"Duplicate URN '{urn}' found in batch, skipping duplicate")
                        continue
                    seen_urns.add(urn)
                    
                    mappings.append(pg.model_dump(exclude={"category"}))
                
                # Skip if no valid mappings (all were duplicates)
                if not mappings:
                    logger.warning(f"All product groups in batch {i} were duplicates, skipping batch")
                    continue
                
                # Create insert statement with ON CONFLICT
                stmt = insert(ProductGroup).values(mappings)
                
                # Define which columns to update on conflict
                # Note: 'category' is excluded from mappings, so we shouldn't try to update it
                update_dict = {
                    'name': stmt.excluded.name,
                    'description': stmt.excluded.description,
                    'url': stmt.excluded.url,
                    'product_group_id': stmt.excluded.product_group_id,
                    'varies_by': stmt.excluded.varies_by,
                    'brand_id': stmt.excluded.brand_id,
                    'category_id': stmt.excluded.category_id,
                    'organization_id': stmt.excluded.organization_id,
                    'raw_data': stmt.excluded.raw_data,
                    'updated_at': func.now(),
                }
                
                # Execute upsert
                stmt = stmt.on_conflict_do_update(
                    index_elements=['urn'],
                    set_=update_dict
                )
                
                self.db_session.execute(stmt)
                self.db_session.flush()
                
                # Fetch upserted records
                urns = [m['urn'] for m in mappings]
                upserted = self.db_session.query(ProductGroup).filter(
                    ProductGroup.urn.in_(urns)
                ).all()
                upserted_groups.extend(upserted)
                
            except Exception as e:
                logger.error(f"Error in bulk_upsert batch {i}: {str(e)}")
                self.db_session.rollback()
                raise
        
        self.db_session.commit()
        return upserted_groups
