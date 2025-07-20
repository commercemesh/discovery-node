from typing import Dict, Any
import logging

from .base import VectorProvider
from .providers.pinecone import PineconeProvider

logger = logging.getLogger(__name__)


class VectorProviderFactory:
    """Factory for creating vector storage providers."""
    
    _providers = {
        "pinecone": PineconeProvider,
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new provider class.
        
        Args:
            name: Provider name
            provider_class: Provider class that inherits from VectorProvider
        """
        if not issubclass(provider_class, VectorProvider):
            raise ValueError(f"{provider_class} must inherit from VectorProvider")
        cls._providers[name] = provider_class
        logger.info(f"Registered vector provider: {name}")
    
    @classmethod
    def create(cls, provider_name: str, config: Dict[str, Any]) -> VectorProvider:
        """Create a vector provider instance.
        
        Args:
            provider_name: Name of the provider (e.g., "pinecone", "pgvector")
            config: Provider-specific configuration
            
        Returns:
            VectorProvider instance
            
        Raises:
            ValueError: If provider is not registered
        """
        if provider_name not in cls._providers:
            raise ValueError(
                f"Unknown vector provider: {provider_name}. "
                f"Available providers: {list(cls._providers.keys())}"
            )
        
        provider_class = cls._providers[provider_name]
        logger.info(f"Creating vector provider: {provider_name}")
        
        return provider_class(config)
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())


# Register pgvector provider if available
try:
    from .providers.pgvector import PgVectorProvider
    VectorProviderFactory.register_provider("pgvector", PgVectorProvider)
except ImportError:
    logger.info("pgvector provider not available (missing dependencies)")