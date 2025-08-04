# Embedding Generation for Admin Products API

This document describes the embedding generation feature that automatically creates vector embeddings when products are created or updated via the admin API.

## Overview

When products are created or updated through the `/api/admin/products` endpoints, the system automatically queues background tasks to generate embeddings for semantic search. This ensures that new or updated products are immediately searchable.

## Architecture

### Components

1. **Celery Tasks** (`app/worker/tasks/embeddings.py`)
   - `generate_embedding_single`: Processes single product embeddings (high priority)
   - `generate_embeddings_batch`: Processes multiple products in batches (bulk operations)
   - `regenerate_organization_embeddings`: Regenerates all embeddings for an organization

2. **Vector Service** (`app/services/vector_service.py`)
   - `upsert_product_by_urn`: Updates embeddings for a single product
   - `upsert_products_by_urns`: Updates embeddings for multiple products

3. **Admin API** (`app/api/routes/admin/products.py`)
   - Automatically queues embedding tasks after successful product operations
   - Uses single tasks for ≤10 products, batch tasks for larger operations

### Queue Configuration

The system uses separate Celery queues for different priority levels:

- **embeddings_high**: For real-time single product updates (rate limit: 1000/min)
- **embeddings_bulk**: For batch operations (rate limit: 10000/hour)
- **celery**: Default queue for other tasks

## Usage

### Starting Workers

To process embedding tasks, start Celery workers with the appropriate queues:

```bash
# Single worker handling all queues
celery -A app.worker.celery_app worker --loglevel=info -Q celery,embeddings_high,embeddings_bulk

# Or separate workers for better resource management
celery -A app.worker.celery_app worker --loglevel=info -Q embeddings_high -n worker.high --concurrency=4
celery -A app.worker.celery_app worker --loglevel=info -Q embeddings_bulk -n worker.bulk --concurrency=2
```

### API Examples

#### Creating Products
```bash
curl -X POST http://localhost:8000/api/admin/products \
  -H "Content-Type: application/json" \
  -H "X-Organization: your-org" \
  -d '{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "itemListElement": [{
      "@type": "ListItem",
      "position": 1,
      "item": {
        "@type": "Product",
        "name": "Example Product",
        "sku": "PROD-001",
        "offers": {
          "@type": "Offer",
          "price": 99.99,
          "priceCurrency": "USD",
          "availability": "https://schema.org/InStock",
          "inventoryLevel": {"@type": "QuantitativeValue", "value": 100}
        }
      }
    }]
  }'
```

#### Updating Products
```bash
curl -X PUT http://localhost:8000/api/admin/products \
  -H "Content-Type: application/json" \
  -H "X-Organization: your-org" \
  -d '{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "itemListElement": [{
      "@type": "ListItem",
      "position": 1,
      "item": {
        "@type": "Product",
        "@id": "urn:cmp:sku:your-org:brand:PROD-001",
        "name": "Updated Product Name",
        "description": "New description for better search"
      }
    }]
  }'
```

## Environment Variables

The feature respects the `VECTOR_PROVIDER` environment variable:
- `pgvector`: Uses PostgreSQL with pgvector extension
- `pinecone`: Uses Pinecone cloud vector database

Both providers are automatically handled by the same task infrastructure.

## Monitoring

### Task Status
Monitor embedding generation tasks in Celery logs:
```
[INFO] Starting embedding generation for product: urn:cmp:sku:org:brand:123
[INFO] Successfully generated embeddings for product: urn:cmp:sku:org:brand:123
```

### Error Handling
- Tasks retry up to 3 times with exponential backoff
- Failed tasks log detailed error messages
- Partial failures in batch operations continue processing remaining items

## Testing

Use the provided test script to verify the implementation:

```bash
python test_embedding_generation.py
```

This will:
1. Create test products via the API
2. Verify embedding tasks are queued
3. Update a product to test regeneration
4. Provide instructions for checking worker logs

## Performance Considerations

- Single product updates are processed immediately (high priority queue)
- Bulk operations are chunked into batches of 100 products
- Rate limiting prevents overwhelming the embedding service
- Separate queues allow dedicated worker scaling