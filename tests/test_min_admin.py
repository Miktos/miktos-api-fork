"""Basic admin test with real User objects."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import uuid

# Import the app
from main import app
import security
from api.auth import is_admin
from models.database_models import User

# Create test client
client = TestClient(app)

# Basic auth headers for testing
AUTH_HEADERS = {"Authorization": "Bearer test-admin-token"}


# Simple test to verify pytest discovery
def test_admin_simple():
    """Simple test to verify pytest discovery."""
    assert True


# Create a test for the admin stats endpoint
def test_admin_stats_with_real_user():
    """Test the admin stats endpoint with a real User object."""
    # Create a real User instance
    user_id = uuid.uuid4()
    admin_user = User(
        id=user_id,
        username="admin",
        email="admin@example.com",
        hashed_password="hashed_password_for_testing",
        is_active=True,
        is_admin=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    # Initialize relationship attributes to avoid None errors
    admin_user.projects = []
    admin_user.messages = []
    admin_user.activities = []
    
    # Define async mock functions for deps
    async def mock_get_current_user():
        return admin_user
        
    async def mock_is_admin_func():
        return admin_user
    
    # Set up repository mocks
    user_repo_mock = MagicMock()
    user_repo_mock.count.return_value = 10
    user_repo_mock.count_active.return_value = 8
    
    project_repo_mock = MagicMock()
    project_repo_mock.count.return_value = 25
    project_repo_mock.count_by_status.return_value = {
        "NONE": 5, "PENDING": 3, "PROCESSING": 2, "COMPLETED": 15
    }
    
    message_repo_mock = MagicMock()
    message_repo_mock.count.return_value = 500
    message_repo_mock.count_since.return_value = 50
    
    # Mock cache stats
    mock_cache_stats = {"total_keys": 100, "hit_rate": 0.75}
    
    # Apply the mocks
    with patch.dict(app.dependency_overrides, {
            security.get_current_user: mock_get_current_user,
            is_admin: mock_is_admin_func
        }), \
        patch("api.admin.UserRepository", return_value=user_repo_mock), \
        patch("api.admin.ProjectRepository", return_value=project_repo_mock), \
        patch("api.admin.MessageRepository", return_value=message_repo_mock), \
        patch("api.admin.response_cache.get_cache_stats", return_value=mock_cache_stats), \
        patch("dependencies.get_db") as mock_db:
        
        # Call the endpoint
        response = client.get("/api/v1/admin/stats", headers=AUTH_HEADERS)
        
        # Print status for debugging
        print(f"Status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")
            
        # Check response
        assert response.status_code == 200
        
        # Verify data structure
        data = response.json()
        assert "users" in data
        assert "projects" in data
        assert "messages" in data
