#!/usr/bin/env python
"""
Test script for embedding generation via admin API.
Run this after starting the API server and Celery workers.
"""
import requests
import json
import time
import sys

# Configuration
API_BASE_URL = "http://localhost:8000"
ORGANIZATION = "test-org"  # Update this with your test organization

# Test data
test_product_group = {
    "@context": "https://schema.org",
    "@type": "ProductGroup",
    "@id": "urn:cmp:product:test-org:samsung:tv-group-001",
    "name": "Samsung Smart TV Series",
    "description": "Latest Samsung Smart TV collection",
    "productGroupID": "tv-group-001",
    "brand": {
        "@type": "Brand",
        "name": "Samsung"
    },
    "category": "Electronics"
}

test_product = {
    "@context": "https://schema.org",
    "@type": "Product",
    "@id": "urn:cmp:sku:test-org:samsung:tv-model-123",
    "name": "Samsung 55\" Smart TV",
    "sku": "tv-model-123",
    "description": "55 inch 4K Smart TV with HDR",
    "brand": {
        "@type": "Brand",
        "name": "Samsung"
    },
    "category": "Electronics",
    "offers": {
        "@type": "Offer",
        "price": 999.99,
        "priceCurrency": "USD",
        "availability": "https://schema.org/InStock",
        "inventoryLevel": {
            "@type": "QuantitativeValue",
            "value": 50
        }
    },
    "isVariantOf": {
        "@type": "ProductGroup",
        "@id": "urn:cmp:product:test-org:samsung:tv-group-001"
    }
}

def create_products():
    """Create test products via the admin API."""
    print(f"Creating products for organization: {ORGANIZATION}")
    
    # Prepare the ItemList payload
    payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "item": test_product_group
            },
            {
                "@type": "ListItem",
                "position": 2,
                "item": test_product
            }
        ]
    }
    
    # Make the API request
    headers = {
        "Content-Type": "application/json",
        "X-Organization": ORGANIZATION
    }
    
    response = requests.post(
        f"{API_BASE_URL}/api/admin/products",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 201:
        result = response.json()
        print("\nProducts created successfully!")
        print(json.dumps(result, indent=2))
        
        # Extract created product URNs
        product_urns = [
            r["urn"] for r in result["results"] 
            if r["type"] == "Product" and r["action"] == "created"
        ]
        print(f"\nCreated {len(product_urns)} products that should have embeddings generated")
        return product_urns
    else:
        print(f"Error creating products: {response.status_code}")
        print(response.text)
        return []

def update_product():
    """Update a product to test embedding regeneration."""
    print(f"\nUpdating product...")
    
    # Update the product description
    updated_product = test_product.copy()
    updated_product["description"] = "Updated: 55 inch 4K Smart TV with HDR and Voice Control"
    
    payload = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "item": updated_product
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Organization": ORGANIZATION
    }
    
    response = requests.put(
        f"{API_BASE_URL}/api/admin/products",
        json=payload,
        headers=headers
    )
    
    if response.status_code == 200:
        result = response.json()
        print("Product updated successfully!")
        print(json.dumps(result, indent=2))
        return True
    else:
        print(f"Error updating product: {response.status_code}")
        print(response.text)
        return False

def check_celery_status():
    """Check if Celery workers are running (basic check)."""
    print("\nNote: Make sure Celery workers are running with the proper queues:")
    print("  celery -A app.worker.celery_app worker --loglevel=info -Q celery,embeddings_high,embeddings_bulk")
    print("\nOr run separate workers for each queue:")
    print("  celery -A app.worker.celery_app worker --loglevel=info -Q embeddings_high -n worker.high")
    print("  celery -A app.worker.celery_app worker --loglevel=info -Q embeddings_bulk -n worker.bulk")

def main():
    """Run the test."""
    print("Testing Embedding Generation for Admin Products API")
    print("=" * 50)
    
    # Test 1: Create products
    print("\nTest 1: Creating new products (should trigger embedding generation)")
    product_urns = create_products()
    
    if product_urns:
        print("\n✅ Products created successfully!")
        print("Check Celery worker logs to see embedding generation tasks")
        
        # Wait a bit before updating
        print("\nWaiting 3 seconds before update test...")
        time.sleep(3)
        
        # Test 2: Update product
        print("\nTest 2: Updating product (should trigger embedding regeneration)")
        if update_product():
            print("\n✅ Product updated successfully!")
            print("Check Celery worker logs to see embedding regeneration task")
    
    # Show Celery info
    check_celery_status()
    
    print("\n" + "=" * 50)
    print("Test completed! Check your Celery worker logs to verify:")
    print("1. Tasks were received in the correct queues")
    print("2. Embeddings were generated successfully")
    print("3. Both pgvector and Pinecone (if configured) were updated")

if __name__ == "__main__":
    main()