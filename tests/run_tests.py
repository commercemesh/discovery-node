#!/usr/bin/env python3
"""
Test runner script for the discovery-node project.
This script helps run tests with proper database configuration.
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_test_environment():
    """Setup test environment variables"""
    # Set test database URL
    os.environ["TEST_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/cmp_discovery_test"
    
    # Set other test-specific environment variables
    os.environ["DEBUG"] = "true"
    os.environ["LOG_LEVEL"] = "debug"
    
    print("✅ Test environment configured")
    print(f"   Test Database: {os.environ['TEST_DATABASE_URL']}")

def run_tests(test_path=None, verbose=False):
    """Run pytest with proper configuration"""
    cmd = ["python", "-m", "pytest"]
    
    if verbose:
        cmd.append("-v")
    
    if test_path:
        cmd.append(test_path)
    else:
        cmd.append("tests/")
    
    # Add pytest options
    cmd.extend([
        "--tb=short",
        "--strict-markers",
        "--disable-warnings"
    ])
    
    print(f"🚀 Running tests with command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("✅ All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed with exit code: {e.returncode}")
        return False

def run_specific_test(test_file):
    """Run a specific test file"""
    test_path = f"tests/{test_file}"
    if not Path(test_path).exists():
        print(f"❌ Test file not found: {test_path}")
        return False
    
    print(f"🎯 Running specific test: {test_path}")
    return run_tests(test_path, verbose=True)

def main():
    """Main function"""
    print("🧪 Discovery Node Test Runner")
    print("=" * 40)
    
    # Setup environment
    setup_test_environment()
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        success = run_specific_test(test_file)
    else:
        success = run_tests(verbose=True)
    
    if success:
        print("\n🎉 Test run completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Test run failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 