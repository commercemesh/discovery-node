#!/usr/bin/env python3
"""
Script to run worker tests with different ingestion configurations.
"""
import os
import sys
import subprocess
from pathlib import Path

def run_tests_with_config(config_file: str, description: str):
    """Run tests with a specific ingestion configuration file."""
    print(f"\n{'='*60}")
    print(f"RUNNING TESTS WITH {description}")
    print(f"Config file: {config_file}")
    print(f"{'='*60}")
    
    # Set environment variables
    env = os.environ.copy()
    env['INGESTION_CONFIG_PATH'] = str(Path(config_file).absolute())
    # Load from .env.test file
    from dotenv import load_dotenv
    load_dotenv(".env.test", override=True)
    # Override with test-specific settings
    env['TRIGGER_INGESTION_ON_STARTUP'] = "false"
    env['FEED_CHECK_INTERVAL'] = "60"
    
    # Run pytest
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/worker/test_worker_ingestion.py",
        "-v",
        "--tb=short"
    ]
    
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        print("STDOUT:")
        print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        success = result.returncode == 0
        print(f"\nResult: {'PASSED' if success else 'FAILED'}")
        return success
        
    except Exception as e:
        print(f"Error running tests: {e}")
        return False

def main():
    """Main function to run tests with different configurations."""
    print("Worker Test Runner")
    print("Testing worker functionality with different ingestion configurations")
    
    # Test with configuration 1 (CMP feeds)
    config_1 = "tests/ingestion_test_config_1.yaml"
    success_1 = run_tests_with_config(config_1, "CONFIGURATION 1 (CMP FEEDS)")
    
    # Test with configuration 2 (Local feeds)
    config_2 = "tests/ingestion_test_config_2.yaml"
    success_2 = run_tests_with_config(config_2, "CONFIGURATION 2 (LOCAL FEEDS)")
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Configuration 1 (CMP): {'PASSED' if success_1 else 'FAILED'}")
    print(f"Configuration 2 (Local): {'PASSED' if success_2 else 'FAILED'}")
    
    overall_success = success_1 and success_2
    print(f"\nOverall Result: {'ALL TESTS PASSED' if overall_success else 'SOME TESTS FAILED'}")
    
    return 0 if overall_success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 