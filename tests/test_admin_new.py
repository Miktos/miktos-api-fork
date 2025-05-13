# tests/test_admin_new.py
import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime  # Ensure datetime is imported
import json
from fastapi import HTTPException, status, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import psutil  # Add if not present, for psutil.NoSuchProcess etc.
import signal  # Add if not present, for signal.SIGTERM

# Import the app instance from main.py
from main import app as main_app

# Import our test helpers
from tests.admin_test_helpers import (
    MOCK_ADMIN_USER,
    MOCK_REGULAR_USER,
    MockUser,
    get_admin_headers,
    get_user_headers,
)

# Import the actual dependency being overridden
from security import get_current_user as app_get_current_user_dependency

# Create test client
client = TestClient(main_app)

@pytest.fixture(autouse=True)
def default_admin_user_override(request: pytest.FixtureRequest):
    """
    Overrides `security.get_current_user` to return an admin user by default for all tests in this module,
    unless a test is marked with `skip_default_admin_override`.
    """
    if "skip_default_admin_override" in request.keywords:
        yield
        return

    admin_user_instance = MockUser(**MOCK_ADMIN_USER)
    
    async def _mock_get_current_admin():
        return admin_user_instance

    original_override = main_app.dependency_overrides.get(app_get_current_user_dependency)
    main_app.dependency_overrides[app_get_current_user_dependency] = _mock_get_current_admin
    
    yield
    
    if original_override is not None:
        main_app.dependency_overrides[app_get_current_user_dependency] = original_override
    elif app_get_current_user_dependency in main_app.dependency_overrides:
        del main_app.dependency_overrides[app_get_current_user_dependency]

# Mock dependency for database access
@pytest.fixture
def mock_get_db():
    """Returns a patchable mock for the get_db dependency."""
    with patch("dependencies.get_db") as mock:
        mock_db = MagicMock(spec=Session)
        mock.return_value = iter([mock_db])
        yield mock, mock_db

# --- Test Admin Access Control ---
@pytest.mark.skip_default_admin_override
@pytest.mark.asyncio
async def test_admin_endpoint_requires_admin():
    """Test that admin endpoints reject non-admin users."""
    regular_user_instance = MockUser(**MOCK_REGULAR_USER)

    async def _mock_get_current_regular():
        return regular_user_instance

    original_app_get_user_override = main_app.dependency_overrides.get(app_get_current_user_dependency)
    main_app.dependency_overrides[app_get_current_user_dependency] = _mock_get_current_regular
    
    try:
        response = client.get("/api/v1/admin/stats", headers=get_user_headers())
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Insufficient permissions" in response.json()["detail"]
    finally:
        if original_app_get_user_override is not None:
            main_app.dependency_overrides[app_get_current_user_dependency] = original_app_get_user_override
        elif app_get_current_user_dependency in main_app.dependency_overrides:
            del main_app.dependency_overrides[app_get_current_user_dependency]

# --- Test Admin Stats Endpoint ---
def test_admin_stats_endpoint(mock_get_db):
    """Test the /admin/stats endpoint with mocked repository methods."""
    _, mock_db_session = mock_get_db
    
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

        response = client.get("/api/v1/admin/stats", headers=get_admin_headers())
        
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert data["users"]["total"] == 10
        assert data["projects"]["total"] == 25
        assert data["messages"]["total"] == 500
        assert data["messages"]["last_24h"] == 50
        assert data["cache"] == mock_cache_stats

# --- Test Admin Health Endpoint ---
def test_admin_health_endpoint(mock_get_db):
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
        "pid": 1234,
        "cpu_percent": 5.2,
        "memory_percent": 2.7,
        "threads": 4,
        "open_files": 8,
        "connections": 3,
        "create_time": 1625000000.0
    }
    mock_detailed_status_obj = MagicMock()
    mock_detailed_status_obj.model_dump.return_value = mock_health_data

    with patch("api.admin.detailed_status", return_value=mock_detailed_status_obj) as mock_detailed_status, \
         patch("api.admin.psutil.Process") as mock_psutil_process:
        process_instance = mock_psutil_process.return_value
        process_instance.pid = mock_process_info["pid"]
        process_instance.cpu_percent.return_value = mock_process_info["cpu_percent"]
        process_instance.memory_percent.return_value = mock_process_info["memory_percent"]
        process_instance.num_threads.return_value = mock_process_info["threads"]
        process_instance.open_files.return_value = [MagicMock()] * mock_process_info["open_files"]
        process_instance.connections.return_value = [MagicMock()] * mock_process_info["connections"]
        process_instance.create_time.return_value = mock_process_info["create_time"]

        response = client.get("/api/v1/admin/system/health", headers=get_admin_headers())
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert data["status"] == "healthy"
        assert data["process_info"]["pid"] == 1234

# --- Test Server Processes Endpoint ---
@patch("server_manager.find_running_servers") # Patched where it's re-imported from
@patch("api.admin.psutil")                   # Patched where it's used in api.admin
def test_admin_server_processes_endpoint(
    mock_api_admin_psutil,                 # Corresponds to @patch("api.admin.psutil")
    mock_server_manager_find_running_servers # Corresponds to @patch("server_manager.find_running_servers")
):
    # Configure the psutil mock that api.admin.get_server_processes will see
    mock_api_admin_psutil.NoSuchProcess = psutil.NoSuchProcess
    mock_api_admin_psutil.AccessDenied = psutil.AccessDenied
    mock_api_admin_psutil.ZombieProcess = psutil.ZombieProcess

    # This is the mock for a psutil.Process object instance
    mock_proc_instance = MagicMock(spec=psutil.Process)
    mock_proc_instance.pid = 1234
    mock_proc_instance.info = {
        'pid': 1234,
        'name': 'python',
        'cmdline': ['python', 'main.py', '--host=127.0.0.1', '--port=8000'],
        'create_time': datetime.now().timestamp() - 3600, # Example: 1 hour ago
        'status': psutil.STATUS_RUNNING 
    }
    # Configure what proc.as_dict() should return inside the endpoint
    mock_proc_instance.as_dict.return_value = {
        'pid': 1234,
        'create_time': mock_proc_instance.info['create_time'],
        'num_threads': 2,
        'cpu_percent': 0.5,
        'memory_percent': 10.0
    }

    # When psutil.Process(pid) is called within the endpoint (if it were), it should return our mock_proc_instance
    mock_api_admin_psutil.Process.return_value = mock_proc_instance 

    # Configure find_running_servers (mocked at server_manager.find_running_servers) to return our mock process
    mock_server_manager_find_running_servers.return_value = [mock_proc_instance]

    current_time = mock_proc_instance.info['create_time'] + 7200 # For uptime calculation
    with patch("api.admin.time.time", return_value=current_time):
        response = client.get("/api/v1/admin/server/processes", headers=get_admin_headers())
    
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}. Response: {response.text}"
    data = response.json()

    assert data["count"] == 1, f"Expected count 1, got {data.get('count')}. Full response: {data}"
    assert len(data["servers"]) == 1
    server_details = data["servers"][0]
    assert server_details["pid"] == 1234
    assert server_details["host"] == "127.0.0.1"
    assert server_details["port"] == "8000"
    assert "uptime" in server_details  # Corrected assertion from "uptime_str" to "uptime"
    # Verify that find_running_servers was called
    mock_server_manager_find_running_servers.assert_called_once()
    # Verify that as_dict was called on the process instance returned by find_running_servers
    mock_proc_instance.as_dict.assert_called_once_with(attrs=['pid', 'create_time', 'num_threads', 'cpu_percent', 'memory_percent'])

# --- Test Cache Invalidation Endpoint ---
@patch("api.admin.response_cache.invalidate_cache_for_model")
def test_admin_cache_invalidation(
    mock_invalidate_cache_call
):
    model_id = "openai_gpt-4"
    mock_removed_count = 15
    mock_invalidate_cache_call.return_value = mock_removed_count

    response = client.post(f"/api/v1/admin/cache/invalidate/{model_id}", headers=get_admin_headers())
    
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["success"] is True
    assert data["model_id"] == model_id
    assert data["entries_removed"] == mock_removed_count
    mock_invalidate_cache_call.assert_called_once_with(model_id)

# --- Test Users List Endpoint ---
def test_admin_users_endpoint(mock_get_db):
    _, mock_db_session = mock_get_db
    
    now_time = datetime.now()
    mock_users_data = [
        MagicMock(
            id="user1",
            email="user1@example.com",
            is_active=True,
            is_admin=False,
            created_at=now_time,
            projects=[]
        ),
        MagicMock(
            id="user2",
            email="user2@example.com",
            is_active=False,
            is_admin=False,
            created_at=now_time,
            projects=[MagicMock(), MagicMock()]
        )
    ]
    
    user_repo_mock = MagicMock()
    user_repo_mock.get_multi.return_value = mock_users_data
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock):
        response = client.get("/api/v1/admin/users", headers=get_admin_headers())
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "user1"
        assert data[0]["created_at"] == now_time.isoformat()

# --- Test Server Stop Endpoint ---
@patch("api.admin.platform.system", return_value="Linux")
@patch("api.admin.os.kill")
@patch("api.admin.psutil.Process")
@patch("api.admin.psutil.pid_exists")
def test_admin_stop_server_endpoint(
    mock_pid_exists,
    mock_psutil_process,
    mock_os_kill,
    mock_platform_system
):
    pid_to_stop = 1234
    
    mock_pid_exists.side_effect = [True, False]
    
    mock_proc_instance = MagicMock()
    mock_proc_instance.pid = pid_to_stop
    mock_psutil_process.return_value = mock_proc_instance

    response = client.post(f"/api/v1/admin/server/stop/{pid_to_stop}", headers=get_admin_headers())
    
    assert response.status_code == 200, f"Response: {response.text}"
    data = response.json()
    assert data["success"] is True
    assert data["pid"] == pid_to_stop
    
    mock_os_kill.assert_called_once_with(pid_to_stop, signal.SIGTERM)
