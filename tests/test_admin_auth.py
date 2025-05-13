# tests/test_admin_auth.py
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Dict, Any, Generator

# Import the app instance
from main import app as main_app
from security import get_current_user
from tests.admin_test_helpers import MockUser

# Create test client directly from app
client = TestClient(main_app)

# --- New Authentication Bypass Fixture using dependency_overrides ---
@pytest.fixture(autouse=True)
def default_admin_user_override(request):
    """
    Default override for get_current_user to return an admin user.
    Tests can opt-out by using the 'skip_default_admin_override' marker.
    """
    if "skip_default_admin_override" in request.keywords:
        yield
        return

    mock_admin_user = MockUser(
        id="admin-user-id-123",
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        is_active=True,
        is_admin=True,
        created_at=datetime.now(),
    )

    async def mock_get_current_user_admin():
        return mock_admin_user

    original_override = main_app.dependency_overrides.get(get_current_user)
    main_app.dependency_overrides[get_current_user] = mock_get_current_user_admin
    yield
    if original_override:
        main_app.dependency_overrides[get_current_user] = original_override
    else:
        del main_app.dependency_overrides[get_current_user]

@pytest.fixture
def mock_db() -> Generator:
    """Mock the database session dependency."""
    with patch("dependencies.get_db") as mock:
        mock_db_session = MagicMock(spec=Session)
        mock.return_value = iter([mock_db_session]) 
        yield mock_db_session

# --- Test Admin Stats Endpoint ---
def test_admin_stats_endpoint(mock_db):
    """Test the admin stats endpoint with mocked repositories."""
    # Mock repository methods
    user_repo_mock = MagicMock()
    user_repo_mock.count.return_value = 10
    user_repo_mock.count_active.return_value = 8
    
    project_repo_mock = MagicMock()
    project_repo_mock.count.return_value = 25
    project_repo_mock.count_by_status.return_value = {
        "NONE": 5,
        "PENDING": 3,
        "PROCESSING": 2,
        "COMPLETED": 15
    }
    
    message_repo_mock = MagicMock()
    message_repo_mock.count.return_value = 500
    message_repo_mock.count_since.return_value = 50 
    
    mock_cache_stats = {
        "total_keys": 100,
        "hit_rate": 0.75,
        "memory_usage_mb": 25.5
    }
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock), \
         patch("api.admin.ProjectRepository", return_value=project_repo_mock), \
         patch("api.admin.MessageRepository", return_value=message_repo_mock), \
         patch("api.admin.response_cache.get_cache_stats", return_value=mock_cache_stats):
        
        # Make the request without auth headers
        response = client.get("/api/v1/admin/stats") 
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert data["users"]["total"] == 10
        assert data["users"]["active"] == 8
        assert data["projects"]["total"] == 25
        assert data["messages"]["total"] == 500
        assert data["cache"] == mock_cache_stats  # Changed "cache_stats" to "cache"
