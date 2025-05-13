# miktos_backend/middleware/activity_logger.py
import time
from typing import Callable
from fastapi import Request, Response
import logging
import uuid
from repositories.activity_repository import ActivityRepository
from sqlalchemy.orm import Session
from config.database import SessionLocal

logger = logging.getLogger(__name__)

class ActivityLoggerMiddleware:
    """
    Middleware for logging user activity in the database.
    
    This middleware tracks:
    - API calls with endpoints
    - Response times
    - User IDs for authenticated requests
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Pass through non-HTTP requests (like WebSockets)
            return await self.app(scope, receive, send)
            
        start_time = time.time()
        
        # Get the route path for categorization
        path = scope["path"]
        route = scope.get("route")
        route_path = getattr(route, "path", path) if route else path
        
        # Create a wrapped send function that captures the response data
        response_status = None
        response_headers = []
        
        async def send_wrapper(message):
            nonlocal response_status, response_headers
            
            if message["type"] == "http.response.start":
                response_status = message["status"]
                response_headers = message.get("headers", [])
                
                # Add processing time header
                process_time = time.time() - start_time
                message["headers"] = message.get("headers", []) + [
                    (b"X-Process-Time", f"{round(process_time * 1000)}ms".encode())
                ]
                
            await send(message)
            
            # After sending the response, attempt to log the activity
            if message["type"] == "http.response.end":
                # Track user ID if authenticated
                user_id = None
                try:
                    # Try to get user ID from the request state
                    if "state" in scope and hasattr(scope["state"], "user_id"):
                        user_id = scope["state"].user_id
                except Exception:
                    pass
                
                # Only log user activity if we have a user ID
                if user_id:
                    try:
                        # Create DB session
                        db = SessionLocal()
                        try:
                            # Get method and user agent
                            method = scope.get("method", "UNKNOWN")
                            headers = {h[0].decode(): h[1].decode() for h in scope.get("headers", [])}
                            user_agent = headers.get("user-agent", "")
                            
                            # Log the activity
                            activity_repo = ActivityRepository(db)
                            process_time = time.time() - start_time
                            activity_repo.record_activity(
                                user_id=user_id,
                                activity_type="api_call", 
                                endpoint=route_path,
                                details={
                                    "method": method,
                                    "status_code": response_status,
                                    "process_time_ms": round(process_time * 1000),
                                    "user_agent": user_agent
                                }
                            )
                        finally:
                            db.close()
                    except Exception as e:
                        logger.error(f"Failed to log user activity: {str(e)}")
        
        # Call the next middleware with our wrapped send function
        await self.app(scope, receive, send_wrapper)
