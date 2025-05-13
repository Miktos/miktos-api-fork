# tests/test_admin_fixed_final.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Generator

# Import the app instance from main.py
from main import app as main_app
from security import get_current_user
from tests.admin_test_helpers import MockUser

# Create test client using the app
client = TestClient(main_app)

# --- New Authentication Bypass Fixture using dependency_overrides ---
@pytest.fixture(autouse=True)
def default_admin_user_override(request):
    if "skip_default_admin_override" in request.keywords:
        yield
        return

    mock_admin_user = MockUser(
        id="admin-user-ff-id",
        email="admin_ff@example.com",
        username="admin_ff",
        full_name="Admin FixedFinal User",
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

# Mock database dependency
@pytest.fixture
def mock_db_session() -> Generator[MagicMock, None, None]:
    """Mock the database session dependency."""
    mock_session = MagicMock(spec=Session)
    with patch("dependencies.get_db", return_value=iter([mock_session])) as mock_get_db_patch:
        yield mock_session

# --- Test Admin Access Control ---
@pytest.mark.skip_default_admin_override
def test_admin_endpoint_requires_admin(mock_db_session: MagicMock):
    """Test that admin endpoints reject non-admin users."""
    mock_regular_user = MockUser(
        id="regular-user-ff-id",
        email="regular_ff@example.com",
        username="regular_ff",
        full_name="Regular FixedFinal User",
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
        if get_current_user in main_app.dependency_overrides:
            del main_app.dependency_overrides[get_current_user]
    
    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions. Admin access required."

# --- Test Admin Stats Endpoint ---
def test_admin_stats_endpoint(mock_db_session: MagicMock):
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
        "total_keys": 100, "hit_rate": 0.75, "memory_usage_mb": 25.5
    }
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock), \
         patch("api.admin.ProjectRepository", return_value=project_repo_mock), \
         patch("api.admin.MessageRepository", return_value=message_repo_mock), \
         patch("api.admin.response_cache.get_cache_stats", AsyncMock(return_value=mock_cache_stats)):
        
        response = client.get("/api/v1/admin/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["users"]["total"] == 10
        assert data["users"]["active"] == 8
        assert data["projects"]["total"] == 25
        assert data["projects"]["by_status"] == {
            "NONE": 5, "PENDING": 3, "PROCESSING": 2, "COMPLETED": 15
        }
        assert data["messages"]["total"] == 500
        assert data["messages"]["last_24h"] == 50
        assert data["cache"] == mock_cache_stats
        assert "system" in data

# --- Test Admin Health Endpoint ---
def test_admin_health_endpoint(mock_db_session: MagicMock):
    """Test the /admin/system/health endpoint for admin users."""
    mock_health_data = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {"status": "ok", "details": "Connected"},
            "cache": {"status": "ok", "details": "Redis operational"}
        },
        "version": "0.2.0"
    }
    
    mock_process_info = {
        "pid": 1234, "cpu_percent": 5.2, "memory_percent": 2.7,
        "threads": 4, "open_files": 8, "connections": 3,
        "create_time": 1625000000.0
    }
    
    mock_detailed_status_obj = MagicMock()
    mock_detailed_status_obj.model_dump.return_value = mock_health_data

    with patch("api.admin.detailed_status", AsyncMock(return_value=mock_detailed_status_obj)), \
         patch("api.admin.psutil.Process") as mock_process:
        
        process_instance = mock_process.return_value
        process_instance.pid = mock_process_info["pid"]
        process_instance.cpu_percent.return_value = mock_process_info["cpu_percent"]
        process_instance.memory_percent.return_value = mock_process_info["memory_percent"]
        process_instance.num_threads.return_value = mock_process_info["threads"]
        process_instance.open_files.return_value = [MagicMock()] * mock_process_info["open_files"]
        process_instance.connections.return_value = [MagicMock()] * mock_process_info["connections"]
        process_instance.create_time.return_value = mock_process_info["create_time"]

        response = client.get("/api/v1/admin/system/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "components" in data
        assert "process_info" in data
        assert data["process_info"]["pid"] == mock_process_info["pid"]
        assert data["process_info"]["cpu_percent"] == mock_process_info["cpu_percent"]

# --- Test Server Processes Endpoint ---
def test_admin_server_processes_endpoint():
    """Test the /admin/server/processes endpoint."""
    mock_proc_instance = MagicMock()
    mock_proc_instance.pid = 1000
    mock_proc_instance.info = {'cmdline': ['python', 'main.py', '--host=127.0.0.1', '--port=8000']}
    mock_proc_instance.as_dict.return_value = {
        'pid': 1000, 'create_time': 1625000000.0, 
        'num_threads': 4, 'cpu_percent': 2.5, 'memory_percent': 1.8
    }
    mock_servers_data = [mock_proc_instance]
    
    with patch("server_manager.find_running_servers", return_value=mock_servers_data), \
         patch("api.admin.time.time", return_value=1625100000.0):
        
        response = client.get("/api/v1/admin/server/processes")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 1
        assert len(data["servers"]) == 1
        server = data["servers"][0]
        assert server["pid"] == 1000
        assert server["host"] == "127.0.0.1"
        assert server["port"] == "8000"
        assert "uptime" in server
        assert server["cpu_percent"] == 2.5
        assert server["memory_percent"] == 1.8

# --- Test Cache Invalidation Endpoint ---
def test_admin_cache_invalidation():
    """Test the /admin/cache/invalidate endpoint for a specific model."""
    model_id = "openai/gpt-4"
    mock_removed_count = 15
    
    with patch("api.admin.response_cache.invalidate_cache_for_model", AsyncMock(return_value=mock_removed_count)):
        response = client.post(f"/api/v1/admin/cache/invalidate/{model_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["model_id"] == model_id
        assert data["entries_removed"] == mock_removed_count
        assert "timestamp" in data

# --- Test Users List Endpoint ---
def test_admin_users_endpoint(mock_db_session: MagicMock):
    """Test the /admin/users endpoint."""
    mock_users_data = [
        MagicMock(id="user1-ff-id", email="user1_ff@example.com", is_active=True, is_admin=False, created_at=datetime.now(), projects=[]),
        MagicMock(id="user2-ff-id", email="user2_ff@example.com", is_active=False, is_admin=False, created_at=datetime.now(), projects=[MagicMock(), MagicMock()])
    ]
    
    user_repo_mock = MagicMock()
    user_repo_mock.get_multi.return_value = mock_users_data
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock):
        response = client.get("/api/v1/admin/users")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        assert data[0]["email"] == "user1_ff@example.com"
        assert data[0]["is_active"] is True
        assert data[0]["project_count"] == 0
        
        assert data[1]["email"] == "user2_ff@example.com"
        assert data[1]["is_active"] is False
        assert data[1]["project_count"] == 2

# --- Test Server Stop Endpoint ---
def test_admin_stop_server_endpoint():
    """Test the /admin/server/stop/{pid} endpoint."""
    pid_to_stop = 12345
    
    with patch("api.admin.psutil.pid_exists", side_effect=[True, False]), \
         patch("api.admin.psutil.Process") as mock_psutil_process, \
         patch("api.admin.os.kill") as mock_os_kill, \
         patch("api.admin.platform.system", return_value="Linux"):
        
        mock_proc_instance = mock_psutil_process.return_value
        mock_proc_instance.pid = pid_to_stop

        response = client.post(f"/api/v1/admin/server/stop/{pid_to_stop}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["pid"] == pid_to_stop
        assert "timestamp" in data
        
        import signal
        mock_os_kill.assert_called_once_with(pid_to_stop, signal.SIGTERM)
