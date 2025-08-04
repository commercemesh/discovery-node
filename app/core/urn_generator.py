import uuid
from urllib.parse import urlparse
from app.core.config import settings

# Static CMP namespace for consistent URN generation
CMP_NAMESPACE = uuid.UUID("4c2d9653-e971-4093-8d5b-82da447c2e85")

def extract_domain_from_url(url: str) -> str:
    """
    Extract domain name from URL.
    
    Args:
        url: The URL to extract domain from (e.g., "http://www.myshopify.com")
        
    Returns:
        The domain name (e.g., "www.myshopify.com")
    """
    if not url:
        raise ValueError("URL cannot be empty")
    
    # Parse the URL
    parsed = urlparse(url)
    
    # Get the netloc (domain + port if any)
    domain = parsed.netloc
    
    # Remove port if present
    if ':' in domain:
        domain = domain.split(':')[0]
    
    # If no netloc found, try to parse as if it's just a domain
    if not domain:
        # Remove protocol if present
        clean_url = url.replace('http://', '').replace('https://', '')
        # Remove path and query parameters
        domain = clean_url.split('/')[0].split('?')[0]
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
    
    if not domain:
        raise ValueError(f"Could not extract domain from URL: {url}")
    
    return domain

def generate_org_urn(domain: str) -> str:
    """
    Generate URN for organization based on domain.
    
    Args:
        domain: The domain name (e.g., "www.myshopify.com")
        
    Returns:
        URN in format "urn:cmp:org:{uuid5}"
    """
    
    # Generate UUID5 using the static CMP namespace and domain
    urn_id = uuid.uuid5(CMP_NAMESPACE, domain)
    
    return f"urn:cmp:org:{urn_id}"

def generate_brand_urn(brand_name: str, org_urn: str) -> str:
    """
    Generates deterministic URN for a brand.

    Args:
        brand_name: The brand name
        org_urn: The organization URN
        
    Returns:
        URN in format "urn:cmp:org:{org_uuid}:brand:{brand_uuid}"
    """
    
    # Extract org UUID part from URN
    org_uuid_part = org_urn
    if org_urn and org_urn.startswith("urn:cmp:org:"):
        org_uuid_part = org_urn.split("urn:cmp:org:")[1]
    
    brand_name = brand_name.strip()
    seed = f"{brand_name.lower()}@{org_uuid_part}"

    brand_uuid = uuid.uuid5(CMP_NAMESPACE, seed)
    
    return f"urn:cmp:org:{org_uuid_part}:brand:{brand_uuid}"

def generate_sku_urn(sku: str, org_urn: str, brand_urn: str) -> str:
    """
    Generates deterministic URN for a SKU.
    
    Args:
        sku: The SKU identifier
        org_urn: The organization URN
        brand_urn: The brand URN
        
    Returns:
        URN in format "urn:cmp:org:{org_uuid}:brand:{brand_uuid}:sku:{sku_uuid}"
    """

    # Extract org UUID part
    org_uuid_part = org_urn
    if org_urn and org_urn.startswith("urn:cmp:org:"):
        org_uuid_part = org_urn.split("urn:cmp:org:")[1]

    # Extract brand UUID part
    brand_uuid_part = brand_urn
    if brand_urn and brand_urn.startswith("urn:cmp:org:"):
        # Extract just the brand UUID part from urn:cmp:org:{org_uuid}:brand:{brand_uuid}
        parts = brand_urn.split(":")
        if len(parts) >= 6:  # urn:cmp:org:{org_uuid}:brand:{brand_uuid}
            brand_uuid_part = parts[5]  # Get the brand UUID part
        else:
            brand_uuid_part = brand_urn.split("urn:cmp:org:")[1]
    elif brand_urn and ":" in brand_urn:
        # If it's not a full URN but contains a colon, assume it's just the UUID part
        brand_uuid_part = brand_urn.split(":")[-1]
    
    sku = sku.strip()
    seed = f"{sku.lower()}@{brand_uuid_part}"

    sku_uuid = uuid.uuid5(CMP_NAMESPACE, seed)

    return f"urn:cmp:org:{org_uuid_part}:brand:{brand_uuid_part}:sku:{sku_uuid}"

def generate_product_group_urn(product_group_id: str, org_urn: str, brand_urn: str) -> str:
    """
    Generates deterministic URN for a product group.
    
    Args:
        product_group_id: The product group identifier
        org_urn: The organization URN
        brand_urn: The brand URN
        
    Returns:
        URN in format "urn:cmp:org:{org_uuid}:brand:{brand_uuid}:product:{product_uuid}"
    """

    # Extract org UUID part
    org_uuid_part = org_urn
    if org_urn and org_urn.startswith("urn:cmp:org:"):
        org_uuid_part = org_urn.split("urn:cmp:org:")[1]

    # Extract brand UUID part
    brand_uuid_part = brand_urn
    if brand_urn and brand_urn.startswith("urn:cmp:org:"):
        # Extract just the brand UUID part from urn:cmp:org:{org_uuid}:brand:{brand_uuid}
        parts = brand_urn.split(":")
        if len(parts) >= 6:  # urn:cmp:org:{org_uuid}:brand:{brand_uuid}
            brand_uuid_part = parts[5]  # Get the brand UUID part
        else:
            brand_uuid_part = brand_urn.split("urn:cmp:org:")[1]
    elif brand_urn and ":" in brand_urn:
        # If it's not a full URN but contains a colon, assume it's just the UUID part
        brand_uuid_part = brand_urn.split(":")[-1]
    
    product_group_id = product_group_id.strip()
    seed = f"{product_group_id.lower()}@{brand_uuid_part}"

    product_uuid = uuid.uuid5(CMP_NAMESPACE, seed)

    return f"urn:cmp:org:{org_uuid_part}:brand:{brand_uuid_part}:product:{product_uuid}"

def generate_urn_from_url(url: str, urn_type: str = "org") -> str:
    """
    Generate URN from URL for specified type.
    
    Args:
        url: The URL to extract domain from
        urn_type: Type of URN ("org" or "brand")
        
    Returns:
        URN string
    """
    domain = extract_domain_from_url(url)
    
    if urn_type == "org":
        return generate_org_urn(domain)
    elif urn_type == "brand":
        return generate_brand_urn(domain, None)
    else:
        raise ValueError(f"Invalid URN type: {urn_type}. Must be 'org' or 'brand'")