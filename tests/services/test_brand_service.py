# tests/services/test_brand_service.py


def test_process_brand(brand_service, organization_service, test_organization_data):
    """Test processing a brand from CMP data."""
    # First create the organization
    org_id = organization_service.process_organization(test_organization_data)

    # Get the first brand data
    brand_data = test_organization_data["brand"][0]

    # Process the brand
    brand_id = brand_service.process_brand(brand_data, org_id)

    # Verify brand was created
    assert brand_id is not None

    # Retrieve the brand
    brand = brand_service.get_brand(brand_id)

    # Verify brand data
    assert brand is not None
    assert brand.name == "WidgetCo"
    assert brand.logo_url == "https://example.com/assets/widgetco-logo.png"
    assert brand.urn == "urn:cmp:brand:129a4567-e89b-12d3-a456-426614174000"
    assert brand.organization_id == org_id

    # Verify raw data was stored
    assert brand.raw_data is not None
