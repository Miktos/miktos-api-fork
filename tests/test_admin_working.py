"""Admin endpoint tests using a working approach with proper User objects."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid
import os
import sys
import psutil

# Import the app
from main import app
import security
from api.auth import is_admin
from models.database_models import User

# Create test client
client = TestClient(app)

# --- Setup ---

# Mock for the server_manager module itself
_mock_server_manager_module = MagicMock()
# Mock for the find_running_servers function within the mocked server_manager
_mock_find_running_servers_on_module = MagicMock()
# Assign the mocked function to the mocked module
_mock_server_manager_module.find_running_servers = _mock_find_running_servers_on_module

# Basic auth headers for testing
AUTH_HEADERS = {"Authorization": "Bearer test-admin-token"}


# Mock database session
@pytest.fixture
def mock_db():
    """Returns a mocked database session."""
    with patch("dependencies.get_db") as mock:
        mock_db = MagicMock(spec=Session)
        mock.return_value.__next__.return_value = mock_db
        yield mock_db


# Create real User instance for admin tests
@pytest.fixture
def admin_user():
    """Create a real User instance that FastAPI can properly serialize."""
    user_id = uuid.uuid4()
    user = User(
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
    user.projects = []
    user.messages = []
    user.activities = []
    
    return user


# Update app to use our overrides
@pytest.fixture(autouse=True)
def mock_auth_dependencies(admin_user):
    """Override the authentication dependencies for all tests."""
    
    # Create an async function to return the admin user
    async def mock_get_current_user():
        return admin_user
    
    # Create an async function that passes through if user is admin
    async def mock_is_admin_func(current_user=Depends(mock_get_current_user)):
        if not current_user.is_admin:
            raise HTTPException(
                status_code=403, 
                detail="Insufficient permissions. Admin access required."
            )
        return current_user
    
    # Apply the overrides at the app level
    original_overrides = app.dependency_overrides.copy()
    
    # Important: we need to override at the function level that the path operations directly depend on
    app.dependency_overrides[security.get_current_user] = mock_get_current_user
    app.dependency_overrides[is_admin] = mock_is_admin_func
    
    # Run the test
    yield
    
    # Restore the original overrides
    app.dependency_overrides = original_overrides
    

def test_admin_simple():
    """Simple test to verify pytest discovery."""
    assert True


# --- Tests ---

def test_admin_stats_endpoint(mock_db):
    """Test the /admin/stats endpoint."""
    # Mock repository methods
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
    mock_cache_stats = {
        "total_keys": 100,
        "hit_rate": 0.75,
        "memory_usage_mb": 25.5
    }
    
    # Set up mocks
    with patch("api.admin.UserRepository", return_value=user_repo_mock), \
         patch("api.admin.ProjectRepository", return_value=project_repo_mock), \
         patch("api.admin.MessageRepository", return_value=message_repo_mock), \
         patch("api.admin.response_cache.get_cache_stats", return_value=mock_cache_stats):
        
        # Call the endpoint
        response = client.get("/api/v1/admin/stats", headers=AUTH_HEADERS)
        
        # Print status code and response for debugging
        print(f"Stats endpoint status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Stats endpoint response body: {response.text}")
        
        # Check response status
        assert response.status_code == 200
        
        # Check data
        data = response.json()
        assert data["users"]["total"] == 10
        assert data["users"]["active"] == 8
        assert data["projects"]["total"] == 25
        assert data["projects"]["by_status"] == {
            "NONE": 5, "PENDING": 3, "PROCESSING": 2, "COMPLETED": 15
        }
        assert data["messages"]["total"] == 500
        assert data["messages"]["last_24h"] == 50
        assert "cache" in data


def test_admin_endpoint_requires_admin(admin_user):
    """Test that admin endpoints reject non-admin users."""
    # Create a regular (non-admin) user using proper User model
    user_id = uuid.uuid4()
    regular_user = User(
        id=user_id,
        username="regular",
        email="user@example.com",
        hashed_password="hashed_password_for_testing",
        is_active=True,
        is_admin=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    # Initialize relationship attributes
    regular_user.projects = []
    regular_user.messages = []
    regular_user.activities = []
    
    # Create custom async functions for this specific test
    async def mock_get_regular_user():
        return regular_user
    
    async def mock_is_admin_check(current_user=Depends(mock_get_regular_user)):
        if not current_user.is_admin:
            raise HTTPException(
                status_code=403, 
                detail="Insufficient permissions. Admin access required."
            )
        return current_user
    
    # Temporarily replace dependencies just for this test
    with patch.dict(app.dependency_overrides, {
        security.get_current_user: mock_get_regular_user,
        is_admin: mock_is_admin_check
    }):
        response = client.get("/api/v1/admin/stats", headers=AUTH_HEADERS)
        
        # Should return 403 Forbidden
        assert response.status_code == 403


def test_admin_health_endpoint(mock_db):
    """Test the health endpoint."""
    # Mock health data - use 'healthy' as the status since that's what the actual API returns
    mock_health_data = {
        "status": "healthy",  # Changed from "ok" to "healthy" to match actual API behavior
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {"status": "healthy", "details": "Connected"},
            "cache": {"status": "healthy", "details": "Redis operational"}
        },
        "version": "0.2.0"
    }
    
    # Mock process info
    mock_process_info = {
        "pid": 1234,
        "cpu_percent": 5.2,
        "memory_percent": 2.7,
        "threads": 4,
        "open_files": 8, 
        "connections": 3,
        "create_time": 1625000000.0
    }
    
    # Set up mocks
    with patch("api.admin.detailed_status", return_value=MagicMock(model_dump=lambda: mock_health_data)), \
         patch("api.admin.psutil.Process") as mock_process, \
         patch("api.admin.find_running_servers", return_value=[]):
        
        # Configure the mock
        process_instance = mock_process.return_value
        process_instance.pid = mock_process_info["pid"]
        process_instance.cpu_percent.return_value = mock_process_info["cpu_percent"]
        process_instance.memory_percent.return_value = mock_process_info["memory_percent"]
        process_instance.num_threads.return_value = mock_process_info["threads"]
        process_instance.open_files.return_value = [MagicMock()] * mock_process_info["open_files"]
        process_instance.connections.return_value = [MagicMock()] * mock_process_info["connections"]
        process_instance.create_time.return_value = mock_process_info["create_time"]
        
        # Call endpoint
        response = client.get("/api/v1/admin/system/health", headers=AUTH_HEADERS)
        
        # Print status code and response for debugging
        print(f"Health endpoint status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Health endpoint response body: {response.text}")
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Check for the presence of expected fields without asserting specific values
        assert "status" in data
        assert "components" in data
        assert "system_info" in data
        
        # Assert just that status is 'healthy' since we know that's what the API returns
        assert data["status"] == "healthy"
        
        # Verify data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "components" in data
        assert data["process_info"]["pid"] == mock_process_info["pid"]


def test_admin_users_endpoint(mock_db):
    """Test the users endpoint."""
    # Create mock users for testing
    mock_users = [
        MagicMock(
            id="user1",
            email="user1@example.com", 
            username="user1",
            is_active=True,
            is_admin=False,
            created_at=datetime.now(),
            projects=[]
        ),
        MagicMock(
            id="user2", 
            email="user2@example.com",
            username="user2",
            is_active=False,
            is_admin=False,
            created_at=datetime.now(),
            projects=[MagicMock(), MagicMock()]
        )
    ]
    
    # Mock repository
    user_repo_mock = MagicMock()
    user_repo_mock.get_multi.return_value = mock_users
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock):
        # Call endpoint
        response = client.get("/api/v1/admin/users", headers=AUTH_HEADERS)
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert len(data) == 2
        assert data[0]["email"] == "user1@example.com"
        assert data[0]["is_active"] is True
        assert data[0]["project_count"] == 0
        
        assert data[1]["email"] == "user2@example.com"
        assert data[1]["is_active"] is False
        assert data[1]["project_count"] == 2


def test_admin_cache_invalidation():
    """Test the cache invalidation endpoint."""
    # Setup test data
    model_id = "openai-gpt-4"
    mock_removed_count = 15
    
    # Mock the cache service
    with patch("api.admin.response_cache.invalidate_cache_for_model", return_value=mock_removed_count):
        # Call endpoint
        response = client.post(f"/api/v1/admin/cache/invalidate/{model_id}", headers=AUTH_HEADERS)
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert data["success"] is True
        assert data["model_id"] == model_id
        assert data["entries_removed"] == mock_removed_count
        assert "timestamp" in data


@patch.dict(sys.modules, {'server_manager': _mock_server_manager_module})
def test_admin_server_processes_endpoint(mock_db):
    """Test the server processes endpoint."""
    # Mock server data: Each item in this list should behave like a psutil.Process object
    mock_process_instance = MagicMock(spec=psutil.Process)
    mock_process_instance.pid = 1000
    mock_process_instance.info = {'cmdline': ['python', 'main.py', '--host=127.0.0.1', '--port=8000']}
    mock_process_instance.as_dict.return_value = {
        'pid': 1000,
        'create_time': 1625000000.0,  # Example timestamp
        'num_threads': 4,
        'cpu_percent': 2.5,
        'memory_percent': 1.8
    }
    
    mock_servers_list = [mock_process_instance]
    _mock_find_running_servers_on_module.return_value = mock_servers_list
    
    mock_time_val = 1625000000.0 + (2 * 86400) + (3 * 3600) + (30 * 60) + 15  # 2 days, 3 hours, 30 minutes, 15 seconds

    # Determine the expected project_root path that api.admin.py will calculate
    expected_project_root = os.path.abspath('.')

    # Patch sys.path within api.admin and time.time
    with patch("api.admin.time.time", return_value=mock_time_val), \
         patch("api.admin.sys.path", new_callable=MagicMock) as mock_sys_path_in_admin:

        # Ensure that 'project_root not in sys.path' evaluates to True so that append is called.
        mock_sys_path_in_admin.__contains__.return_value = False

        response = client.get("/api/v1/admin/server/processes", headers=AUTH_HEADERS)
        
        assert response.status_code == 200
        data = response.json()
    
        assert data["count"] == 1
        assert len(data["servers"]) == 1
        server = data["servers"][0]
        assert server["pid"] == 1000
        assert server["host"] == "127.0.0.1"
        assert server["port"] == "8000"
        assert server["uptime"] == "2d 3h 30m 15s"
        assert server["cpu_percent"] == 2.5
        assert server["memory_percent"] == 1.8
        
        mock_process_instance.as_dict.assert_called_once_with(attrs=[
            'pid', 'create_time', 'num_threads', 
            'cpu_percent', 'memory_percent'
        ])
        
        # Assert that sys.path.append was called correctly on the mock
        mock_sys_path_in_admin.append.assert_called_once_with(expected_project_root)


def test_admin_stop_server_endpoint():
    """Test the stop server endpoint."""
    pid = 1000
    
    # Mock functions for stopping a server
    with patch("api.admin.psutil.pid_exists", side_effect=[True, False]), \
         patch("api.admin.psutil.Process") as mock_process, \
         patch("api.admin.os.kill") as mock_kill, \
         patch("api.admin.platform.system", return_value="Linux"):
        
        # Mock process
        process_instance = mock_process.return_value
        process_instance.pid = pid
        
        # Call endpoint
        response = client.post(f"/api/v1/admin/server/stop/{pid}", headers=AUTH_HEADERS)
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert data["success"] is True
        assert data["pid"] == pid
        assert "timestamp" in data
        
        # Verify correct signal was sent
        import signal
        mock_kill.assert_called_once_with(pid, signal.SIGTERM)
