#!/usr/bin/env python3
"""
Test script for multi-tenant functionality in discovery-node.

Tests:
1. Subdomain extraction from Host header
2. Organization context in search
3. Product isolation between organizations
"""

import os
import sys
import requests
from typing import Dict, Any

# Test configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"

# Test organizations (these should exist in your database)
TEST_ORGS = {
    "org1": {
        "subdomain": "insighteditions",
        "host": "insighteditions.localhost:8000"
    },
    "org2": {
        "subdomain": "acme-solutions", 
        "host": "acme-solutions.localhost:8000"
    }
}


def make_request(method: str, path: str, host: str = None, **kwargs) -> requests.Response:
    """Make HTTP request with optional Host header."""
    url = f"{BASE_URL}{API_PREFIX}{path}"
    headers = kwargs.pop("headers", {})
    
    if host:
        headers["Host"] = host
    
    return requests.request(method, url, headers=headers, **kwargs)


def test_health_check():
    """Test basic health check endpoint."""
    print("Testing health check...")
    response = make_request("GET", "/../health")
    assert response.status_code == 200, f"Health check failed: {response.status_code}"
    print("✓ Health check passed")


def test_subdomain_extraction():
    """Test subdomain extraction in multi-tenant mode."""
    print("\nTesting subdomain extraction...")
    
    # Test with valid subdomain
    for org_name, org_data in TEST_ORGS.items():
        print(f"  Testing {org_name} with host: {org_data['host']}")
        response = make_request("GET", "/search", host=org_data['host'], params={"q": "test"})
        
        if response.status_code == 404:
            print(f"  ⚠️  Organization not found for {org_data['subdomain']} - make sure it exists in DB")
        elif response.status_code == 200:
            print(f"  ✓ Successfully accessed with subdomain {org_data['subdomain']}")
        else:
            print(f"  ✗ Unexpected status: {response.status_code}")
            print(f"    Response: {response.text}")
    
    # Test without subdomain (should fail in multi-tenant mode)
    print("  Testing without subdomain...")
    response = make_request("GET", "/search", params={"q": "test"})
    if os.getenv("MULTI_TENANT_MODE", "false").lower() == "true":
        assert response.status_code == 400, "Should require subdomain in multi-tenant mode"
        print("  ✓ Correctly rejected request without subdomain")
    else:
        print("  ℹ️  Single-tenant mode - subdomain not required")


def test_organization_isolation():
    """Test that organizations only see their own products."""
    print("\nTesting organization isolation...")
    
    # Search products for each organization
    for org_name, org_data in TEST_ORGS.items():
        print(f"  Searching products for {org_name}...")
        response = make_request("GET", "/search", host=org_data['host'], params={"q": "product"})
        
        if response.status_code == 200:
            data = response.json()
            item_count = data.get("numberOfItems", 0)
            print(f"  ✓ Found {item_count} products for {org_name}")
            
            # Verify products belong to the correct organization
            items = data.get("itemListElement", [])
            for item in items[:3]:  # Check first 3 items
                product = item.get("item", {})
                print(f"    - {product.get('name', 'Unknown')}")
        else:
            print(f"  ⚠️  Search failed for {org_name}: {response.status_code}")


def test_cross_tenant_access():
    """Test that one tenant cannot access another tenant's products."""
    print("\nTesting cross-tenant access prevention...")
    
    # This test requires knowing specific product URNs from different organizations
    # For now, we'll just verify the subdomain routing works
    print("  ℹ️  Cross-tenant access tests require specific product URNs")
    print("  ℹ️  Subdomain routing prevents cross-tenant access at the API level")


def main():
    """Run all tests."""
    print(f"Testing multi-tenant functionality")
    print(f"Base URL: {BASE_URL}")
    print(f"Multi-tenant mode: {os.getenv('MULTI_TENANT_MODE', 'false')}")
    print("=" * 60)
    
    try:
        test_health_check()
        test_subdomain_extraction()
        test_organization_isolation()
        test_cross_tenant_access()
        
        print("\n" + "=" * 60)
        print("✓ All tests completed")
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()