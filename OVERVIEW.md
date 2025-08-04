# Discovery Node - Technical Overview

## Introduction

Discovery Node is an AI-powered product search engine that provides semantic search capabilities with multi-tenant support. It serves as the core backend for the CommerceMesh Platform (CMP) discovery system, enabling organizations to offer intelligent product discovery through natural language queries.

## Core Features

### 🔍 Semantic Search Engine
- **Natural Language Processing**: Understands queries like "comfortable running shoes under $100" or "eco-friendly water bottles"
- **Vector Similarity Search**: Uses OpenAI embeddings to find semantically similar products
- **Hybrid Search**: Combines semantic search with traditional filters (price, category, brand)
- **Multiple Vector Storage Backends**: Supports both PGVector (PostgreSQL) and Pinecone

### 🏢 Multi-Tenant Architecture
- **Subdomain-Based Isolation**: Each organization gets their own subdomain (e.g., `acme.discovery.com`)
- **Data Segregation**: Complete isolation of product data between tenants
- **Custom Branding**: Organizations can customize their brand registry information
- **API Key Authentication**: Secure access control with organization-scoped API keys

### 📊 Analytics & Metrics
- **Comprehensive API Usage Tracking**: Monitors all API calls with response times, status codes, and errors
- **Organization-Scoped Analytics**: Each tenant sees only their own metrics
- **Endpoint Categorization**: Breaks down usage by feed, admin, query, and public endpoints
- **Timezone-Aware Reporting**: Supports multiple timezones for accurate daily metrics
- **Root Path Tracking**: Special tracking for brand registry access via subdomains

## API Interfaces

### 1. Query API (`/api/v1/query`)
The main search interface for product discovery:

```http
POST /api/v1/query/search
{
  "query": "organic coffee beans",
  "filters": {
    "price_min": 10,
    "price_max": 50,
    "category": "beverages"
  },
  "limit": 20
}
```

**Features:**
- Natural language query processing
- Advanced filtering options
- Pagination support
- Schema.org compliant responses

### 2. Admin API (`/api/v1/admin`)
Protected endpoints for data management:

```http
# Product Management
GET    /api/v1/admin/products
POST   /api/v1/admin/products
PUT    /api/v1/admin/products/{id}
DELETE /api/v1/admin/products/{id}

# Analytics
GET    /api/v1/admin/analytics
```

**Authentication:** Requires API key with admin permissions

### 3. Feed API (`/api/v1/feed`)
Standardized product feed access:

```http
GET /api/v1/feed/products.json
GET /api/v1/feed/products.xml
GET /api/v1/feed/products.csv
```

**Features:**
- Multiple format support (JSON, XML, CSV)
- Pagination for large catalogs
- Schema.org compliant data structure

### 4. Public API (`/api/v1`)
Open endpoints for basic information:

```http
# Organization Management
POST /api/v1/organizations      # Create new organization
GET  /api/v1/organizations/{urn} # Get organization details

# Health Check
GET  /api/v1/health
```

### 5. Brand Registry (Root Path)
Special endpoint for brand information:

```http
GET http://acme.discovery.com/
```

Returns organization's brand registry in JSON-LD format.

## MCP Server Integration

Discovery Node includes a Model Context Protocol (MCP) server that allows AI assistants to:

- **Search Products**: Natural language product search
- **Manage Inventory**: CRUD operations on products
- **Access Analytics**: Query usage metrics and performance data

**Usage:**
```bash
python main.py mcp
```

## Data Model

### Core Entities

1. **Organizations**
   - Multi-tenant support
   - Custom subdomains
   - Brand information
   - API key management

2. **Products**
   - Schema.org compliant structure
   - Rich metadata support
   - Vector embeddings for similarity search
   - Flexible offer pricing

3. **Categories**
   - Hierarchical taxonomy
   - Organization-specific categories
   - Automatic categorization support

4. **API Usage Metrics**
   - Request/response tracking
   - Performance metrics
   - Error monitoring
   - Organization attribution

## Architecture Components

### 1. Web Framework
- **FastAPI**: Modern, fast web framework
- **Async Support**: High-performance async request handling
- **Automatic OpenAPI**: Self-documenting APIs at `/docs`

### 2. Database Layer
- **PostgreSQL**: Primary data store
- **SQLAlchemy ORM**: Database abstraction
- **Alembic**: Database migration management
- **Repository Pattern**: Clean data access layer

### 3. Vector Storage
- **Abstracted Interface**: Swap between backends easily
- **PGVector**: PostgreSQL-native vector similarity
- **Pinecone**: Cloud-based vector database
- **Automatic Embedding**: OpenAI integration for text embeddings

### 4. Background Processing
- **Celery**: Distributed task queue
- **Redis**: Message broker
- **Scheduled Tasks**: Automated data ingestion
- **Async Processing**: Non-blocking operations

### 5. Ingestion System
- **Multiple Sources**: Registry, feeds, APIs
- **Configurable Pipeline**: YAML-based configuration
- **Incremental Updates**: Efficient data synchronization
- **Error Handling**: Robust failure recovery

## Deployment Options

### Development
```bash
python main.py serve
```

### Production
```bash
python main.py serve --production --workers 4
```

### Environment Configuration
- **Single-Tenant Mode**: Simple deployment for one organization
- **Multi-Tenant Mode**: Full subdomain-based multi-tenancy
- **Vector Backend Selection**: Choose between PGVector or Pinecone
- **Configurable via `.env`**: Easy environment-specific settings

## Security Features

1. **API Key Authentication**
   - Bearer token authentication
   - Scoped permissions (read/write)
   - Audit logging

2. **Multi-Tenant Isolation**
   - Data segregation at database level
   - Organization-scoped queries
   - Subdomain validation

3. **Rate Limiting Support**
   - Configurable limits
   - Per-organization tracking
   - Graceful degradation

## Monitoring & Operations

### Health Checks
```http
GET /api/v1/health
GET /api/v1/admin/analytics/health
```

### Metrics & Analytics
- Real-time API usage statistics
- Performance metrics (response times, error rates)
- Endpoint-specific analytics
- Organization-level insights

### Logging
- Structured logging throughout
- Configurable log levels
- Integration-ready format

## Integration Points

1. **Discovery Client**: Embeddable search widget
2. **Discovery API**: Backend orchestration layer
3. **Discovery Dashboard**: Management interface
4. **Buying Agent**: Automated purchasing decisions

## Use Cases

1. **E-commerce Search**: Natural language product discovery
2. **B2B Catalogs**: Multi-tenant product databases
3. **Marketplace Integration**: Federated product search
4. **AI Shopping Assistants**: Conversational commerce

## Getting Started

1. **Setup Database**: PostgreSQL with optional PGVector extension
2. **Configure Environment**: Copy `.env.example` to `.env`
3. **Run Migrations**: `alembic upgrade head`
4. **Start Server**: `python main.py serve`
5. **Create Organization**: Use `/api/v1/organizations` endpoint
6. **Begin Searching**: Use the Query API with natural language

For detailed setup and usage instructions, see the main README.md file.