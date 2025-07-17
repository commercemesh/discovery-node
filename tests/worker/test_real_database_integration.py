# tests/worker/test_real_database_integration.py
"""
Real database integration test that demonstrates actual data persistence.
This test can be run to populate the test database with sample data.
"""
import pytest
import os
import tempfile
import yaml
import json
from pathlib import Path
from unittest.mock import patch
from dotenv import load_dotenv

# Load test environment
load_dotenv("tests/test.env", override=True)

from app.worker.tasks.ingest import ingest_all
from app.ingestors.manager import IngestorManager
from app.db.repositories.organization_repository import OrganizationRepository
from app.db.repositories.brand_repository import BrandRepository
from app.db.repositories.product_group_repository import ProductGroupRepository
from app.db.repositories.category_respository import CategoryRepository


class TestRealDatabaseIntegration:
    """Tests that actually populate the test database for inspection."""

    @pytest.fixture(autouse=True)
    def setup_sample_data(self, tmp_path):
        """Create sample data files using existing samples structure."""
        # Use the existing samples for a real test
        self.samples_dir = Path(__file__).parent.parent.parent / "samples"
        
        # Set DATA_DIR to the samples directory for this test
        self.original_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = str(self.samples_dir)
    
    def teardown_method(self):
        """Restore original DATA_DIR after each test."""
        if self.original_data_dir:
            os.environ["DATA_DIR"] = self.original_data_dir
        else:
            os.environ.pop("DATA_DIR", None)

    @pytest.mark.integration
    def test_populate_test_database_with_acme_data(self, db_session):
        """
        This test populates the test database with Acme Solutions data.
        After running this test, you can inspect the cmp_discovery_test database
        to see actual ingested data.
        """
        ingestor_config = {
            "name": "acme-corp",
            "source_type": "local",
            "registry": "acme-solutions/brand-registory.json",
            "feed_path": "acme-solutions/feed/feed.json"
        }
        
        # Use actual database session (don't mock SessionLocal)
        # This will write real data to the test database
        manager = IngestorManager()
        
        print(f"\\n=== Starting Real Database Integration Test ===")
        print(f"Database URL: {os.environ.get('DATABASE_URL')}")
        print(f"Data directory: {os.environ.get('DATA_DIR')}")
        
        # Ingest registry
        print("\\n1. Ingesting registry data...")
        registry_result = manager.ingest_registry(ingestor_config)
        print(f"Registry result: {registry_result['status']}")
        
        # Verify registry data was written
        org_repo = OrganizationRepository(db_session)
        organizations = org_repo.list()
        print(f"Organizations in database: {len(organizations)}")
        for org in organizations:
            print(f"  - {org.name} ({org.urn})")
        
        brand_repo = BrandRepository(db_session)
        brands = brand_repo.list()
        print(f"Brands in database: {len(brands)}")
        for brand in brands:
            print(f"  - {brand.name} ({brand.urn})")
        
        # Ingest feed
        print("\\n2. Ingesting feed data...")
        feed_result = manager.ingest_feed(ingestor_config)
        print(f"Feed result: {feed_result['status']}")
        
        # Verify feed data was written
        product_group_repo = ProductGroupRepository(db_session)
        product_groups = product_group_repo.list()
        print(f"Product groups in database: {len(product_groups)}")
        for pg in product_groups[:5]:  # Show first 5
            print(f"  - {pg.name} ({pg.urn})")
        if len(product_groups) > 5:
            print(f"  ... and {len(product_groups) - 5} more")
        
        # Ingest vectors
        print("\\n3. Ingesting vector data...")
        vector_result = manager.ingest_vector(ingestor_config)
        print(f"Vector result: {vector_result['status']}")
        
        # Show categories
        category_repo = CategoryRepository(db_session)
        categories = category_repo.list()
        print(f"Categories in database: {len(categories)}")
        for cat in categories:
            print(f"  - {cat.name}")
        
        print(f"\\n=== Test Database Population Complete ===")
        print(f"You can now inspect the 'cmp_discovery_test' database to see the ingested data.")
        print(f"Total organizations: {len(organizations)}")
        print(f"Total brands: {len(brands)}")
        print(f"Total product groups: {len(product_groups)}")
        print(f"Total categories: {len(categories)}")
        
        # Assertions to ensure the test passes
        assert len(organizations) > 0, "No organizations were ingested"
        assert len(brands) > 0, "No brands were ingested"
        assert len(product_groups) > 0, "No product groups were ingested"
        assert len(categories) > 0, "No categories were ingested"
        
        # Verify specific data
        acme_org = next((org for org in organizations if "acme" in org.name.lower()), None)
        assert acme_org is not None, "Acme organization not found"
        
        return {
            "organizations": len(organizations),
            "brands": len(brands), 
            "product_groups": len(product_groups),
            "categories": len(categories)
        }

    @pytest.mark.integration
    def test_using_ingest_all_task(self, db_session):
        """Test using the actual ingest_all Celery task."""
        ingestor_config = {
            "name": "acme-corp-task",
            "source_type": "local",
            "registry": "acme-solutions/brand-registory.json",
            "feed_path": "acme-solutions/feed/feed.json"
        }
        
        print(f"\\n=== Testing ingest_all Task ===")
        
        # Call the actual task function (not the Celery task)
        result = ingest_all("acme-corp-task", ingestor_config)
        
        print(f"Task result status: {result['status']}")
        print(f"Registry status: {result['results']['registry']['status']}")
        print(f"Feed status: {result['results']['feed']['status']}")
        print(f"Vector status: {result['results']['vector']['status']}")
        
        # Verify task completed successfully
        assert result["status"] == "success"
        assert result["results"]["registry"]["status"] == "success"
        assert result["results"]["feed"]["status"] == "success"
        assert result["results"]["vector"]["status"] == "success"
        
        # Verify data exists in database
        org_repo = OrganizationRepository(db_session)
        organizations = org_repo.list()
        assert len(organizations) > 0
        
        print(f"Successfully ingested data using ingest_all task!")
        return result