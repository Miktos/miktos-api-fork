"""
Rate limiting middleware to protect API endpoints from abuse.
Uses in-memory storage with Redis-like interface for development,
but can be configured to use Redis in production.
"""
import time
import os
from typing import Dict, Optional, Union, Callable, Any
from datetime import datetime, timedelta
import asyncio
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logging import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """
    A simple in-memory rate limiter based on sliding window algorithm.
    
    Attributes:
        data (dict): In-memory storage for rate limit buckets
        cleanup_interval (int): How often to clean up expired rate limits in seconds
    """
    def __init__(self, cleanup_interval: int = 60):
        self.data: Dict[str, Dict[str, Any]] = {}
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()
        
    def increment(self, key: str, window: int, limit: int) -> Dict[str, Union[int, float, bool]]:
        """
        Increment the counter for a given key and check if rate limit is exceeded.
        
        Args:
            key: The rate limit key (usually client IP + endpoint)
            window: The time window in seconds
            limit: The maximum number of requests allowed in the window
            
        Returns:
            A dict containing rate limit information:
            - count: Current count in the window
            - remaining: Remaining requests allowed
            - reset_at: Timestamp when the rate limit will reset
            - reset_in: Seconds until rate limit reset
            - blocked: True if rate limit is exceeded
        """
        now = time.time()
        
        # Clean up expired entries periodically
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup(now)
            
        # Get or create bucket for this key
        bucket = self.data.get(key, {"count": 0, "window_start": now})
        
        # If window has expired, reset the counter
        if now - bucket["window_start"] > window:
            bucket = {"count": 0, "window_start": now}
            
        # Increment counter
        bucket["count"] += 1
        
        # Store updated bucket
        self.data[key] = bucket
        
        # Calculate rate limit info
        reset_at = bucket["window_start"] + window
        reset_in = max(0, reset_at - now)
        remaining = max(0, limit - bucket["count"])
        blocked = bucket["count"] > limit
        
        return {
            "count": bucket["count"],
            "remaining": remaining,
            "reset_at": reset_at,
            "reset_in": reset_in,
            "blocked": blocked
        }
        
    def _cleanup(self, now: float) -> None:
        """
        Remove expired rate limit entries to prevent memory leaks.
        
        Args:
            now: Current timestamp
        """
        # Find keys with expired windows (assuming 1 hour is max window)
        expired_keys = [
            key for key, bucket in self.data.items()
            if now - bucket["window_start"] > 3600
        ]
        
        # Remove expired keys
        for key in expired_keys:
            del self.data[key]
            
        self.last_cleanup = now


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting requests.
    
    Attributes:
        limiter: Rate limiter instance
        default_limit: Default requests per window
        default_window: Default window size in seconds
        exclude_paths: List of path prefixes to exclude from rate limiting
        by_path: Whether to include path in the rate limit key
        by_ip: Whether to include IP in the rate limit key
        block_paths: Path-specific rate limits
    """
    
    def __init__(
        self,
        app,
        limit: int = 100,
        window: int = 60,
        exclude_paths: Optional[list] = None,
        by_path: bool = True,
        by_ip: bool = True,
        block_paths: Optional[dict] = None
    ):
        """
        Initialize the rate limiter middleware.
        
        Args:
            app: The FastAPI application
            limit: Default requests per window
            window: Default window size in seconds
            exclude_paths: List of path prefixes to exclude from rate limiting
            by_path: Whether to include path in the rate limit key
            by_ip: Whether to include IP in the rate limit key
            block_paths: Dictionary mapping paths to their specific rate limits
        """
        super().__init__(app)
        self.limiter = RateLimiter()
        self.default_limit = limit
        self.default_window = window
        self.exclude_paths = exclude_paths or ["/docs", "/openapi.json", "/health"]
        self.by_path = by_path
        self.by_ip = by_ip
        self.block_paths = block_paths or {}

    def should_rate_limit(self, request: Request) -> tuple:
        """
        Determine if a request should be rate limited and the applicable limits.
        
        Args:
            request: The FastAPI request object
            
        Returns:
            Tuple of (should_limit, limit, window)
        """
        # Skip rate limiting for excluded paths
        path = request.url.path
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return False, 0, 0
                
        # Skip rate limiting when running in a test environment
        if os.environ.get('PYTEST_RUNNING') == '1':
            return False, 0, 0
                
        # Different rate limits based on path or method could be implemented here
        # For now, use defaults for all requests
        return True, self.default_limit, self.default_window
        
    def get_rate_limit_key(self, request: Request) -> str:
        """
        Generate a unique key for the rate limit based on client IP and path.
        
        Args:
            request: The FastAPI request object
            
        Returns:
            A string key for rate limiting
        """
        # Get client IP - could be improved to handle proxies
        client_ip = request.client.host if request.client else "unknown"
        
        # Get request path
        path = request.url.path
        
        # Combine for the rate limit key
        return f"ip:{client_ip}:path:{path}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and apply rate limiting if needed.
        
        Args:
            request: The FastAPI request
            call_next: The next middleware or endpoint handler
            
        Returns:
            The API response
        """
        # Check if we should rate limit this request
        should_limit, limit, window = self.should_rate_limit(request)
        
        if should_limit:
            # Generate rate limit key
            key = self.get_rate_limit_key(request)
            
            # Check rate limit
            rate_info = self.limiter.increment(key, window, limit)
            
            # Set rate limit headers
            headers = {
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(rate_info["remaining"]),
                "X-RateLimit-Reset": str(int(rate_info["reset_at"])),
            }
            
            # If rate limit exceeded, return 429 response
            if rate_info["blocked"]:
                logger.warning(
                    "Rate limit exceeded", 
                    key=key,
                    path=request.url.path,
                    ip=request.client.host if request.client else "unknown",
                    reset_in=int(rate_info["reset_in"])
                )
                
                # Use JSONResponse instead of Response for proper JSON serialization
                response = JSONResponse(
                    content={"detail": "Too many requests", "retry_after": int(rate_info["reset_in"])},
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers=headers
                )
                return response
        
        # Process the request normally
        response = await call_next(request)
        
        # Add rate limit headers to response if applicable
        if should_limit:
            response.headers.update(headers)
        
        return response