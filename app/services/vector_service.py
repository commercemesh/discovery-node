import time
import logging
from uuid import UUID
from app.core.config import settings
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.vector_repository_native import VectorRepository
from app.schemas.product import ProductForVector
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class UpsertResult:
    total_products: int
    successful_records: int
    failed_records: int
    dense_index_success: bool
    sparse_index_success: bool
    errors: List[str]
    processing_time: float


class VectorService:
    def __init__(self, db_session):
        self.db_session = db_session
        self.product_repository = ProductRepository(db_session)
        self.vector_repository = VectorRepository()

    def _canonical_text(self, product: ProductForVector) -> str:
        """
        Build the text string fed to BOTH dense and sparse embedders.
        Keeps one space between tokens; drops blanks automatically.
        """
        parts = []
        if product.name:
            parts.append(product.name)

        if product.description:
            parts.append(product.description)

        # Brand is crucial for exact matches
        if product.brand_name:
            parts.append(f"brand:{product.brand_name}")

        # Category helps with semantic grouping
        if product.category_name:
            parts.append(product.category_name)

        # Key variant attributes
        for k, v in product.variant_attrs.items():
            if v:  # Only if value exists
                parts.append(f"{k}:{v}")

        # Metadata
        if product.availability == "IN_STOCK":
            parts.append("in stock")

        canonical_text = " ".join(parts)

        # logger.info(f"Canonical text: {canonical_text}")

        return canonical_text

    def _add_metadata(self, product: ProductForVector) -> dict:
        """Add metadata to the product"""
        metadata = {
            "price": product.price,
            "availability": product.availability,
            "brand": product.brand_name,
            "category": product.category_name,
            "product_group_id": product.product_group_id,
        }
        return metadata

    def _prepare_records(self, products: List[ProductForVector]) -> List[dict]:
        """Prepare records for vector upsert using clean ProductForVector schema"""
        records = []
        for product in products:
            try:
                record = {
                    "id": product.urn,  # Use URN for consistency with pgvector
                    "canonical_text": self._canonical_text(product),
                    **self._add_metadata(product),
                }
                records.append(record)
            except Exception as e:
                logger.error(f"Error preparing record for product {product.urn}: {e}")
        logger.info(f"Prepared {len(records)} records out of {len(products)} products")
        return records

    def upsert_products(self, org_id: UUID):
        """Upsert products into Pinecone"""

        logger.info(f"Starting upsert_products for org_id={org_id}")
        start_time = time.time()
        result = UpsertResult(
            total_products=0,
            successful_records=0,
            failed_records=0,
            dense_index_success=True,
            sparse_index_success=True,
            errors=[],
            processing_time=0.0,
        )

        offset = 0
        batch_num = 0
        while True:
            logger.debug(
                f"Fetching products with offset={offset}, batch_size={settings.PINECONE_BATCH_SIZE}, org_id={org_id}"
            )
            products = self.product_repository.get_products_for_vector(
                offset, settings.PINECONE_BATCH_SIZE, org_id
            )
            if not products:
                logger.info(
                    f"No more products to process. Exiting loop at offset={offset}."
                )
                break

            batch_num += 1
            logger.info(
                f"Processing batch {batch_num}: {len(products)} products (offset={offset})"
            )
            result.total_products += len(products)
            records = self._prepare_records(products)
            logger.debug(f"Prepared {len(records)} records for upsert.")

            # Try dense index
            try:
                logger.info(
                    f"Upserting {len(records)} records into dense index (batch {batch_num})"
                )
                self.vector_repository.upsert_products_into_dense_index(records, db=self.db_session)
                logger.info(
                    f"Dense index: successfully processed {len(records)} records (batch {batch_num})"
                )
            except Exception as e:
                logger.error(f"Dense index error in batch {batch_num}: {str(e)}")
                result.dense_index_success = False
                result.failed_records += len(records)
                result.errors.append(f"Dense index error: {str(e)}")

            # Try sparse index
            try:
                logger.info(
                    f"Upserting {len(records)} records into sparse index (batch {batch_num})"
                )
                self.vector_repository.upsert_products_into_sparse_index(records)
                logger.info(
                    f"Sparse index: successfully processed {len(records)} records (batch {batch_num})"
                )
            except Exception as e:
                logger.error(f"Sparse index error in batch {batch_num}: {str(e)}")
                result.sparse_index_success = False
                result.failed_records += len(records)
                result.errors.append(f"Sparse index error: {str(e)}")

            if result.dense_index_success and result.sparse_index_success:
                result.successful_records += len(records)
                logger.info(
                    f"Batch {batch_num} processed successfully: {len(records)} records"
                )
            else:
                logger.warning(
                    f"Batch {batch_num} had errors. See result.errors for details."
                )

            offset += settings.PINECONE_BATCH_SIZE

        result.processing_time = time.time() - start_time
        logger.info(
            f"Finished upsert_products for org_id={org_id}. Total products: {result.total_products}, Successful: {result.successful_records}, Failed: {result.failed_records}, Time: {result.processing_time:.2f}s"
        )
        if result.errors:
            logger.warning(
                f"Errors encountered during upsert_products: {result.errors}"
            )
        return result
