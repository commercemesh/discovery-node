# tests/worker/test_basic_setup.py
"""
Basic setup tests to verify the test environment is working correctly.
"""
import pytest
import os
import yaml
from pathlib import Path

def test_environment_variables():
    """Test that environment variables can be set and read."""
    # Test setting environment variables
    os.environ['TEST_VAR'] = 'test_value'
    assert os.environ['TEST_VAR'] == 'test_value'

def test_yaml_loading():
    """Test that YAML files can be loaded."""
    test_config = {
        "ingestion": [
            {
                "name": "test-ingestor",
                "source_type": "test",
                "schedule": "0 */4 * * *"
            }
        ]
    }
    
    # Test YAML dump and load
    yaml_str = yaml.dump(test_config)
    loaded_config = yaml.safe_load(yaml_str)
    
    assert loaded_config == test_config
    assert "ingestion" in loaded_config
    assert len(loaded_config["ingestion"]) == 1
    assert loaded_config["ingestion"][0]["name"] == "test-ingestor"

def test_config_file_paths():
    """Test that configuration files exist."""
    config_1_path = Path("tests/ingestion_test_config_1.yaml")
    config_2_path = Path("tests/ingestion_test_config_2.yaml")
    
    assert config_1_path.exists(), f"Config file 1 not found: {config_1_path}"
    assert config_2_path.exists(), f"Config file 2 not found: {config_2_path}"

def test_config_file_contents():
    """Test that configuration files have valid content."""
    config_1_path = Path("tests/ingestion_test_config_1.yaml")
    config_2_path = Path("tests/ingestion_test_config_2.yaml")
    
    # Test config 1
    with open(config_1_path, 'r') as f:
        config_1 = yaml.safe_load(f)
    
    assert "ingestion" in config_1
    assert len(config_1["ingestion"]) == 1
    assert config_1["ingestion"][0]["name"] == "insight-editions"
    assert config_1["ingestion"][0]["source_type"] == "cmp"
    
    # Test config 2
    with open(config_2_path, 'r') as f:
        config_2 = yaml.safe_load(f)
    
    assert "ingestion" in config_2
    assert len(config_2["ingestion"]) == 1
    assert config_2["ingestion"][0]["name"] == "acme-corp"
    assert config_2["ingestion"][0]["source_type"] == "local"

def test_imports():
    """Test that required modules can be imported."""
    try:
        from app.worker.tasks.ingest import ingest_all, ingest_registry, ingest_feed, ingest_vector
        from app.worker.schedulers import get_beat_schedule
        from app.ingestors.manager import IngestorManager
        assert True, "All imports successful"
    except ImportError as e:
        pytest.fail(f"Import failed: {e}")

def test_mock_functionality():
    """Test that mocking works correctly."""
    from unittest.mock import patch, MagicMock
    
    # Test basic mocking
    with patch('builtins.print') as mock_print:
        print("test")
        mock_print.assert_called_once_with("test")
    
    # Test MagicMock
    mock_obj = MagicMock()
    mock_obj.some_method.return_value = "test_result"
    assert mock_obj.some_method() == "test_result" 