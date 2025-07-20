# Vector Storage Abstraction

This module provides a flexible abstraction layer for vector storage, allowing you to switch between different vector database providers (Pinecone, pgvector, etc.) via configuration.

## Architecture

```
app/vectors/
├── base.py              # Abstract base class defining the interface
├── types.py             # Common data types (VectorRecord, SearchResult, etc.)
├── factory.py           # Factory for creating provider instances
└── providers/
    ├── pinecone.py      # Pinecone implementation
    └── pgvector.py      # PostgreSQL pgvector implementation
```

## Configuration

Set the vector provider in your environment variables:

```bash
# Use Pinecone (default)
VECTOR_PROVIDER=pinecone
PINECONE_API_KEY=your-api-key
PINECONE_DENSE_INDEX=your-dense-index
PINECONE_SPARSE_INDEX=your-sparse-index

# Use PostgreSQL pgvector
VECTOR_PROVIDER=pgvector
PGVECTOR_CONNECTION_STRING=postgresql://user:pass@localhost/db
PGVECTOR_TABLE_PREFIX=vectors
PGVECTOR_EMBEDDING_SERVICE_URL=http://localhost:8000  # Optional
```

## Usage

### Using VectorRepositoryV2

```python
from app.db.repositories.vector_repository_v2 import VectorRepositoryV2

# Initialize repository - provider is selected based on VECTOR_PROVIDER env var
repo = VectorRepositoryV2()

# Upsert products
records = [
    {
        "id": "product-1",
        "values": [0.1, 0.2, ...],  # Dense vector
        "metadata": {"brand": "Nike", "price": 99.99}
    }
]
repo.upsert_products_into_dense_index(records)

# Search
results = repo._search_dense_index("running shoes", top_k=10)
```

### Direct Provider Usage

```python
from app.vectors import VectorProviderFactory
from app.vectors.types import VectorRecord, SearchType

# Create provider
provider = VectorProviderFactory.create("pgvector", {
    "connection_string": "postgresql://localhost/mydb",
    "table_prefix": "products"
})

# Upsert vectors
records = [
    VectorRecord(
        id="item-1",
        values=[0.1, 0.2, ...],
        metadata={"category": "electronics"}
    )
]
provider.upsert_vectors("my_index", records)

# Search
results = provider.search(
    index_name="my_index",
    query="laptop computer",
    search_type=SearchType.HYBRID
)
```

## Migration Guide

To migrate from the old VectorRepository to the new abstraction:

1. **Update imports:**
   ```python
   # Old
   from app.db.repositories.vector_repository import VectorRepository
   
   # New
   from app.db.repositories.vector_repository_v2 import VectorRepositoryV2
   ```

2. **Update instantiation:**
   ```python
   # Old
   repo = VectorRepository()
   
   # New
   repo = VectorRepositoryV2()
   ```

3. **The API remains the same** - all existing methods work as before

## Adding a New Provider

To add support for a new vector database:

1. Create a new provider class in `app/vectors/providers/`:
   ```python
   from app.vectors.base import VectorProvider
   
   class MyProvider(VectorProvider):
       def _setup(self):
           # Initialize connection
           pass
           
       def upsert_vectors(self, index_name, records, namespace=None):
           # Implement upsert logic
           pass
           
       # Implement other required methods...
   ```

2. Register the provider in `factory.py`:
   ```python
   VectorProviderFactory.register_provider("myprovider", MyProvider)
   ```

3. Configure via environment variables:
   ```bash
   VECTOR_PROVIDER=myprovider
   # Add provider-specific settings
   ```

## Provider-Specific Features

### Pinecone
- Supports separate dense and sparse indexes
- Built-in inference API for text-to-vector conversion
- Automatic retry with exponential backoff

### pgvector
- Uses PostgreSQL with pgvector extension
- HNSW indexes for fast similarity search
- Stores sparse vectors as JSONB
- Requires external embedding service for text queries

## Performance Considerations

- **Batch Operations**: Use `batch_upsert_vectors()` for better performance
- **Connection Pooling**: pgvector uses async connection pooling
- **Index Types**: Choose appropriate index types based on your use case
  - Dense vectors: Better for semantic search
  - Sparse vectors: Better for keyword matching
  - Hybrid: Combines both approaches

## Troubleshooting

1. **Provider not found**: Check `VECTOR_PROVIDER` environment variable
2. **Connection errors**: Verify provider-specific configuration
3. **Missing dependencies**: Install provider-specific packages:
   ```bash
   # For pgvector
   pip install asyncpg pgvector
   ```