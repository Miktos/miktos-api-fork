# services/cache_service.py
import json
import hashlib
from typing import Any, Dict, Optional
import redis.asyncio as redis
from config.settings import settings

class CacheService:
    """Service for caching frequently accessed data."""
    
    def __init__(self):
        """Initialize the Redis connection."""
        self.redis = redis.from_url(
            settings.REDIS_URL or "redis://localhost:6379/0",
            encoding="utf-8",
            decode_responses=True
        )
        self.default_ttl = 3600  # 1 hour default
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a value from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            The cached value or None if not found
        """
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(
        self, key: str, value: Dict[str, Any], ttl: Optional[int] = None
    ) -> bool:
        """Set a value in the cache.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            True if successful
        """
        ttl = ttl or self.default_ttl
        return await self.redis.set(
            key, json.dumps(value), ex=ttl
        )
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            True if successful
        """
        return await self.redis.delete(key) > 0
    
    @staticmethod
    def generate_key(namespace: str, identifier: str) -> str:
        """Generate a cache key.
        
        Args:
            namespace: The namespace (e.g., 'project', 'context')
            identifier: The specific identifier
            
        Returns:
            A formatted cache key
        """
        return f"{namespace}:{identifier}"
    
    @staticmethod
    def generate_context_key(project_id: str, messages_hash: str) -> str:
        """Generate a cache key for project context.
        
        Args:
            project_id: The project ID
            messages_hash: Hash of the messages to ensure freshness
            
        Returns:
            A cache key that includes a hash of the messages
        """
        return f"context:{project_id}:{messages_hash}"
    
    @staticmethod
    def hash_messages(messages: list) -> str:
        """Create a hash of messages to use in cache keys.
        
        This helps invalidate cached contexts when messages change.
        
        Args:
            messages: List of message objects
            
        Returns:
            A hash string representing the messages state
        """
        message_str = json.dumps(messages, sort_keys=True)
        return hashlib.md5(message_str.encode()).hexdigest()