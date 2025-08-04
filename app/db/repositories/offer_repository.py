# app/db/repositories/offer_repository.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from app.db.models.offer import Offer
from app.schemas.offer import OfferCreate, OfferUpdate


class OfferRepository:
    """Repository for CRUD operations on Offer model"""

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_by_id(self, offer_id: UUID) -> Optional[Offer]:
        """Get offer by ID"""
        return self.db_session.query(Offer).filter(Offer.id == offer_id).first()

    def list(self, skip: int = 0, limit: int = 100, organization_id: Optional[UUID] = None) -> List[Offer]:
        """List offers with pagination, optionally filtered by organization (seller)"""
        query = self.db_session.query(Offer)
        if organization_id:
            query = query.filter(Offer.organization_id == organization_id)
        return query.offset(skip).limit(limit).all()

    def list_by_product(
        self, product_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Offer]:
        """List offers for a specific product"""
        return (
            self.db_session.query(Offer)
            .filter(Offer.product_id == product_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_by_organization(
        self, organization_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Offer]:
        """List offers from a specific organization"""
        return (
            self.db_session.query(Offer)
            .filter(Offer.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_best_price(self, product_id: UUID) -> Optional[Offer]:
        """Get the offer with the lowest price for a specific product"""
        return (
            self.db_session.query(Offer)
            .filter(Offer.product_id == product_id, Offer.availability == "InStock")
            .order_by(Offer.price)
            .first()
        )

    def create(self, offer_data: OfferCreate) -> Offer:
        """Create a new offer"""
        # Convert Pydantic model to dict
        offer_dict = offer_data.model_dump()

        # Create new Offer model instance
        db_offer = Offer(**offer_dict)

        # Add to session and commit
        self.db_session.add(db_offer)
        self.db_session.commit()
        self.db_session.refresh(db_offer)

        return db_offer

    def update(self, offer_id: UUID, offer_data: OfferUpdate) -> Optional[Offer]:
        """Update an existing offer"""
        db_offer = self.get_by_id(offer_id)

        if not db_offer:
            return None

        # Update model with data from Pydantic model
        offer_data_dict = offer_data.model_dump(exclude_unset=True)
        for key, value in offer_data_dict.items():
            setattr(db_offer, key, value)

        # Commit changes
        self.db_session.commit()
        self.db_session.refresh(db_offer)

        return db_offer

    def delete(self, offer_id: UUID) -> bool:
        """Delete an offer by ID"""
        db_offer = self.get_by_id(offer_id)

        if not db_offer:
            return False

        self.db_session.delete(db_offer)
        self.db_session.commit()

        return True

    def list_by_filter(
        self, filters: Dict[str, Any], skip: int = 0, limit: int = 100
    ) -> List[Offer]:
        """
        List offers with flexible filtering.

        Filters can include:
        - price_min: Minimum price
        - price_max: Maximum price
        - seller_id: Seller ID
        - availability: Availability status
        """
        query = self.db_session.query(Offer)

        if "price_min" in filters and filters["price_min"] is not None:
            query = query.filter(Offer.price >= filters["price_min"])

        if "price_max" in filters and filters["price_max"] is not None:
            query = query.filter(Offer.price <= filters["price_max"])

        if "organization_id" in filters and filters["organization_id"] is not None:
            query = query.filter(Offer.organization_id == filters["organization_id"])

        if "availability" in filters and filters["availability"] is not None:
            query = query.filter(Offer.availability == filters["availability"])

        if (
            "shipping_destination" in filters
            and filters["shipping_destination"] is not None
        ):
            query = query.filter(
                Offer.shipping_destination == filters["shipping_destination"]
            )

        return query.offset(skip).limit(limit).all()
