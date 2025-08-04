# app/ingestors/sources/factory.py
"""
Factory for creating source instances.
"""
import logging
from typing import Dict, Any, Optional

from app.ingestors.sources.base import BaseSource
from app.ingestors.sources.local import LocalSource
from app.ingestors.sources.cmp import CMPSource
from app.ingestors.sources.managed import ManagedSource
from app.ingestors.base import SourceError

logger = logging.getLogger(__name__)


class SourceFactory:
    """
    Factory for creating source instances.
    """

    @staticmethod
    def create(source_type: str, config: Optional[Dict[str, Any]] = None) -> BaseSource:
        """
        Create a source instance based on type.

        Args:
            source_type: Type of source ("local", "remote", "ftp")
            config: Configuration dictionary

        Returns:
            Source instance

        Raises:
            SourceError: If source type is unknown
        """
        logger.info(f"Creating source of type: {source_type}")
        print(f"Creating source of type: {source_type}")

        if source_type == "local":
            return LocalSource(config)
        elif source_type == "cmp":
            return CMPSource(config)
        elif source_type == "managed":
            return ManagedSource(config)
        # elif source_type == "remote":
        #     return RemoteSource(config)
        # elif source_type == "ftp":
        #     return FtpSource(config)
        else:
            raise SourceError(f"Unknown source type: {source_type}")
