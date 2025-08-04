# Feed Serving Implementation - Discovery Node
## July 29, 2025

## Overview
Implemented feed serving functionality that retrieves product feeds from S3 based on subdomain or custom domain. The system maps organization domains/subdomains to their URNs and uses the UUID portion to locate files in S3.

## Architecture

### Request Flow
1. **Request arrives** at `http://subdomain.localhost:8000/feed/feed.json`
2. **Extract host** from request headers
3. **Check custom domain** - Query if host matches any organization's custom domain
4. **Extract subdomain** - If not custom domain, extract first part of host
5. **Get organization** - Lookup by domain or subdomain
6. **Extract URN** - Get organization's URN (e.g., `urn:cmp:org:uuid`)
7. **Extract UUID** - Parse UUID from URN
8. **Construct S3 path** - Use pattern `{uuid}/{filename}`
9. **Retrieve from S3** - Fetch and serve the JSON file

### S3 Storage Pattern
OpenFeed stores files using the organization's UUID:
```
bucket/
├── 6794c67d-8258-5273-a8f7-612f3bfdfe79/
│   ├── feed.json          # Main feed index
│   ├── feed-001.json      # Shard 1
│   ├── feed-002.json      # Shard 2
│   └── ...
```

## Code Changes

### Updated `app/api/routes/feed.py`
- Complete rewrite of `serve_feed` function
- Added support for custom domains
- Proper subdomain extraction
- URN to UUID conversion
- S3 path construction matching OpenFeed's pattern
- Fallback to `feeds/` prefix for legacy feeds

### Key Features
1. **Dual Domain Support**:
   - Subdomain: `overway-inc.localhost:8000`
   - Custom domain: `agent.overway.com`

2. **URN-based Storage**:
   - Organizations identified by URN
   - Files stored by UUID extracted from URN
   - Consistent with OpenFeed's storage strategy

3. **Error Handling**:
   - 400: Bad request (missing host, invalid format)
   - 404: Organization or feed not found
   - 500: Server errors (invalid URN, S3 issues)
   - 503: S3 not configured

4. **CORS Support**:
   - Full CORS headers for crawler/bot access
   - Cache control headers
   - Robot-friendly headers

## Configuration Requirements

### Environment Variables
```bash
# S3 Configuration (required)
AWS_S3_BUCKET_NAME=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Host configuration for feed URL generation
HOST=localhost:8000
```

### Database Requirements
- Organizations must have:
  - `subdomain`: For subdomain-based access
  - `domain`: For custom domain access (optional)
  - `urn`: Required for S3 path construction

## Usage Examples

### 1. Subdomain-based Access
```bash
# Access feed via subdomain
curl http://overway-inc.localhost:8000/feed/feed.json

# With explicit Host header
curl -H "Host: overway-inc.localhost:8000" \
     http://localhost:8000/feed/feed.json
```

### 2. Custom Domain Access
```bash
# Access feed via custom domain
curl http://agent.overway.com/feed/feed.json

# With explicit Host header
curl -H "Host: agent.overway.com" \
     http://localhost:8000/feed/feed.json
```

### 3. Accessing Sharded Feeds
```bash
# Access specific shard
curl http://overway-inc.localhost:8000/feed/feed-001.json
```

## Integration with OpenFeed

OpenFeed creates feeds with this structure:
1. Generates organization with URN
2. Extracts UUID from URN for folder name
3. Stores feeds in S3: `{uuid}/feed.json`
4. Creates shards as needed: `{uuid}/feed-001.json`

Discovery Node serves these feeds by:
1. Resolving subdomain/domain to organization
2. Getting organization's URN
3. Extracting UUID from URN
4. Reading from S3: `{uuid}/{filename}`

## Testing

### Prerequisites
1. Organization exists in database with:
   - Valid subdomain (e.g., `overway-inc`)
   - Valid URN (e.g., `urn:cmp:org:6794c67d-8258-5273-a8f7-612f3bfdfe79`)
   - Optional custom domain (e.g., `agent.overway.com`)

2. Feed exists in S3 at:
   - Path: `{uuid}/feed.json`
   - Where UUID is extracted from organization's URN

### Test Commands
```bash
# Start Discovery Node
python main.py serve

# Test subdomain access
curl -v http://overway-inc.localhost:8000/feed/feed.json

# Test custom domain access
curl -v -H "Host: agent.overway.com" \
     http://localhost:8000/feed/feed.json

# Check response headers
curl -I http://overway-inc.localhost:8000/feed/feed.json
```

## Troubleshooting

### Common Issues

1. **404 Organization not found**
   - Check subdomain exists in database
   - Verify custom domain is set correctly
   - Check logs for extracted subdomain/domain

2. **404 Feed file not found**
   - Verify S3 bucket and credentials
   - Check S3 path: `{uuid}/feed.json`
   - Ensure UUID extraction is correct
   - Check if feed has `feeds/` prefix

3. **500 Invalid URN format**
   - Verify organization has valid URN
   - URN format: `urn:cmp:org:{uuid}`
   - UUID must be valid format

4. **503 S3 not configured**
   - Set AWS_S3_BUCKET_NAME in environment
   - Verify AWS credentials are set

### Debug Logging
The implementation includes extensive logging:
- Host header extraction
- Subdomain/domain resolution
- Organization lookup
- URN and UUID extraction
- S3 path construction
- S3 access attempts

Enable debug logging:
```bash
LOG_LEVEL=debug python main.py serve
```

## Security Considerations

1. **CORS Headers**: Allows all origins for public feed access
2. **No Authentication**: Feeds are publicly accessible
3. **Input Validation**: 
   - Only JSON files allowed
   - UUID format validation
   - Host header validation
4. **Error Messages**: Generic errors to avoid information leakage

## Future Enhancements

1. **Caching Layer**: Add Redis caching for frequently accessed feeds
2. **CDN Integration**: Serve feeds through CloudFront
3. **Compression**: Support gzip compression for large feeds
4. **Rate Limiting**: Add rate limiting per domain/IP
5. **Analytics**: Track feed access patterns