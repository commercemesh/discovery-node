# Discovery Node

A high-performance product discovery engine that uses AI-powered semantic search to find products matching natural language queries. Built with FastAPI, PostgreSQL, and supports multiple vector storage backends (PGVector and Pinecone) for scalable semantic search capabilities.

## 🚀 Features

- **AI-Powered Search**: Natural language product search using state-of-the-art embeddings
- **Multiple Vector Backends**: Support for both PGVector (PostgreSQL) and Pinecone
- **Hybrid Search**: Combines semantic search with traditional filtering
- **Data Ingestion**: Automated ingestion from various feed formats
- **Scheduled Tasks**: Background processing with Celery for continuous updates
- **REST API**: FastAPI-based API with automatic OpenAPI documentation
- **MCP Server**: Model Context Protocol server for AI assistant integration
- **Multi-tenant Support**: Handle multiple brands and organizations
- **Full-Text Search**: Tantivy-based search engine for text matching
- **Scalable Architecture**: Microservices design with Redis message queue

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   Celery        │    │   PostgreSQL    │
│   Web Server    │    │   Worker        │    │   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Vector Storage │    │   Redis         │    │   Search Engine │
│ PGVector/Pinecone│    │   Message Queue │    │    Tantivy      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL 14+ (with pgvector extension if using PGVector backend)
- Redis 6+
- OpenAI API key (for embeddings)
- Optional: Pinecone account (if using Pinecone backend)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd discovery-node
   ```

2. **Install dependencies**
   ```bash
   # Using uv (recommended)
   uv sync
   
   # Or using pip
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.sample .env
   # Edit .env with your configuration
   ```

4. **Configure database**
   ```bash
   # Run database migrations
   alembic upgrade head
   ```

5. **Initialize vector storage**
   ```bash
   # If using PGVector (default)
   # The pgvector extension will be created automatically
   
   # If using Pinecone
   python scripts/setup_pinecone.py
   ```

## ⚙️ Configuration

### Environment Variables

See `.env.sample` for a complete list of configuration options. Key variables include:

- `DATABASE_URL`: PostgreSQL connection string
- `VECTOR_STORAGE_BACKEND`: Choose between `pgvector` (default) or `pinecone`
- `EMBEDDING_API_KEY`: OpenAI API key for generating embeddings
- `REDIS_URL`: Redis connection for Celery tasks
- `SEARCH_BACKEND`: Choose between `tantivy` (default) or `opensearch`

### Ingestion Configuration

Configure data sources in `ingestion.yaml`:
You can use the samples files provided /samples  

```yaml
ingestion:
  - name: "acme-corp"
    source_type: "local"
    registry: "/user/username/samples/acme-solutions/brand-registory.json"
    feed_path: "/user/username/samples/acme-solutions/feed/feed.json"
    schedule: "0 */4 * * *"  # Every 4 hours
```

## 🚀 Usage

### Start the API Server

```bash
# Development mode
python main.py serve

# Production mode
python main.py serve --production --workers 4
```

### Start the MCP Server

```bash
# Start MCP server for AI assistant integration
python main.py mcp
```

### Start Celery Worker

```bash
# Start worker
celery -A app.worker.celery_app worker --loglevel=info

# Start scheduler (in separate terminal)
celery -A app.worker.celery_app beat --loglevel=info
```

### API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📁 Project Structure

```
discovery-node/
├── app/
│   ├── api/                 # FastAPI routes and web app
│   ├── core/                # Configuration and logging
│   ├── db/                  # Database models and repositories
│   ├── ingestors/           # Data ingestion components
│   ├── mcp/                 # MCP server implementation
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic services
│   └── worker/              # Celery tasks and schedulers
├── docs/                    # Documentation
├── examples/                # Example code and clients
├── migrations/              # Database migrations
├── samples/                 # Sample data and feeds
├── scripts/                 # Utility scripts
├── tests/                   # Test suite
├── ingestion.yaml           # Ingestion configuration
├── main.py                  # CLI entry point
└── pyproject.toml          # Project configuration
```

## 🔧 Development

### Running Tests

The project includes comprehensive test suites for different scenarios:

#### 1. Run All Tests
```bash
# Run all worker tests (both mocked and database integration)
python -m pytest tests/worker/ -v

# Run all tests in the project
python -m pytest tests/ -v
```

#### 2. Run Specific Test Types

**Mocked Tests (fast, don't touch database):**
```bash
python -m pytest tests/worker/test_worker_ingestion.py -v
```

**Database Integration Tests (write to test database):**
```bash
python -m pytest tests/worker/test_database_ingestion.py -v
```

**Real Database Population Test (populates with sample data):**
```bash
python -m pytest tests/worker/test_real_database_integration.py -v -s
```

#### 3. Run Individual Tests

**Test registry ingestion to database:**
```bash
python -m pytest tests/worker/test_database_ingestion.py::TestDatabaseIngestion::test_ingest_registry_to_database -v -s
```

**Test complete ingestion workflow:**
```bash
python -m pytest tests/worker/test_database_ingestion.py::TestDatabaseIngestion::test_ingest_all_task_with_database -v -s
```

**Populate test database with Acme data:**
```bash
python -m pytest tests/worker/test_real_database_integration.py::TestRealDatabaseIntegration::test_populate_test_database_with_acme_data -v -s
```

#### 4. Check Database After Tests

After running the database tests, you can inspect the `cmp_discovery_test` database:

```sql
-- Connect to your PostgreSQL and check the test database
\c cmp_discovery_test

-- See what data was inserted
SELECT * FROM organizations;
SELECT * FROM brands;
SELECT * FROM product_groups;
SELECT * FROM categories;
```

#### 5. Test Environment Setup

The tests use a separate test database defined in `tests/test.env`:

```bash
# Check that test.env is being used
cat tests/test.env

# Verify test database connection
psql postgresql://postgres:admin@localhost:5432/cmp_discovery_test -c "SELECT 1;"
```

#### Test Options

- Use `-v` for verbose output (shows test names)
- Use `-s` to see print statements and debug output
- Use `--tb=short` for shorter error traces if tests fail

The database integration tests will actually populate your `cmp_discovery_test` database with real data from the ingestion.yaml scenarios, so you'll be able to see the results of the ingestion process in the database.

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Code Formatting

```bash
# Using uv
uv run black .
uv run isort .
```

## 📊 API Endpoints

### Products
- `GET /api/products` - Search products with natural language queries
  - Query parameters: `q` (search query), `limit`, `offset`, `brand`, `category`
- `GET /api/products/{urn}` - Get product details by URN (coming soon)

### Health & Monitoring
- `GET /health` - Health check endpoint
- `GET /api/stats` - System statistics (coming soon)

## 🤖 MCP Server

The Discovery Node includes a Model Context Protocol (MCP) server that provides AI assistants with a search tool that uses the exact same logic as the `/products` API endpoint. The MCP server exposes:

### Available Tools
- **search** - Search for products using natural language query
  - Uses the same hybrid search logic as the `/products` API
  - Returns structured JSON-LD response with product details, offers, and media

### Available Resources
- **discovery://products** - Access to products database
- **discovery://categories** - Access to categories database
- **discovery://brands** - Access to brands database

For detailed MCP server documentation, see [docs/mcp-server.md](docs/mcp-server.md).



## 🔄 Data Ingestion

The system supports multiple ingestion modes:

1. **Local Sources**: Read from local JSON files


### Adding New Data Sources

1. Create a new ingestor in `app/ingestors/sources/`
2. Update `ingestion.yaml` with the new source
3. Configure the schedule for automatic ingestion

## 📈 Monitoring

- **Health Check**: `/health` endpoint
- **Logs**: Check `logs/` directory
- **Celery Monitoring**: TODO


