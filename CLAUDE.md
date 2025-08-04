# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development Server
```bash
# Start API server (development mode with auto-reload)
python main.py serve

# Start API server (production mode)
python main.py serve --production --workers 4
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run worker tests (including database integration)
pytest tests/worker/ -v

# Run specific test types
pytest tests/worker/test_worker_ingestion.py -v  # Mocked tests (fast)
pytest tests/worker/test_database_ingestion.py -v  # Database integration tests

# Run individual tests
pytest tests/worker/test_database_ingestion.py::TestDatabaseIngestion::test_ingest_registry_to_database -v -s
```

### Linting and Formatting
```bash
# Format code with black and isort
uv run black .
uv run isort .
```

### Database Migrations
```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Worker and Scheduler
```bash
# Start Celery worker
celery -A app.worker.celery_app worker --loglevel=info

# Start Celery scheduler (separate terminal)
celery -A app.worker.celery_app beat --loglevel=info
```

### MCP Server
```bash
# Start MCP server for AI assistant integration
python main.py mcp
```

### Data Ingestion
```bash
# List available ingestors
python main.py list-ingestors

# Run ingestion for specific ingestor
python main.py ingest --ingestor <name> --type all
```

## Architecture Overview

This is a **Discovery Node** - an AI-powered product search engine using semantic search with multiple vector storage backends.

### Core Components

1. **FastAPI Web Server** (`app/api/`) - REST API with automatic OpenAPI docs
   - `/api/products` - Natural language product search endpoint
   - `/health` - Health check endpoint

2. **Database Layer** (`app/db/`)
   - SQLAlchemy models for products, brands, categories, organizations
   - Repository pattern for data access
   - PostgreSQL with optional PGVector extension

3. **Vector Storage** (`app/vectors/`)
   - Abstracted vector storage interface supporting:
     - PGVector (PostgreSQL extension)
     - Pinecone (cloud vector database)
   - Handles embedding storage and similarity search

4. **Search Services** (`app/services/search/`)
   - Factory pattern for search backend selection
   - Supports PGVector and Pinecone search implementations
   - Hybrid search combining semantic and traditional filtering

5. **Ingestion System** (`app/ingestors/`)
   - Automated data ingestion from various sources
   - Registry and feed processing
   - Vector embedding generation using OpenAI
   - Configured via `ingestion.yaml`

6. **Worker System** (`app/worker/`)
   - Celery-based background task processing
   - Scheduled ingestion tasks
   - Redis as message broker

7. **MCP Server** (`app/mcp/`)
   - Model Context Protocol server for AI assistant integration
   - Exposes search tools and resources
   - Uses same search logic as REST API

### Key Design Patterns

- **Repository Pattern**: All database operations go through repository classes
- **Factory Pattern**: For vector storage and search backend selection
- **Service Layer**: Business logic separated from data access
  - **Important**: All business logic belongs in the service layer, not in API routes
  - API routes should only validate input and delegate to service methods
  - Services handle complex operations like creating related entities, data transformation, etc.
- **Data Format Conversion**: Use formatters for all JSON-LD conversions
  - **Important**: All JSON-LD to internal schema conversions should use `app.utils.formatters`
  - Input conversion: `parse_jsonld_to_*` functions convert JSON-LD to service schemas (ProductCreate, etc.)
  - Output conversion: `format_*` functions convert internal objects to JSON-LD format
  - Services should only work with schema objects, never with raw JSON-LD
  - This ensures consistent data transformation and separation of concerns
- **Dependency Injection**: Using FastAPI's dependency system
- **Configuration Management**: Environment-based configuration with Pydantic

### Environment Configuration

The application uses environment variables configured in `.env` file:
- `DATABASE_URL`: PostgreSQL connection string
- `VECTOR_STORAGE_BACKEND`: Choose between `pgvector` or `pinecone`
- `EMBEDDING_API_KEY`: OpenAI API key for embeddings
- `REDIS_URL`: Redis connection for Celery

### Testing Strategy

- Unit tests with mocked dependencies
- Database integration tests using `cmp_discovery_test` database
- Separate test configuration in `tests/test.env`
- Use `-v` for verbose output, `-s` to see print statements