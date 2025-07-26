# Discovery Node v0.1.0

## 🎉 Initial Alpha Release

We're excited to announce the first release of Discovery Node - a powerful data ingestion and vector search platform for e-commerce product catalogs following the Commerce Mesh Protocol (CMP) standards.

## 🚀 Key Features

### Core Capabilities
- **Multi-Source Data Ingestion**: Support for local files and CMP-compliant feeds
- **Vector Search**: Dual vector database support (PostgreSQL with pgvector and Pinecone)
- **Flexible Architecture**: Modular design with support for multiple embedding providers
- **Background Processing**: Celery-based async task processing for scalable ingestion
- **RESTful API**: FastAPI-based API for search and data access

### Data Ingestion
- **Brand Registry Support**: Ingest organization and brand data from CMP-compliant registries
- **Product Feed Processing**: Handle sharded product feeds with automatic shard discovery
- **Batch Processing**: Efficient batch processing of large product catalogs
- **Error Handling**: Robust error handling with retry mechanisms

### Vector Search
- **Multiple Embedding Providers**: Support for OpenAI embeddings with extensible architecture
- **Hybrid Search**: Combined dense and sparse vector search capabilities
- **Configurable Indexes**: Switch between pgvector and Pinecone based on requirements
- **Real-time Updates**: Automatic vector updates on product data changes

### Database & Storage
- **PostgreSQL**: Primary database with pgvector extension for vector similarity search
- **Alembic Migrations**: Database version control and migration management
- **Efficient Schema**: Optimized schema for product, brand, and organization data

## 📋 Requirements

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Redis (for Celery task queue)
- OpenAI API key (for embeddings)
- Optional: Pinecone API key (for Pinecone vector store)

## 🛠️ Configuration

The system is configured via environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/discovery_node

# Vector Store
VECTOR_PROVIDER=pgvector  # or pinecone

# Embeddings
EMBEDDING_MODEL_PROVIDER=openai
EMBEDDING_API_KEY=your-openai-api-key
EMBEDDING_MODEL_NAME=text-embedding-3-small

# Optional Pinecone
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=your-environment
PINECONE_INDEX_NAME=your-index-name
```

## 🏃 Getting Started

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup Database**
   ```bash
   alembic upgrade head
   ```

3. **Configure Ingestion**
   Edit `ingestion.yaml` to define your data sources

4. **Start Services**
   ```bash
   # Start Redis
   redis-server
   
   # Start Celery Worker
   celery -A app.worker worker --loglevel=info
   
   # Start API Server
   uvicorn main:app --reload
   ```

5. **Trigger Ingestion**
   ```bash
   python main.py ingest-all
   ```

## 📊 Sample Data

The release includes sample data for testing:
- `samples/acme-solutions/`: Example brand registry and product feed
- Includes TVs and cameras with multiple variants
- Demonstrates proper CMP data structure

## 🐛 Known Issues

1. **Feed Index Organization URN**: The system now supports both `orgid` and `organization.urn` formats in feed indexes
2. **Vector Updates**: Products are updated by URN, not UUID
3. **Embedding Service**: Currently requires OpenAI API key; local embedding support planned

## 🔮 Future Enhancements

- Additional embedding providers (Cohere, local models)
- More data source adapters (Shopify, BigCommerce, etc.)
- Advanced search features (filters, facets, recommendations)
- Admin UI for monitoring and management
- Comprehensive test coverage
- Performance optimizations for large catalogs

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines (coming soon).

## 📄 License

[License information to be added]

## 🙏 Acknowledgments

Built with the Commerce Mesh Protocol (CMP) standards for interoperable commerce data.

---

**Note**: This is an alpha release (v0.1.0) of Discovery Node. APIs and interfaces may change in future releases. We're actively developing new features and welcome feedback from the community.