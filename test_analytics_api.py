#!/usr/bin/env python3
"""
Test script for analytics API endpoints.

IMPORTANT: These endpoints require authentication. 
Set the API_KEY variable below with a valid API key from your database.
You can get an API key by creating an organization via POST /api/v1/organizations
"""
import requests
import json
from datetime import date, timedelta

# Base URL for the API
BASE_URL = "http://localhost:8000"

# API key for authentication (replace with actual key)
API_KEY = "your-api-key-here"  # Replace with actual API key from database

# Headers for authenticated requests
AUTH_HEADERS = {
    "Authorization": f"Bearer {API_KEY}"
}

def test_analytics_endpoints():
    """Test all analytics endpoints"""
    print("🧪 Testing Analytics API Endpoints")
    print("=" * 50)
    
    print("\n1. Testing GET /api/v1/admin/analytics (default - today)")
    response = requests.get(f"{BASE_URL}/api/v1/admin/analytics", headers=AUTH_HEADERS)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Period: {data['period']['from']} to {data['period']['to']}")
        print(f"   Total requests: {data['overall']['total_requests']}")
        print(f"   Error rate: {data['overall']['error_rate']}%")
        print(f"   Categories tracked: {list(data['by_category'].keys())}")
        
        # Show breakdown by category
        for category, cat_data in data['by_category'].items():
            metrics = cat_data['metrics']
            print(f"   {category.upper()}: {metrics['total_requests']} requests, "
                  f"{metrics['error_rate']}% error rate, "
                  f"{metrics['avg_response_time']}ms avg")
    else:
        print(f"   Error: {response.text}")
    
    print("\n2. Testing GET /api/v1/admin/analytics with date range")
    yesterday = date.today() - timedelta(days=1)
    today = date.today()
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/analytics",
        params={
            "from_date": yesterday.isoformat(),
            "to_date": today.isoformat()
        },
        headers=AUTH_HEADERS
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Period: {data['period']['from']} to {data['period']['to']}")
        print(f"   Total requests: {data['overall']['total_requests']}")
    else:
        print(f"   Error: {response.text}")
    
    print("\n3. Testing GET /api/v1/admin/analytics with common date ranges")
    # Test common date ranges
    ranges = [
        ("today", today, today),
        ("yesterday", yesterday, yesterday),
        ("week", today - timedelta(days=6), today),
        ("month", today - timedelta(days=29), today)
    ]
    
    for name, from_dt, to_dt in ranges:
        response = requests.get(
            f"{BASE_URL}/api/v1/admin/analytics",
            params={
                "from_date": from_dt.isoformat(),
                "to_date": to_dt.isoformat(),
                "timezone": "America/Los_Angeles"
            },
            headers=AUTH_HEADERS
        )
        print(f"   {name.upper()}: Status {response.status_code}", end="")
        if response.status_code == 200:
            data = response.json()
            print(f" - {data['overall']['total_requests']} requests")
        else:
            print(f" - Error: {response.text}")
    
    print("\n4. Testing GET /api/v1/admin/analytics/health")
    response = requests.get(f"{BASE_URL}/api/v1/admin/analytics/health", headers=AUTH_HEADERS)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   Overall status: {data['status']}")
        print(f"   Request rate: {data['metrics']['request_rate']}")
        print(f"   Error rate: {data['metrics']['error_rate']}%")
        print(f"   Avg response time: {data['metrics']['avg_response_time']}ms")
        print(f"   Service statuses: {data['services']}")
    else:
        print(f"   Error: {response.text}")
    
    print("\n5. Testing error cases")
    
    # Invalid date range
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/analytics",
        params={
            "from_date": "2024-12-31",
            "to_date": "2024-01-01"  # from > to
        },
        headers=AUTH_HEADERS
    )
    print(f"   Invalid date range: Status {response.status_code} (expected 400)")
    
    # Date range too large
    old_date = date.today() - timedelta(days=100)
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/analytics",
        params={
            "from_date": old_date.isoformat(),
            "to_date": date.today().isoformat()
        },
        headers=AUTH_HEADERS
    )
    print(f"   Date range too large: Status {response.status_code} (expected 400)")
    
    # Invalid timezone
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/analytics",
        params={
            "from_date": date.today().isoformat(),
            "to_date": date.today().isoformat(),
            "timezone": "Invalid/Timezone"
        },
        headers=AUTH_HEADERS
    )
    print(f"   Invalid timezone: Status {response.status_code} (expected to use UTC)")
    
    print("\n✅ Analytics API test completed!")

def generate_some_test_data():
    """Generate some test data by making API calls"""
    print("\n📊 Generating test data...")
    
    # Make some requests to different endpoints
    endpoints = [
        f"{BASE_URL}/api/v1/organizations/test",  # Public endpoint
        f"{BASE_URL}/api/v1/health",  # Health endpoint (not tracked)
        f"{BASE_URL}/api/v1/query/search",  # Query endpoint (will 405 but tracked)
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint)
            print(f"   {endpoint}: {response.status_code}")
        except:
            print(f"   {endpoint}: Failed")
    
    print("   Test data generation completed!")

def main():
    """Run all tests"""
    # Generate some test data first
    generate_some_test_data()
    
    # Test analytics endpoints
    test_analytics_endpoints()

if __name__ == "__main__":
    main()