# app/ingestors/sources/base.py
"""
Base classes for data sources.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from app.ingestors.base import SourceError

logger = logging.getLogger(__name__)


class BaseSource(ABC):
    """
    Abstract base class for all data sources.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the source with optional configuration.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        logger.info(f"Initialized {self.__class__.__name__} with config: {self.config}")

    @abstractmethod
    def fetch_registry(self,  ingestor_config: Dict[str, Any]) -> str:
        """
        Fetch data from the source.

        Args:
            path: Path or URL to the data

        Returns:
            Raw data as string

        Raises:
            SourceError: If data cannot be fetched
        """
        pass



    @abstractmethod
    def fetch_feed_index(self, ingestor_config: Dict[str, Any]) -> str:
        """
        Fetch data from the source.
        """
        pass

    @abstractmethod
    def fetch_feed(self, path: str) -> str:
        """
        Fetch data from the source.

        Args:
            path: Path or URL to the data

        Returns:
            Raw data as string

        Raises:
            SourceError: If data cannot be fetched
        """
        pass

    def validate_connection(self) -> bool:
        """
        Validate that the source is accessible.

        Returns:
            True if the source is accessible, False otherwise
        """
        logger.info(f"Validating connection for {self.__class__.__name__}")
        print(f"Validating connection for {self.__class__.__name__}")
        return True

    def get_org_id(self) -> str:
        """
        Get the organization ID from the data.
        """
        pass
