# app/ingestors/base.py
"""
Base ingestor functionality and shared utilities.
"""
import logging
import json
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


class IngestorError(Exception):
    """Base exception for ingestor errors."""

    pass


class SourceError(IngestorError):
    """Exception raised for errors in data sources."""

    pass


class ValidationError(IngestorError):
    """Exception raised for data validation errors."""

    pass


class ProcessingError(IngestorError):
    """Exception raised for data processing errors."""

    pass


def validate_json(data: str) -> Dict[str, Any]:
    """
    Validate and parse JSON data.

    Args:
        data: JSON string to validate

    Returns:
        Parsed JSON data as dictionary

    Raises:
        ValidationError: If the data is not valid JSON
    """
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON data: {str(e)}")


def validate_cmp_data(data: Dict[str, Any], data_type: str) -> bool:
    """
    Validate that data conforms to CMP specifications.

    Args:
        data: Data dictionary to validate
        data_type: Type of data ("registry" or "feed")

    Returns:
        True if valid, False otherwise

    Raises:
        ValidationError: If the data doesn't conform to CMP specifications
    """
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dictionary, got {type(data)}")

    # Check context - be more lenient for feeds
    if "@context" not in data:
        if data_type == "registry":
            raise ValidationError("Missing @context in registry data")
        else:
            # For feeds, log a warning but continue processing
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Missing @context in {data_type} data, continuing anyway")

    # Validate based on data type
    if data_type == "registry":
        # Simple validation for registry
        if "@type" not in data or data["@type"] != "Organization":
            raise ValidationError("Registry must have @type = Organization")

        if "name" not in data:
            raise ValidationError("Registry must have a name")

        if "identifier" not in data or not isinstance(data["identifier"], dict):
            raise ValidationError("Registry must have an identifier object")

    elif data_type == "feed":
        # Simple validation for feed
        if "@type" not in data or data["@type"] != "ItemList":
            raise ValidationError("Feed must have @type = ItemList")

        if "itemListElement" not in data or not isinstance(
            data["itemListElement"], list
        ):
            raise ValidationError("Feed must have an itemListElement array")

    else:
        raise ValueError(f"Unknown data type: {data_type}")

    return True
