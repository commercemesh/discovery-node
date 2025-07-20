# app/db/repositories/product_repository.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from sqlalchemy.dialects.postgresql import insert
from app.db.models.product import Product
from app.db.models.category import Category
from app.schemas.product import ProductCreate, ProductUpdate, ProductForVector
from sqlalchemy.orm import selectinload


class ProductRepository:
    """Repository for CRUD operations on Product model"""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_by_id(self, product_id: UUID) -> Optional[Product]:
        """Get product by ID"""
        return self.db_session.query(Product).filter(Product.id == product_id).first()

    def get_by_urn(self, urn: str) -> Optional[Product]:
        """Get product by CMP URN"""
        return self.db_session.query(Product).filter(Product.urn == urn).first()

    def get_by_sku(self, sku: str, brand_id: UUID = None) -> Optional[Product]:
        """Get product by SKU, optionally filtered by brand"""
        query = self.db_session.query(Product).filter(Product.sku == sku)
        if brand_id:
            query = query.filter(Product.brand_id == brand_id)
        return query.first()

    def list(self, skip: int = 0, limit: int = 100) -> List[Product]:
        """List products with pagination"""
        return self.db_session.query(Product).offset(skip).limit(limit).all()

    def list_by_product_group(
        self, product_group_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """List products by product group"""
        return (
            self.db_session.query(Product)
            .filter(Product.product_group_id == product_group_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_brand(
        self, brand_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """List products by brand"""
        return (
            self.db_session.query(Product)
            .filter(Product.brand_id == brand_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """List products by organization"""
        return (
            self.db_session.query(Product)
            .filter(Product.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search(self, query: str, skip: int = 0, limit: int = 100) -> List[Product]:
        """Search products by name or description"""
        search_term = f"%{query}%"
        return (
            self.db_session.query(Product)
            .filter(
                or_(
                    Product.name.ilike(search_term),
                    Product.description.ilike(search_term),
                    Product.sku.ilike(search_term),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, product_data: ProductCreate) -> Product:
        """Create a new product"""
        # Handle offers data
        offers_data = None
        if product_data.offers:
            offers_data = product_data.offers.model_dump()
        # Handle additional properties
        variant_attributes = product_data.variant_attributes or {}
        if product_data.additional_properties:
            for prop in product_data.additional_properties:
                variant_attributes[prop.name] = prop.value
        # Create dict for SQLAlchemy model
        product_dict = product_data.model_dump(
            exclude={"offers", "additional_properties", "category"}
        )
        # Add offers data if present
        if offers_data:
            product_dict["price"] = offers_data.get("price")
            product_dict["price_currency"] = offers_data.get("price_currency")
            product_dict["availability"] = offers_data.get("availability")
            product_dict["inventory_level"] = offers_data.get("inventory_level")
            product_dict["price_valid_until"] = offers_data.get("price_valid_until")
        # Update variant attributes
        product_dict["variant_attributes"] = variant_attributes
        # Create new Product model instance
        db_product = Product(**product_dict)
        # Add to session
        self.db_session.add(db_product)
        self.db_session.commit()
        self.db_session.refresh(db_product)
        return db_product

    def update(
        self, product_id: UUID, product_data: ProductUpdate
    ) -> Optional[Product]:
        """Update an existing product"""
        db_product = self.get_by_id(product_id)
        if not db_product:
            return None
        # Handle offers data
        offers_data = None
        if product_data.offers:
            offers_data = product_data.offers.model_dump(exclude_unset=True)
        # Handle additional properties
        variant_attributes = None
        if "variant_attributes" in product_data.model_dump(exclude_unset=True):
            variant_attributes = product_data.variant_attributes or {}
        if product_data.additional_properties:
            if variant_attributes is None:
                variant_attributes = (
                    db_product.variant_attributes.copy()
                    if db_product.variant_attributes
                    else {}
                )
            for prop in product_data.additional_properties:
                variant_attributes[prop.name] = prop.value
        # Update model with data from Pydantic model
        product_data_dict = product_data.model_dump(
            exclude={"offers", "additional_properties", "variant_attributes"},
            exclude_unset=True,
        )
        for key, value in product_data_dict.items():
            setattr(db_product, key, value)
        # Update variant attributes if provided
        if variant_attributes is not None:
            db_product.variant_attributes = variant_attributes
        # Add offers data if present
        if offers_data:
            if "price" in offers_data:
                db_product.price = offers_data["price"]
            if "price_currency" in offers_data:
                db_product.price_currency = offers_data["price_currency"]
            if "availability" in offers_data:
                db_product.availability = offers_data["availability"]
            if "inventory_level" in offers_data:
                db_product.inventory_level = offers_data["inventory_level"]
            if "price_valid_until" in offers_data:
                db_product.price_valid_until = offers_data["price_valid_until"]
        self.db_session.commit()
        self.db_session.refresh(db_product)
        return db_product

    def delete(self, product_id: UUID) -> bool:
        """Delete a product by ID"""
        db_product = self.get_by_id(product_id)

        if not db_product:
            return False

        self.db_session.delete(db_product)
        self.db_session.commit()

        return True

    def list_by_category_id(
        self, category_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """List products by category ID (using category_id column)"""
        return (
            self.db_session.query(Product)
            .filter(Product.category_id == category_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_filter(
        self, filters: Dict[str, Any], skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """
        List products with flexible filtering.

        Filters can include:
        - price_min: Minimum price
        - price_max: Maximum price
        - brand_id: Brand ID
        - availability: Availability status
        - variant_attributes: Dict of variant attributes to match
        """
        query = self.db_session.query(Product)

        if "price_min" in filters and filters["price_min"] is not None:
            query = query.filter(Product.price >= filters["price_min"])

        if "price_max" in filters and filters["price_max"] is not None:
            query = query.filter(Product.price <= filters["price_max"])

        if "brand_id" in filters and filters["brand_id"] is not None:
            query = query.filter(Product.brand_id == filters["brand_id"])

        if "availability" in filters and filters["availability"] is not None:
            query = query.filter(Product.availability == filters["availability"])

        if "variant_attributes" in filters and filters["variant_attributes"]:
            for attr_name, attr_value in filters["variant_attributes"].items():
                # This uses JSONB containment operator @> for Postgres
                query = query.filter(
                    Product.variant_attributes.contains({attr_name: attr_value})
                )

        return query.offset(skip).limit(limit).all()

    def get_products_with_relations_for_org(self, offset: int, limit: int, org_id: UUID):
        """Get products with all vector-needed data in one query"""
        return (
            self.db_session.query(Product)
            .options(
                selectinload(Product.brand),
                selectinload(Product.product_group),
                selectinload(Product.category),
                selectinload(Product.offers),
            )
            .filter(Product.organization_id == org_id)
            .order_by(Product.id)  # IMPORTANT: Consistent ordering for pagination
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_products_for_vector(
        self, offset: int, limit: int, org_id: UUID
    ) -> List[ProductForVector]:
        """Get products formatted specifically for vector processing"""
        products = self.get_products_with_relations_for_org(offset, limit, org_id)
        return [
            ProductForVector.from_product_with_relations(product)
            for product in products
        ]

    def get_products_with_relations(self, product_ids: List[UUID]) -> List[Product]:
        """Get products by IDs"""
        return (
            self.db_session.query(Product)
            .options(
                selectinload(Product.brand),
                selectinload(Product.product_group),
                selectinload(Product.category),
                selectinload(Product.offers),
            )
            .filter(Product.id.in_(product_ids))
            .all()
        )
    
    def get_products_by_urns(self, urns: List[str]) -> List[Product]:
        """Get multiple products by their URNs with relations"""
        return (
            self.db_session.query(Product)
            .options(
                selectinload(Product.brand),
                selectinload(Product.category),
                selectinload(Product.offers),
                selectinload(Product.product_group),
            )
            .filter(Product.urn.in_(urns))
            .all()
        )

    def bulk_upsert(self, products: List[ProductCreate], batch_size: int = 1000) -> List[Product]:
        """
        Bulk upsert (insert or update) products using SQLAlchemy's bulk operations.
        Processes in batches to handle large datasets efficiently.
        Returns list of upserted Product objects.
        """
        from sqlalchemy.dialects.postgresql import insert
        import logging
        
        logger = logging.getLogger(__name__)
        upserted_products = []
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            
            try:
                # Prepare data with deduplication
                mappings = []
                seen_urns = set()
                
                for product_data in batch:
                    # Check for duplicate URNs within this batch
                    urn = product_data.urn
                    if urn in seen_urns:
                        logger.warning(f"Duplicate URN '{urn}' found in batch, skipping duplicate")
                        continue
                    seen_urns.add(urn)
                    
                    # Handle offers data
                    offers_data = None
                    if product_data.offers:
                        offers_data = product_data.offers.model_dump()
                    
                    # Handle additional properties
                    variant_attributes = product_data.variant_attributes or {}
                    if product_data.additional_properties:
                        for prop in product_data.additional_properties:
                            variant_attributes[prop.name] = prop.value
                    
                    # Create dict for bulk operation
                    product_dict = product_data.model_dump(
                        exclude={"offers", "additional_properties", "category"}
                    )
                    
                    # Note: Offers data (price, availability, etc.) is handled separately
                    # through the Offer model and should not be added to the Product record
                    
                    # Update variant attributes
                    product_dict["variant_attributes"] = variant_attributes
                    
                    mappings.append(product_dict)
                
                # Skip if no valid mappings (all were duplicates)
                if not mappings:
                    logger.warning(f"All products in batch {i} were duplicates, skipping batch")
                    continue
                
                # Create insert statement with ON CONFLICT
                stmt = insert(Product).values(mappings)
                
                # Define which columns to update on conflict
                # Note: price-related fields are handled separately through the Offer model
                update_dict = {
                    'name': stmt.excluded.name,
                    'url': stmt.excluded.url,
                    'sku': stmt.excluded.sku,
                    'description': stmt.excluded.description,
                    'product_group_id': stmt.excluded.product_group_id,
                    'brand_id': stmt.excluded.brand_id,
                    'category_id': stmt.excluded.category_id,
                    'organization_id': stmt.excluded.organization_id,
                    'variant_attributes': stmt.excluded.variant_attributes,
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
                upserted = self.db_session.query(Product).filter(
                    Product.urn.in_(urns)
                ).all()
                upserted_products.extend(upserted)
                
            except Exception as e:
                logger.error(f"Error in bulk_upsert batch {i}: {str(e)}")
                self.db_session.rollback()
                raise
        
        self.db_session.commit()
        return upserted_products
