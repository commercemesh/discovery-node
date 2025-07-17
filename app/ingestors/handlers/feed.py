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

            # Process ProductGroups first (Phase 1)
            for item_data in product_groups:
                try:
                    # Get brand_id for this product group
                    item_brand_id = self._get_brand_id(item_data)
                    
                    if item_brand_id is None:
                        logger.warning(
                            f"Skipping ProductGroup '{item_data.get('name', 'unknown')}' - no brand information"
                        )
                        continue

                    # Get the brand object to extract organization_id
                    brand = self.brand_service.get_brand(item_brand_id)
                    if not brand:
                        logger.warning(
                            f"Skipping ProductGroup '{item_data.get('name', 'unknown')}' - brand not found by ID {item_brand_id}"
                        )
                        continue

                    organization_id = brand.organization_id
                    self.product_group_service.process_product_group(
                        item_data, item_brand_id, organization_id
                    )
                    product_groups_processed += 1
                    print(f"Processed product group: {item_data.get('name')}")

                except Exception as e:
                    logger.error(f"Error processing product group {item_data.get('name', 'unknown')}: {str(e)}")
                    continue

            # Process Products second (Phase 2)
            for item_data in products:
                try:
                    # Get brand_id for this product
                    item_brand_id = self._get_brand_id(item_data)
                    
                    if item_brand_id is None:
                        logger.warning(
                            f"Skipping Product '{item_data.get('name', 'unknown')}' - no brand information"
                        )
                        continue

                    # Get category name for this product
                    category_name = self._get_category_name(item_data)
                    if category_name is None:
                        logger.warning(
                            f"Skipping product '{item_data.get('name', 'unknown')}' - no category information"
                        )
                        continue

                    # Process product with category information
                    self.product_service.process_product(
                        item_data, item_brand_id, category_name
                    )
                    products_processed += 1
                    print(f"Processed product: {item_data.get('name')}")

                    # Check for offers
                    if "offers" in item_data:
                        offers_processed += 1

                except Exception as e:
                    logger.error(f"Error processing product {item_data.get('name', 'unknown')}: {str(e)}")
                    continue

            return {
                "product_groups_processed": product_groups_processed,
                "products_processed": products_processed,
                "offers_processed": offers_processed,
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
