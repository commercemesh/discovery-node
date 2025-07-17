# app/services/category_service.py
from typing import List, Optional
from uuid import UUID
from app.db.repositories.category_respository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryInDB


class CategoryService:
    """Service for category-related business logic"""

    def __init__(self, db_session):
        self.category_repo = CategoryRepository(db_session)

    def get_category(self, category_id: UUID) -> Optional[CategoryInDB]:
        """Get category by ID"""
        category = self.category_repo.get_by_id(category_id)
        if not category:
            return None
        return CategoryInDB.model_validate(category)

    def get_by_slug(self, slug: str) -> Optional[CategoryInDB]:
        """Get category by slug"""
        category = self.category_repo.get_by_slug(slug)
        if not category:
            return None
        return CategoryInDB.model_validate(category)

    def list_categories(self, skip: int = 0, limit: int = 100) -> List[CategoryInDB]:
        """List categories with pagination"""
        categories = self.category_repo.list(skip, limit)
        return [CategoryInDB.model_validate(category) for category in categories]

    def create_category(self, category_data: CategoryCreate) -> CategoryInDB:
        """Create a new category"""
        # Check if category with same slug already exists
        existing = self.category_repo.get_by_slug(category_data.slug)
        if existing:
            raise ValueError(
                f"Category with slug '{category_data.slug}' already exists"
            )

        category = self.category_repo.create(category_data)
        return CategoryInDB.model_validate(category)

    def update_category(
        self, category_id: UUID, category_data: CategoryUpdate
    ) -> Optional[CategoryInDB]:
        """Update an existing category"""
        # If slug is being updated, check it doesn't conflict
        if category_data.slug:
            existing = self.category_repo.get_by_slug(category_data.slug)
            if existing and existing.id != category_id:
                raise ValueError(
                    f"Category with slug '{category_data.slug}' already exists"
                )

        category = self.category_repo.update(category_id, category_data)
        if not category:
            return None
        return CategoryInDB.model_validate(category)

    def delete_category(self, category_id: UUID) -> bool:
        """Delete a category by ID"""
        return self.category_repo.delete(category_id)

    def get_or_create_categories(self, category_slugs: List[str]) -> List[UUID]:
        """
        Get or create categories based on slugs.
        Returns a list of category IDs.
        """
        result = []
        for slug in category_slugs:
            # Create a readable name from slug
            name = slug.replace("-", " ").title()
            category = self.category_repo.get_or_create(slug, name)
            result.append(category.id)
        return result

    def get_or_create_by_name(self, category_name: str):
        """
        Get or create a category by name. If name is blank, use 'uncategorized'.
        Returns the CategoryInDB object.
        """
        if not category_name:
            category_name = "uncategorized"
        slug = self._slugify(category_name)
        category = self.category_repo.get_by_slug(slug)
        if not category:
            category = self.category_repo.create(CategoryCreate(slug=slug, name=category_name))
        return CategoryInDB.model_validate(category)

    def _slugify(self, text: str) -> str:
        """
        Convert a string to a slug format.
        For example: "Electronics & Computers" -> "electronics-computers"
        """
        return text.lower().replace(" ", "-").replace("&", "").replace("_", "-")
