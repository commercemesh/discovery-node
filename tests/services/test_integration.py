# tests/services/test_integration.py


def test_process_organization_with_brands(
    organization_service, brand_service, test_organization_data
):
    """Integration test to process an organization with all its brands."""
    # Process the organization
    org_id = organization_service.process_organization(test_organization_data)

    # Verify organization was created
    org = organization_service.get_organization(org_id)
    assert org is not None
    assert org.name == "Acme Corporation"

    # Process the brands from the organization data
    if "brand" in test_organization_data:
        print(f"Found {len(test_organization_data['brand'])} brands to process")
        for brand_data in test_organization_data["brand"]:
            print(f"Processing brand: {brand_data.get('name', 'Unknown')}")
            brand_service.process_brand(brand_data, org_id)
    else:
        print("No brands found in organization data")

    # Get brands for the organization
    brands = brand_service.list_by_organization(org_id)

    # Verify all brands were created
    assert len(brands) == 2  # We included 2 brands in our test data

    # Verify brand data
    brand_names = [brand.name for brand in brands]
    assert "WidgetCo" in brand_names
    assert "GizmoWorks" in brand_names

    # Get URNs for verification
    brand_urns = [brand.urn for brand in brands]
    assert "urn:cmp:brand:129a4567-e89b-12d3-a456-426614174000" in brand_urns
    assert "urn:cmp:brand:129b4567-e89b-12d3-a456-426614174001" in brand_urns
