# tests/fixtures/test_data.py
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from app.db.models.brand import Brand
from app.db.models.category import Category
from app.db.models.offer import Offer
from app.db.models.organization import Organization
from app.db.models.product import Product
from app.db.models.product_group import ProductGroup


@pytest.fixture
def test_category(db_session) -> Category:
    """Test category object in database."""
    category = Category(
        id=uuid4(),
        slug="childrens-books",
        name="Children's Books",
        description="Books for children",
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_brand(db_session, test_organization) -> Brand:
    """Test brand object in database."""
    brand = Brand(
        id=uuid4(),
        name="Test Brand",
        urn=f"urn:cmp:brand:test-brand-{uuid4().hex[:8]}",
        organization_id=test_organization.id,
    )
    db_session.add(brand)
    db_session.commit()
    db_session.refresh(brand)
    return brand


@pytest.fixture
def test_organization(db_session) -> Organization:
    """Test organization object in database."""
    org = Organization(
        id=uuid4(),
        name="Test Organization",
        description="A test organization for testing",
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_product_group(db_session, test_category, test_brand, test_organization) -> ProductGroup:
    """Test product group object in database."""
    group = ProductGroup(
        id=uuid4(),
        urn=f"urn:cmp:product:test-group-{uuid4().hex[:8]}",
        name="The Boy with the Big Hair",
        product_group_id=f"test-group-{uuid4().hex[:8]}",
        varies_by=["color", "size"],
        category_id=test_category.id,
        brand_id=test_brand.id,
        organization_id=test_organization.id,
        raw_data={
            "@cmp:media": [
                {
                    "url": "https://cdn.shopify.com/s/files/1/0421/4502/2103/products/76026-44852-interior-1.jpg?v=1719048395",
                    "name": "Product Image",
                    "@type": "ImageObject",
                    "width": 1024,
                    "height": 466,
                    "caption": "",
                    "encodingFormat": "image/jpeg",
                }
            ]
        },
    )
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    return group


@pytest.fixture
def test_offer(db_session, test_product, test_organization) -> Offer:
    """Test offer object in database."""
    offer = Offer(
        id=uuid4(),
        product_id=test_product.id,
        seller_id=test_organization.id,
        price=14.99,
        price_currency="USD",
        availability="OutOfStock",
        inventory_level=0,
        price_valid_until=datetime(
            2026, 7, 9, 17, 15, 44, 159775, tzinfo=timezone.utc
        ),
        raw_data={
            "@type": "Offer",
            "price": 14.99,
            "availability": "https://schema.org/OutOfStock",
            "priceCurrency": "USD",
            "inventoryLevel": {
                "@type": "QuantitativeValue",
                "value": 0,
            },
            "priceValidUntil": "2026-07-09T17:15:44.159775",
        },
    )
    db_session.add(offer)
    db_session.commit()
    db_session.refresh(offer)
    return offer


@pytest.fixture
def test_product(
    db_session, test_product_group, test_category, test_brand, test_organization
) -> Product:
    """Test product object with all relationships in database."""
    product = Product(
        id=uuid4(),
        urn=f"urn:cmp:sku:test-product-{uuid4().hex[:8]}",
        name="The Boy with the Big Hair (Default Title)",
        description=(
            "Harry hates brushing his hair, but when two doves decide to build a nest "
            "in his tangled mop, he has bigger problems than just avoiding an annoying "
            "comb. As Harry's hair continues to grow more and more tangled, a tree "
            "begins to grow right out of his head! The tree attracts more birds before "
            "their singing starts to drive Harry crazy. Thankfully, his mom comes to "
            "the rescue with a solution, but not before Harry learns a big lesson "
            "about the importance of keeping himself and his hair neat and tidy."
        ),
        sku=f"SKU-{uuid4().hex[:8]}",
        url="https://example.com/product",
        product_group_id=test_product_group.id,
        brand_id=test_brand.id,
        category_id=test_category.id,
        organization_id=test_organization.id,
        raw_data={
            "@cmp:media": [
                {
                    "url": "https://cdn.shopify.com/s/files/1/0421/4502/2103/products/76026-44851-cover.jpg?v=1598680680",
                    "name": "Product Image",
                    "@type": "ImageObject",
                    "width": 838,
                    "height": 768,
                    "caption": "",
                    "encodingFormat": "image/jpeg",
                }
            ]
        },
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_search_results() -> List[Dict[str, Any]]:
    """Test search results."""
    return [
        {
            "id": f"test-product-{uuid4().hex[:8]}",
            "score": 0.95,
            "metadata": {
                "name": "The Boy with the Big Hair",
                "brand": "Test Brand",
                "category": "Children's Books",
                "price": 14.99,
            },
            "product_name": "The Boy with the Big Hair (Default Title)",
            "product_brand": "Test Brand",
            "product_category": "Children's Books",
            "product_price": 14.99,
            "product_description": "Harry hates brushing his hair...",
            "product_url": "https://example.com/product",
            "product_media": [
                {
                    "url": "https://cdn.shopify.com/s/files/1/0421/4502/2103/products/76026-44851-cover.jpg?v=1598680680",
                    "name": "Product Image",
                    "@type": "ImageObject",
                    "width": 838,
                    "height": 768,
                    "caption": "",
                    "encodingFormat": "image/jpeg",
                }
            ],
            "product_offers": [
                {
                    "@type": "Offer",
                    "price": 14.99,
                    "availability": "https://schema.org/OutOfStock",
                    "priceCurrency": "USD",
                    "inventoryLevel": {
                        "@type": "QuantitativeValue",
                        "value": 0,
                    },
                    "priceValidUntil": "2026-07-09T17:15:44.159775",
                }
            ],
        }
    ]


@pytest.fixture
def test_organization_data() -> Dict[str, Any]:
    """Test organization data for service testing."""
    return {
        "name": "Acme Corporation",
        "description": "Acme Corporation is a leading provider of innovative solutions.",
        "url": "https://acme-corp.example.com",
        "logo_url": "https://example.com/assets/acme-logo.png",
        "urn": "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000",
        "feed_url": "https://acme-corp.example.com/feeds/products.json",
        "social_links": [
            "https://www.linkedin.com/company/acme-corp",
            "https://twitter.com/acme_corp"
        ],
        "brand": [
            {
                "name": "WidgetCo",
                "logo_url": "https://example.com/assets/widgetco-logo.png",
                "urn": "urn:cmp:brand:129a4567-e89b-12d3-a456-426614174000",
                "description": "WidgetCo is a leading brand in innovative widgets."
            },
            {
                "name": "GizmoWorks",
                "logo_url": "https://example.com/assets/gizmoworks-logo.png",
                "urn": "urn:cmp:brand:129b4567-e89b-12d3-a456-426614174001",
                "description": "GizmoWorks specializes in cutting-edge gizmos."
            }
        ],
        "raw_data": {
            "@type": "Organization",
            "name": "Acme Corporation",
            "description": "Acme Corporation is a leading provider of innovative solutions.",
            "url": "https://acme-corp.example.com",
            "logo": "https://example.com/assets/acme-logo.png",
            "sameAs": [
                "https://www.linkedin.com/company/acme-corp",
                "https://twitter.com/acme_corp"
            ]
        }
    } 