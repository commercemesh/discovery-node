# app/services/product_service.py
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from app.db.repositories.product_repository import ProductRepository
from app.services.category_service import CategoryService
from app.services.product_group_service import ProductGroupService
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductInDB,
    PropertyValueBase,
)
from app.db.models.brand import Brand

logger = logging.getLogger(__name__)


class ProductService:
    """Service for product-related business logic"""

    def __init__(self, db_session):
        self.db_session = db_session
        self.product_repo = ProductRepository(db_session)
        self.category_service = CategoryService(db_session)
        self.product_group_service = ProductGroupService(db_session)

    def get_product(self, product_id: UUID) -> Optional[ProductInDB]:
        """Get product by ID"""
        product = self.product_repo.get_by_id(product_id)
        if not product:
            return None
        return ProductInDB.model_validate(product)

    def get_by_urn(self, urn: str) -> Optional[ProductInDB]:
        """Get product by URN"""
        product = self.product_repo.get_by_urn(urn)
        if not product:
            return None
        return ProductInDB.model_validate(product)

    def get_by_sku(
        self, sku: str, brand_id: Optional[UUID] = None
    ) -> Optional[ProductInDB]:
        """Get product by SKU, optionally filtered by brand"""
        product = self.product_repo.get_by_sku(sku, brand_id)
        if not product:
            return None
        return ProductInDB.model_validate(product)

    def list_products(self, skip: int = 0, limit: int = 100) -> List[ProductInDB]:
        """List products with pagination"""
        products = self.product_repo.list(skip, limit)
        return [ProductInDB.model_validate(p) for p in products]

    def list_by_product_group(
        self, product_group_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ProductInDB]:
        """List products by product group"""
        products = self.product_repo.list_by_product_group(
            product_group_id, skip, limit
        )
        return [ProductInDB.model_validate(p) for p in products]

    def search_products(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[ProductInDB]:
        """Search products by name or description"""
        products = self.product_repo.search(query, skip, limit)
        return [ProductInDB.model_validate(p) for p in products]

    def create_product(self, product_data: ProductCreate) -> ProductInDB:
        """Create a new product"""
        # Business logic validation
        existing = self.product_repo.get_by_urn(product_data.urn)
        if existing:
            logger.warning(f"Product with URN {product_data.urn} already exists")
            # Could raise an exception here, or update the existing product

        # Create the product
        product = self.product_repo.create(product_data)
        return ProductInDB.model_validate(product)

    def update_product(
        self, product_id: UUID, product_data: ProductUpdate
    ) -> Optional[ProductInDB]:
        """Update an existing product"""
        # Business logic validation
        if product_data.urn:
            existing = self.product_repo.get_by_urn(product_data.urn)
            if existing and existing.id != product_id:
                logger.warning(
                    f"Another product with URN {product_data.urn} already exists"
                )
                # Could raise an exception here

        # Update the product
        product = self.product_repo.update(product_id, product_data)
        if not product:
            return None
        return ProductInDB.model_validate(product)

    def delete_product(self, product_id: UUID) -> bool:
        """Delete a product by ID"""
        return self.product_repo.delete(product_id)

    def process_product(
        self, product_data: Dict[str, Any], brand_id: UUID, category_name: str
    ) -> UUID:
        """
        Process product data from the CMP product feed.
        Creates or updates the product in the database.
        Returns the product ID.
        """
        # Extract URN
        urn = product_data.get("@id", "")

        if not urn:
            logger.error("Product data missing required @id field")
            raise ValueError("Product data missing required @id field")

        # Check if product already exists
        product_id = None
        existing_product = self.product_repo.get_by_urn(urn)
        if existing_product:
            product_id = existing_product.id

        # Extract SKU
        sku = product_data.get("sku", "")

        # Extract description
        description = product_data.get("description", "")

        # Process product group reference
        product_group_id = None
        product_group = None
        if "isVariantOf" in product_data and "@id" in product_data["isVariantOf"]:
            product_group_urn = product_data["isVariantOf"]["@id"]
            product_group = self.product_group_service.get_by_urn(product_group_urn)
            if product_group:
                product_group_id = product_group.id
            else:
                logger.warning(
                    f"Product {urn} references non-existent product group {product_group_urn}"
                )


        if not product_group_id:
            logger.error(f"Product {urn} missing required product group reference")
            raise ValueError(f"Product {urn} missing required product group reference")

        # Pull description from product group if not present in product
        if not description and product_group and product_group.description:
            description = product_group.description
            logger.info(f"Using description from product group for product {urn}")

        # Process additional properties
        additional_properties = []
        variant_attributes = {}
        if "additionalProperty" in product_data:
            props = product_data["additionalProperty"]
            if not isinstance(props, list):
                props = [props]

            for prop in props:
                if "@type" in prop and "name" in prop and "value" in prop:
                    name = prop["name"]
                    value = prop["value"]
                    additional_properties.append(
                        PropertyValueBase(name=name, value=value)
                    )
                    variant_attributes[name] = value

        # Category resolution (always required)
        category = self.category_service.get_or_create_by_name(category_name)
        category_id = category.id

        # Fetch organization_id from brand
        brand = self.db_session.query(Brand).filter(Brand.id == brand_id).first()
        if not brand:
            logger.error(f"Brand with id {brand_id} not found for product {urn}")
            raise ValueError(f"Brand with id {brand_id} not found for product {urn}")
        organization_id = brand.organization_id

        # Create product data
        product_create_data = ProductCreate(
            name=product_data.get("name", ""),
            url=product_data.get("url", ""),
            sku=sku,
            description=description,
            product_group_id=product_group_id,
            brand_id=brand_id,
            urn=urn,
            variant_attributes=variant_attributes,
            raw_data=product_data,
            additional_properties=additional_properties,
            category_id=category_id,
            organization_id=organization_id,
        )

        # Create or update the product
        if product_id:
            product_update = ProductUpdate(**product_create_data.model_dump())
            updated_product = self.product_repo.update(product_id, product_update)
            product_id = updated_product.id
        else:
            new_product = self.product_repo.create(product_create_data)
            product_id = new_product.id

        # Process offers if present
        if "offers" in product_data:
            # Import locally to avoid circular imports
            from app.services.offer_service import OfferService

            # Get the organization ID from the brand for the seller
            brand = self.db_session.query(Brand).filter(Brand.id == brand_id).first()
            if not brand:
                logger.error(f"Brand with ID {brand_id} not found")
                raise ValueError(f"Brand with ID {brand_id} not found")

            seller_id = brand.organization_id

            # Initialize offer service
            offer_service = OfferService(self.db_session)

            # Process the offer
            offer_service.process_offer(product_data["offers"], product_id, seller_id)

        return product_id

    def filter_products(
        self, filters: Dict[str, Any], skip: int = 0, limit: int = 100
    ) -> List[ProductInDB]:
        """Filter products by various criteria"""
        products = self.product_repo.list_by_filter(filters, skip, limit)
        return [ProductInDB.model_validate(p) for p in products]

    def _slugify(self, text: str) -> str:
        """
        Convert a string to a slug format.
        For example: "Electronics & Computers" -> "electronics-computers"
        """
        # Very basic implementation - for production, use a proper slugify library
        return text.lower().replace(" ", "-").replace("&", "").replace("_", "-")
