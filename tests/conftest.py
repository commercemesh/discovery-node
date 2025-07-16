# tests/conftest.py
import os
import sys
from pathlib import Path

import alembic.config
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from app.api.web_app import app

from app.db.base import get_db_session
from app.services.brand_service import BrandService
from app.services.category_service import CategoryService
from app.services.organization_service import OrganizationService
from app.services.product_service import ProductService
from app.services.search_service import SearchService

# Import test data fixtures, do not remove
from tests.fixtures.test_data import (
    test_brand,
    test_category,
    test_offer,
    test_organization,
    test_organization_data,
    test_product,
    test_product_group,
    test_search_results,
)

# Test database configuration
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/cmp_discovery_test",
)

if "cmp_discovery_test" not in TEST_DATABASE_URL:
    raise RuntimeError(
        f"TEST_DATABASE_URL is not using the test DB! Value: {TEST_DATABASE_URL}"
    )


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine."""
    engine = create_engine(TEST_DATABASE_URL)

    # Set environment variable for migrations
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    # Run Alembic downgrade to base, then upgrade to head
    alembic_ini_path = Path(__file__).parent.parent / "alembic.ini"
    alembic_cfg = alembic.config.Config(str(alembic_ini_path.resolve()))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    try:
        alembic.command.downgrade(alembic_cfg, "base")
        alembic.command.upgrade(alembic_cfg, "head")
    except Exception as e:
        print(f"Warning: Could not run migrations: {e}")

    yield engine

    # Cleanup
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session."""
    connection = db_engine.connect()
    transaction = connection.begin()

    Session = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = Session()

    yield session

    # Roll back transaction to undo any changes
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_db_session(db_session):
    """Test database session for dependency injection."""
    return db_session


@pytest.fixture
def app_with_test_db(test_db_session):
    """App with test database dependency."""

    def _get_test_db_session():
        yield test_db_session

    app.dependency_overrides[get_db_session] = _get_test_db_session
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def product_service(db_session):
    """Create a product service for testing."""
    return ProductService(db_session)


@pytest.fixture
def brand_service(db_session):
    """Create a brand service for testing."""
    return BrandService(db_session)


@pytest.fixture
def category_service(db_session):
    """Create a category service for testing."""
    return CategoryService(db_session)


@pytest.fixture
def organization_service(db_session):
    """Create an organization service for testing."""
    return OrganizationService(db_session)


@pytest.fixture
def search_service(db_session):
    """Create a search service for testing."""
    return SearchService(db_session)
