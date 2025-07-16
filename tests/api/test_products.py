# tests/api/test_products.py
from unittest.mock import patch

import pytest
from fastapi import status

from app.api.routes.products import get_product, get_products
from app.db.models.offer import Offer
from app.db.models.product import Product
from app.schemas.product import ProductDetailResponse, ProductSearchResponse


class TestGetProduct:
    """Test cases for get_product endpoint using real database."""

    async def test_get_product_success(self, db_session, test_product, test_offer):
        """Test successful product retrieval with real database."""
        # Get the product with relationships loaded
        product = (
            db_session.query(Product)
            .filter(Product.id == test_product.id)
            .first()
        )

        response = await get_product(product.urn, db_session)

        assert isinstance(response, ProductDetailResponse)
        assert response.id == str(product.id)
        assert response.name == product.name
        assert response.description == product.description
        assert response.category == product.category.name
        assert response.price == 14.99  # Minimum price from offers
        assert len(response.offers) == 1
        assert len(response.media) == 2  # Combined from product and product group
        assert response.group is not None
        assert response.group["id"] == str(product.product_group.id)

    async def test_get_product_not_found(self, db_session):
        """Test product not found scenario with real database."""
        response = await get_product("urn:cmp:sku:nonexistent", db_session)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.body.decode()

    async def test_get_product_without_relationships(
        self, db_session, test_category, test_brand, test_organization
    ):
        """Test product without relationships using real database."""
        # Create a product without product group
        product = Product(
            urn="urn:cmp:sku:product-without-relationships",
            name="Product Without Relationships",
            description="A product without any relationships",
            sku="SKU123",
            url="https://example.com/product",
            brand_id=test_brand.id,
            category_id=test_category.id,
            organization_id=test_organization.id,
            raw_data={},
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)

        response = await get_product(product.urn, db_session)

        assert isinstance(response, ProductDetailResponse)
        assert response.id == str(product.id)
        assert response.name == product.name
        assert response.category == test_category.name
        assert response.price is None
        assert response.offers == []
        assert response.media == []
        assert response.group is None

    async def test_get_product_with_multiple_offers(
        self, db_session, test_product, test_organization
    ):
        """Test product with multiple offers - should return minimum price."""
        # Create multiple offers with different prices
        offer1 = Offer(
            product_id=test_product.id,
            seller_id=test_organization.id,
            price=20.00,
            price_currency="USD",
            availability="InStock",
            inventory_level=10,
            raw_data={
                "@type": "Offer",
                "price": 20.00,
                "availability": "https://schema.org/InStock",
                "priceCurrency": "USD",
                "inventoryLevel": {"@type": "QuantitativeValue", "value": 10},
                "priceValidUntil": "2026-12-31T23:59:59Z",
            },
        )

        offer2 = Offer(
            product_id=test_product.id,
            seller_id=test_organization.id,
            price=15.00,
            price_currency="USD",
            availability="InStock",
            inventory_level=5,
            raw_data={
                "@type": "Offer",
                "price": 15.00,
                "availability": "https://schema.org/InStock",
                "priceCurrency": "USD",
                "inventoryLevel": {"@type": "QuantitativeValue", "value": 5},
                "priceValidUntil": "2026-12-31T23:59:59Z",
            },
        )

        db_session.add(offer1)
        db_session.add(offer2)
        db_session.commit()

        response = await get_product(test_product.urn, db_session)

        assert isinstance(response, ProductDetailResponse)
        assert response.price == 15.00  # Minimum price from offers
        assert len(response.offers) == 3  # Original offer + 2 new offers

    async def test_get_product_with_invalid_offer_data(
        self, db_session, test_product, test_organization
    ):
        """Test product with invalid offer data."""
        # Create an offer with invalid raw_data
        offer = Offer(
            product_id=test_product.id,
            seller_id=test_organization.id,
            price=10.00,
            price_currency="USD",
            availability="InStock",
            inventory_level=5,
            raw_data=None,  # Invalid data
        )
        db_session.add(offer)
        db_session.commit()

        response = await get_product(test_product.urn, db_session)

        assert isinstance(response, ProductDetailResponse)
        # Should still work and include valid offers
        assert len(response.offers) >= 1

    async def test_get_product_with_invalid_media_data(self, db_session, test_product):
        """Test product with invalid media data."""
        # Update product with invalid media data
        test_product.raw_data = {"@cmp:media": "invalid_string"}
        db_session.commit()

        response = await get_product(test_product.urn, db_session)

        assert isinstance(response, ProductDetailResponse)
        # Should handle invalid media gracefully
        assert isinstance(response.media, list)


class TestGetProducts:
    """Test cases for get_products endpoint using real database."""

    def test_get_products_success(self, db_session, test_search_results):
        """Test successful product search with real database."""
        with patch("app.api.routes.products.SearchService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search_products.return_value = test_search_results

            with patch(
                "app.api.routes.products.format_product_search_response"
            ) as mock_formatter:
                mock_formatter.return_value = {
                    "@context": {
                        "schema": "https://schema.org",
                        "cmp": "https://schema.commercemesh.ai/ns#",
                    },
                    "@type": "ItemList",
                    "itemListElement": test_search_results,
                    "cmp:totalResults": 1,
                    "cmp:nodeVersion": "v1.0.0",
                    "datePublished": "2025-07-15T00:00:00Z",
                }

                response = get_products("test query", db_session)

                assert isinstance(response, ProductSearchResponse)
                assert response.type == "ItemList"
                assert len(response.itemListElement) == 1
                assert response.cmp_totalResults == 1

    async def test_get_products_empty_query(self, db_session):
        """Test search with empty query."""
        with pytest.raises(Exception) as exc_info:
            await get_products("", db_session)

        assert "Search query cannot be empty" in str(exc_info.value)

    async def test_get_products_whitespace_query(self, db_session):
        """Test search with whitespace-only query."""
        with pytest.raises(Exception) as exc_info:
            await get_products("   ", db_session)

        assert "Search query cannot be empty" in str(exc_info.value)

    async def test_get_products_search_service_error(self, db_session):
        """Test search service error handling."""
        with patch("app.api.routes.products.SearchService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search_products.side_effect = Exception("Search service error")

            with pytest.raises(Exception) as exc_info:
                await get_products("test query", db_session)

            assert "Search service error" in str(exc_info.value)

    async def test_get_products_formatter_error(self, db_session, test_search_results):
        """Test formatter error handling."""
        with patch("app.api.routes.products.SearchService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search_products.return_value = test_search_results

            with patch(
                "app.api.routes.products.format_product_search_response"
            ) as mock_formatter:
                mock_formatter.side_effect = Exception("Formatter error")

                with pytest.raises(Exception) as exc_info:
                    await get_products("test query", db_session)

                assert "Search service error" in str(exc_info.value)


class TestProductsAPIEndpoints:
    """Integration tests for products API endpoints using real database."""

    def test_get_product_endpoint_success(
        self, client, app_with_test_db, test_product, test_offer
    ):
        """Test GET /v1/products/{sku_urn} endpoint success with real database."""
        response = client.get(f"/v1/products/{test_product.urn}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(test_product.id)
        assert data["name"] == test_product.name
        assert data["description"] == test_product.description
        assert data["category"] == test_product.category.name
        assert data["price"] == 14.99
        assert len(data["offers"]) >= 1
        assert len(data["media"]) >= 1
        assert data["group"] is not None

    def test_get_product_endpoint_not_found(self, client, app_with_test_db):
        """Test GET /v1/products/{sku_urn} endpoint not found with real database."""
        response = client.get("/v1/products/urn:cmp:sku:nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"]

    def test_get_products_endpoint_success(
        self, client, app_with_test_db, test_search_results
    ):
        """Test GET /v1/products endpoint success with real database."""
        with patch("app.api.routes.products.SearchService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search_products.return_value = test_search_results

            with patch(
                "app.api.routes.products.format_product_search_response"
            ) as mock_formatter:
                mock_formatter.return_value = {
                    "@context": {
                        "schema": "https://schema.org",
                        "cmp": "https://schema.commercemesh.ai/ns#",
                    },
                    "@type": "ItemList",
                    "itemListElement": test_search_results,
                    "cmp:totalResults": 1,
                    "cmp:nodeVersion": "v1.0.0",
                    "datePublished": "2025-07-15T00:00:00Z",
                }

                response = client.get("/v1/products?q=test+query")

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["@type"] == "ItemList"
                assert len(data["itemListElement"]) == 1
                assert data["cmp:totalResults"] == 1

    def test_get_products_endpoint_empty_query(self, client, app_with_test_db):
        """Test GET /v1/products endpoint with empty query."""
        response = client.get("/v1/products?q=")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Search query cannot be empty" in data["detail"]

    def test_get_products_endpoint_default_query(
        self, client, app_with_test_db, test_search_results
    ):
        """Test GET /v1/products endpoint with default query."""
        with patch("app.api.routes.products.SearchService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search_products.return_value = test_search_results

            with patch(
                "app.api.routes.products.format_product_search_response"
            ) as mock_formatter:
                mock_formatter.return_value = {
                    "@context": {
                        "schema": "https://schema.org",
                        "cmp": "https://schema.commercemesh.ai/ns#",
                    },
                    "@type": "ItemList",
                    "itemListElement": test_search_results,
                    "cmp:totalResults": 1,
                    "cmp:nodeVersion": "v1.0.0",
                    "datePublished": "2025-07-15T00:00:00Z",
                }

                response = client.get("/v1/products")  # Uses default query "James Cameron"

                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["@type"] == "ItemList"

    def test_get_products_endpoint_long_query(self, client, app_with_test_db):
        """Test GET /v1/products endpoint with query too long."""
        long_query = "a" * 501  # Exceeds max_length of 500
        response = client.get(f"/v1/products?q={long_query}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_products_endpoint_invalid_query_type(self, client, app_with_test_db):
        """Test GET /v1/products endpoint with invalid query type."""
        response = client.get("/v1/products?q=123")  # Query should be string

        # This should work fine as 123 is converted to string
        assert response.status_code == status.HTTP_200_OK


class TestProductResponseValidation:
    """Test cases for response validation using real database."""

    async def test_product_detail_response_validation(
        self, db_session, test_product, test_offer
    ):
        """Test that ProductDetailResponse validates correctly with real database."""
        response = await get_product(test_product.urn, db_session)

        # Verify the response can be serialized to JSON
        json_data = response.model_dump()
        assert "id" in json_data
        assert "name" in json_data
        assert "description" in json_data
        assert "category" in json_data
        assert "price" in json_data
        assert "offers" in json_data
        assert "media" in json_data
        assert "group" in json_data

    async def test_product_search_response_validation(
        self, db_session, test_search_results
    ):
        """Test that ProductSearchResponse validates correctly with real database."""
        with patch("app.api.routes.products.SearchService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search_products.return_value = test_search_results

            with patch(
                "app.api.routes.products.format_product_search_response"
            ) as mock_formatter:
                mock_formatter.return_value = {
                    "@context": {
                        "schema": "https://schema.org",
                        "cmp": "https://schema.commercemesh.ai/ns#",
                    },
                    "@type": "ItemList",
                    "itemListElement": test_search_results,
                    "cmp:totalResults": 1,
                    "cmp:nodeVersion": "v1.0.0",
                    "datePublished": "2025-07-15T00:00:00Z",
                }

                response = await get_products("test query", db_session)

                # Verify the response can be serialized to JSON
                json_data = response.model_dump()
                assert "@context" in json_data
                assert "@type" in json_data
                assert "itemListElement" in json_data
                assert "cmp:totalResults" in json_data
