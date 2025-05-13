# tests/test_admin_simple.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
from typing import Generator
import uuid

# Import the app from main
from main import app as main_app
from security import get_current_user
from tests.admin_test_helpers import MockUser

# Set up the test client
client = TestClient(main_app)

# --- Fixtures ---

@pytest.fixture(autouse=True)
def default_admin_user_override(request):
    if "skip_default_admin_override" in request.keywords:
        yield
        return

    mock_admin_user = MockUser(
        id="admin-user-simple-id",
        email="admin_simple@example.com",
        username="admin_simple",
        full_name="Admin Simple User",
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
        if get_current_user in main_app.dependency_overrides:
            del main_app.dependency_overrides[get_current_user]

@pytest.fixture
def mock_db_session() -> Generator[MagicMock, None, None]:
    """Mock the database session dependency."""
    from sqlalchemy.orm import Session
    mock_session = MagicMock(spec=Session)
    with patch("dependencies.get_db", return_value=iter([mock_session])) as mock_get_db_patch:
        yield mock_session

# --- Tests ---

def test_stats_endpoint(mock_db_session: MagicMock):
    """Test the admin stats endpoint."""
    # Mock all the required repository functions
    with patch("api.admin.UserRepository") as mock_user_repo, \
         patch("api.admin.ProjectRepository") as mock_proj_repo, \
         patch("api.admin.MessageRepository") as mock_msg_repo, \
         patch("api.admin.response_cache.get_cache_stats", AsyncMock(return_value={
            "total_keys": 100,
            "hit_rate": 0.75,
            "memory_usage_mb": 25.5
        })) as mock_cache:
        
        # Configure mocks for repository instances
        user_repo_instance = mock_user_repo.return_value
        user_repo_instance.count.return_value = 10
        user_repo_instance.count_active.return_value = 8
        
        proj_repo_instance = mock_proj_repo.return_value
        proj_repo_instance.count.return_value = 25
        proj_repo_instance.count_by_status.return_value = {
            "NONE": 5, "PENDING": 3, "PROCESSING": 2, "COMPLETED": 15
        }
        
        msg_repo_instance = mock_msg_repo.return_value
        msg_repo_instance.count.return_value = 500
        msg_repo_instance.count_since.return_value = 50
        
        # Call the endpoint
        response = client.get("/api/v1/admin/stats")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify content
        assert data["users"]["total"] == 10
        assert data["users"]["active"] == 8
        assert data["projects"]["total"] == 25
        assert data["projects"]["by_status"] == {
            "NONE": 5, "PENDING": 3, "PROCESSING": 2, "COMPLETED": 15
        }
        assert data["messages"]["total"] == 500
        assert data["messages"]["last_24h"] == 50
        assert data["cache"] == {
            "total_keys": 100,
            "hit_rate": 0.75,
            "memory_usage_mb": 25.5
        }
        assert "system" in data

@pytest.mark.skip_default_admin_override
def test_admin_access_required(mock_db_session: MagicMock):
    """Test that non-admin users can't access admin endpoints."""
    mock_regular_user = MockUser(
        id="regular-user-simple-id",
        email="regular_simple@example.com",
        username="regular_simple",
        full_name="Regular Simple User",
        is_active=True,
        is_admin=False,
        created_at=datetime.now(),
    )

    async def _mock_get_current_user_regular():
        return mock_regular_user

    original_override = main_app.dependency_overrides.get(get_current_user)
    main_app.dependency_overrides[get_current_user] = _mock_get_current_user_regular
    
    # Added necessary patches for repositories and cache stats
    with patch("api.admin.UserRepository", MagicMock()), \
         patch("api.admin.ProjectRepository", MagicMock()), \
         patch("api.admin.MessageRepository", MagicMock()), \
         patch("api.admin.response_cache.get_cache_stats", AsyncMock(return_value={})):
        response = client.get("/api/v1/admin/stats")

    if original_override:
        main_app.dependency_overrides[get_current_user] = original_override
    else:
        if get_current_user in main_app.dependency_overrides:
            del main_app.dependency_overrides[get_current_user]
            
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions. Admin access required."

def test_users_endpoint(mock_db_session: MagicMock):
    """Test the admin/users endpoint."""
    # Create mock users for the repository response
    mock_users_data = [
        MagicMock(id="user1-simple-id", email="user1_simple@example.com", username="user1_simple", is_active=True, is_admin=False, created_at=datetime.now(), projects=[]),
        MagicMock(id="user2-simple-id", email="user2_simple@example.com", username="user2_simple", is_active=False, is_admin=False, created_at=datetime.now(), projects=[MagicMock(), MagicMock()])
    ]
    
    # Mock the UserRepository
    with patch("api.admin.UserRepository") as mock_repo:
        repo_instance = mock_repo.return_value
        repo_instance.get_multi.return_value = mock_users_data
        
        # Call the endpoint
        response = client.get("/api/v1/admin/users")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert len(data) == 2
        assert data[0]["email"] == "user1_simple@example.com"
        assert data[0]["is_active"] is True
        assert data[0]["project_count"] == 0
        
        assert data[1]["email"] == "user2_simple@example.com"
        assert data[1]["is_active"] is False
        assert data[1]["project_count"] == 2

def test_cache_invalidation(mock_db_session: MagicMock):
    """Test the admin/cache/invalidate endpoint."""
    model_id = "openai/gpt-4"
    mock_removed_count = 15
    
    # Mock the cache invalidation function
    with patch("api.admin.response_cache.invalidate_cache_for_model", AsyncMock(return_value=mock_removed_count)):
        # Call the endpoint
        response = client.post(f"/api/v1/admin/cache/invalidate/{model_id}")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert data["success"] is True
        assert data["model_id"] == model_id
        assert data["entries_removed"] == mock_removed_count
        assert "timestamp" in data
