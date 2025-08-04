"""
Test the flow from search API to products API.
Tests searching for a product and then retrieving it by URN.
"""
import pytest
from fastapi.testclient import TestClient
from app.api.web_app import app
from app.db.base import get_db_session
from app.services.product_service import ProductService
from app.services.product_group_service import ProductGroupService
from app.services.brand_service import BrandService
from app.services.category_service import CategoryService
from app.schemas.product import ProductCreate
from app.schemas.product_group import ProductGroupCreate
from app.schemas.brand import BrandCreate
from app.schemas.category import CategoryCreate
from app.schemas.organization import OrganizationCreate
from uuid import uuid4
import json


@pytest.fixture
def test_client(db_session):
    """Create FastAPI test client with test database session."""
    # Override the database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db_session] = override_get_db
    
    with TestClient(app) as client:
        yield client
    
    # Clear the override after the test
    app.dependency_overrides.clear()


@pytest.fixture
def setup_test_data(db_session):
    """Set up test data for search and product retrieval."""
    # Create services
    brand_service = BrandService(db_session)
    category_service = CategoryService(db_session)
    product_group_service = ProductGroupService(db_session)
    product_service = ProductService(db_session)
    
    # Create test organization (required for brand)
    from app.services.organization_service import OrganizationService
    org_service = OrganizationService(db_session)
    org_data = OrganizationCreate(
        name="Test Organization",
        urn="urn:cmp:org:test-org-123",
        url="https://test-org.com",
        description="Test organization for API tests"
    )
    organization = org_service.create_organization(org_data)
    
    # Create test brand
    brand_data = BrandCreate(
        name="Stellar Books",
        urn="urn:cmp:brand:stellar-books",
        organization_id=organization.id,
        logo="https://example.com/stellar-books-logo.png"
    )
    brand = brand_service.create_brand(brand_data)
    
    # Create test category
    category_data = CategoryCreate(
        name="Books",
        slug="books",
        description="Book products"
    )
    category = category_service.create_category(category_data)
    
    # Create product group for "Supernova" book
    product_group_data = ProductGroupCreate(
        name="Supernova: A Cosmic Journey",
        urn="urn:cmp:product:supernova-cosmic-journey",
        description="An epic exploration of stellar explosions and cosmic phenomena",
        url="https://stellar-books.com/products/supernova",
        product_group_id="supernova-001",
        varies_by=["edition", "format"],
        brand_id=brand.id,
        category_id=category.id,
        organization_id=organization.id,
        raw_data={
            "@type": "ProductGroup",
            "@id": "urn:cmp:product:supernova-cosmic-journey",
            "name": "Supernova: A Cosmic Journey"
        }
    )
    product_group = product_group_service.create_product_group(product_group_data)
    
    # Create product variants
    products = []
    
    # Hardcover edition
    product1_data = ProductCreate(
        name="Supernova: A Cosmic Journey (Hardcover)",
        urn="urn:cmp:sku:supernova-hardcover-001",
        sku="SUPERNOVA-HC-001",
        description="Hardcover edition of Supernova: A Cosmic Journey",
        url="https://stellar-books.com/products/supernova?variant=hardcover",
        product_group_id=product_group.id,
        brand_id=brand.id,
        category_id=category.id,
        organization_id=organization.id,
        variant_attributes={
            "edition": "First Edition",
            "format": "Hardcover",
            "pages": "456"
        },
        raw_data={
            "@type": "Product",
            "@id": "urn:cmp:sku:supernova-hardcover-001",
            "name": "Supernova: A Cosmic Journey (Hardcover)"
        }
    )
    product1 = product_service.create_product(product1_data)
    products.append(product1)
    
    # Paperback edition
    product2_data = ProductCreate(
        name="Supernova: A Cosmic Journey (Paperback)",
        urn="urn:cmp:sku:supernova-paperback-001",
        sku="SUPERNOVA-PB-001",
        description="Paperback edition of Supernova: A Cosmic Journey",
        url="https://stellar-books.com/products/supernova?variant=paperback",
        product_group_id=product_group.id,
        brand_id=brand.id,
        category_id=category.id,
        organization_id=organization.id,
        variant_attributes={
            "edition": "First Edition",
            "format": "Paperback",
            "pages": "456"
        },
        raw_data={
            "@type": "Product",
            "@id": "urn:cmp:sku:supernova-paperback-001",
            "name": "Supernova: A Cosmic Journey (Paperback)"
        }
    )
    product2 = product_service.create_product(product2_data)
    products.append(product2)
    
    # Create some offers
    from app.services.offer_service import OfferService
    from app.schemas.offer import OfferCreate
    offer_service = OfferService(db_session)
    
    # Offer for hardcover
    offer1_data = OfferCreate(
        product_id=product1.id,
        organization_id=organization.id,
        price=29.99,
        price_currency="USD",
        availability="InStock",
        inventory_level=100
    )
    offer_service.create_offer(offer1_data)
    
    # Offer for paperback
    offer2_data = OfferCreate(
        product_id=product2.id,
        organization_id=organization.id,
        price=19.99,
        price_currency="USD",
        availability="InStock",
        inventory_level=250
    )
    offer_service.create_offer(offer2_data)
    
    # Commit all changes
    db_session.commit()
    
    return {
        "organization": organization,
        "brand": brand,
        "category": category,
        "product_group": product_group,
        "products": products
    }


class TestSearchToProductsFlow:
    """Test the complete flow from search API to products API."""
    
    def test_search_and_retrieve_product_by_urn(self, test_client, setup_test_data):
        """
        Test searching for 'supernova' and then retrieving the first result by URN.
        """
        # Step 1: Search for "supernova"
        search_response = test_client.get("/api/v1/search", params={"q": "supernova"})
        
        # Assert search was successful
        assert search_response.status_code == 200
        search_data = search_response.json()
        
        # Verify we have search results
        assert "@context" in search_data
        assert "@type" in search_data
        assert search_data["@type"] == "ItemList"
        assert "itemListElement" in search_data
        assert len(search_data["itemListElement"]) > 0
        
        # Get the first result
        first_result = search_data["itemListElement"][0]
        assert first_result["@type"] == "ListItem"
        assert "item" in first_result
        
        first_product = first_result["item"]
        assert "@type" in first_product
        assert first_product["@type"] == "Product"
        assert "@id" in first_product
        
        # Extract the URN from the first result
        product_urn = first_product["@id"]
        assert product_urn.startswith("urn:cmp:")
        
        # Verify the product name contains "supernova" (case insensitive)
        assert "supernova" in first_product["name"].lower()
        
        # Step 2: Use the URN to call the products API
        # URL encode the URN if needed
        import urllib.parse
        encoded_urn = urllib.parse.quote(product_urn, safe='')
        
        products_response = test_client.get(f"/api/v1/products/{encoded_urn}")
        
        # Assert products API was successful
        assert products_response.status_code == 200
        products_data = products_response.json()
        
        # Verify the response structure
        assert "@context" in products_data
        assert "@type" in products_data
        assert products_data["@type"] == "ItemList"
        assert "itemListElement" in products_data
        assert len(products_data["itemListElement"]) >= 1
        
        # Check if we got a ProductGroup and Product (or just Product)
        items = products_data["itemListElement"]
        
        # Find the product in the response
        product_found = False
        for item in items:
            if item["@type"] == "ListItem" and "item" in item:
                item_data = item["item"]
                if item_data["@type"] == "Product" and item_data["@id"] == product_urn:
                    product_found = True
                    # Verify product details
                    assert "name" in item_data
                    assert "supernova" in item_data["name"].lower()
                    break
        
        assert product_found, f"Product with URN {product_urn} not found in products API response"
        
    def test_search_returns_correct_urn_format(self, test_client, setup_test_data):
        """
        Test that the search API returns correctly formatted URNs in @id fields.
        """
        # Search for a product
        search_response = test_client.get("/api/v1/search", params={"q": "cosmic journey"})
        
        assert search_response.status_code == 200
        search_data = search_response.json()
        
        # Check all results have proper URN format
        for list_item in search_data["itemListElement"]:
            product = list_item["item"]
            assert "@id" in product
            urn = product["@id"]
            
            # Verify URN format
            assert urn.startswith("urn:cmp:"), f"Invalid URN format: {urn}"
            assert not urn.startswith("urn:cmp:sku:") or len(urn.split(":")) >= 4
            
            # URN should not contain UUID patterns (unless it's part of the actual SKU)
            import re
            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            if re.search(uuid_pattern, urn):
                # If there's a UUID pattern, it should be part of the original URN, not added
                assert "urn:cmp:sku:" + re.search(uuid_pattern, urn).group() != urn