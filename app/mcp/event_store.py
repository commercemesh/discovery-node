import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StoredEvent:
    """Represents a stored SSE event for resumability"""
    id: str
    event: str
    data: str
    timestamp: float


class RedisEventStore:
    """
    Redis-based event store for MCP StreamableHTTP resumability.
    Uses Redis streams for efficient event storage and retrieval.
    """
    
    def __init__(self, max_events_per_stream: int = 1000):
        self.redis_client: Optional[redis.Redis] = None
        self.max_events = max_events_per_stream
        self.key_prefix = "mcp:events"
        self.ttl_seconds = 3600  # Events expire after 1 hour
        
    async def _get_redis(self) -> redis.Redis:
        """Get Redis client, create if needed"""
        if self.redis_client is None:
            # Handle SSL connections
            conn_params = {
                "decode_responses": True
            }
            if settings.mcp_redis_url.startswith("rediss://"):
                conn_params["ssl_cert_reqs"] = "none"
            
            self.redis_client = redis.from_url(
                settings.mcp_redis_url,
                **conn_params
            )
        return self.redis_client
    
    def _stream_key(self, stream_id: str) -> str:
        """Generate Redis key for a stream"""
        return f"{self.key_prefix}:{stream_id}"
    
    async def store_event(
        self, 
        stream_id: str, 
        event_id: str, 
        event_type: str = "message", 
        data: str = ""
    ) -> None:
        """Store an event for a specific stream"""
        try:
            redis_client = await self._get_redis()
            stream_key = self._stream_key(stream_id)
            
            # Convert data to string if it's not already
            if not isinstance(data, str):
                try:
                    # Try to serialize as JSON first
                    data = json.dumps(data, default=str)
                except (TypeError, ValueError):
                    # Fallback to string conversion
                    data = str(data)
            
            event = StoredEvent(
                id=event_id,
                event=event_type,
                data=data,
                timestamp=time.time()
            )
            
            # Store event in Redis stream
            await redis_client.xadd(
                stream_key,
                fields=asdict(event),
                maxlen=self.max_events,
                approximate=True
            )
            
            # Set TTL on the stream
            await redis_client.expire(stream_key, self.ttl_seconds)
            
            logger.debug(f"Stored event {event_id} for stream {stream_id}")
            
        except Exception as e:
            logger.error(f"Failed to store event {event_id}: {e}")
            # Don't raise - event storage failure shouldn't break MCP operations
    
    async def get_events_since(
        self, 
        stream_id: str, 
        last_event_id: Optional[str] = None
    ) -> List[StoredEvent]:
        """Get events since the last event ID (for resumability)"""
        try:
            redis_client = await self._get_redis()
            stream_key = self._stream_key(stream_id)
            
            # Check if stream exists
            if not await redis_client.exists(stream_key):
                return []
            
            # Read from stream
            if last_event_id:
                # Find events after the last event ID
                start_id = await self._find_next_id(stream_key, last_event_id)
            else:
                start_id = "0"  # Start from beginning
            
            # Read events from Redis stream
            stream_data = await redis_client.xread(
                {stream_key: start_id},
                count=self.max_events
            )
            
            events = []
            if stream_data:
                for stream, messages in stream_data:
                    for message_id, fields in messages:
                        event = StoredEvent(
                            id=fields["id"],
                            event=fields["event"],
                            data=fields["data"],
                            timestamp=float(fields["timestamp"])
                        )
                        events.append(event)
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get events for stream {stream_id}: {e}")
            return []
    
    async def _find_next_id(self, stream_key: str, last_event_id: str) -> str:
        """Find the Redis stream ID after the given event ID"""
        try:
            redis_client = await self._get_redis()
            
            # Read all events and find the one after last_event_id
            stream_data = await redis_client.xread(
                {stream_key: "0"},
                count=self.max_events
            )
            
            if not stream_data:
                return "0"
            
            found_last = False
            for stream, messages in stream_data:
                for message_id, fields in messages:
                    if found_last:
                        return message_id
                    if fields.get("id") == last_event_id:
                        found_last = True
            
            # If we didn't find the event or it was the last one
            return "$"  # Start from end
            
        except Exception as e:
            logger.error(f"Failed to find next ID after {last_event_id}: {e}")
            return "0"
    
    async def cleanup_old_streams(self, max_age_seconds: int = 3600) -> None:
        """Clean up old streams to prevent memory leaks"""
        try:
            redis_client = await self._get_redis()
            
            # Find all event streams
            pattern = f"{self.key_prefix}:*"
            keys = await redis_client.keys(pattern)
            
            current_time = time.time()
            cleaned_count = 0
            
            for key in keys:
                try:
                    # Get the latest event from stream
                    stream_data = await redis_client.xrevrange(key, count=1)
                    
                    if not stream_data:
                        # Empty stream, delete it
                        await redis_client.delete(key)
                        cleaned_count += 1
                        continue
                    
                    # Check if latest event is too old
                    latest_message = stream_data[0]
                    fields = latest_message[1]
                    event_timestamp = float(fields.get("timestamp", 0))
                    
                    if current_time - event_timestamp > max_age_seconds:
                        await redis_client.delete(key)
                        cleaned_count += 1
                        
                except Exception as e:
                    logger.error(f"Error cleaning stream {key}: {e}")
                    continue
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old event streams")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old streams: {e}")
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()


# Factory function for dependency injection
def create_event_store() -> RedisEventStore:
    """Create Redis event store instance"""
    return RedisEventStore()