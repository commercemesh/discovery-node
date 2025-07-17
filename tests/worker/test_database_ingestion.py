# tests/worker/test_database_ingestion.py
"""
Integration tests for worker ingestion tasks that write to the test database.
"""
import pytest
import os
import tempfile
import yaml
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from celery.result import AsyncResult
from dotenv import load_dotenv

# Load test environment
load_dotenv("tests/test.env", override=True)

from app.worker.tasks.ingest import (
    ingest_all,
    ingest_registry,
    ingest_feed,
    ingest_vector,
    schedule_all_ingestors,
)
from app.worker.schedulers import get_beat_schedule
from app.ingestors.manager import IngestorManager
from app.db.repositories.organization_repository import OrganizationRepository
from app.db.repositories.brand_repository import BrandRepository
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.product_group_repository import ProductGroupRepository
from app.db.repositories.category_respository import CategoryRepository
from app.db.base import SessionLocal


class TestDatabaseIngestion:
    """Integration tests that write actual data to the test database."""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, tmp_path):
        """Create test data files for ingestion."""
        # Create test data directory that mimics the samples structure
        test_data_dir = tmp_path / "test_samples"
        test_data_dir.mkdir(exist_ok=True)
        
        # Create test registry data
        registry_data = {
            "@context": {
                "schema": "https://schema.org",
                "cmp": "https://schema.commercemesh.ai/ns#"
            },
            "@type": "Organization",
            "name": "Test Organization",
            "description": "Test organization for integration tests",
            "url": "https://test-org.example.com",
            "identifier": {
                "@type": "PropertyValue",
                "propertyID": "cmp:orgId",
                "value": "urn:cmp:orgid:test-org-001"
            },
            "brand": [
                {
                    "@type": "Brand",
                    "name": "TestBrand1",
                    "description": "First test brand",
                    "logo": "https://example.com/testbrand1-logo.png",
                    "identifier": {
                        "@type": "PropertyValue",
                        "propertyID": "cmp:brandId",
                        "value": "urn:cmp:brand:test-brand-001"
                    }
                },
                {
                    "@type": "Brand",
                    "name": "TestBrand2",
                    "description": "Second test brand",
                    "logo": "https://example.com/testbrand2-logo.png",
                    "identifier": {
                        "@type": "PropertyValue",
                        "propertyID": "cmp:brandId",
                        "value": "urn:cmp:brand:test-brand-002"
                    }
                }
            ],
            "cmp:category": ["electronics", "gadgets"],
            "cmp:productFeed": {
                "@type": "DataFeed",
                "url": "feed.json"
            }
        }
        
        # Create test feed index data
        feed_index_data = {
            "@context": "https://schema.commercemesh.org/v0.1",
            "@type": "ProductFeedIndex",
            "version": "0.1",
            "lastUpdated": "2025-07-17T00:00:00Z",
            "totalShards": 1,
            "organization": {
                "urn": "urn:cmp:orgid:test-org-001",
                "name": "Test Organization"
            },
            "shards": [
                {
                    "url": "test-feed-shard.json",
                    "lastUpdated": "2025-07-17T00:00:00Z"
                }
            ]
        }
        
        # Create test feed shard data
        feed_shard_data = {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:test-product-001",
                        "name": "Test Product 1",
                        "description": "First test product",
                        "brand": {
                            "@type": "Brand",
                            "name": "TestBrand1"
                        },
                        "category": "electronics",
                        "productGroupID": "test-product-001",
                        "variesBy": ["size"],
                        "hasVariant": [
                            {
                                "@type": "Product",
                                "name": "Test Product 1",
                                "sku": "TEST-001",
                                "offers": {
                                    "@type": "Offer",
                                    "price": "99.99",
                                    "priceCurrency": "USD",
                                    "availability": "https://schema.org/InStock"
                                }
                            }
                        ]
                    }
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "item": {
                        "@context": "https://schema.org",
                        "@type": "ProductGroup",
                        "@id": "urn:cmp:product:test-product-002",
                        "name": "Test Product 2",
                        "description": "Second test product",
                        "brand": {
                            "@type": "Brand",
                            "name": "TestBrand2"
                        },
                        "category": "gadgets",
                        "productGroupID": "test-product-002",
                        "variesBy": ["color"],
                        "hasVariant": [
                            {
                                "@type": "Product",
                                "name": "Test Product 2",
                                "sku": "TEST-002",
                                "offers": {
                                    "@type": "Offer",
                                    "price": "149.99",
                                    "priceCurrency": "USD",
                                    "availability": "https://schema.org/InStock"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        
        # Write registry file
        registry_file = test_data_dir / "test-registry.json"
        with open(registry_file, "w") as f:
            json.dump(registry_data, f, indent=2)
        
        # Write feed index file
        feed_file = test_data_dir / "test-feed.json"
        with open(feed_file, "w") as f:
            json.dump(feed_index_data, f, indent=2)
            
        # Write feed shard file
        feed_shard_file = test_data_dir / "test-feed-shard.json"
        with open(feed_shard_file, "w") as f:
            json.dump(feed_shard_data, f, indent=2)
        
        self.test_data_dir = test_data_dir
        self.registry_file = str(registry_file)
        self.feed_file = str(feed_file)
        self.feed_shard_file = str(feed_shard_file)
        
        # Store original DATA_DIR and set to test directory
        self.original_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = str(test_data_dir)
    
    def teardown_method(self):
        """Restore original DATA_DIR after each test."""
        if self.original_data_dir:
            os.environ["DATA_DIR"] = self.original_data_dir
        else:
            os.environ.pop("DATA_DIR", None)

    @pytest.fixture
    def temp_ingestion_config_db(self):
        """Create a temporary ingestion config file for database tests."""
        config_content = f"""
ingestion:
  - name: "test-db-ingestor"
    source_type: "local"
    registry: "{os.path.basename(self.registry_file)}"
    feed_path: "{os.path.basename(self.feed_file)}"
    schedule: "0 */4 * * *"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)

    def test_ingest_registry_to_database(self, db_session):
        """Test that registry ingestion writes data to the database."""
        ingestor_config = {
            "name": "test-db-ingestor",
            "source_type": "local",
            "registry": os.path.basename(self.registry_file)
        }
        
        # Mock SessionLocal to return our test session
        with patch('app.ingestors.manager.SessionLocal') as mock_session_local:
            mock_session_local.return_value = db_session
            # Also patch the settings to ensure DATA_DIR is used
            with patch('app.ingestors.sources.local.settings') as mock_settings:
                mock_settings.DATA_DIR = str(self.test_data_dir)
                # Create manager and run registry ingestion
                manager = IngestorManager()
                result = manager.ingest_registry(ingestor_config)
        
        # Verify data was written to database
        org_repo = OrganizationRepository(db_session)
        organizations = org_repo.list()
        assert len(organizations) == 1
        assert organizations[0].name == "Test Organization"
        assert organizations[0].urn == "urn:cmp:orgid:test-org-001"
        
        brand_repo = BrandRepository(db_session)
        brands = brand_repo.list()
        assert len(brands) == 2
        brand_names = [b.name for b in brands]
        assert "TestBrand1" in brand_names
        assert "TestBrand2" in brand_names

    def test_ingest_feed_to_database(self, db_session):
        """Test that feed ingestion writes product data to the database."""
        # First ingest registry to create organization and brands
        ingestor_config = {
            "name": "test-db-ingestor",
            "source_type": "local",
            "registry": os.path.basename(self.registry_file),
            "feed_path": os.path.basename(self.feed_file)
        }
        
        # Mock SessionLocal to return our test session
        with patch('app.ingestors.manager.SessionLocal') as mock_session_local:
            mock_session_local.return_value = db_session
            # Also patch the settings to ensure DATA_DIR is used
            with patch('app.ingestors.sources.local.settings') as mock_settings:
                mock_settings.DATA_DIR = str(self.test_data_dir)
                # Create manager
                manager = IngestorManager()
                
                # First ingest registry
                registry_result = manager.ingest_registry(ingestor_config)
                assert registry_result["status"] == "success"
                assert "result" in registry_result
                
                # Then ingest feed
                feed_result = manager.ingest_feed(ingestor_config)
                assert feed_result["status"] == "success"
                assert "result" in feed_result
        
        # Verify product groups were written to database
        product_group_repo = ProductGroupRepository(db_session)
        product_groups = product_group_repo.list()
        assert len(product_groups) == 2
        
        group_names = [pg.name for pg in product_groups]
        assert "Test Product 1" in group_names
        assert "Test Product 2" in group_names
        
        # Verify product group details
        group1 = next(pg for pg in product_groups if pg.name == "Test Product 1")
        assert group1.urn == "urn:cmp:product:test-product-001"

    def test_ingest_all_task_with_database(self, db_session):
        """Test the complete ingest_all task with database writes."""
        ingestor_config = {
            "name": "test-db-ingestor",
            "source_type": "local",
            "registry": os.path.basename(self.registry_file),
            "feed_path": os.path.basename(self.feed_file)
        }
        
        # Mock SessionLocal to return our test session for all manager instances
        with patch('app.ingestors.manager.SessionLocal') as mock_session_local:
            mock_session_local.return_value = db_session
            # Also patch the settings to ensure DATA_DIR is used
            with patch('app.ingestors.sources.local.settings') as mock_settings:
                mock_settings.DATA_DIR = str(self.test_data_dir)
                # Run the ingest_all task
                result = ingest_all("test-db-ingestor", ingestor_config)
        
        assert result["status"] == "success"
        assert result["results"]["registry"]["status"] == "success"
        assert result["results"]["feed"]["status"] == "success"
        
        # Verify all data in database
        org_repo = OrganizationRepository(db_session)
        assert len(org_repo.list()) == 1
        
        brand_repo = BrandRepository(db_session)
        assert len(brand_repo.list()) == 2
        
        # Verify product groups were created
        product_group_repo = ProductGroupRepository(db_session)
        product_groups = product_group_repo.list()
        assert len(product_groups) == 2
        
        category_repo = CategoryRepository(db_session)
        categories = category_repo.list()
        assert len(categories) > 0
        category_names = [c.name for c in categories]
        assert "electronics" in category_names
        assert "gadgets" in category_names

    def test_schedule_with_database_config(self, temp_ingestion_config_db):
        """Test that scheduled tasks can be created with database configuration."""
        with patch('app.worker.schedulers.settings') as mock_settings:
            mock_settings.INGESTION_CONFIG_PATH = temp_ingestion_config_db
            mock_settings.FEED_CHECK_INTERVAL = 300
            
            schedule = get_beat_schedule()
            
            assert "ingest-all-test-db-ingestor" in schedule
            task = schedule["ingest-all-test-db-ingestor"]
            assert task["task"] == "ingest:all"
            assert task["args"][0] == "test-db-ingestor"

    def test_error_handling_with_database(self, db_session):
        """Test error handling when database operations fail."""
        ingestor_config = {
            "name": "test-db-ingestor",
            "source_type": "local",
            "registry": "non-existent-file.json"
        }
        
        # Mock SessionLocal to return our test session
        with patch('app.ingestors.manager.SessionLocal') as mock_session_local:
            mock_session_local.return_value = db_session
            # Also patch the settings to ensure DATA_DIR is used
            with patch('app.ingestors.sources.local.settings') as mock_settings:
                mock_settings.DATA_DIR = str(self.test_data_dir)
                manager = IngestorManager()
                # This should handle the error gracefully
                result = manager.ingest_registry(ingestor_config)
            
        assert result["status"] == "error"
        assert "error_message" in result
        
        # Verify no partial data was written
        org_repo = OrganizationRepository(db_session)
        assert len(org_repo.list()) == 0