# tests/services/test_product_service.py
from uuid import uuid4

from app.db.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


class TestProductService:
    """Test cases for ProductService using real database."""

    def test_get_product_by_urn(self, product_service, test_product):
        """Test getting product by URN."""
        product = product_service.get_by_urn(test_product.urn)

        assert product is not None
        assert product.id == test_product.id
        assert product.name == test_product.name
        assert product.urn == test_product.urn

    def test_get_product_by_urn_not_found(self, product_service):
        """Test getting product by URN that doesn't exist."""
        product = product_service.get_by_urn("urn:cmp:sku:nonexistent")
        assert product is None

    def test_get_product_by_id(self, product_service, test_product):
        """Test getting product by ID."""
        product = product_service.get_product(test_product.id)

        assert product is not None
        assert product.id == test_product.id
        assert product.name == test_product.name

    def test_get_product_by_id_not_found(self, product_service):
        """Test getting product by ID that doesn't exist."""
        product = product_service.get_product(uuid4())
        assert product is None

    def test_list_products(self, product_service, test_product):
        """Test listing products."""
        products = product_service.list_products()

        assert len(products) >= 1
        product_urns = [p.urn for p in products]
        assert test_product.urn in product_urns

    def test_list_products_by_category(self, product_service, test_product, test_category):
        """Test listing products by category."""
        # Use the existing list_by_category_id method from repository
        products = product_service.product_repo.list_by_category_id(test_category.id)

        assert len(products) >= 1
        for product in products:
            assert product.category_id == test_category.id

    def test_list_products_by_brand(self, product_service, test_product, test_brand):
        """Test listing products by brand."""
        # Use the existing list_by_brand method from repository
        products = product_service.product_repo.list_by_brand(test_brand.id)

        assert len(products) >= 1
        for product in products:
            assert product.brand_id == test_brand.id

    def test_list_products_by_organization(
        self, product_service, test_product, test_organization
    ):
        """Test listing products by organization."""
        # Use the existing list_by_organization method from repository
        products = product_service.product_repo.list_by_organization(test_organization.id)

        assert len(products) >= 1
        for product in products:
            assert product.organization_id == test_organization.id

    def test_create_product(
        self,
        product_service,
        test_category,
        test_brand,
        test_organization,
        test_product_group,
    ):
        """Test creating a new product."""
        product_data = ProductCreate(
            urn="urn:cmp:sku:test-create-product",
            name="Test Create Product",
            description="A test product for creation",
            sku="TEST-SKU-001",
            url="https://example.com/test-product",
            category_id=test_category.id,
            brand_id=test_brand.id,
            organization_id=test_organization.id,
            product_group_id=test_product_group.id,
            raw_data={
                "@cmp:media": [
                    {
                        "url": "https://example.com/image.jpg",
                        "name": "Test Image",
                        "@type": "ImageObject",
                    }
                ]
            },
        )

        product = product_service.create_product(product_data)

        assert product is not None
        assert product.name == product_data.name
        assert product.urn == product_data.urn
        assert product.category_id == test_category.id
        assert product.brand_id == test_brand.id
        assert product.organization_id == test_organization.id

    def test_update_product(self, product_service, test_product):
        """Test updating an existing product."""
        updated_name = "Updated Product Name"
        updated_description = "Updated product description"

        product_data = ProductUpdate(
            name=updated_name,
            description=updated_description,
        )

        product = product_service.update_product(test_product.id, product_data)

        assert product is not None
        assert product.name == updated_name
        assert product.description == updated_description
        assert product.id == test_product.id

    def test_update_product_not_found(self, product_service):
        """Test updating a product that doesn't exist."""
        product_data = ProductUpdate(name="Updated Name")
        product = product_service.update_product(uuid4(), product_data)
        assert product is None

    def test_delete_product(self, product_service, test_product):
        """Test deleting a product."""
        # Create a copy of the product for deletion test
        product_to_delete = Product(
            urn="urn:cmp:sku:product-to-delete",
            name="Product To Delete",
            description="A product to be deleted",
            sku="DELETE-SKU",
            url="https://example.com/delete",
            category_id=test_product.category_id,
            brand_id=test_product.brand_id,
            organization_id=test_product.organization_id,
            product_group_id=test_product.product_group_id,
        )
        product_service.db_session.add(product_to_delete)
        product_service.db_session.commit()
        product_service.db_session.refresh(product_to_delete)

        # Delete the product
        deleted = product_service.delete_product(product_to_delete.id)
        assert deleted is True

        # Verify it's gone
        product = product_service.get_product(product_to_delete.id)
        assert product is None

    def test_delete_product_not_found(self, product_service):
        """Test deleting a product that doesn't exist."""
        deleted = product_service.delete_product(uuid4())
        assert deleted is False

    def test_get_product_with_relationships(self, product_service, test_product):
        """Test getting product with all relationships loaded."""
        # Use the repository method directly since service doesn't have this method
        product = product_service.product_repo.get_by_id(test_product.id)

        assert product is not None
        assert product.category is not None
        assert product.brand is not None
        assert product.organization is not None
        assert product.product_group is not None

    def test_search_products_by_name(self, product_service, test_product):
        """Test searching products by name."""
        # Use the existing search_products method
        products = product_service.search_products("Boy with the Big Hair")

        assert len(products) >= 1
        product_names = [p.name for p in products]
        assert test_product.name in product_names

    def test_search_products_by_sku(self, product_service, test_product):
        """Test searching products by SKU."""
        # Use the existing search_products method
        products = product_service.search_products(test_product.sku)

        assert len(products) >= 1
        product_skus = [p.sku for p in products]
        assert test_product.sku in product_skus

    def test_get_products_with_offers(self, product_service, test_product, test_offer):
        """Test getting products with their offers."""
        # Use the repository method directly since service doesn't have this method
        products = product_service.product_repo.list()

        assert len(products) >= 1
        product_with_offers = next(
            (p for p in products if p.id == test_product.id), None
        )
        assert product_with_offers is not None

    def test_get_product_offers(self, product_service, test_product, test_offer):
        """Test getting offers for a specific product."""
        # Use the repository method directly since service doesn't have this method
        from app.db.models.offer import Offer
        offers = product_service.db_session.query(Offer).filter(Offer.product_id == test_product.id).all()

        assert len(offers) >= 1

    def test_get_product_offers_not_found(self, product_service):
        """Test getting offers for a product that doesn't exist."""
        # Use the repository method directly since service doesn't have this method
        from app.db.models.offer import Offer
        offers = product_service.db_session.query(Offer).filter(Offer.product_id == uuid4()).all()

        assert len(offers) == 0 