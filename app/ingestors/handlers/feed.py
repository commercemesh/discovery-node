# app/ingestors/handlers/feed.py
"""
Handler for product feed data.
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.ingestors.base import validate_json, validate_cmp_data, ProcessingError
from app.services.product_service import ProductService
from app.services.product_group_service import ProductGroupService
from app.services.offer_service import OfferService
from app.services.brand_service import BrandService

logger = logging.getLogger(__name__)


class FeedHandler:
    """
    Handler for processing product feed data.
    """

    def __init__(self, db_session, org_urn: str):
        """
        Initialize the handler with database session.

        Args:
            db_session: SQLAlchemy database session
            brand_id: Optional brand ID to associate products with
        """
        self.db_session = db_session
        self.org_urn = org_urn
        self.product_service = ProductService(db_session)
        self.product_group_service = ProductGroupService(db_session)
        self.offer_service = OfferService(db_session)
        self.brand_service = BrandService(db_session)

    def process(self, data: str) -> Dict[str, Any]:
        """
        Process raw feed data.

        Args:
            data: Raw feed data as string

        Returns:
            Processing result

        Raises:
            ProcessingError: If data cannot be processed
        """
        logger.info("Processing product feed data")
        print("Processing product feed data")

        try:
            # Parse and validate JSON
            json_data = validate_json(data)
            validate_cmp_data(json_data, "feed")

            # Extract items
            items = json_data.get("itemListElement", [])

            # Separate ProductGroups and Products like the other project
            product_groups = []
            products = []

            for item in items:
                if "item" not in item:
                    logger.warning("Item missing 'item' field, skipping")
                    continue

                item_data = item["item"]
                item_type = item_data.get("@type")

                if item_type == "ProductGroup":
                    product_groups.append(item_data)
                elif item_type == "Product":
                    products.append(item_data)
                else:
                    logger.warning(f"Unknown item type: {item_type}")

            logger.info(f"Extracted {len(product_groups)} product groups and {len(products)} products")

            # Track processing statistics
            product_groups_processed = 0
            products_processed = 0
            offers_processed = 0
            product_groups_skipped = 0
            products_skipped = 0

            # Phase 1: Bulk process ProductGroups
            if product_groups:
                logger.info(f"Processing {len(product_groups)} product groups in bulk")
                import time
                start_time = time.time()
                
                # Validate and prepare product groups for bulk processing
                valid_product_groups = []
                
                for pg_data in product_groups:
                    try:
                        # Get brand_id for this product group
                        item_brand_id = self._get_brand_id(pg_data)
                        
                        if item_brand_id is None:
                            logger.warning(
                                f"Skipping ProductGroup '{pg_data.get('name', 'unknown')}' - no brand information"
                            )
                            product_groups_skipped += 1
                            continue

                        # Get the brand object to extract organization_id
                        brand = self.brand_service.get_brand(item_brand_id)
                        if not brand:
                            logger.warning(
                                f"Skipping ProductGroup '{pg_data.get('name', 'unknown')}' - brand not found by ID {item_brand_id}"
                            )
                            product_groups_skipped += 1
                            continue

                        valid_product_groups.append((pg_data, item_brand_id, brand.organization_id))
                        
                    except Exception as e:
                        logger.error(f"Error validating product group {pg_data.get('name', 'unknown')}: {str(e)}")
                        product_groups_skipped += 1
                        continue
                
                # Group by brand_id and org_id for efficient bulk processing
                if valid_product_groups:
                    groups_by_brand = {}
                    for pg_data, brand_id, org_id in valid_product_groups:
                        key = (brand_id, org_id)
                        if key not in groups_by_brand:
                            groups_by_brand[key] = []
                        groups_by_brand[key].append(pg_data)
                    
                    # Bulk upsert for each brand/org combination
                    for (brand_id, org_id), pg_list in groups_by_brand.items():
                        try:
                            logger.info(f"Bulk upserting {len(pg_list)} product groups for brand {brand_id}")
                            upserted = self.product_group_service.bulk_process_product_groups(
                                pg_list, brand_id, org_id, batch_size=500
                            )
                            product_groups_processed += len(upserted)
                            print(f"Bulk processed {len(upserted)} product groups for brand {brand_id}")
                        except Exception as e:
                            logger.error(f"Error bulk processing product groups for brand {brand_id}: {str(e)}")
                            product_groups_skipped += len(pg_list)
                            # Rollback the transaction to clear the error state
                            self.db_session.rollback()
                
                pg_duration = time.time() - start_time
                logger.info(f"Product groups processing completed in {pg_duration:.2f} seconds")

            # Phase 2: Bulk process Products
            if products:
                logger.info(f"Processing {len(products)} products in bulk")
                products_start_time = time.time()
                
                # Validate and prepare products for bulk processing
                valid_products = []
                
                for product_data in products:
                    try:
                        # Get brand_id for this product
                        item_brand_id = self._get_brand_id(product_data)
                        
                        if item_brand_id is None:
                            logger.warning(
                                f"Skipping Product '{product_data.get('name', 'unknown')}' - no brand information"
                            )
                            products_skipped += 1
                            continue

                        # Get category name for this product
                        category_name = self._get_category_name(product_data)
                        if category_name is None:
                            logger.warning(
                                f"Skipping product '{product_data.get('name', 'unknown')}' - no category information"
                            )
                            products_skipped += 1
                            continue

                        valid_products.append((product_data, item_brand_id, category_name))
                        
                        # Check for offers
                        if "offers" in product_data:
                            offers_processed += 1
                            
                    except Exception as e:
                        logger.error(f"Error validating product {product_data.get('name', 'unknown')}: {str(e)}")
                        products_skipped += 1
                        continue
                
                # Group by brand_id and category for efficient bulk processing
                if valid_products:
                    products_by_brand_category = {}
                    for product_data, brand_id, category_name in valid_products:
                        key = (brand_id, category_name)
                        if key not in products_by_brand_category:
                            products_by_brand_category[key] = []
                        products_by_brand_category[key].append(product_data)
                    
                    # Bulk upsert for each brand/category combination
                    for (brand_id, category_name), product_list in products_by_brand_category.items():
                        try:
                            logger.info(f"Bulk upserting {len(product_list)} products for brand {brand_id}, category {category_name}")
                            upserted = self.product_service.bulk_process_products(
                                product_list, brand_id, category_name, batch_size=500
                            )
                            products_processed += len(upserted)
                            print(f"Bulk processed {len(upserted)} products for brand {brand_id}, category {category_name}")
                        except Exception as e:
                            logger.error(f"Error bulk processing products for brand {brand_id}, category {category_name}: {str(e)}")
                            products_skipped += len(product_list)
                            # Rollback the transaction to clear the error state
                            self.db_session.rollback()
                
                products_duration = time.time() - products_start_time
                logger.info(f"Products processing completed in {products_duration:.2f} seconds")

            logger.info(f"Feed processing complete: {product_groups_processed} product groups, {products_processed} products processed")
            logger.info(f"Skipped: {product_groups_skipped} product groups, {products_skipped} products")
            
            return {
                "product_groups_processed": product_groups_processed,
                "products_processed": products_processed,
                "offers_processed": offers_processed,
                "product_groups_skipped": product_groups_skipped,
                "products_skipped": products_skipped,
                "total_product_groups": len(product_groups),
                "total_products": len(products),
            }
        except Exception as e:
            logger.exception(f"Error processing feed data: {str(e)}")
            raise ProcessingError(f"Error processing feed data: {str(e)}")

    def _get_brand_id(self, item_data: Dict[str, Any]) -> Optional[UUID]:
        """
        Get brand ID for an item, following these rules:
        1. If ProductGroup: require brand element, check/create brand by brand.identifier.value (brand URN)
        2. If Product: find ProductGroup by isVariantOf['@id'], get brand_urn from product group, look up brand by URN
        3. If ProductGroup missing brand, skip
        4. If ProductGroup brand missing identifier.value, skip
        5. If Product's ProductGroup not found, skip
        """
        item_type = item_data.get("@type")

        # 1. ProductGroup logic
        if item_type == "ProductGroup":
            brand_info = item_data.get("brand")
            if not brand_info:
                logger.warning(f"ProductGroup '{item_data.get('name', 'unknown')}' missing brand element, skipping.")
                return None
            brand_urn = None
            if isinstance(brand_info, dict):
                brand_urn = brand_info.get("identifier", {}).get("value")
            if not brand_urn:
                logger.warning(f"ProductGroup '{item_data.get('name', 'unknown')}' brand missing identifier.value, skipping.")
                return None
            # Look up brand by URN
            logger.debug(f"Looking up brand by URN: {brand_urn}")
            brand = self.brand_service.get_by_urn(brand_urn)
            if not brand:
                # Create brand if it doesn't exist
                # Use org_urn from handler context
                logger.debug(f"Brand not found by URN, creating new brand with data: {brand_info}")
                logger.debug(f"Handler org_urn: {self.org_urn}")
                brand = self.brand_service.get_or_create_by_urn(brand_info, self.org_urn)
                if not brand:
                    logger.warning(f"Could not create brand for ProductGroup '{item_data.get('name', 'unknown')}' with URN {brand_urn}")
                    return None
            return brand.id

        # 2. Product logic
        elif item_type == "Product":
            # Find ProductGroup by isVariantOf['@id']
            product_group_urn = None
            if "isVariantOf" in item_data and "@id" in item_data["isVariantOf"]:
                product_group_urn = item_data["isVariantOf"]["@id"]
            if not product_group_urn:
                logger.warning(f"Product '{item_data.get('name', 'unknown')}' missing isVariantOf['@id'], skipping brand lookup.")
                return None
            # Look up ProductGroup in DB
            product_group = self.product_group_service.get_by_urn(product_group_urn)
            if not product_group:
                logger.warning(f"Product '{item_data.get('name', 'unknown')}' references ProductGroup '{product_group_urn}' not in DB, skipping brand lookup.")
                return None
            # Get brand_id from product group (this is a UUID, not a URN)
            brand_id = getattr(product_group, 'brand_id', None)
            if not brand_id:
                logger.warning(f"ProductGroup '{product_group_urn}' for Product '{item_data.get('name', 'unknown')}' missing brand_id, skipping brand lookup.")
                return None
            # Look up brand by ID (not URN)
            brand = self.brand_service.get_brand(brand_id)
            if not brand:
                logger.warning(f"Brand with ID '{brand_id}' for Product '{item_data.get('name', 'unknown')}' not found in DB.")
                return None
            return brand.id

        # 3. Unknown type
        else:
            logger.warning(f"Unknown item type '{item_type}' for item '{item_data.get('name', 'unknown')}', skipping brand lookup.")
            return None

    def _get_category_name(self, item_data: Dict[str, Any]) -> Optional[str]:
        """
        Get category name for an item, either from item data or from product group.

        Args:
            item_data: The item data containing category information

        Returns:
            Category name if found, None if category information is missing
        """
        # Try to extract category information from item data
        category_name = item_data.get("category", "").strip()

        # If item doesn't have category info and it's a Product, try to get category from product group
        if not category_name and item_data.get("@type") == "Product":
            product_group_urn = None
            if "isVariantOf" in item_data and "@id" in item_data["isVariantOf"]:
                product_group_urn = item_data["isVariantOf"]["@id"]

            if product_group_urn:
                # Look up the product group to get its category
                product_group = self.product_group_service.get_by_urn(product_group_urn)
                if product_group and product_group.category:
                    # Get the category name from the relationship
                    category_name = product_group.category.name
                    logger.info(
                        f"Product {item_data.get('name', 'unknown')} using category '{category_name}' from product group {product_group_urn}"
                    )
                else:
                    logger.warning(
                        f"Product {item_data.get('name', 'unknown')} references product group {product_group_urn} but no category found"
                    )
                    return None

        # Return category name if found
        if category_name:
            return category_name

        # No category information found
        logger.warning(
            f"Item {item_data.get('name', 'unknown')} has no category information"
        )
        return None
