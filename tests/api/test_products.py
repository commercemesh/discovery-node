# tests/api/test_products.py
from unittest.mock import patch

import pytest
from fastapi import status


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
