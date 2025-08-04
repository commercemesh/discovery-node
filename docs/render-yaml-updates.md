# Render.yaml Updates Summary

## Changes Made

### 1. Updated Celery Worker Command
- **Changed**: The discovery-worker service now specifies which queues to process
- **Old**: `celery -A app.worker.celery_app worker --loglevel=info`
- **New**: `celery -A app.worker.celery_app worker --loglevel=info -Q celery,embeddings_high,embeddings_bulk`
- **Reason**: The new embedding generation feature uses separate queues for different priority levels

### 2. Added EMBEDDING_API_KEY Environment Variable
- **Added to all services**: 
  - discovery-web
  - discovery-worker  
  - discovery-scheduler
  - discovery-mcp
- **Configuration**: `sync: false` (requires manual configuration in Render dashboard)
- **Reason**: Required for generating OpenAI embeddings when using pgvector

## Additional Considerations for Production

### 1. Separate Workers for Better Performance (Optional)
For high-volume production environments, consider running separate workers:

```yaml
# High-priority embeddings worker
- type: worker
  name: discovery-worker-embeddings-high
  runtime: python
  region: oregon
  plan: starter
  startCommand: celery -A app.worker.celery_app worker --loglevel=info -Q embeddings_high --concurrency=4
  # ... same env vars ...

# Bulk embeddings worker  
- type: worker
  name: discovery-worker-embeddings-bulk
  runtime: python
  region: oregon
  plan: starter
  startCommand: celery -A app.worker.celery_app worker --loglevel=info -Q embeddings_bulk --concurrency=2
  # ... same env vars ...

# Regular tasks worker
- type: worker
  name: discovery-worker-general
  runtime: python
  region: oregon
  plan: starter
  startCommand: celery -A app.worker.celery_app worker --loglevel=info -Q celery
  # ... same env vars ...
```

### 2. Environment Variables to Set in Render Dashboard
After deployment, set these secret environment variables:
- `EMBEDDING_API_KEY`: Your OpenAI API key (required for pgvector embeddings)
- `PINECONE_API_KEY`: Your Pinecone API key (if using Pinecone)
- `PINECONE_ENVIRONMENT`: Your Pinecone environment
- `PINECONE_DENSE_INDEX`: Name of your Pinecone dense index
- `PINECONE_SPARSE_INDEX`: Name of your Pinecone sparse index

### 3. Database Considerations
- The existing `alembic upgrade head` in preDeployCommand will handle any new migrations
- Ensure pgvector extension is installed if using `VECTOR_PROVIDER=pgvector`

### 4. Monitoring
- Monitor the Celery worker logs to ensure embedding tasks are being processed
- Check for any rate limiting issues with the embedding API
- Monitor queue depths to ensure tasks aren't backing up