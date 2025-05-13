"""Helper functions for admin endpoint testing."""
from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, Optional, AsyncGenerator

from jose import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel  # Ensure BaseModel is imported

# Import main app for dependency override helpers
from main import app as main_app

# Mock user data
MOCK_ADMIN_USER_ID = str(uuid.uuid4())
MOCK_REGULAR_USER_ID = str(uuid.uuid4())

MOCK_ADMIN_USER = {
    "id": MOCK_ADMIN_USER_ID,
    "email": "admin@example.com",
    "username": "admin_user",  # Added username
    "full_name": "Admin User",  # Added full name
    "is_active": True,
    "is_admin": True,
    "created_at": datetime.now(),
}

MOCK_REGULAR_USER = {
    "id": MOCK_REGULAR_USER_ID,
    "email": "user@example.com",
    "username": "regular_user",  # Added username
    "full_name": "Regular User",  # Added full name
    "is_active": True,
    "is_admin": False,
    "created_at": datetime.now(),
}

# Mock JWT settings
TEST_JWT_SECRET = "test_secret_key_for_tests_only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_test_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT token for testing."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, TEST_JWT_SECRET, algorithm=ALGORITHM)

# Define AUTH_HEADERS for admin and regular users
ADMIN_TOKEN = create_test_token({"sub": MOCK_ADMIN_USER_ID, "is_admin": True})
REGULAR_USER_TOKEN = create_test_token({"sub": MOCK_REGULAR_USER_ID, "is_admin": False})

AUTH_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
REGULAR_USER_AUTH_HEADERS = {"Authorization": f"Bearer {REGULAR_USER_TOKEN}"}

def get_admin_token() -> str:
    """Creates an admin token for tests."""
    return create_test_token({"sub": MOCK_ADMIN_USER_ID})

def get_user_token() -> str:
    """Creates a regular user token for tests."""
    return create_test_token({"sub": MOCK_REGULAR_USER_ID})

def get_auth_headers() -> Dict[str, str]:
    """Creates authentication headers with admin token."""
    return {"Authorization": f"Bearer {get_admin_token()}"}

def get_admin_headers() -> Dict[str, str]:
    """Creates authentication headers for admin users."""
    return {"Authorization": f"Bearer {get_admin_token()}"}

def get_user_headers() -> Dict[str, str]:
    """Creates authentication headers for regular users."""
    return {"Authorization": f"Bearer {get_user_token()}"}

# User class that mimics the SQLAlchemy User model
class MockUser(BaseModel):
    """Mock user class for testing that mimics the SQLAlchemy User model."""
    id: str
    email: str
    username: str
    full_name: str
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime

async def mock_get_current_admin_user() -> MockUser:
    """Mock function to return an admin user."""
    return MockUser(**MOCK_ADMIN_USER)

async def mock_get_current_regular_user() -> MockUser:
    """Mock function to return a regular user."""
    return MockUser(**MOCK_REGULAR_USER)

async def mock_is_admin(current_user: MockUser) -> MockUser:
    """Mock function to check if user is admin."""
    if not current_user.is_admin:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin access required."
        )
    return current_user

def setup_test_client() -> TestClient:
    """Create a TestClient with authentication dependencies overridden"""
    # Import dependencies - do this here to avoid circular imports
    from security import get_current_user
    from api.auth import is_admin
    
    # Create a fresh FastAPI app
    test_app = FastAPI()
    
    # Copy the routes from main_app
    for route in main_app.routes:
        test_app.routes.append(route)
    
    # Override dependencies for testing
    test_app.dependency_overrides[get_current_user] = mock_get_current_admin_user
    test_app.dependency_overrides[is_admin] = mock_is_admin
    
    return TestClient(test_app)

def configure_auth_for_testing(app_instance=main_app):
    """Configure the app with authentication overrides for testing"""
    # Import dependencies
    from security import get_current_user
    from api.auth import is_admin
    
    # Store original dependency overrides
    original_overrides = app_instance.dependency_overrides.copy()
    
    # Override dependencies for testing
    app_instance.dependency_overrides[get_current_user] = mock_get_current_admin_user
    app_instance.dependency_overrides[is_admin] = mock_is_admin
    
    return {
        "original_overrides": original_overrides,
        "admin_user": MockUser(**MOCK_ADMIN_USER),
        "regular_user": MockUser(**MOCK_REGULAR_USER),
    }

def reset_auth_overrides(app_instance=main_app, original_overrides=None):
    """Reset authentication overrides to original state"""
    if original_overrides:
        app_instance.dependency_overrides = original_overrides
    else:
        # Import dependencies
        from security import get_current_user
        from api.auth import is_admin
        
        # Clear specific overrides
        if get_current_user in app_instance.dependency_overrides:
            del app_instance.dependency_overrides[get_current_user]
        
        if is_admin in app_instance.dependency_overrides:
            del app_instance.dependency_overrides[is_admin]
