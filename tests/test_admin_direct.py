# tests/test_admin_direct.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from fastapi import Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Generator

# Import our test helpers
from tests.admin_test_helpers import MockUser

# Import the app instance and security functions
from main import app as main_app
from security import get_current_user

# Create test client with our app
client = TestClient(main_app)

# --- New Authentication Bypass Fixture using dependency_overrides ---
@pytest.fixture(autouse=True)
def default_admin_user_override(request):
    if "skip_default_admin_override" in request.keywords:
        yield
        return

    mock_admin_user = MockUser(
        id="admin-user-id-direct",
        email="admin_direct@example.com",
        username="admin_direct",
        full_name="Admin Direct User",
        is_active=True,
        is_admin=True,
        created_at=datetime.now(),
    )

    async def _mock_get_current_user():
        return mock_admin_user

    original_override = main_app.dependency_overrides.get(get_current_user)
    main_app.dependency_overrides[get_current_user] = _mock_get_current_user
    yield
    if original_override:
        main_app.dependency_overrides[get_current_user] = original_override
    else:
        del main_app.dependency_overrides[get_current_user]

# --- Mock database access ---
@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:  # Corrected type hint
    """Returns a mock database session."""
    mock_session = MagicMock(spec=Session)
    with patch("dependencies.get_db", return_value=iter([mock_session])) as mock_get_db:
        yield mock_session

# --- Test Admin Stats Endpoint ---
def test_admin_stats_endpoint(mock_db):
    """Test the /admin/stats endpoint with mocked repository methods."""
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
    
    mock_cache_stats = {
        "total_keys": 100,
        "hit_rate": 0.75,
        "memory_usage_mb": 25.5
    }
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock), \
         patch("api.admin.ProjectRepository", return_value=project_repo_mock), \
         patch("api.admin.MessageRepository", return_value=message_repo_mock), \
         patch("api.admin.response_cache.get_cache_stats", return_value=mock_cache_stats):
        
        response = client.get("/api/v1/admin/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["users"]["total"] == 10
        assert data["users"]["active"] == 8
        assert data["projects"]["total"] == 25
        assert data["messages"]["total"] == 500
        assert data["messages"]["last_24h"] == 50
        assert data["cache"] == mock_cache_stats

# Test that regular user is rejected
@pytest.mark.skip_default_admin_override
def test_admin_access_control(mock_db):
    """Test that admin endpoints reject non-admin users."""
    
    mock_regular_user = MockUser(
        id="regular-user-id-direct",
        email="regular_direct@example.com",
        username="regular_direct",
        full_name="Regular Direct User",
        is_active=True,
        is_admin=False,
        created_at=datetime.now(),
    )

    async def _mock_get_current_user_regular():
        return mock_regular_user

    original_override = main_app.dependency_overrides.get(get_current_user)
    main_app.dependency_overrides[get_current_user] = _mock_get_current_user_regular
    
    with patch("api.admin.UserRepository", MagicMock()), \
         patch("api.admin.ProjectRepository", MagicMock()), \
         patch("api.admin.MessageRepository", MagicMock()), \
         patch("api.admin.response_cache.get_cache_stats", AsyncMock(return_value={})):
        response = client.get("/api/v1/admin/stats")
    
    if original_override:
        main_app.dependency_overrides[get_current_user] = original_override
    else:
        del main_app.dependency_overrides[get_current_user]
        
    assert response.status_code == 403
    # The detail message comes from the is_admin dependency now
    assert "Insufficient permissions. Admin access required." in response.json()["detail"]  # Corrected assertion message
