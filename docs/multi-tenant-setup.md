# Multi-Tenant Setup Guide

This guide explains how to configure and use the discovery-node in multi-tenant mode.

## Overview

The discovery-node supports two modes of operation:
- **Single-tenant mode** (default): All data belongs to one organization
- **Multi-tenant mode**: Multiple organizations isolated by subdomain

## Configuration

### Environment Variables

```bash
# Enable multi-tenant mode
MULTI_TENANT_MODE=true

# For single-tenant mode, optionally set default organization
DEFAULT_ORGANIZATION_ID=550e8400-e29b-41d4-a716-446655440000
```

### Database Setup

1. Run the migration to add subdomain support:
```bash
alembic upgrade head
```

2. Ensure each organization has a unique subdomain:
```sql
UPDATE organizations 
SET subdomain = 'insighteditions' 
WHERE name = 'Insight Editions';
```

## How It Works

### Subdomain-Based Routing

In multi-tenant mode, the system uses the subdomain from the Host header to identify the organization:

- `insighteditions.overway.net` → Insight Editions organization
- `acme-solutions.overway.net` → Acme Solutions organization

### Request Flow

1. Client makes request to `insighteditions.overway.net/api/v1/search?q=books`
2. Middleware extracts `insighteditions` from Host header
3. System looks up organization by subdomain
4. All queries are filtered by organization_id
5. Only Insight Editions' products are returned

### API Changes

All API endpoints automatically filter by organization in multi-tenant mode:

- `/api/v1/search` - Returns only products for the subdomain's organization
- `/api/v1/products/{urn}` - Returns 404 if product belongs to different organization
- `/api/v1/filter` - Shows only filters relevant to the organization's products

## Client Configuration

### Direct Access
Clients can access their data directly via subdomain:
```bash
curl -H "Host: insighteditions.overway.net" \
  "http://localhost:8000/api/v1/search?q=star+wars"
```

### Custom Domain Mapping
Organizations can map their own domains using:
- Vercel rewrites
- Cloudflare Workers
- Nginx proxy configuration

Example: `agent.insighteditions.com` → `insighteditions.overway.net`

## Testing Multi-Tenant Setup

1. Set environment variable:
```bash
export MULTI_TENANT_MODE=true
```

2. Add test organizations with subdomains to database

3. Run the test script:
```bash
python test_multitenant.py
```

## Security Considerations

1. **Organization Isolation**: Each organization can only access its own data
2. **Subdomain Validation**: Invalid subdomains return 404
3. **No Cross-Tenant Access**: URNs from one organization cannot be accessed via another's subdomain

## Migration from Single-Tenant

To migrate existing single-tenant deployment:

1. Add subdomain to existing organization
2. Set `DEFAULT_ORGANIZATION_ID` to maintain backward compatibility
3. Enable `MULTI_TENANT_MODE=true`
4. Update clients to use subdomain-based URLs

## Troubleshooting

### Common Issues

1. **"Host header is required"** - Ensure client sends Host header
2. **"Organization not found"** - Check subdomain exists in database
3. **Products not showing** - Verify products have correct organization_id

### Debug Mode

Enable debug logging to see organization resolution:
```bash
export LOG_LEVEL=debug
```

## Example Setup

```python
# 1. Create organizations with subdomains
org1 = Organization(
    name="Insight Editions",
    subdomain="insighteditions",
    # ... other fields
)

org2 = Organization(
    name="Acme Solutions", 
    subdomain="acme-solutions",
    # ... other fields
)

# 2. Products automatically filtered by organization
# When accessing via insighteditions.overway.net,
# only Insight Editions products are visible
```