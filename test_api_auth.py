#!/usr/bin/env python3
"""Test script for API key authentication flow"""
import requests
import json
import sys

# Base URL for the API
BASE_URL = "http://localhost:8000"

def test_create_organization():
    """Test creating an organization and getting an API key"""
    print("1. Testing organization creation...")
    
    # Create organization payload
    payload = {
        "organization": {
            "name": "Test Corp",
            "url": "https://testcorp.com",
            "logo": "https://testcorp.com/logo.png",
            "description": "Test Corporation",
            "category": "Technology",
            "urn": "urn:cmp:org:testcorp.com",
            "domain": "testcorp.com",
            "brand": {
                "name": "Test Brand",
                "url": "https://testcorp.com",
                "logo": "https://testcorp.com/brand-logo.png"
            }
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/organizations",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ Organization created successfully!")
        print(json.dumps(data, indent=2))
        
        # Extract API key
        if "cmp:services" in data and "cmp:adminAPI" in data["cmp:services"]:
            auth_info = data["cmp:services"]["cmp:adminAPI"].get("cmp:authentication", {})
            if "cmp:keys" in auth_info and auth_info["cmp:keys"]:
                api_key = auth_info["cmp:keys"][0]["key"]
                print(f"\n📝 API Key obtained: {api_key}")
                return api_key, data["identifier"]["value"]
        
        print("❌ No API key found in response")
        return None, None
    else:
        print(f"❌ Failed to create organization: {response.status_code}")
        print(response.text)
        return None, None

def test_api_key_auth(api_key, org_urn):
    """Test using the API key to access protected endpoints"""
    print("\n2. Testing API key authentication...")
    
    # Test accessing products endpoint without auth
    print("\n   a) Testing without authentication...")
    response = requests.get(f"{BASE_URL}/api/v1/admin/products")
    print(f"   Status: {response.status_code} (Expected: 401)")
    
    # Test with invalid API key
    print("\n   b) Testing with invalid API key...")
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/products",
        headers={"Authorization": "Bearer invalid_key_123"}
    )
    print(f"   Status: {response.status_code} (Expected: 401)")
    
    # Test with valid API key
    print("\n   c) Testing with valid API key...")
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/products",
        headers={"Authorization": f"Bearer {api_key}"}
    )
    print(f"   Status: {response.status_code} (Expected: 200)")
    if response.status_code == 200:
        print("   ✅ Authentication successful!")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"   ❌ Authentication failed: {response.text}")

def test_create_product(api_key):
    """Test creating a product with API key"""
    print("\n3. Testing product creation with API key...")
    
    # Create product payload
    payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "item": {
                    "@type": "Product",
                    "name": "Test Product",
                    "sku": "TEST-001",
                    "description": "A test product",
                    "url": "https://testcorp.com/products/test-001",
                    "brand": {
                        "@type": "Brand",
                        "name": "Test Brand"
                    },
                    "category": "Electronics",
                    "offers": {
                        "@type": "Offer",
                        "price": 99.99,
                        "priceCurrency": "USD",
                        "availability": "https://schema.org/InStock",
                        "inventoryLevel": {
                            "@type": "QuantitativeValue",
                            "value": 100
                        }
                    }
                }
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/admin/products",
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    )
    
    if response.status_code == 201:
        print("✅ Product created successfully!")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"❌ Failed to create product: {response.status_code}")
        print(response.text)

def main():
    """Run all tests"""
    print("🧪 Testing API Key Authentication Flow")
    print("=" * 50)
    
    # Test 1: Create organization and get API key
    api_key, org_urn = test_create_organization()
    
    if not api_key:
        print("\n❌ Failed to obtain API key. Exiting.")
        sys.exit(1)
    
    # Test 2: Test API key authentication
    test_api_key_auth(api_key, org_urn)
    
    # Test 3: Create product with API key
    test_create_product(api_key)
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main()