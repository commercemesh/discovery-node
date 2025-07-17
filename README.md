# Discovery Node

A product discovery engine that uses AI to find products that match search queries. Built with FastAPI, Celery, PostgreSQL, and Pinecone for vector search.

## 🚀 Features

- **Product Discovery**: AI-powered product search and matching
- **Data Ingestion**: Automated ingestion from CMP feeds and local sources
- **Vector Search**: Semantic search using Pinecone vector database
- **Scheduled Tasks**: Background processing with Celery
- **REST API**: FastAPI-based API with automatic documentation
- **MCP Server**: Model Context Protocol server for AI assistant integration
- **Multi-brand Support**: Handle multiple brands and organizations

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
│   Pinecone      │    │   Redis         │    │   Data Sources  │
│   Vector DB     │    │   Message Queue │    │   (CMP Feeds)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- Pinecone account and API key

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
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Configure database**
   ```bash
   # Run database migrations
   alembic upgrade head
   ```

5. **Set up Pinecone**
   ```bash
   # Run the Pinecone setup script
   python scripts/setup_pinecone.py
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/discovery_db

# Redis (for Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_environment
PINECONE_DENSE_INDEX=your_dense_index_name
PINECONE_SPARSE_INDEX=your_sparse_index_name

# Application
DEBUG=true
LOG_LEVEL=info
DATA_DIR=/path/to/your/data
INGESTION_CONFIG_PATH=/path/to/ingestion.yaml
```

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
- `GET /api/products` - List products
- `GET /api/products/{urn}` - to be done

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


