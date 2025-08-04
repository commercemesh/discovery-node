# PR: Major Bug Fixes and New Features for Discovery Node

## Summary
This PR introduces critical bug fixes for search and ingestion issues, along with new filtering and comparison features. Also includes infrastructure improvements for Redis caching and health monitoring.

## Changes Made

### 🐛 Bug Fixes

1. **Fixed @cmp:media objects not returning in search results**
   - Enhanced media extraction in `_extract_media_from_jsonld` method
   - Updated formatters to include correct JSON-LD context
   - Files: `app/services/search_service.py`, `app/utils/formatters.py`

2. **Fixed duplicate offers during ingestion**
   - Changed from index-based to URN-based product matching
   - Added offer deduplication logic
   - Files: `app/services/product_service.py`, `app/services/offer_service.py`

3. **Fixed MCP server database session management**
   - Implemented factory pattern for proper session lifecycle
   - Files: `app/core/dependencies.py`, `app/mcp/server.py`, `app/mcp/tools/discovery_tools.py`

### ✨ New Features

1. **Request ID Generation and Caching**
   - 6-character request IDs for all responses
   - 15-minute Redis caching (database 2)
   - Enables operation chaining (search → filter → compare)

2. **Product Filtering API**
   - POST `/api/v1/filter`
   - Natural language filtering with regex patterns
   - Price range filtering
   - Returns new request ID for filtered results

3. **Product Comparison API**  
   - POST `/api/v1/compare`
   - Compare 2-5 products by index
   - Auto-detects comparison aspects
   - Provides recommendations and narrative

4. **Health Check Endpoints**
   - `/api/v1/health/detailed` - Checks all dependencies
   - Helps diagnose Redis connectivity issues
   - Tests database, cache, and Pinecone connections

### 🔧 Infrastructure Changes

1. **Render.yaml Updates**
   - Added `VECTOR_PROVIDER=pinecone` to all services
   - Consistent environment configuration

2. **Configuration Management**
   - Added `ingestion.yaml.example` template
   - Added `ingestion.yaml` to `.gitignore`
   - Added optional `CACHE_REDIS_URL` setting

## Known Issues

There's a minor merge conflict in `app/mcp/tools/discovery_tools.py` that needs to be resolved. The conflict is around the formatting of the response handling - both versions are functionally equivalent.

## Testing
- ✅ All unit tests pass
- ✅ Integration tests for new features
- ✅ Manual testing completed
- ✅ Health check endpoint verified

## Deployment Notes
- No database migrations required
- Redis cache will auto-populate
- Use `/api/v1/health/detailed` to verify Redis connectivity on Render

## Commits Included
- 4711d37 - Add detailed health check and improve Redis cache configuration
- 195195a - Add ingestion.yaml.example and update .gitignore
- 851c566 - updating for render
- fe4a88f - added compare api
- f4b5854 - BUG FIX: sending missing def _extract_media_from_jsonld
- 6b4a297 - Fix MCP server to use same search service as API
- 6f62229 - Fix MCP server database session management

Ready for review and merge!