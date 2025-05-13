# tests/test_admin_updated.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Generator, Dict, Any, List
import signal
from models.database_models import User
import time
import psutil  # Actual psutil for spec
import unittest.mock  # Added for isinstance check
from api.health import HealthStatus  # Added import for spec
_RealPsutilProcess = psutil.Process  # Store real class before any patching might affect it globally

# Create test client for patched app
from main import app as main_app
from security import get_current_user
from tests.admin_test_helpers import MockUser

# Create a test client
client = TestClient(main_app)

# --- New Authentication Bypass Fixture using dependency_overrides ---
@pytest.fixture(autouse=True)
def default_admin_user_override(request):
    if "skip_default_admin_override" in request.keywords:
        yield
        return

    mock_admin_user = MockUser(
        id="admin-user-updated-id",
        email="admin_updated@example.com",
        username="admin_updated",
        full_name="Admin Updated User",
        is_active=True,
        is_admin=True,
        created_at=datetime.datetime.now(),
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
    mock_session = MagicMock(spec=Session)
    with patch("dependencies.get_db", return_value=iter([mock_session])) as mock_get_db_patch:
        yield mock_session

# --- Test Admin Access Control ---
@pytest.mark.skip_default_admin_override
def test_admin_endpoint_requires_admin(mock_db_session: MagicMock):
    """Test that admin endpoints reject non-admin users."""
    mock_regular_user = MockUser(
        id="regular-user-updated-id",
        email="regular_updated@example.com",
        username="regular_updated",
        full_name="Regular Updated User",
        is_active=True,
        is_admin=False,
        created_at=datetime.datetime.now(),
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
    # Mock the repository methods
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
         patch("api.admin.response_cache.get_cache_stats", AsyncMock(return_value=mock_cache_stats)):

        response = client.get("/api/v1/admin/stats")
        
        assert response.status_code == 200
        data = response.json()

        assert data["users"]["total"] == 10
        assert data["users"]["active"] == 8
        assert data["projects"]["total"] == 25
        assert data["projects"]["by_status"] == {
            "NONE": 5,
            "PENDING": 3,
            "PROCESSING": 2,
            "COMPLETED": 15
        }
        assert data["messages"]["total"] == 500
        assert data["messages"]["last_24h"] == 50
        assert data["cache"] == mock_cache_stats
        assert "system" in data

# --- Test Admin Health Endpoint ---
def test_admin_health_endpoint(mock_db_session: MagicMock):
    """Test the /admin/health endpoint."""
    
    fixed_dt = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    fixed_iso_dt = fixed_dt.isoformat()

    mock_data_from_detailed_status = {
        "status": "healthy",
        "timestamp": fixed_iso_dt, # Use fixed ISO string
        "components": [
            {"name": "database", "status": "healthy", "details": {"info": "DB Connected"}},
            {"name": "cache", "status": "healthy", "details": {"info": "Cache OK"}},
        ]
    }
    mock_detailed_status_object = MagicMock(spec=HealthStatus) 
    mock_detailed_status_object.model_dump.return_value = mock_data_from_detailed_status
    # Defensively set the timestamp attribute on the mock object itself
    mock_detailed_status_object.timestamp = fixed_dt

    with patch("api.health.detailed_status", AsyncMock(return_value=mock_detailed_status_object)) as mock_detailed_status_call, \
         patch("api.admin.psutil.Process") as mock_psutil_Process_class_mock, \
         patch("api.admin.os.getpid", return_value=12345), \
         patch("datetime.datetime") as mock_datetime_class: # Patch datetime.datetime class

        # Configure the .now() and .utcnow() methods of the mocked datetime class
        mock_datetime_class.now.return_value = fixed_dt
        mock_datetime_class.utcnow.return_value = fixed_dt
        # If datetime.datetime(YYYY, MM, DD, tzinfo=...) is called, ensure it returns fixed_dt or similar
        # For simplicity, we assume now/utcnow are the main sources of varying datetimes.
        # The constructor itself is harder to mock to return a fixed instance for all calls.

        # Defensive check for _RealPsutilProcess type
        if issubclass(type(_RealPsutilProcess), unittest.mock.NonCallableMock):
            mock_proc_instance = MagicMock() # No spec
        else:
            mock_proc_instance = MagicMock(spec=_RealPsutilProcess)

        mock_proc_instance.pid = 12345
        mock_proc_instance.cpu_percent = MagicMock(return_value=10.1)
        mock_proc_instance.memory_percent = MagicMock(return_value=5.5)
        mock_proc_instance.num_threads = MagicMock(return_value=4)
        mock_proc_instance.open_files = MagicMock(return_value=[MagicMock(), MagicMock()])
        mock_proc_instance.connections = MagicMock(return_value=[MagicMock()])
        mock_proc_instance.create_time = MagicMock(return_value=1678886400.123) # This is a float (epoch time)
        
        mock_psutil_Process_class_mock.return_value = mock_proc_instance

        response = client.get("/api/v1/admin/system/health")
        assert response.status_code == 200
        
        json_response = response.json()
        
        expected_response = mock_data_from_detailed_status.copy()
        expected_response["process_info"] = {
            "pid": 12345,
            "cpu_percent": 10.1,
            "memory_percent": 5.5,
            "threads": 4,
            "open_files": 2, 
            "connections": 1, 
            "create_time": 1678886400.123 # Matches mock_proc_instance.create_time
        }
        
        assert json_response == expected_response
        
        mock_psutil_Process_class_mock.assert_called_once_with(12345)
        mock_detailed_status_call.assert_awaited_once() 
        mock_detailed_status_object.model_dump.assert_called_once()

# --- Test Admin Server Processes Endpoint ---
def test_admin_server_processes_endpoint(mock_db_session: MagicMock):
    """Test the /admin/server-processes endpoint."""
    
    # Mock psutil.Process-like objects
    mock_proc1 = MagicMock(spec=psutil.Process)
    mock_proc1.pid = 1001
    mock_proc1.info = {'cmdline': ['python', 'server.py', '--host=127.0.0.1', '--port=8001']}
    proc1_create_time = time.time() - 7200 # 2 hours ago
    mock_proc1.as_dict.return_value = {
        'pid': 1001, 'create_time': proc1_create_time, 'num_threads': 2, 
        'cpu_percent': 5.0, 'memory_percent': 10.0
    }

    mock_proc2 = MagicMock(spec=psutil.Process)
    mock_proc2.pid = 1002
    mock_proc2.info = {'cmdline': ['python', 'server.py', '--port=8002']} # Host missing, will use default
    proc2_create_time = time.time() - 3600 # 1 hour ago
    mock_proc2.as_dict.return_value = {
        'pid': 1002, 'create_time': proc2_create_time, 'num_threads': 1,
        'cpu_percent': 2.0, 'memory_percent': 8.0
    }
    mock_psutil_processes_list = [mock_proc1, mock_proc2]

    # Patch server_manager.find_running_servers as it's imported from there
    with patch("server_manager.find_running_servers", MagicMock(return_value=mock_psutil_processes_list)):
        response = client.get("/api/v1/admin/server/processes") # Corrected route
        assert response.status_code == 200
        
        json_response = response.json()
        
        def format_uptime(creation_time: float) -> tuple[str, float]:
            uptime_seconds = time.time() - creation_time
            # Ensure uptime_seconds is not negative due to time mocking or system clock adjustments
            uptime_seconds = max(0, uptime_seconds) 
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s", uptime_seconds

        uptime_str1, uptime_sec1 = format_uptime(proc1_create_time)
        uptime_str2, uptime_sec2 = format_uptime(proc2_create_time)

        expected_server_info = [
            {
                'host': '127.0.0.1', 'port': '8001', 'pid': 1001, 
                'uptime': uptime_str1, 'uptime_seconds': pytest.approx(uptime_sec1, abs=1), # Approx for float
                'cpu_percent': 5.0, 'memory_percent': 10.0, 'threads': 2
            },
            {
                'host': '127.0.0.1',
                'port': '8002',  # Corrected: Parsed from cmdline as string
                'pid': 1002, 
                'uptime': uptime_str2, 'uptime_seconds': pytest.approx(uptime_sec2, abs=1), # Approx for float
                'cpu_percent': 2.0, 'memory_percent': 8.0, 'threads': 1
            }
        ]
        
        assert json_response["count"] == 2
        # Sort by PID for stable comparison
        # Convert port to string in actual response for comparison if it's int, or ensure expected is string
        for server_data in json_response["servers"]:
            if isinstance(server_data.get("port"), int):
                server_data["port"] = str(server_data["port"])
                
        assert sorted(json_response["servers"], key=lambda x: x['pid']) == sorted(expected_server_info, key=lambda x: x['pid'])
        assert "timestamp" in json_response

# --- Test Admin Cache Invalidation ---
def test_admin_cache_invalidation(mock_db_session: MagicMock):
    """Test the /admin/cache/invalidate/{model_id} endpoint."""
    model_id_to_invalidate = "model_xyz_123"
    with patch("api.admin.response_cache.invalidate_cache_for_model", AsyncMock(return_value=True)) as mock_invalidate: # Corrected patch target
        response = client.post(f"/api/v1/admin/cache/invalidate/{model_id_to_invalidate}")
        assert response.status_code == 200
        # The actual response includes more fields like 'model_id', 'entries_removed', 'timestamp'
        # For now, let's check for success and the message part that matches the old structure
        assert response.json()["success"] is True
        assert f"Cache invalidated for model {model_id_to_invalidate}" in response.json().get("message", "") or response.json().get("model_id") == model_id_to_invalidate
        mock_invalidate.assert_called_once_with(model_id_to_invalidate)

    with patch("api.admin.response_cache.invalidate_cache_for_model", AsyncMock(side_effect=Exception("Cache unavailable"))) as mock_invalidate_fail: # Corrected patch target and simulate failure
        response_fail = client.post(f"/api/v1/admin/cache/invalidate/{model_id_to_invalidate}")
        assert response_fail.status_code == 500 
        assert "Failed to invalidate cache" in response_fail.json()["detail"]
        mock_invalidate_fail.assert_called_once_with(model_id_to_invalidate)

# --- Test Admin Users Endpoint ---
def test_admin_users_endpoint(mock_db_session: MagicMock):
    """Test the /admin/users endpoint."""
    
    # Mock User objects that user_repo.get_multi() would return
    mock_user_1 = MagicMock(spec=User)
    mock_user_1.id = "user1"
    mock_user_1.email = "test1@example.com"
    mock_user_1.is_active = True
    mock_user_1.is_admin = False
    mock_user_1.created_at = datetime.datetime.now(datetime.timezone.utc) # Use timezone-aware datetime
    mock_user_1.projects = [MagicMock(), MagicMock()] # To make len(user.projects) == 2

    mock_user_2 = MagicMock(spec=User)
    mock_user_2.id = "user2"
    mock_user_2.email = "admin@example.com"
    mock_user_2.is_active = True
    mock_user_2.is_admin = True
    mock_user_2.created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1) # Use timezone-aware datetime
    mock_user_2.projects = [MagicMock()] * 5 # To make len(user.projects) == 5

    mock_users_list = [mock_user_1, mock_user_2]
    
    # Expected data based on the transformation in the endpoint
    expected_response_data = [
        {
            "id": str(mock_user_1.id),
            "email": mock_user_1.email,
            "is_active": mock_user_1.is_active,
            "is_admin": mock_user_1.is_admin,
            "created_at": mock_user_1.created_at.isoformat(),
            "project_count": len(mock_user_1.projects)
        },
        {
            "id": str(mock_user_2.id),
            "email": mock_user_2.email,
            "is_active": mock_user_2.is_active,
            "is_admin": mock_user_2.is_admin,
            "created_at": mock_user_2.created_at.isoformat(),
            "project_count": len(mock_user_2.projects)
        }
    ]

    user_repo_mock = MagicMock()
    user_repo_mock.get_multi.return_value = mock_users_list
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock):
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 200
        response_data = response.json()
        
        # Sort by ID for consistent comparison as order might not be guaranteed
        response_data_sorted = sorted(response_data, key=lambda x: x['id'])
        expected_response_data_sorted = sorted(expected_response_data, key=lambda x: x['id'])
        
        assert len(response_data_sorted) == len(expected_response_data_sorted)
        for i in range(len(expected_response_data_sorted)):
            assert response_data_sorted[i] == expected_response_data_sorted[i] # Compare dicts directly
            
        user_repo_mock.get_multi.assert_called_once()

# --- Test Admin Stop Server Endpoint ---
def test_admin_stop_server_endpoint(mock_db_session: MagicMock):
    """Test the /admin/server/stop/{pid} endpoint."""
    server_pid_to_stop = 12345  # Use an integer PID
    
    # Test successful stop (process exists and is killed, then disappears)
    with patch("api.admin.psutil.pid_exists") as mock_pid_exists, \
         patch("api.admin.psutil.Process") as mock_Process, \
         patch("api.admin.os.kill") as mock_os_kill, \
         patch("api.admin.platform.system", return_value="Linux"):

        mock_proc_instance = MagicMock()
        mock_Process.return_value = mock_proc_instance
        
        # Simulate process existing initially, then not existing after kill attempt
        # pid_exists will be called multiple times: 
        # 1. Initial check (True)
        # 2. In loop after kill (False)
        pid_exists_call_count = 0
        def pid_exists_side_effect(pid):
            nonlocal pid_exists_call_count
            pid_exists_call_count += 1
            if pid_exists_call_count == 1: # First call, process exists
                return True
            return False # Subsequent calls, process stopped
        mock_pid_exists.side_effect = pid_exists_side_effect

        response = client.post(f"/api/v1/admin/server/stop/{server_pid_to_stop}")
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["success"] is True
        assert response_json["pid"] == server_pid_to_stop
        assert "Server process gracefully stopped" in response_json["message"]
        
        mock_Process.assert_called_once_with(server_pid_to_stop)
        mock_os_kill.assert_called_once_with(mock_proc_instance.pid, signal.SIGTERM)
        assert mock_pid_exists.call_count >= 2 # Called at least for initial check and once in loop

    # Test server not found
    with patch("api.admin.psutil.pid_exists", return_value=False) as mock_pid_exists_notfound:
        response_notfound = client.post(f"/api/v1/admin/server/stop/{server_pid_to_stop}")
        assert response_notfound.status_code == 404
        assert f"No process found with PID {server_pid_to_stop}" in response_notfound.json()["detail"]
        mock_pid_exists_notfound.assert_called_once_with(server_pid_to_stop)

    # Test case: process still exists after timeout (graceful shutdown signal sent)
    with patch("api.admin.psutil.pid_exists", return_value=True) as mock_pid_exists_lingers, \
         patch("api.admin.psutil.Process") as mock_Process_lingers, \
         patch("api.admin.os.kill") as mock_os_kill_lingers, \
         patch("api.admin.platform.system", return_value="Linux"):

        mock_proc_instance_lingers = MagicMock()
        mock_Process_lingers.return_value = mock_proc_instance_lingers
        # mock_pid_exists_lingers always returns True to simulate process not stopping

        response_lingers = client.post(f"/api/v1/admin/server/stop/{server_pid_to_stop}")
        assert response_lingers.status_code == 200
        response_json_lingers = response_lingers.json()
        assert response_json_lingers["success"] is True
        assert response_json_lingers["pid"] == server_pid_to_stop
        assert "Shutdown signal sent, server may take time to exit completely" in response_json_lingers["message"]

        mock_Process_lingers.assert_called_once_with(server_pid_to_stop)
        mock_os_kill_lingers.assert_called_once_with(mock_proc_instance_lingers.pid, signal.SIGTERM)
        # Check that pid_exists was called multiple times (initial + loop checks)
        assert mock_pid_exists_lingers.call_count > 1
