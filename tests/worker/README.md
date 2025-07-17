# Worker Tests

This directory contains tests for the worker functionality, specifically testing ingestion tasks with different configurations.

## Test Files

- `test_worker_ingestion.py` - Comprehensive tests for worker ingestion tasks
- `test_runner.py` - Test runner script for running tests with different configurations
- `ingestion_test_config_1.yaml` - Test configuration for CMP feeds
- `ingestion_test_config_2.yaml` - Test configuration for local feeds

## Test Configurations

### Configuration 1: CMP Feeds
- **File**: `tests/ingestion_test_config_1.yaml`
- **Type**: Native CMP feeds (single brand)
- **Source**: Remote registry from GitHub
- **Features**: Organization filtering

### Configuration 2: Local Feeds
- **File**: `tests/ingestion_test_config_2.yaml`
- **Type**: Local feeds (single brand)
- **Source**: Local files in samples directory
- **Features**: Local registry and feed files

## Running Tests

### Option 1: Run with specific configuration

```bash
# Set the ingestion config path and run tests
export INGESTION_CONFIG_PATH=tests/ingestion_test_config_1.yaml
pytest tests/worker/test_worker_ingestion.py -v
```

### Option 2: Run with different configurations automatically

```bash
# Run the test runner script
python run_worker_tests.py
```

### Option 3: Run the comprehensive test runner

```bash
# Run the worker test runner
python tests/worker/test_runner.py
```

## Test Environment Setup

The tests use the following environment variables:

- `DATABASE_URL`: Test database connection
- `CELERY_BROKER_URL`: Redis broker for Celery
- `CELERY_RESULT_BACKEND`: Redis backend for Celery results
- `INGESTION_CONFIG_PATH`: Path to the ingestion configuration file
- `TRIGGER_INGESTION_ON_STARTUP`: Set to false for tests
- `FEED_CHECK_INTERVAL`: Reduced interval for faster tests

## Test Coverage

The tests cover:

1. **Task Execution**: Testing individual ingestion tasks (registry, feed, vector)
2. **Configuration Loading**: Testing scheduler configuration from YAML files
3. **Error Handling**: Testing error scenarios and retry mechanisms
4. **Integration**: Testing complete ingestion flows
5. **Different Configurations**: Testing both CMP and local feed configurations

## Test Structure

### TestWorkerIngestion
- Tests individual task functions
- Tests configuration loading
- Tests error handling and retry mechanisms
- Tests scheduler configuration

### TestWorkerIntegration
- Tests complete workflow integration
- Tests environment configuration
- Tests task execution flow

## Mocking

The tests use extensive mocking to avoid:
- Actual database operations
- Real API calls
- Actual file system operations
- Real Celery task execution

This ensures tests are fast, reliable, and don't require external dependencies.

## Running Individual Tests

```bash
# Run specific test class
pytest tests/worker/test_worker_ingestion.py::TestWorkerIngestion -v

# Run specific test method
pytest tests/worker/test_worker_ingestion.py::TestWorkerIngestion::test_ingest_all_with_config_1 -v

# Run integration tests only
pytest tests/worker/test_worker_ingestion.py::TestWorkerIntegration -v
```

## Debugging

To debug tests, you can:

1. Add `--pdb` flag to pause on failures
2. Add `--tb=long` for detailed tracebacks
3. Set `LOG_LEVEL=debug` for verbose logging

```bash
pytest tests/worker/test_worker_ingestion.py -v --pdb --tb=long
``` 