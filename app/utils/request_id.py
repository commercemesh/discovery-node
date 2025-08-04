"""Request ID generation utility"""
import random
import string
from typing import Optional


def generate_request_id(length: int = 6) -> str:
    """
    Generate a random request ID.
    
    Args:
        length: Length of the request ID (default: 6)
    
    Returns:
        A random string of uppercase letters and digits
    """
    # Use uppercase letters and digits for better readability
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))


def validate_request_id(request_id: Optional[str]) -> bool:
    """
    Validate a request ID format.
    
    Args:
        request_id: The request ID to validate
    
    Returns:
        True if valid, False otherwise
    """
    if not request_id:
        return False
    
    # Check length
    if len(request_id) != 6:
        return False
    
    # Check characters (uppercase letters and digits only)
    allowed = set(string.ascii_uppercase + string.digits)
    return all(c in allowed for c in request_id)