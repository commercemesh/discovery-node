# tests/services/test_organization_service.py
import json


def test_process_organization(organization_service, test_organization_data):
    """Test processing an organization from CMP data."""
    # Process the organization
    org_id = organization_service.process_organization(test_organization_data)

    # Verify organization was created
    assert org_id is not None

    # Retrieve the organization
    org = organization_service.get_organization(org_id)

    # Verify organization data
    assert org is not None
    assert org.name == "Acme Corporation"
    assert (
        org.description
        == "Acme Corporation is a leading provider of innovative solutions."
    )
    assert org.url == "https://acme-corp.example.com"
    assert org.logo_url == "https://example.com/assets/acme-logo.png"
    assert org.urn == "urn:cmp:orgid:123e4667-e89b-12d3-a456-426614174000"
    assert org.feed_url == "https://acme-corp.example.com/feeds/products.json"

    # Verify social links
    if isinstance(org.social_links, list):
        assert "https://www.linkedin.com/company/acme-corp" in org.social_links
        assert "https://twitter.com/acme_corp" in org.social_links
    elif isinstance(org.social_links, str):
        # If stored as JSON string, parse it
        links = json.loads(org.social_links)
        assert "https://www.linkedin.com/company/acme-corp" in links
        assert "https://twitter.com/acme_corp" in links
    else:
        # If stored as JSONB/dict
        assert "https://www.linkedin.com/company/acme-corp" in org.social_links
        assert "https://twitter.com/acme_corp" in org.social_links

    # Verify raw data was stored
    assert org.raw_data is not None
