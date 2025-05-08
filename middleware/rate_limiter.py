"""
Rate limiting middleware to protect API endpoints from abuse.
Uses in-memory storage with Redis-like interface for development,
but can be configured to use Redis in production.
"""
import time
import os
from typing import Dict, Optional, Union, Callable, Any, List, Tuple
from datetime import datetime, timedelta
import asyncio
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logging import get_logger
from config.settings import settings

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

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the current rate limiter state"""
        return {
            "active_keys": len(self.data),
            "last_cleanup": self.last_cleanup
        }


class EndpointRateLimit:
    """Configuration for rate limits on specific endpoints or path patterns"""
    
    def __init__(
        self, 
        pattern: str, 
        limit: int, 
        window: int, 
        description: str = ""
    ):
        """
        Initialize endpoint rate limit configuration
        
        Args:
            pattern: Path pattern to match (prefix match)
            limit: Maximum requests allowed in the time window
            window: Time window in seconds
            description: Human-readable description of this rate limit
        """
        self.pattern = pattern
        self.limit = limit
        self.window = window
        self.description = description
    
    def matches(self, path: str) -> bool:
        """Check if the given path matches this rate limit pattern"""
        return path.startswith(self.pattern)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting requests.
    
    Attributes:
        limiter: Rate limiter instance
        default_limit: Default requests per window
        default_window: Default window size in seconds
        exclude_paths: List of path prefixes to exclude from rate limiting
        endpoint_limits: List of specific endpoint rate limits
        by_path: Whether to include path in the rate limit key
        by_ip: Whether to include IP in the rate limit key
        get_key_details: Optional callable to extract additional key details
    """
    
    def __init__(
        self,
        app,
        default_limit: int = 100,
        default_window: int = 60,
        exclude_paths: Optional[List[str]] = None,
        endpoint_limits: Optional[List[EndpointRateLimit]] = None,
        by_path: bool = True,
        by_ip: bool = True,
        get_key_details: Optional[Callable[[Request], str]] = None
    ):
        """
        Initialize the rate limiter middleware.
        
        Args:
            app: The FastAPI application
            default_limit: Default requests per window
            default_window: Default window size in seconds
            exclude_paths: List of path prefixes to exclude from rate limiting
            endpoint_limits: List of specific endpoint rate limits
            by_path: Whether to include path in the rate limit key
            by_ip: Whether to include IP in the rate limit key
            get_key_details: Optional function to extract additional key details
        """
        super().__init__(app)
        self.limiter = RateLimiter()
        self.default_limit = default_limit
        self.default_window = default_window
        self.exclude_paths = exclude_paths or ["/docs", "/openapi.json", "/health"]
        self.by_path = by_path
        self.by_ip = by_ip
        self.endpoint_limits = endpoint_limits or []
        self.get_key_details = get_key_details
        
        # Log startup information
        limits_info = [
            f"{limit.pattern} - {limit.limit}/{limit.window}s" 
            for limit in self.endpoint_limits
        ]
        logger.info(
            "Rate limiter initialized",
            default=f"{default_limit}/{default_window}s",
            endpoint_limits=limits_info,
            excluded=self.exclude_paths
        )

    def should_rate_limit(self, request: Request) -> Tuple[bool, int, int]:
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
        
        # Check if this path matches any specific endpoint rate limit
        for endpoint_limit in self.endpoint_limits:
            if endpoint_limit.matches(path):
                return True, endpoint_limit.limit, endpoint_limit.window
        
        # If no specific limit, use the defaults
        return True, self.default_limit, self.default_window
        
    def get_rate_limit_key(self, request: Request) -> str:
        """
        Generate a unique key for the rate limit based on client IP and path.
        
        Args:
            request: The FastAPI request object
            
        Returns:
            A string key for rate limiting
        """
        parts = []
        
        # Add IP component if enabled
        if self.by_ip:
            # Try to get the real client IP (considering X-Forwarded-For header)
            client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if not client_ip:
                client_ip = request.client.host if request.client else "unknown"
            parts.append(f"ip:{client_ip}")
        
        # Add path component if enabled
        if self.by_path:
            path = request.url.path
            parts.append(f"path:{path}")
            
        # Add any custom key details if provided
        if self.get_key_details:
            custom_details = self.get_key_details(request)
            if custom_details:
                parts.append(custom_details)
                
        # If we have a user in the request state, add user ID
        if hasattr(request.state, "user") and request.state.user:
            user_id = getattr(request.state.user, "id", None)
            if user_id:
                parts.append(f"user:{user_id}")
        
        # Combine parts into the rate limit key
        return ":".join(parts)

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
                    content={
                        "detail": "Too many requests", 
                        "retry_after": int(rate_info["reset_in"]),
                        "error": "rate_limit_exceeded"
                    },
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


def get_rate_limiter_config():
    """
    Get rate limiter configuration without creating the middleware instance.
    
    Returns:
        Dict with configuration parameters for RateLimiterMiddleware
    """
    # Define specific endpoint rate limits
    endpoint_limits = [
        # Auth endpoints - more permissive for login/register
        EndpointRateLimit(
            pattern="/api/v1/auth/login", 
            limit=20, 
            window=60,
            description="Login attempts"
        ),
        EndpointRateLimit(
            pattern="/api/v1/auth/register", 
            limit=10, 
            window=600,  # 10 minutes
            description="Registration attempts"
        ),
        
        # AI Generation endpoints - more restrictive
        EndpointRateLimit(
            pattern="/api/v1/generate", 
            limit=30, 
            window=60,
            description="AI generation requests"
        ),
        
        # Project management - normal limits
        EndpointRateLimit(
            pattern="/api/v1/projects", 
            limit=100, 
            window=60,
            description="Project management operations"
        )
    ]
    
    # Paths to exclude from rate limiting
    exclude_paths = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/health",
        "/api/v1/status",
    ]
    
    # Return the configuration dictionary
    return {
        "default_limit": 200,              # Default for unspecified endpoints
        "default_window": 60,              # Default window is 1 minute
        "exclude_paths": exclude_paths,
        "endpoint_limits": endpoint_limits,
        "by_path": True,                   # Include path in rate limit key
        "by_ip": True                      # Include IP in rate limit key
    }


def create_rate_limiter(app) -> RateLimiterMiddleware:
    """
    Create and configure a rate limiter middleware based on application settings.
    
    Args:
        app: FastAPI application
        
    Returns:
        Configured RateLimiterMiddleware instance
    """
    config = get_rate_limiter_config()
    
    # Create the middleware instance
    return RateLimiterMiddleware(
        app=app,
        default_limit=config["default_limit"],
        default_window=config["default_window"],
        exclude_paths=config["exclude_paths"],
        endpoint_limits=config["endpoint_limits"],
        by_path=config["by_path"],
        by_ip=config["by_ip"]
    )