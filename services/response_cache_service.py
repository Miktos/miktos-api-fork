# services/response_cache_service.py
"""
Service for caching AI responses to improve performance and reduce costs.
"""
import json
import hashlib
from typing import Any, Dict, List, Optional, Union
import redis.asyncio as redis

from config.settings import settings

class ResponseCacheService:
    """
    Service for caching AI model responses.
    
    This service caches responses from AI models to:
    1. Reduce latency for identical or similar requests
    2. Reduce costs by avoiding redundant API calls
    3. Provide fallbacks when external APIs are unavailable
    """
    
    def __init__(self):
        """Initialize the Redis connection."""
        self.redis = redis.from_url(
            settings.REDIS_URL or "redis://localhost:6379/0",
            encoding="utf-8",
            decode_responses=True
        )
        # Default TTL values by provider
        self.ttl_by_provider = {
            "openai": 7200,       # 2 hours for OpenAI
            "anthropic": 7200,    # 2 hours for Anthropic
            "google": 7200,       # 2 hours for Google
            "default": 3600       # 1 hour default
        }
        self.cache_enabled = settings.RESPONSE_CACHE_ENABLED
    
    def get_ttl_for_model(self, model_id: str) -> int:
        """
        Determine appropriate TTL based on the model ID.
        
        Args:
            model_id: The model identifier (e.g., 'openai/gpt-4')
            
        Returns:
            TTL in seconds
        """
        # Extract provider from model_id
        provider = model_id.split('/')[0] if '/' in model_id else "default"
        return self.ttl_by_provider.get(provider, self.ttl_by_provider["default"])
    
    def create_request_hash(
        self, 
        messages: List[Dict[str, str]], 
        model_id: str, 
        temperature: float,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Create a deterministic hash of the request parameters.
        
        Args:
            messages: List of message objects
            model_id: The model identifier
            temperature: The temperature parameter (affects output randomness)
            system_prompt: Optional system instructions
            
        Returns:
            A hash string representing the request
        """
        # Create a canonical representation of the request
        request_dict = {
            "messages": messages,
            "model": model_id,
            "temperature": temperature,
            "system_prompt": system_prompt or ""
        }
        
        # Convert to sorted JSON for deterministic serialization
        request_str = json.dumps(request_dict, sort_keys=True)
        
        # Create a hash of the request
        return hashlib.sha256(request_str.encode()).hexdigest()
    
    async def get_cached_response(
        self,
        messages: List[Dict[str, str]], 
        model_id: str, 
        temperature: float,
        system_prompt: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a cached response for the given request parameters.
        
        Args:
            messages: List of message objects
            model_id: The model identifier
            temperature: The temperature parameter
            system_prompt: Optional system instructions
            
        Returns:
            The cached response or None if not found
        """
        if not self.cache_enabled:
            return None
            
        # Generate a hash for the request
        request_hash = self.create_request_hash(
            messages, 
            model_id, 
            temperature,
            system_prompt
        )
        
        # Create the cache key
        cache_key = f"response:{model_id}:{request_hash}"
        
        # Attempt to retrieve from cache
        cached_value = await self.redis.get(cache_key)
        if cached_value:
            try:
                return json.loads(cached_value)
            except json.JSONDecodeError:
                # If JSON decoding fails, invalidate the cache entry
                await self.redis.delete(cache_key)
                return None
        
        return None
    
    async def cache_response(
        self,
        messages: List[Dict[str, str]], 
        model_id: str, 
        temperature: float,
        response: Dict[str, Any],
        system_prompt: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache a response for future use.
        
        Args:
            messages: List of message objects
            model_id: The model identifier
            temperature: The temperature parameter
            response: The response to cache
            system_prompt: Optional system instructions
            ttl: Optional time-to-live override in seconds
            
        Returns:
            True if caching was successful
        """
        if not self.cache_enabled:
            return False
            
        # Don't cache error responses
        if response.get("error", False):
            return False
            
        # Generate a hash for the request
        request_hash = self.create_request_hash(
            messages, 
            model_id, 
            temperature,
            system_prompt
        )
        
        # Create the cache key
        cache_key = f"response:{model_id}:{request_hash}"
        
        # Determine TTL
        if ttl is None:
            ttl = self.get_ttl_for_model(model_id)
        
        # Cache the response
        return await self.redis.set(
            cache_key, 
            json.dumps(response), 
            ex=ttl
        )

    async def invalidate_cache_for_model(self, model_id: str) -> int:
        """
        Invalidate all cached responses for a specific model.
        
        Args:
            model_id: The model identifier
            
        Returns:
            Number of cache entries removed
        """
        # Get all keys for this model
        pattern = f"response:{model_id}:*"
        cursor = 0
        count = 0
        
        # Scan and delete in batches
        while True:
            cursor, keys = await self.redis.scan(cursor, match=pattern)
            if keys:
                count += await self.redis.delete(*keys)
            if cursor == 0:
                break
        
        return count

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the response cache.
        
        Returns:
            Dictionary with cache statistics
        """
        # Get cursor for scanning
        cursor = 0
        stats = {
            "total_entries": 0,
            "by_model": {}
        }
        
        # Scan all response cache keys
        while True:
            cursor, keys = await self.redis.scan(cursor, match="response:*")
            
            for key in keys:
                stats["total_entries"] += 1
                
                # Extract model from key
                key_parts = key.split(":")
                if len(key_parts) >= 2:
                    model = key_parts[1]
                    stats["by_model"][model] = stats["by_model"].get(model, 0) + 1
            
            if cursor == 0:
                break
        
        # Get memory usage if possible
        try:
            memory_info = await self.redis.info("memory")
            stats["memory_usage"] = memory_info.get("used_memory_human", "unknown")
        except:
            stats["memory_usage"] = "unknown"
            
        return stats
        
# Create a singleton instance
response_cache = ResponseCacheService()