import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.ingestors.base import validate_json, validate_cmp_data, ProcessingError
from app.services.vector_service import VectorService
from app.services.organization_service import OrganizationService

logger = logging.getLogger(__name__)


class VectorHandler:
    """
    Handler for embedding data.
    """

    def __init__(self, db_session, brand_id: Optional[UUID] = None):
        self.db_session = db_session
        self.vector_service = VectorService(db_session)
        self.organization_service = OrganizationService(db_session)

    def process(self, org_urn: str) -> Dict[str, Any]:
        logger.info("Processing vector data")
        print("Processing vector data")
        print(f"Looking for organization with URN: {org_urn}")

        organization = self.organization_service.get_organization_by_urn(org_urn)
        print(f"Found organization: {organization}")

        # Extract the UUID from the organization object
        if organization and hasattr(organization, "id"):
            org_id = organization.id
            logger.info(f"Extracted org_id UUID: {org_id}")
            print(f"Extracted org_id UUID: {org_id}")
        else:
            logger.error(f"Could not extract UUID from organization: {organization}")
            print(f"Could not extract UUID from organization: {organization}")
            return {
                "status": "failed",
                "error": "Could not extract organization UUID",
                "total_products": 0,
                "successful_records": 0,
            }

        try:
            result = self.vector_service.upsert_products(org_id)

            return {
                "status": "completed" if not result.errors else "partial_failure",
                "total_products": result.total_products,
                "successful_records": result.successful_records,
                "failed_records": result.failed_records,
                "dense_index_success": result.dense_index_success,
                "sparse_index_success": result.sparse_index_success,
                "errors": result.errors,
                "processing_time_seconds": result.processing_time,
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "total_products": 0,
                "successful_records": 0,
            }
