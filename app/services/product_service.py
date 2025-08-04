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
from app.schemas.offer import OfferCreate
from app.db.models.brand import Brand
from app.core.urn_generator import generate_brand_urn

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

    def get_product_with_details_by_urn(self, urn: str, organization_id: Optional[UUID] = None) -> Optional[Dict[str, Any]]:
        """
        Search for URN in both products and product groups tables.
        If found as product: return ONLY the product
        If found as product group: return product group and all linked products
        
        In multi-tenant mode, verifies the product belongs to the organization.
        """
        # First try to find as a product
        product = self.product_repo.get_by_urn(urn)
        if product:
            # In multi-tenant mode, verify the product belongs to the organization
            if organization_id and product.organization_id != organization_id:
                return None
            
            # Found as product - return ONLY the product (no product group)
            # Get brand
            from app.services.brand_service import BrandService
            brand_service = BrandService(self.db_session)
            brand = brand_service.get_brand(product.brand_id)
            
            # Get category
            category = None
            if product.category_id:
                category = self.category_service.get_category(product.category_id)
            
            # Get offers
            from app.services.offer_service import OfferService
            offer_service = OfferService(self.db_session)
            offers = offer_service.list_by_product(product.id)
            
            return {
                "type": "product",
                "product": ProductInDB.model_validate(product),
                "brand": brand,
                "category": category,
                "offers": offers
            }
        
        # Then try to find as a product group
        product_group = self.product_group_service.get_by_urn(urn)
        if product_group:
            # In multi-tenant mode, verify the product group belongs to the organization
            if organization_id and product_group.organization_id != organization_id:
                return None
            
            # Found as product group - get all linked products
            from app.db.repositories.product_repository import ProductRepository
            product_repo = ProductRepository(self.db_session)
            linked_products = product_repo.list_by_product_group(product_group.id)
            
            # Get brand
            from app.services.brand_service import BrandService
            brand_service = BrandService(self.db_session)
            brand = brand_service.get_brand(product_group.brand_id)
            
            # Get category
            category = None
            if product_group.category_id:
                category = self.category_service.get_category(product_group.category_id)
            
            # Get offers for all linked products
            from app.services.offer_service import OfferService
            offer_service = OfferService(self.db_session)
            all_offers = []
            for product in linked_products:
                offers = offer_service.list_by_product(product.id)
                all_offers.extend(offers)
            
            return {
                "type": "product_group", 
                "product_group": product_group,
                "linked_products": [ProductInDB.model_validate(p) for p in linked_products],
                "brand": brand,
                "category": category,
                "offers": all_offers
            }
        
        # Not found in either table
        return None

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
    
    def list_products_by_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ProductInDB]:
        """List products by organization with pagination"""
        products = self.product_repo.list_by_organization(organization_id, skip, limit)
        return [ProductInDB.model_validate(p) for p in products]
    
    def count_products_by_organization(self, organization_id: UUID) -> int:
        """Count total products for an organization"""
        return self.product_repo.count_by_organization(organization_id)

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
            logger.warning(f"Product with URN {product_data.urn} already exists, returning existing product")
            return ProductInDB.model_validate(existing)

        # Create the product
        product = self.product_repo.create(product_data)
        return ProductInDB.model_validate(product)
    
    def create_product_from_jsonld(self, jsonld_data: Dict[str, Any], organization_id: UUID) -> ProductInDB:
        """
        Create a product from JSON-LD data, handling brand and category creation
        
        This method handles:
        - Brand creation/lookup (using provided URN or generating one)
        - Category creation/lookup
        - Product group reference resolution
        - URN generation if not provided
        """
        from app.services.brand_service import BrandService
        from app.services.organization_service import OrganizationService
        from app.core.urn_generator import generate_brand_urn, generate_sku_urn
        
        # Get organization for URN generation
        org_service = OrganizationService(self.db_session)
        organization = org_service.get_organization(organization_id)
        
        # Handle brand
        brand_id = None
        brand_data = jsonld_data.get("brand")
        if brand_data and isinstance(brand_data, dict):
            brand_service = BrandService(self.db_session)
            
            # Extract brand URN from identifier if provided
            brand_urn = None
            if "identifier" in brand_data and isinstance(brand_data["identifier"], dict):
                brand_urn = brand_data["identifier"].get("value")
            
            # Generate URN if not provided
            if not brand_urn:
                brand_urn = generate_brand_urn(brand_data.get("name", ""), organization.urn)
            
            # Check if brand exists
            existing_brand = brand_service.get_by_urn(brand_urn)
            if existing_brand:
                brand_id = existing_brand.id
            else:
                # Create brand
                from app.schemas.brand import BrandCreate
                brand_create = BrandCreate(
                    name=brand_data.get("name", ""),
                    urn=brand_urn,
                    organization_id=organization_id
                )
                new_brand = brand_service.create_brand(brand_create)
                brand_id = new_brand.id
        else:
            # No brand provided - use organization as default brand
            brand_service = BrandService(self.db_session)
            default_brand_name = organization.name
            brand_urn = generate_brand_urn(default_brand_name, organization.urn)
            
            existing_brand = brand_service.get_by_urn(brand_urn)
            if existing_brand:
                brand_id = existing_brand.id
            else:
                from app.schemas.brand import BrandCreate
                brand_create = BrandCreate(
                    name=default_brand_name,
                    urn=brand_urn,
                    organization_id=organization_id
                )
                new_brand = brand_service.create_brand(brand_create)
                brand_id = new_brand.id
        
        # Handle category
        category_name = jsonld_data.get("category", "uncategorized")
        category = self.category_service.get_or_create_by_name(category_name)
        
        # Handle product group reference
        product_group_id = None
        variant_of = jsonld_data.get("isVariantOf")
        if variant_of and isinstance(variant_of, dict) and "@id" in variant_of:
            pg = self.product_group_service.get_by_urn(variant_of["@id"])
            if pg:
                product_group_id = pg.id
            else:
                logger.warning(f"Product group {variant_of['@id']} not found")
        
        # Generate URN if not provided
        product_urn = jsonld_data.get("@id")
        if not product_urn:
            sku = jsonld_data.get("sku", "")
            product_urn = generate_sku_urn(sku, organization.urn, brand_urn)
            jsonld_data["@id"] = product_urn
        
        # Parse JSON-LD to ProductCreate schema
        from app.utils import formatters
        product_create = formatters.parse_jsonld_to_product_create(
            jsonld_data,
            organization_id,
            brand_id,
            category.id,
            product_group_id
        )
        
        # Create the product
        return self.create_product(product_create)

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


        # Pull description from product group if not present in product and product group exists
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
            # Use the create_product method which handles duplicate checking
            new_product = self.create_product(product_create_data)
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

            organization_id = brand.organization_id

            # Initialize offer service
            offer_service = OfferService(self.db_session)

            # Process the offer
            offer_service.process_offer(product_data["offers"], product_id, organization_id)

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

    def bulk_process_products(
        self, products_data: List[Dict[str, Any]], brand_id: UUID, category_name: str, batch_size: int = 1000
    ) -> List[ProductInDB]:
        """
        Bulk process products from CMP product feed.
        Returns list of created/updated products.
        """
        product_creates = []
        
        # Get brand for organization_id
        brand = self.db_session.query(Brand).filter(Brand.id == brand_id).first()
        if not brand:
            raise ValueError(f"Brand with id {brand_id} not found")
        organization_id = brand.organization_id
        
        # Get category
        category = self.category_service.get_or_create_by_name(category_name)
        
        for product_data in products_data:
            # Extract URN
            urn = product_data.get("@id", "")
            if not urn:
                logger.warning("Skipping product without @id")
                continue
            
            # Extract SKU
            sku = product_data.get("sku", "")
            
            # Process product group reference
            product_group_id = None
            product_group = None
            if "isVariantOf" in product_data and "@id" in product_data["isVariantOf"]:
                product_group_urn = product_data["isVariantOf"]["@id"]
                product_group = self.product_group_service.get_by_urn(product_group_urn)
                if product_group:
                    product_group_id = product_group.id
                else:
                    logger.warning(f"Product {urn} references non-existent product group {product_group_urn}")
            
            # Get description from product or product group
            description = product_data.get("description", "")
            if not description and product_group and product_group.description:
                description = product_group.description
            
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
            
            # Create product data
            product_create = ProductCreate(
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
                category_id=category.id,
                organization_id=organization_id,
            )
            product_creates.append(product_create)
        
        # Bulk upsert
        upserted = self.product_repo.bulk_upsert(product_creates, batch_size)
        
        # Create a mapping of URN to product for efficient lookup
        urn_to_product = {product.urn: product for product in upserted}
        
        # Process offers if needed (after products are created)
        for product_data in products_data:
            if "offers" in product_data:
                urn = product_data.get("@id", "")
                if urn and urn in urn_to_product:
                    from app.services.offer_service import OfferService
                    offer_service = OfferService(self.db_session)
                    offer_service.process_offer(product_data["offers"], urn_to_product[urn].id, organization_id)
        
        return [ProductInDB.model_validate(p) for p in upserted]
    
    
    
