from typing import Type
import logging

from app.core.config import settings
from .base import BaseSearchService
from .pinecone_search import PineconeSearchService
from .pgvector_search import PgVectorSearchService

logger = logging.getLogger(__name__)


class SearchServiceFactory:
    """Factory for creating search service instances based on configuration"""
    
    _services = {
        "pinecone": PineconeSearchService,
        "pgvector": PgVectorSearchService,
    }
    
    @classmethod
    def create(cls, db_session) -> BaseSearchService:
        """
        Create a search service instance based on VECTOR_PROVIDER setting
        
        Args:
            db_session: Database session
            
        Returns:
            BaseSearchService instance
        """
        provider = settings.VECTOR_PROVIDER
        
        if provider not in cls._services:
            raise ValueError(
                f"Unknown search provider: {provider}. "
                f"Available providers: {list(cls._services.keys())}"
            )
        
        service_class = cls._services[provider]
        logger.info(f"Creating search service for provider: {provider}")
        
        return service_class(db_session)
    
    @classmethod
    def register_service(cls, provider: str, service_class: Type[BaseSearchService]):
        """Register a new search service provider"""
        if not issubclass(service_class, BaseSearchService):
            raise ValueError(f"{service_class} must inherit from BaseSearchService")
        
        cls._services[provider] = service_class
        logger.info(f"Registered search service: {provider}")