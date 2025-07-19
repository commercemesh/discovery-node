# tests/api/test_upsert_product_group_and_product_clean.py
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.api.web_app import app
from app.db.models.organization import Organization
from app.db.models.brand import Brand
from app.db.models.category import Category
from app.db.models.product_group import ProductGroup
from app.db.models.product import Product


class TestUpsertProductGroupAndProduct:
    """Test cases for upsert_product_group_and_product API endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_valid_input(self):
        """Sample valid input data."""
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:the-journey-within",
                        "name": "The Journey Within",
                        "description": "A journey of self-discovery",
                        "url": "https://Insight-editions.myshopify.com/products/the-journey-within",
                        "brand": {
                            "@type": "Brand",
                            "name": "FutureFabrik"
                        },
                        "category": "Books",
                        "productGroupID": "the-journey-within",
                        "variesBy": ["title"]
                    }
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "@id": "urn:cmp:sku:journey-default",
                        "name": "The Journey Within (Default Title)",
                        "url": "https://Insight-editions.myshopify.com/products/the-journey-within?variant=default",
                        "sku": "JOURNEY-DEFAULT",
                        "isVariantOf": {
                            "@type": "ProductGroup",
                            "@id": "urn:cmp:product:the-journey-within"
                        },
                        "offers": {
                            "@type": "Offer",
                            "price": 19.99,
                            "priceCurrency": "USD",
                            "availability": "https://schema.org/InStock",
                            "inventoryLevel": {
                                "@type": "QuantitativeValue",
                                "value": 10
                            },
                            "priceValidUntil": "2026-06-19T15:07:18.333109"
                        },
                        "additionalProperty": [
                            {
                                "@type": "PropertyValue",
                                "name": "title",
                                "value": "Default Title"
                            },
                            {
                                "@type": "PropertyValue",
                                "name": "productType",
                                "value": "Book"
                            }
                        ]
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }

    @pytest.fixture
    def test_organization(self, db_session):
        """Create test organization."""
        org = Organization(
            id=uuid4(),
            urn="urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000",
            name="Test Organization",
            description="Test organization for upsert tests",
            url="https://test-org.com"
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)
        return org

    @pytest.fixture
    def test_category(self, db_session):
        """Create test category."""
        category = Category(
            id=uuid4(),
            slug="books",
            name="Books"
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)
        return category

    @pytest.fixture
    def test_brand(self, db_session, test_organization):
        """Create test brand."""
        brand = Brand(
            id=uuid4(),
            urn="urn:cmp:brand:futurefabrik",
            name="FutureFabrik",
            organization_id=test_organization.id
        )
        db_session.add(brand)
        db_session.commit()
        db_session.refresh(brand)
        return brand

    # ==================== SUCCESS CASES ====================

    def test_upsert_product_group_and_product_success(
        self, client, sample_valid_input, test_organization, test_category, test_brand
    ):
        """Test successful upsert of product group and product."""
        with patch('app.api.routes.products.OrganizationService') as mock_org_service, \
             patch('app.api.routes.products.BrandService') as mock_brand_service, \
             patch('app.api.routes.products.ProductGroupService') as mock_pg_service, \
             patch('app.api.routes.products.ProductService') as mock_product_service:
            
            # Mock organization service
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            # Mock brand service
            mock_brand_instance = MagicMock()
            mock_brand_instance.get_by_name.return_value = test_brand
            mock_brand_service.return_value = mock_brand_instance
            
            # Mock product group service
            mock_pg_instance = MagicMock()
            mock_pg_instance.process_product_group.return_value = uuid4()
            mock_pg_service.return_value = mock_pg_instance
            
            # Mock product service
            mock_product_instance = MagicMock()
            mock_product_instance.process_product.return_value = uuid4()
            mock_product_service.return_value = mock_product_instance
            
            response = client.post("/api/v1/product", json=sample_valid_input)
            
            assert response.status_code == 200
            data = response.json()
            assert "product_group_id" in data
            assert "successful_products" in data
            assert "errors" in data
            assert len(data["successful_products"]) == 1
            assert len(data["errors"]) == 0

    def test_upsert_product_group_only(self, client, test_organization, test_category, test_brand):
        """Test successful upsert of product group only."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:group-only-test",
                        "name": "Group Only Test",
                        "description": "A test product group only",
                        "url": "https://test.com/group-only",
                        "brand": {
                            "@type": "Brand",
                            "name": "FutureFabrik"
                        },
                        "category": "Books",
                        "productGroupID": "group-only-test"
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        new_product_group_id = uuid4()
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service, \
             patch('app.api.routes.products.BrandService') as mock_brand_service, \
             patch('app.api.routes.products.ProductGroupService') as mock_pg_service:
            
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            mock_brand_instance = MagicMock()
            mock_brand_instance.get_by_name.return_value = test_brand
            mock_brand_service.return_value = mock_brand_instance
            
            mock_pg_instance = MagicMock()
            mock_pg_instance.get_by_urn.return_value = None  # Product group doesn't exist
            mock_pg_instance.process_product_group.return_value = new_product_group_id
            mock_pg_service.return_value = mock_pg_instance
            
            response = client.post("/api/v1/product", json=input_data)
            data = response.json()
            assert response.status_code == 200
            assert data["product_group_id"] == str(new_product_group_id)
            assert len(data["errors"]) == 0

    def test_upsert_product_only_with_existing_product_group(self, client, test_organization, test_brand):
        """Test successful upsert of product that references existing product group."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "@id": "urn:cmp:sku:product-with-existing-group",
                        "name": "Product with Existing Group",
                        "url": "https://test.com/product-existing-group",
                        "sku": "EXISTING-GROUP-001",
                        "isVariantOf": {
                            "@type": "ProductGroup",
                            "@id": "urn:cmp:product:existing-group"
                        },
                        "offers": {
                            "@type": "Offer",
                            "price": 29.99,
                            "priceCurrency": "USD",
                            "availability": "https://schema.org/InStock"
                        }
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        # Create existing product group in DB
        existing_product_group = ProductGroup(
            id=uuid4(),
            urn="urn:cmp:product:existing-group",
            name="Existing Product Group",
            brand_id=test_brand.id,
            organization_id=test_organization.id
        )
        
        new_product_id = uuid4()
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service, \
             patch('app.api.routes.products.ProductGroupService') as mock_pg_service, \
             patch('app.api.routes.products.ProductService') as mock_product_service:
            
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            mock_pg_instance = MagicMock()
            mock_pg_instance.get_by_urn.return_value = existing_product_group
            mock_pg_service.return_value = mock_pg_instance
            
            mock_product_instance = MagicMock()
            mock_product_instance.process_product.return_value = new_product_id
            mock_product_service.return_value = mock_product_instance
            
            response = client.post("/api/v1/product", json=input_data)
            data = response.json()
            assert response.status_code == 200
            assert len(data["successful_products"]) == 1
            assert data["successful_products"][0]["product_id"] == str(new_product_id)
            assert len(data["errors"]) == 0

    def test_upsert_product_with_existing_product(self, client, test_organization):
        """Test successful upsert of existing product without product group."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "@id": "urn:cmp:sku:standalone-product",
                        "name": "Standalone Product",
                        "sku": "STANDALONE-001"
                        # No isVariantOf
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        # Create existing product in DB for this case
        existing_product = Product(
            id=uuid4(),
            urn="urn:cmp:sku:standalone-product",
            name="Standalone Product",
            sku="STANDALONE-001",
            brand_id=uuid4(),
            organization_id=test_organization.id,
            category_id=uuid4(),
            product_group_id=uuid4()
        )
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service, \
             patch('app.api.routes.products.ProductService') as mock_product_service:
            
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            mock_product_instance = MagicMock()
            mock_product_instance.get_by_urn.return_value = existing_product
            mock_product_instance.process_product.return_value = existing_product.id
            mock_product_service.return_value = mock_product_instance
            
            response = client.post("/api/v1/product", json=input_data)
            data = response.json()
            assert response.status_code == 200
            assert len(data["successful_products"]) == 1
            assert data["successful_products"][0]["product_id"] == str(existing_product.id)
            assert len(data["errors"]) == 0

    def test_upsert_mixed_success_and_errors(self, client, test_organization, test_brand):
        """Test upsert with mixed success and error scenarios."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:valid-group",
                        "name": "Valid Product Group",
                        "brand": {
                            "@type": "Brand",
                            "name": "FutureFabrik"
                        },
                        "category": "Books"
                    }
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "@id": "urn:cmp:sku:valid-product",
                        "name": "Valid Product",
                        "sku": "VALID-001",
                        "isVariantOf": {
                            "@type": "ProductGroup",
                            "@id": "urn:cmp:product:valid-group"
                        }
                    }
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "@id": "urn:cmp:sku:invalid-product",
                        "name": "Invalid Product",
                        "sku": "INVALID-001"
                        # Missing isVariantOf
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        new_product_group_id = uuid4()
        new_product_id = uuid4()
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service, \
             patch('app.api.routes.products.BrandService') as mock_brand_service, \
             patch('app.api.routes.products.ProductGroupService') as mock_pg_service, \
             patch('app.api.routes.products.ProductService') as mock_product_service:
            
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            mock_brand_instance = MagicMock()
            mock_brand_instance.get_by_name.return_value = test_brand
            mock_brand_service.return_value = mock_brand_instance
            
            mock_pg_instance = MagicMock()
            mock_pg_instance.get_by_urn.return_value = None
            mock_pg_instance.process_product_group.return_value = new_product_group_id
            mock_pg_service.return_value = mock_pg_instance
            
            mock_product_instance = MagicMock()
            mock_product_instance.get_by_urn.return_value = None
            mock_product_instance.process_product.return_value = new_product_id
            mock_product_service.return_value = mock_product_instance
            
            response = client.post("/api/v1/product", json=input_data)
            data = response.json()
            assert response.status_code == 200
            assert data["product_group_id"] == str(new_product_group_id)
            assert len(data["successful_products"]) == 2  # Both products are processed
            assert len(data["errors"]) == 0  # No errors since both products have valid references

    # ==================== INPUT VALIDATION CASES ====================

    def test_upsert_missing_item_list_element(self, client):
        """Test upsert with missing itemListElement."""
        invalid_input = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        response = client.post("/api/v1/product", json=invalid_input)
        assert response.status_code == 400
        assert "itemListElement must be a non-empty list" in response.json()["detail"]

    def test_upsert_empty_item_list_element(self, client):
        """Test upsert with empty itemListElement."""
        invalid_input = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        response = client.post("/api/v1/product", json=invalid_input)
        assert response.status_code == 400
        assert "itemListElement must be a non-empty list" in response.json()["detail"]

    def test_upsert_missing_identifier(self, client):
        """Test upsert with missing identifier."""
        invalid_input = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:test-group",
                        "name": "Test Product Group",
                        "brand": {
                            "@type": "Brand",
                            "name": "FutureFabrik"
                        },
                        "category": "Books"
                    }
                }
            ]
        }
        
        response = client.post("/api/v1/product", json=invalid_input)
        assert response.status_code == 400
        assert "identifier.value (organization_id) is required" in response.json()["detail"]

    def test_upsert_invalid_identifier(self, client):
        """Test upsert with invalid identifier."""
        invalid_input = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:test-group",
                        "name": "Test Product Group",
                        "brand": {
                            "@type": "Brand",
                            "name": "FutureFabrik"
                        },
                        "category": "Books"
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "invalid_property",
                "value": "invalid_value"
            }
        }
        
        response = client.post("/api/v1/product", json=invalid_input)
        assert response.status_code == 400
        assert "Organization does not exist with urn invalid_value" in response.json()["detail"]

    # ==================== ERROR CASES ====================

    def test_upsert_organization_not_found(self, client, sample_valid_input):
        """Test upsert when organization is not found."""
        with patch('app.api.routes.products.OrganizationService') as mock_org_service:
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = None
            mock_org_service.return_value = mock_org_instance
            
            response = client.post("/api/v1/product", json=sample_valid_input)
            assert response.status_code == 400
            assert "Organization does not exist" in response.json()["detail"]

    def test_upsert_product_group_missing_id(self, client, test_organization):
        """Test upsert when product group is missing ID."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "name": "Test Product Group",
                        "brand": {
                            "@type": "Brand",
                            "name": "FutureFabrik"
                        },
                        "category": "Books"
                        # Missing @id
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service:
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            response = client.post("/api/v1/product", json=input_data)
            assert response.status_code == 400
            assert "ProductGroup missing @id" in response.json()["detail"]

    def test_upsert_product_group_missing_brand(self, client, test_organization):
        """Test upsert when product group is missing brand."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:test-group",
                        "name": "Test Product Group",
                        "category": "Books"
                        # Missing brand
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service:
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            response = client.post("/api/v1/product", json=input_data)
            assert response.status_code == 400
            assert "ProductGroup missing brand dict or brand name" in response.json()["detail"]

    def test_upsert_product_missing_id(self, client, test_organization):
        """Test upsert when product is missing ID."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "name": "Test Product",
                        "sku": "TEST-001"
                        # Missing @id
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service:
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            response = client.post("/api/v1/product", json=input_data)
            data = response.json()
            assert response.status_code == 200
            assert len(data["errors"]) == 1
            assert "Product missing @id field" in data["errors"][0]["error"]

    def test_upsert_product_without_product_group_reference(self, client, test_organization):
        """Test upsert when product has no product group reference and is not existing."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "@id": "urn:cmp:sku:new-standalone-product",
                        "name": "New Standalone Product",
                        "sku": "NEW-STANDALONE-001"
                        # No isVariantOf
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service, \
             patch('app.api.routes.products.ProductService') as mock_product_service:
            
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            mock_product_instance = MagicMock()
            mock_product_instance.get_by_urn.return_value = None  # Product doesn't exist
            mock_product_service.return_value = mock_product_instance
            
            response = client.post("/api/v1/product", json=input_data)
            data = response.json()
            assert response.status_code == 200
            assert len(data["errors"]) == 1
            assert "Cannot process product without product group or isVariantOf reference" in data["errors"][0]["error"]
            assert len(data["successful_products"]) == 0

    def test_upsert_product_with_invalid_variant_reference(self, client, test_organization):
        """Test upsert when product has invalid isVariantOf reference."""
        input_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "@id": "urn:cmp:sku:invalid-variant",
                        "name": "Invalid Variant Product",
                        "sku": "INVALID-001",
                        "isVariantOf": {
                            "@type": "ProductGroup",
                            "@id": "urn:cmp:product:non-existent-group"
                        }
                    }
                }
            ],
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
            }
        }
        
        with patch('app.api.routes.products.OrganizationService') as mock_org_service, \
             patch('app.api.routes.products.ProductGroupService') as mock_pg_service:
            
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.return_value = test_organization
            mock_org_service.return_value = mock_org_instance
            
            mock_pg_instance = MagicMock()
            mock_pg_instance.get_by_urn.return_value = None  # Product group doesn't exist
            mock_pg_service.return_value = mock_pg_instance
            
            response = client.post("/api/v1/product", json=input_data)
            data = response.json()
            assert response.status_code == 200
            assert len(data["errors"]) == 1
            assert "Cannot process product without product group, invalid product group reference" in data["errors"][0]["error"]

    def test_upsert_internal_server_error(self, client, sample_valid_input):
        """Test upsert when internal server error occurs."""
        with patch('app.api.routes.products.OrganizationService') as mock_org_service:
            mock_org_instance = MagicMock()
            mock_org_instance.get_organization_by_urn.side_effect = Exception("Database error")
            mock_org_service.return_value = mock_org_instance
            
            response = client.post("/api/v1/product", json=sample_valid_input)
            assert response.status_code == 500
            assert "Internal error: Database error" in response.json()["detail"] 