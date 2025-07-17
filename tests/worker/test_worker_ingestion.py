# tests/worker/test_worker_ingestion.py
"""
Tests for worker ingestion tasks with different ingestion configurations.
"""
import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
from celery.result import AsyncResult

from app.worker.tasks.ingest import (
    ingest_all,
    ingest_registry,
    ingest_feed,
    ingest_vector,
    schedule_all_ingestors,
)
from app.worker.schedulers import get_beat_schedule
from app.ingestors.manager import IngestorManager


@pytest.fixture
def mock_ingestor_manager():
    """Mock the IngestorManager to avoid actual ingestion."""
    with patch('app.worker.tasks.ingest.IngestorManager') as mock_manager:
        # Mock the manager instance
        mock_instance = MagicMock()
        mock_manager.return_value = mock_instance
        
        # Mock the ingest methods
        mock_instance.ingest_registry.return_value = {
            "status": "success",
            "processed": 5,
            "errors": []
        }
        mock_instance.ingest_feed.return_value = {
            "status": "success",
            "processed": 10,
            "errors": []
        }
        mock_instance.ingest_vector.return_value = {
            "status": "success",
            "processed": 5,
            "errors": []
        }
        mock_instance.get_ingestors.return_value = [
            {
                "name": "test-ingestor",
                "source_type": "test",
                "registry": "test-registry.json",
                "feed_path": "test-feed.json"
            }
        ]
        
        yield mock_instance


class TestWorkerIngestion:
    """Test worker ingestion tasks with different configurations."""

    @pytest.fixture
    def temp_ingestion_config_1(self):
        """Create a temporary ingestion config file for test config 1."""
        config_content = """
ingestion:
  - name: "insight-editions"
    source_type: "cmp"
    registry: "https://github.com/commercemesh/commercemesh/blob/main/registry/example/brands.json"
    filter:
      organization: ["urn:cmp:orgid:22eefabc-7b1d-6d29-9e12-22g812190dd3"]
    schedule: "0 */4 * * *"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)

    @pytest.fixture
    def temp_ingestion_config_2(self):
        """Create a temporary ingestion config file for test config 2."""
        config_content = """
ingestion:
  - name: "acme-corp"
    source_type: "local"
    registry: "samples/acme-solutions/brand-registory.json"
    feed_path: "samples/acme-solutions/feed/feed.json"
    schedule: "0 */4 * * *"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)

    def test_ingest_all_with_config_1(self, temp_ingestion_config_1, mock_ingestor_manager):
        """Test ingest_all task with CMP configuration."""
        ingestor_config = {
            "name": "insight-editions",
            "source_type": "cmp",
            "registry": "https://github.com/commercemesh/commercemesh/blob/main/registry/example/brands.json",
            "filter": {
                "organization": ["urn:cmp:orgid:22eefabc-7b1d-6d29-9e12-22g812190dd3"]
            },
            "schedule": "0 */4 * * *"
        }
        
        # Test the ingest_all task
        result = ingest_all("insight-editions", ingestor_config)
        
        assert result["status"] == "success"
        assert "results" in result
        assert result["results"]["registry"]["status"] == "success"
        assert result["results"]["feed"]["status"] == "skipped"  # No feed_path in config
        assert result["results"]["vector"]["status"] == "success"
        
        # Verify the manager was called correctly
        mock_ingestor_manager.ingest_registry.assert_called_once_with(ingestor_config)
        mock_ingestor_manager.ingest_vector.assert_called_once_with(ingestor_config)
        mock_ingestor_manager.ingest_feed.assert_not_called()

    def test_ingest_all_with_config_2(self, temp_ingestion_config_2, mock_ingestor_manager):
        """Test ingest_all task with local configuration."""
        ingestor_config = {
            "name": "acme-corp",
            "source_type": "local",
            "registry": "samples/acme-solutions/brand-registory.json",
            "feed_path": "samples/acme-solutions/feed/feed.json",
            "schedule": "0 */4 * * *"
        }
        
        # Test the ingest_all task
        result = ingest_all("acme-corp", ingestor_config)
        
        assert result["status"] == "success"
        assert "results" in result
        assert result["results"]["registry"]["status"] == "success"
        assert result["results"]["feed"]["status"] == "success"
        assert result["results"]["vector"]["status"] == "success"
        
        # Verify the manager was called correctly
        mock_ingestor_manager.ingest_registry.assert_called_once_with(ingestor_config)
        mock_ingestor_manager.ingest_feed.assert_called_once_with(ingestor_config)
        mock_ingestor_manager.ingest_vector.assert_called_once_with(ingestor_config)

    def test_ingest_registry_task(self, mock_ingestor_manager):
        """Test ingest_registry task."""
        ingestor_config = {
            "name": "test-ingestor",
            "source_type": "test",
            "registry": "test-registry.json"
        }
        
        # Test the ingest_registry task
        result = ingest_registry("test-ingestor", ingestor_config)
        
        assert result["status"] == "success"
        assert result["ingestor"] == "test-ingestor"
        assert result["type"] == "registry"
        assert result["source_type"] == "test"
        assert result["path"] == "test-registry.json"
        
        mock_ingestor_manager.ingest_registry.assert_called_once_with(ingestor_config)

    def test_ingest_feed_task(self, mock_ingestor_manager):
        """Test ingest_feed task."""
        ingestor_config = {
            "name": "test-ingestor",
            "source_type": "test",
            "feed_path": "test-feed.json"
        }
        
        # Test the ingest_feed task
        result = ingest_feed("test-ingestor", ingestor_config)
        
        assert result["status"] == "success"
        assert result["ingestor"] == "test-ingestor"
        assert result["type"] == "feed"
        assert result["source_type"] == "test"
        assert result["path"] == "test-feed.json"
        
        mock_ingestor_manager.ingest_feed.assert_called_once_with(ingestor_config)

    def test_ingest_vector_task(self, mock_ingestor_manager):
        """Test ingest_vector task."""
        ingestor_config = {
            "name": "test-ingestor",
            "source_type": "test",
            "registry": "test-registry.json"
        }
        
        # Test the ingest_vector task
        result = ingest_vector("test-ingestor", ingestor_config)
        
        assert result["status"] == "success"
        assert result["ingestor"] == "test-ingestor"
        assert result["type"] == "vector"
        assert result["source_type"] == "test"
        assert result["path"] == "test-registry.json"
        
        mock_ingestor_manager.ingest_vector.assert_called_once_with(ingestor_config)

    def test_schedule_all_ingestors(self, mock_ingestor_manager):
        """Test schedule_all_ingestors task."""
        # Test the schedule_all_ingestors task
        result = schedule_all_ingestors()
        
        assert result["status"] == "success"
        assert "message" in result
        assert "Scheduled 1 ingestors" in result["message"]
        
        mock_ingestor_manager.get_ingestors.assert_called_once()

    def test_get_beat_schedule_with_config_1(self, temp_ingestion_config_1):
        """Test get_beat_schedule with CMP configuration."""
        # Mock the settings object to use our temp config file
        with patch('app.worker.schedulers.settings') as mock_settings:
            mock_settings.INGESTION_CONFIG_PATH = temp_ingestion_config_1
            mock_settings.FEED_CHECK_INTERVAL = 300
            
            schedule = get_beat_schedule()
            assert "check-feed-updates" in schedule
            assert "ingest-all-insight-editions" in schedule
            insight_task = schedule["ingest-all-insight-editions"]
            assert insight_task["task"] == "ingest:all"
            assert "args" in insight_task
            assert insight_task["args"][0] == "insight-editions"

    def test_get_beat_schedule_with_config_2(self, temp_ingestion_config_2):
        """Test get_beat_schedule with local configuration."""
        # Mock the settings object to use our temp config file
        with patch('app.worker.schedulers.settings') as mock_settings:
            mock_settings.INGESTION_CONFIG_PATH = temp_ingestion_config_2
            mock_settings.FEED_CHECK_INTERVAL = 300
            
            schedule = get_beat_schedule()
            assert "check-feed-updates" in schedule
            assert "ingest-all-acme-corp" in schedule
            acme_task = schedule["ingest-all-acme-corp"]
            assert acme_task["task"] == "ingest:all"
            assert "args" in acme_task
            assert acme_task["args"][0] == "acme-corp"

    def test_ingest_all_error_handling(self, mock_ingestor_manager):
        """Test error handling in ingest_all task."""
        # Configure mock to raise an exception
        mock_ingestor_manager.ingest_registry.side_effect = Exception("Test error")
        
        ingestor_config = {
            "name": "test-ingestor",
            "source_type": "test",
            "registry": "test-registry.json"
        }
        
        # Test the ingest_all task with error
        result = ingest_all("test-ingestor", ingestor_config)
        
        assert result["status"] == "error"
        assert result["step"] == "registry"
        assert "results" in result
        assert result["results"]["registry"]["status"] == "error"
        assert "Test error" in result["results"]["registry"]["error"]

    def test_ingest_all_retry_mechanism(self, mock_ingestor_manager):
        """Test retry mechanism in ingest tasks."""
        # Configure mock to raise an exception
        mock_ingestor_manager.ingest_registry.side_effect = Exception("Test error")
        
        ingestor_config = {
            "name": "test-ingestor",
            "source_type": "test",
            "registry": "test-registry.json"
        }
        
        # Test retry mechanism by catching the exception
        # Since we're calling the task directly without Celery, it will raise
        with pytest.raises(Exception) as exc_info:
            ingest_registry("test-ingestor", ingestor_config)
        
        # Verify the exception message
        assert str(exc_info.value) == "Test error"
        
        # Verify the manager was called
        mock_ingestor_manager.ingest_registry.assert_called_once_with(ingestor_config)


class TestWorkerIntegration:
    """Integration tests for worker functionality."""
    
    @pytest.fixture
    def test_environment(self):
        """Set up test environment variables."""
        original_env = os.environ.copy()
        
        # Set test environment variables
        os.environ.update({
            "DATABASE_URL": "postgresql://postgres:admin@localhost:5432/cmp_discovery_test",
            "CELERY_BROKER_URL": "redis://localhost:6379/1",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/1",
            "TRIGGER_INGESTION_ON_STARTUP": "false",
            "FEED_CHECK_INTERVAL": "60"
        })
        
        yield
        
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)

    def test_worker_configuration_loading(self, test_environment):
        """Test that worker can load configuration from environment."""
        # Test that the configuration can be loaded
        schedule = get_beat_schedule()
        
        # Should have at least the default tasks
        assert "check-feed-updates" in schedule

    def test_worker_task_execution_flow(self, test_environment, mock_ingestor_manager):
        """Test the complete task execution flow."""
        ingestor_config = {
            "name": "integration-test",
            "source_type": "test",
            "registry": "test-registry.json",
            "feed_path": "test-feed.json"
        }
        
        # Test the complete flow
        result = ingest_all("integration-test", ingestor_config)
        
        # Verify all steps were executed
        assert result["status"] == "success"
        assert result["results"]["registry"]["status"] == "success"
        assert result["results"]["feed"]["status"] == "success"
        assert result["results"]["vector"]["status"] == "success"
        
        # Verify manager calls
        mock_ingestor_manager.ingest_registry.assert_called_once()
        mock_ingestor_manager.ingest_feed.assert_called_once()
        mock_ingestor_manager.ingest_vector.assert_called_once() 