# tests/worker/test_runner.py
"""
Test runner for worker tests with different ingestion configurations.
"""
import os
import sys
import subprocess
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(project_root))


def create_test_config(config_data: Dict[str, Any], config_name: str) -> str:
    """Create a temporary test configuration file."""
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
    yaml.dump(config_data, temp_file)
    temp_file.close()
    return temp_file.name


def run_tests_with_config(config_path: str, test_pattern: str = "test_worker_ingestion.py"):
    """Run tests with a specific ingestion configuration."""
    # Set environment variables for the test run
    env = os.environ.copy()
    env['INGESTION_CONFIG_PATH'] = config_path
    # Load from .env.test file
    from dotenv import load_dotenv
    load_dotenv(".env.test", override=True)
    # Override with test-specific settings
    env['TRIGGER_INGESTION_ON_STARTUP'] = "false"
    env['FEED_CHECK_INTERVAL'] = "60"
    
    # Run pytest with the specific configuration
    cmd = [
        sys.executable, "-m", "pytest",
        f"tests/worker/{test_pattern}",
        "-v",
        "--tb=short"
    ]
    
    print(f"Running tests with config: {config_path}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return False


def main():
    """Main test runner function."""
    print("Starting worker tests with different configurations...")
    
    # Configuration 1: CMP feeds
    config_1 = {
        "ingestion": [
            {
                "name": "insight-editions",
                "source_type": "cmp",
                "registry": "https://github.com/commercemesh/commercemesh/blob/main/registry/example/brands.json",
                "filter": {
                    "organization": ["urn:cmp:orgid:22eefabc-7b1d-6d29-9e12-22g812190dd3"]
                },
                "schedule": "0 */4 * * *"
            }
        ]
    }
    
    # Configuration 2: Local feeds
    config_2 = {
        "ingestion": [
            {
                "name": "acme-corp",
                "source_type": "local",
                "registry": "samples/acme-solutions/brand-registory.json",
                "feed_path": "samples/acme-solutions/feed/feed.json",
                "schedule": "0 */4 * * *"
            }
        ]
    }
    
    # Create temporary config files
    config_1_path = create_test_config(config_1, "config_1")
    config_2_path = create_test_config(config_2, "config_2")
    
    try:
        # Run tests with configuration 1
        print("\n" + "="*50)
        print("RUNNING TESTS WITH CONFIGURATION 1 (CMP FEEDS)")
        print("="*50)
        success_1 = run_tests_with_config(config_1_path)
        
        # Run tests with configuration 2
        print("\n" + "="*50)
        print("RUNNING TESTS WITH CONFIGURATION 2 (LOCAL FEEDS)")
        print("="*50)
        success_2 = run_tests_with_config(config_2_path)
        
        # Summary
        print("\n" + "="*50)
        print("TEST SUMMARY")
        print("="*50)
        print(f"Configuration 1 (CMP): {'PASSED' if success_1 else 'FAILED'}")
        print(f"Configuration 2 (Local): {'PASSED' if success_2 else 'FAILED'}")
        
        overall_success = success_1 and success_2
        print(f"\nOverall Result: {'ALL TESTS PASSED' if overall_success else 'SOME TESTS FAILED'}")
        
        return 0 if overall_success else 1
        
    finally:
        # Cleanup temporary files
        try:
            os.unlink(config_1_path)
            os.unlink(config_2_path)
        except Exception as e:
            print(f"Warning: Could not cleanup temporary files: {e}")


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 