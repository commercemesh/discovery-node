# Vector Storage Architecture

## Overview

The Discovery Node supports flexible vector storage for semantic search capabilities. This architecture allows developers to choose between different vector storage providers based on their needs:

- **pgvector** (default): PostgreSQL extension for vector operations, ideal for local development and self-hosted deployments
- **Pinecone**: Cloud-based vector database service, suitable for production workloads with managed infrastructure

## Architecture Design

### Abstraction Layers

```
┌─────────────────────────────────────────────────┐
│              Search API Endpoint                 │
│            (/api/v1/search?q=...)               │
└─────────────────────┬───────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────┐
│           SearchServiceFactory                   │
│    (Selects provider based on config)           │
└─────────────────────┬───────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐         ┌───────▼────────┐
│ PgVectorSearch │         │ PineconeSearch │
│    Service     │         │    Service     │
└───────┬────────┘         └───────┬────────┘
        │                           │
┌───────▼────────┐         ┌───────▼────────┐
│   pgvector     │         │   Pinecone     │
│  Repository    │         │  Repository    │
└───────┬────────┘         └───────┬────────┘
        │                           │
┌───────▼────────┐         ┌───────▼────────┐
│  PostgreSQL    │         │ Pinecone Cloud │
│  + pgvector    │         │    Indexes     │
└────────────────┘         └────────────────┘
```

### Key Components

1. **Vector Repository** (`app/db/repositories/vector_repository_native.py`)
   - Abstract base class defining vector storage operations
   - Provider-specific implementations for pgvector and Pinecone
   - Handles embedding storage and retrieval

2. **Search Services** (`app/services/search/`)
   - `BaseSearchService`: Abstract base class for search operations
   - `PgVectorSearchService`: pgvector-specific search implementation
   - `PineconeSearchService`: Pinecone-specific search implementation
   - `SearchServiceFactory`: Creates appropriate service based on configuration

3. **Vector Service** (`app/services/vector_service.py`)
   - Manages vector ingestion workflow
   - Prepares product data for embedding
   - Coordinates with vector repository for storage

## Configuration

### Environment Variables

```bash
# Vector provider selection
VECTOR_PROVIDER=pgvector  # Options: pgvector (default), pinecone

# Embedding configuration (for pgvector)
EMBEDDING_MODEL_PROVIDER=openai
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_API_KEY=sk-...
EMBEDDING_DIMENSION=1536

# Pinecone configuration (when using Pinecone)
PINECONE_API_KEY=pcsk-...
PINECONE_ENVIRONMENT=production
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
PINECONE_DENSE_INDEX=cmp-discovery-dense
PINECONE_SPARSE_INDEX=cmp-discovery-sparse
PINECONE_NAMESPACE=__default__
```

## pgvector Implementation

### Database Schema

The pgvector implementation adds an embedding column to the existing products table:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to products table
ALTER TABLE products ADD COLUMN embedding vector(1536);

-- Create index for fast similarity search
CREATE INDEX idx_products_embedding ON products 
USING hnsw (embedding vector_cosine_ops);
```

### Embedding Generation

When using pgvector, embeddings are computed locally using OpenAI's API:

1. Product data is converted to canonical text format
2. Text is sent to OpenAI's embedding API
3. Resulting vectors are stored in the products table
4. Embeddings are computed in batches for efficiency

### Search Process

1. Query text is converted to embedding using same model
2. Cosine similarity search is performed using pgvector
3. Results are enriched with product metadata
4. Response is formatted according to schema.org standards

## Pinecone Implementation

### Index Structure

Pinecone uses two separate indexes:

1. **Dense Index**: Uses learned embeddings for semantic search
2. **Sparse Index**: Uses keyword-based embeddings for exact matching

### Data Flow

1. Products are prepared with canonical text
2. Pinecone's built-in inference API generates embeddings
3. Records are upserted to both dense and sparse indexes
4. Search results from both indexes are merged using Reciprocal Rank Fusion (RRF)

## Switching Providers

### From Pinecone to pgvector

1. Update `.env` file:
   ```bash
   VECTOR_PROVIDER=pgvector
   EMBEDDING_API_KEY=your-openai-key
   ```

2. Run database migration:
   ```bash
   alembic upgrade head
   ```

3. Re-ingest vectors:
   ```bash
   # Trigger vector ingestion through your worker
   ```

### From pgvector to Pinecone

1. Update `.env` file:
   ```bash
   VECTOR_PROVIDER=pinecone
   PINECONE_API_KEY=your-pinecone-key
   ```

2. Create Pinecone indexes (if not exists):
   ```bash
   python -m scripts.setup_pinecone
   ```

3. Re-ingest vectors:
   ```bash
   # Trigger vector ingestion through your worker
   ```

## Development Workflow

### Local Development with pgvector

1. Ensure PostgreSQL has pgvector extension available
2. Set `VECTOR_PROVIDER=pgvector` in `.env`
3. Run migrations to create embedding column
4. Ingest products - embeddings will be computed and stored locally

### Testing Search

```bash
# Search API endpoint works the same regardless of provider
curl -X GET "http://localhost:8000/api/v1/search?q=harry%20potter" \
  -H "accept: application/json"
```

### Managing Pinecone Indexes

```bash
# Create indexes
python -m scripts.setup_pinecone

# Truncate indexes (clear all vectors)
python -m scripts.truncate_pinecone_indexes
```

## Key Design Decisions

### URN as Primary Identifier

Both pgvector and Pinecone use the product URN (not UUID) as the primary identifier for vector records. This ensures:
- Consistency across storage providers
- Compatibility with CMP specification
- Easier debugging and data tracking

### Embedding Dimensions

The system uses 1536-dimensional embeddings (OpenAI's text-embedding-3-small default). This provides a good balance between:
- Search quality
- Storage requirements
- Computation speed

### Batch Processing

Vector ingestion processes products in batches (default: 96) to:
- Optimize API calls for embedding generation
- Prevent memory issues with large datasets
- Allow for incremental progress tracking

## Troubleshooting

### Common Issues

1. **"No products with embeddings" in pgvector**
   - Ensure vector ingestion has completed successfully
   - Check that `EMBEDDING_API_KEY` is valid
   - Verify products exist in the database

2. **Empty search results with Pinecone**
   - Confirm indexes exist and contain vectors
   - Check that URNs match between database and Pinecone
   - Verify namespace configuration

3. **Vector ingestion stops early**
   - Check logs for errors in embedding generation
   - Ensure all products have required fields (name, description)
   - Verify API rate limits aren't being hit

### Performance Optimization

1. **pgvector**
   - Use HNSW index for better performance
   - Consider adjusting `work_mem` for large queries
   - Monitor index size and maintenance needs

2. **Pinecone**
   - Use appropriate pod type for workload
   - Implement caching for frequently searched queries
   - Monitor index utilization and costs

## Future Enhancements

1. **Additional Providers**
   - Weaviate integration
   - Qdrant support
   - Elasticsearch with vector search

2. **Hybrid Search**
   - Combine vector search with traditional filters
   - Implement faceted search capabilities
   - Add relevance tuning parameters

3. **Embedding Models**
   - Support for alternative embedding models
   - Model versioning and migration tools
   - Custom fine-tuned embeddings