"""Redis caching service for API responses"""
import json
import redis
from typing import Optional, Dict, Any
from datetime import timedelta
from app.core.config import settings
from app.core.logging import get_logger
from app.utils.request_id import generate_request_id, validate_request_id

logger = get_logger(__name__)


class CacheService:
    """Service for caching API responses in Redis"""
    
    def __init__(self, redis_url: Optional[str] = None, db: int = 2, ttl_minutes: int = 15):
        """
        Initialize the cache service.
        
        Args:
            redis_url: Redis URL (defaults to settings.MCP_REDIS_URL base)
            db: Redis database number (default: 2 for cache)
            ttl_minutes: Cache TTL in minutes (default: 15)
        """
        self.ttl = timedelta(minutes=ttl_minutes)
        
        # Parse Redis URL and use specified database
        if redis_url:
            base_url = redis_url.rsplit('/', 1)[0]
        else:
            # Use the base Redis URL from MCP settings
            base_url = settings.MCP_REDIS_URL.rsplit('/', 1)[0]
        
        self.redis_url = f"{base_url}/{db}"
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis cache at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis cache: {e}")
            self.redis_client = None
    
    def generate_cache_key(self, prefix: str = "api") -> str:
        """
        Generate a new cache key with request ID.
        
        Args:
            prefix: Key prefix (default: "api")
        
        Returns:
            Cache key in format: {prefix}:{request_id}
        """
        request_id = generate_request_id()
        return f"{prefix}:{request_id}"
    
    def cache_response(
        self, 
        key: str, 
        data: Dict[str, Any], 
        ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Cache a response in Redis.
        
        Args:
            key: Cache key (should include prefix and request ID)
            data: Response data to cache
            ttl: Optional custom TTL (defaults to instance TTL)
        
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.redis_client:
            logger.warning("Redis client not available, skipping cache")
            return False
        
        try:
            # Serialize data to JSON
            json_data = json.dumps(data, separators=(',', ':'))
            
            # Set with TTL
            ttl_seconds = int((ttl or self.ttl).total_seconds())
            self.redis_client.setex(key, ttl_seconds, json_data)
            
            logger.info(f"Cached response with key: {key} (TTL: {ttl_seconds}s)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache response: {e}")
            return False
    
    def get_cached_response(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached response from Redis.
        
        Args:
            key: Cache key
        
        Returns:
            Cached data if found, None otherwise
        """
        if not self.redis_client:
            return None
        
        try:
            json_data = self.redis_client.get(key)
            if json_data:
                logger.info(f"Cache hit for key: {key}")
                return json.loads(json_data)
            else:
                logger.info(f"Cache miss for key: {key}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to retrieve cached response: {e}")
            return None
    
    def delete_cached_response(self, key: str) -> bool:
        """
        Delete a cached response from Redis.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            result = self.redis_client.delete(key)
            if result:
                logger.info(f"Deleted cache key: {key}")
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to delete cached response: {e}")
            return False
    
    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a cache key.
        
        Args:
            key: Cache key
        
        Returns:
            Remaining TTL in seconds, None if key doesn't exist
        """
        if not self.redis_client:
            return None
        
        try:
            ttl = self.redis_client.ttl(key)
            return ttl if ttl > 0 else None
            
        except Exception as e:
            logger.error(f"Failed to get TTL: {e}")
            return None
    
    def close(self):
        """Close Redis connection"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Closed Redis cache connection")


# Singleton instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get or create the cache service singleton"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service