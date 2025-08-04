# Domain Feature Implementation - Discovery Node
## July 29, 2025

## Overview
Added support for custom domains in organization configuration. Organizations can now have either:
1. A custom domain (e.g., `agent.brand.com`) configured by the seller
2. An auto-generated subdomain with the configured HOST (e.g., `brand-name.localhost:8000`)

## Database Changes

### New Column
- Added `domain` column to the `organizations` table
- Type: `String`, nullable
- Comment: "Custom domain configured by seller (e.g., agent.brand.com)"

### Migration
- File: `migrations/versions/7cc8136a45a3_add_domain_field_to_organizations_table.py`
- Run: `alembic upgrade head`

## Code Changes

### 1. Configuration (`app/core/config.py`)
```python
# Host configuration for feed URL generation
HOST: str = os.getenv("HOST", "localhost:8000")
```
- Reads HOST from environment variable
- Default: `localhost:8000`

### 2. Model (`app/db/models/organization.py`)
```python
domain = Column(String, nullable=True, comment="Custom domain configured by seller (e.g., agent.brand.com)")
```

### 3. Schemas (`app/schemas/organization.py`)
- Added `domain` field to:
  - `OrganizationBase`
  - `OrganizationUpdate`

### 4. API Routes (`app/api/routes/organization.py`)
- Added `domain` field to `OrganizationData` model
- Updated organization creation to include domain
- Updated organization update to include domain

### 5. Feed URL Generation (`app/utils/formatters.py`)
```python
# Add product feed URL using domain or subdomain+HOST
if hasattr(organization, 'domain') and organization.domain:
    # Use custom domain if configured
    response["cmp:productFeed"] = {
        "@type": "DataFeed",
        "url": f"https://{organization.domain}/feed/feed.json"
    }
elif hasattr(organization, 'subdomain') and organization.subdomain:
    # Use subdomain with HOST from config
    from app.core.config import settings
    response["cmp:productFeed"] = {
        "@type": "DataFeed",
        "url": f"https://{organization.subdomain}.{settings.HOST}/feed/feed.json"
    }
```

## Usage Examples

### 1. Organization with Custom Domain
```json
{
  "organization": {
    "name": "Example Brand",
    "url": "https://example.com",
    "domain": "agent.example.com",
    "shop": "example.myshopify.com",
    "brand": {
      "name": "Example",
      "url": "https://example.com"
    }
  }
}
```
**Result**: Feed URL will be `https://agent.example.com/feed/feed.json`

### 2. Organization without Custom Domain
```json
{
  "organization": {
    "name": "Another Brand",
    "url": "https://another.com",
    "shop": "another.myshopify.com",
    "brand": {
      "name": "Another",
      "url": "https://another.com"
    }
  }
}
```
**Result**: Feed URL will be `https://another-brand.localhost:8000/feed/feed.json`
(subdomain auto-generated from name)

## Environment Configuration
Add to `.env` file:
```
HOST=localhost:8000
```
Or for production:
```
HOST=overway.net
```

## Migration Steps
1. Update code with these changes
2. Run database migration: `alembic upgrade head`
3. Update `.env` file with appropriate HOST value
4. Restart Discovery Node service

## Benefits
1. **Flexibility**: Sellers can configure custom domains for their agents
2. **Backward Compatibility**: Existing organizations continue to work with subdomain+HOST
3. **Clean URLs**: Custom domains provide cleaner, branded feed URLs
4. **Easy Configuration**: Simple environment variable for HOST configuration