# app/services/offer_service.py
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from app.db.repositories.offer_repository import OfferRepository
from app.schemas.offer import OfferCreate, OfferUpdate, OfferInDB

logger = logging.getLogger(__name__)


class OfferService:
    """Service for offer-related business logic"""

    def __init__(self, db_session):
        self.offer_repo = OfferRepository(db_session)

    def get_offer(self, offer_id: UUID) -> Optional[OfferInDB]:
        """Get offer by ID"""
        offer = self.offer_repo.get_by_id(offer_id)
        if not offer:
            return None
        return OfferInDB.model_validate(offer)

    def list_offers(self, skip: int = 0, limit: int = 100) -> List[OfferInDB]:
        """List offers with pagination"""
        offers = self.offer_repo.list(skip, limit)
        return [OfferInDB.model_validate(o) for o in offers]

    def list_by_product(
        self, product_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[OfferInDB]:
        """List offers for a specific product"""
        offers = self.offer_repo.list_by_product(product_id, skip, limit)
        return [OfferInDB.model_validate(o) for o in offers]

    def list_by_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[OfferInDB]:
        """List offers from a specific organization"""
        offers = self.offer_repo.list_by_organization(organization_id, skip, limit)
        return [OfferInDB.model_validate(o) for o in offers]

    def get_best_price(self, product_id: UUID) -> Optional[OfferInDB]:
        """Get the offer with the lowest price for a specific product"""
        offer = self.offer_repo.get_best_price(product_id)
        if not offer:
            return None
        return OfferInDB.model_validate(offer)

    def create_offer(self, offer_data: OfferCreate) -> OfferInDB:
        """Create a new offer"""
        # Additional business logic/validation could go here
        offer = self.offer_repo.create(offer_data)
        return OfferInDB.model_validate(offer)

    def update_offer(
        self, offer_id: UUID, offer_data: OfferUpdate
    ) -> Optional[OfferInDB]:
        """Update an existing offer"""
        offer = self.offer_repo.update(offer_id, offer_data)
        if not offer:
            return None
        return OfferInDB.model_validate(offer)

    def delete_offer(self, offer_id: UUID) -> bool:
        """Delete an offer by ID"""
        return self.offer_repo.delete(offer_id)

    def process_offer(
        self, offer_data: Dict[str, Any], product_id: UUID, organization_id: UUID
    ) -> UUID:
        """
        Process offer data from the CMP product feed.
        Creates or updates the offer in the database.
        Returns the offer ID.
        """
        # Check if an offer already exists for this product and organization
        existing_offers = self.offer_repo.list_by_product(product_id)
        existing_offer = None
        for offer in existing_offers:
            if offer.organization_id == organization_id:
                existing_offer = offer
                break
        
        # Extract pricing information
        price = offer_data.get("price", 0.0)
        price_currency = offer_data.get("priceCurrency", "USD")

        # Extract availability
        availability = offer_data.get("availability", "OutOfStock")
        if availability and "https://schema.org/" in availability:
            # Extract just the status part from the URL
            availability = availability.split("/")[-1]

        # Extract inventory level
        inventory_level = None
        if "inventoryLevel" in offer_data and "value" in offer_data["inventoryLevel"]:
            inventory_level = offer_data["inventoryLevel"]["value"]

        # Extract price validity
        price_valid_until = offer_data.get("priceValidUntil")

        # Extract shipping information
        shipping_info = offer_data.get("shippingDetails", {})
        shipping_cost = None
        shipping_currency = None
        shipping_destination = None

        if "shippingRate" in shipping_info:
            shipping_rate = shipping_info["shippingRate"]
            shipping_cost = shipping_rate.get("price")
            shipping_currency = shipping_rate.get("priceCurrency")

        if "shippingDestination" in shipping_info:
            shipping_destination = shipping_info["shippingDestination"].get("name")

        # Extract service level information
        service_info = offer_data.get("serviceLevel", {})
        shipping_speed_tier = service_info.get("speedTier")
        est_delivery_min_days = service_info.get("minDays")
        est_delivery_max_days = service_info.get("maxDays")

        # Extract warranty information
        warranty_info = offer_data.get("warranty", {})
        warranty_months = warranty_info.get("durationMonths")
        warranty_type = warranty_info.get("type")

        # Extract return information
        return_info = offer_data.get("returnPolicy", {})
        return_window_days = return_info.get("returnWindow")
        restocking_fee_pct = return_info.get("restockingFee")

        # Extract additional flags
        gift_wrap = offer_data.get("giftWrap", False)

        # If offer exists, update it; otherwise create new one
        if existing_offer:
            logger.info(f"Updating existing offer {existing_offer.id} for product {product_id} and organization {organization_id}")
            # Update existing offer
            offer_update_data = OfferUpdate(
                price=price,
                price_currency=price_currency,
                availability=availability,
                inventory_level=inventory_level,
                price_valid_until=price_valid_until,
                shipping_cost=shipping_cost,
                shipping_currency=shipping_currency,
                shipping_destination=shipping_destination,
                shipping_speed_tier=shipping_speed_tier,
                est_delivery_min_days=est_delivery_min_days,
                est_delivery_max_days=est_delivery_max_days,
                warranty_months=warranty_months,
                warranty_type=warranty_type,
                return_window_days=return_window_days,
                restocking_fee_pct=restocking_fee_pct,
                gift_wrap=gift_wrap,
                raw_data=offer_data,
            )
            updated_offer = self.offer_repo.update(existing_offer.id, offer_update_data)
            return updated_offer.id
        else:
            logger.info(f"Creating new offer for product {product_id} and organization {organization_id}")
            # Create new offer
            offer_create_data = OfferCreate(
                product_id=product_id,
                organization_id=organization_id,
                price=price,
                price_currency=price_currency,
                availability=availability,
                inventory_level=inventory_level,
                price_valid_until=price_valid_until,
                shipping_cost=shipping_cost,
                shipping_currency=shipping_currency,
                shipping_destination=shipping_destination,
                shipping_speed_tier=shipping_speed_tier,
                est_delivery_min_days=est_delivery_min_days,
                est_delivery_max_days=est_delivery_max_days,
                warranty_months=warranty_months,
                warranty_type=warranty_type,
                return_window_days=return_window_days,
                restocking_fee_pct=restocking_fee_pct,
                gift_wrap=gift_wrap,
                raw_data=offer_data,
            )
            offer = self.offer_repo.create(offer_create_data)
            return offer.id

    def filter_offers(
        self, filters: Dict[str, Any], skip: int = 0, limit: int = 100
    ) -> List[OfferInDB]:
        """Filter offers by various criteria"""
        offers = self.offer_repo.list_by_filter(filters, skip, limit)
        return [OfferInDB.model_validate(o) for o in offers]
