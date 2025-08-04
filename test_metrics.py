#!/usr/bin/env python3
"""Test script for API metrics collection"""
import requests
import json
import time
import psycopg2
from datetime import datetime, timedelta

# Base URL for the API
BASE_URL = "http://localhost:8000"

# Database connection (adjust as needed)
import os
from dotenv import load_dotenv
load_dotenv()

# Parse DATABASE_URL
import urllib.parse
db_url = os.getenv("DATABASE_URL", "postgresql://localhost/cmp_discovery")
parsed = urllib.parse.urlparse(db_url)

DB_CONFIG = {
    "host": parsed.hostname or "localhost",
    "port": parsed.port or 5432,
    "database": parsed.path.lstrip("/"),
    "user": parsed.username,
    "password": parsed.password
}

def test_public_endpoints():
    """Test metrics collection for public endpoints"""
    print("1. Testing public endpoints...")
    
    # Test health endpoint (should not be tracked)
    response = requests.get(f"{BASE_URL}/health")
    print(f"   Health check: {response.status_code}")
    
    # Test organization GET (public)
    response = requests.get(f"{BASE_URL}/api/v1/organizations/urn:cmp:org:testcorp.com")
    print(f"   GET organization: {response.status_code}")
    
    # Test organization POST (public)
    payload = {
        "organization": {
            "name": "Metrics Test Corp",
            "url": "https://metricstest.com",
            "brand": {
                "name": "Metrics Brand",
                "url": "https://metricstest.com"
            }
        }
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/organizations",
        json=payload,
        headers={"X-Request-ID": "test-create-org-123"}
    )
    print(f"   POST organization: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        # Extract API key for admin tests
        api_key = None
        if "cmp:services" in data:
            auth_info = data["cmp:services"]["cmp:adminAPI"].get("cmp:authentication", {})
            if "cmp:keys" in auth_info and auth_info["cmp:keys"]:
                api_key = auth_info["cmp:keys"][0]["key"]
        return api_key, data["identifier"]["value"]
    
    return None, None

def test_admin_endpoints(api_key):
    """Test metrics collection for admin endpoints"""
    print("\n2. Testing admin endpoints...")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Test products GET (admin)
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/products",
        headers=headers
    )
    print(f"   GET products: {response.status_code}")
    
    # Test products POST with error (admin)
    invalid_payload = {"invalid": "data"}
    response = requests.post(
        f"{BASE_URL}/api/v1/admin/products",
        json=invalid_payload,
        headers={**headers, "X-Request-Source": "test-script"}
    )
    print(f"   POST products (invalid): {response.status_code}")
    
    # Test products POST with valid data (admin)
    valid_payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "item": {
                    "@type": "Product",
                    "name": "Metrics Test Product",
                    "sku": "METRICS-001",
                    "description": "Product for testing metrics",
                    "brand": {"@type": "Brand", "name": "Metrics Brand"},
                    "offers": {
                        "@type": "Offer",
                        "price": 99.99,
                        "priceCurrency": "USD",
                        "availability": "https://schema.org/InStock",
                        "inventoryLevel": {"@type": "QuantitativeValue", "value": 50}
                    }
                }
            }
        ]
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/admin/products",
        json=valid_payload,
        headers=headers
    )
    print(f"   POST products (valid): {response.status_code}")

def test_query_endpoints():
    """Test metrics collection for query endpoints"""
    print("\n3. Testing query endpoints...")
    
    # Test product search
    response = requests.post(
        f"{BASE_URL}/api/v1/query/search",
        json={"query": "test product", "limit": 10},
        headers={"X-Correlation-ID": "search-test-456"}
    )
    print(f"   POST search: {response.status_code}")

def check_metrics_in_database():
    """Check if metrics were logged to database"""
    print("\n4. Checking metrics in database...")
    
    # Wait a bit for async logging
    time.sleep(2)
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Query recent metrics
        query = """
        SELECT 
            method,
            path,
            route_pattern,
            status_code,
            response_time_ms,
            organization_id,
            api_key_id,
            metrics
        FROM api_usage_metrics
        WHERE timestamp > %s
        ORDER BY timestamp DESC
        LIMIT 10
        """
        
        cursor.execute(query, (datetime.utcnow() - timedelta(minutes=5),))
        rows = cursor.fetchall()
        
        print(f"\n   Found {len(rows)} metrics in last 5 minutes:")
        for row in rows:
            method, path, route_pattern, status, response_time, org_id, api_key_id, metrics = row
            print(f"   - {method} {path} -> {status} ({response_time}ms)")
            print(f"     Route: {route_pattern}")
            print(f"     Org: {org_id}, API Key: {api_key_id}")
            print(f"     Metrics: {json.dumps(metrics, indent=2)}")
            print()
        
        # Summary statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                AVG(response_time_ms) as avg_response_time,
                MAX(response_time_ms) as max_response_time,
                COUNT(DISTINCT organization_id) as unique_orgs,
                COUNT(DISTINCT path) as unique_paths
            FROM api_usage_metrics
            WHERE timestamp > %s
        """, (datetime.utcnow() - timedelta(minutes=5),))
        
        stats = cursor.fetchone()
        print(f"   Summary stats:")
        print(f"   - Total requests: {stats[0]}")
        print(f"   - Avg response time: {stats[1]:.2f}ms")
        print(f"   - Max response time: {stats[2]}ms")
        print(f"   - Unique organizations: {stats[3]}")
        print(f"   - Unique paths: {stats[4]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"   Error checking database: {str(e)}")

def main():
    """Run all tests"""
    print("🧪 Testing API Metrics Collection")
    print("=" * 50)
    
    # Test public endpoints
    api_key, org_urn = test_public_endpoints()
    
    # Test admin endpoints if we got an API key
    if api_key:
        test_admin_endpoints(api_key)
    
    # Test query endpoints
    test_query_endpoints()
    
    # Check metrics in database
    check_metrics_in_database()
    
    print("\n✅ Metrics test completed!")

if __name__ == "__main__":
    main()