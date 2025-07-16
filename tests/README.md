# Discovery Node Tests

This directory contains comprehensive tests for the Discovery Node API using real database fixtures.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Test fixtures and database configuration
├── run_tests.py             # Test runner script
├── test_db_connection.py    # Database connection tests
├── test_simple.py           # Simple smoke tests
├── api/                     # API endpoint tests
│   ├── __init__.py
│   ├── test_products.py     # Mock-based API tests (legacy)
│   └── test_products_db.py  # Real database API tests (recommended)
├── services/                # Service layer tests
│   ├── __init__.py
│   ├── test_brand_service.py
│   ├── test_integration.py
│   ├── test_organization_service.py
│   └── test_product_service.py
├── fixtures/                # Test data fixtures
│   ├── __init__.py
│   └── test_data.py         # Test data generation functions
└── worker/                  # Worker/background task tests
    └── __init__.py
```

## Setup

### 1. Database Setup

Create a test database:

```sql
CREATE DATABASE cmp_discovery_test;
```

### 2. Environment Variables

Set up test environment variables:

```bash
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/cmp_discovery_test"
export DEBUG="true"
export LOG_LEVEL="debug"
```

### 3. Dependencies

Install test dependencies:

```bash
pip install pytest pytest-asyncio httpx
```

## Running Tests

### Using the Test Runner

```bash
# Run all tests
python tests/run_tests.py

# Run specific test file
python tests/run_tests.py api/test_products_db.py

# Run with verbose output
python tests/run_tests.py -v
```

### Using pytest directly

```bash
# Run all tests
pytest tests/

# Run API tests only
pytest tests/api/

# Run service tests only
pytest tests/services/

# Run database tests only
pytest tests/api/test_products_db.py

# Run with verbose output
pytest -v tests/

# Run specific test class
pytest tests/api/test_products_db.py::TestGetProductWithDatabase

# Run specific test method
pytest tests/api/test_products_db.py::TestGetProductWithDatabase::test_get_product_success
```

## Test Fixtures

### Database Fixtures

- `db_engine` - SQLAlchemy engine for test database
- `db_session` - Database session with transaction rollback
- `test_db_session` - Session for dependency injection
- `app_with_test_db` - FastAPI app with test database

### Service Fixtures

- `product_service` - ProductService instance
- `brand_service` - BrandService instance
- `category_service` - CategoryService instance
- `organization_service` - OrganizationService instance
- `search_service` - SearchService instance

### Data Fixtures

- `test_category` - Test category in database
- `test_brand` - Test brand in database
- `test_organization` - Test organization in database
- `test_product_group` - Test product group in database
- `test_product` - Test product with all relationships
- `test_offer` - Test offer linked to product


## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check if PostgreSQL is running
   - Verify database credentials
   - Ensure test database exists

2. **Migration Errors**
   - Run `alembic upgrade head` manually
   - Check migration files are up to date
   - Verify database schema matches models

3. **Import Errors**
   - Ensure Python path includes project root
   - Check all dependencies are installed
   - Verify import statements are correct

### Debug Mode

Run tests with debug output:

```bash
pytest -v -s --tb=long tests/
```

This will show:
- Detailed error traces
- Print statements
- Database queries (if DB_ECHO is enabled) 