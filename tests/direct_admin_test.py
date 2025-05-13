# tests/direct_admin_test.py
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import the app
from main import app

# Create test client
client = TestClient(app)

# Set up basic auth headers for tests
AUTH_HEADERS = {"Authorization": "Bearer test_token"}

# Mock database session
@pytest.fixture
def mock_db():
    """Returns a mocked database session."""
    with patch("dependencies.get_db") as mock:
        mock_db = MagicMock(spec=Session)
        mock.return_value.__next__.return_value = mock_db
        yield mock_db

# Mock authentication for all routes
@pytest.fixture(autouse=True)
def mock_auth():
    """Mock authentication for all endpoints"""
    # Create a mock user
    mock_user = MagicMock()
    mock_user.id = "test-admin-id"
    mock_user.email = "admin@example.com"
    mock_user.username = "admin_user"
    mock_user.is_active = True
    mock_user.is_admin = True
    mock_user.created_at = datetime.now()
    
    # Mock auth dependencies
    with patch("api.auth.get_current_user", return_value=mock_user), \
         patch("api.auth.is_admin", return_value=mock_user), \
         patch("security.get_current_user", return_value=mock_user):
        yield mock_user

# --- Tests ---

def test_admin_stats_endpoint(mock_db, mock_auth):
    """Test the /api/v1/admin/stats endpoint"""
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
    
    # Mock cache stats
    mock_cache_stats = {
        "total_keys": 100,
        "hit_rate": 0.75,
        "memory_usage_mb": 25.5
    }
    
    # Set up all the mocks
    with patch("api.admin.UserRepository", return_value=user_repo_mock), \
         patch("api.admin.ProjectRepository", return_value=project_repo_mock), \
         patch("api.admin.MessageRepository", return_value=message_repo_mock), \
         patch("api.admin.response_cache.get_cache_stats", return_value=mock_cache_stats):
        
        # Call the endpoint with auth headers
        response = client.get("/api/v1/admin/stats", headers=AUTH_HEADERS)
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data matches mock values
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

def test_admin_health_endpoint(mock_db, mock_auth):
    """Test the admin health endpoint"""
    # Mock health data
    mock_health_data = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {"status": "ok", "details": "Connected"},
            "cache": {"status": "ok", "details": "Redis operational"}
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
    
    with patch("api.admin.detailed_status", return_value=MagicMock(model_dump=lambda: mock_health_data)), \
         patch("api.admin.psutil.Process") as mock_process:
        
        # Set up the Process mock
        process_instance = mock_process.return_value
        process_instance.pid = mock_process_info["pid"]
        process_instance.cpu_percent.return_value = mock_process_info["cpu_percent"]
        process_instance.memory_percent.return_value = mock_process_info["memory_percent"]
        process_instance.num_threads.return_value = mock_process_info["threads"]
        process_instance.open_files.return_value = [MagicMock()] * mock_process_info["open_files"]
        process_instance.connections.return_value = [MagicMock()] * mock_process_info["connections"]
        process_instance.create_time.return_value = mock_process_info["create_time"]

        # Call the endpoint with authentication headers
        response = client.get("/api/v1/admin/system/health", headers=AUTH_HEADERS)
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "components" in data
        assert "process_info" in data
        assert data["process_info"]["pid"] == mock_process_info["pid"]
        assert data["process_info"]["cpu_percent"] == mock_process_info["cpu_percent"]

def test_admin_users_endpoint(mock_db, mock_auth):
    """Test the /api/v1/admin/users endpoint"""
    # Create mock users
    mock_users = [
        MagicMock(
            id="user1",
            email="user1@example.com",
            is_active=True,
            is_admin=False,
            username="user1", 
            created_at=datetime.now(),
            projects=[]
        ),
        MagicMock(
            id="user2",
            email="user2@example.com",
            is_active=False,
            is_admin=False,
            username="user2",
            created_at=datetime.now(),
            projects=[MagicMock(), MagicMock()]
        )
    ]
    
    # Configure user repository mock
    user_repo_mock = MagicMock()
    user_repo_mock.get_multi.return_value = mock_users
    
    with patch("api.admin.UserRepository", return_value=user_repo_mock):
        # Call the endpoint with auth headers
        response = client.get("/api/v1/admin/users", headers=AUTH_HEADERS)
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        
        # Verify the response data
        assert len(data) == 2
        assert data[0]["email"] == "user1@example.com"
        assert data[0]["is_active"] is True
        assert data[0]["project_count"] == 0
        
        assert data[1]["email"] == "user2@example.com" 
        assert data[1]["is_active"] is False
        assert data[1]["project_count"] == 2

def test_admin_server_processes_endpoint(mock_auth):
    """Test the server processes endpoint"""
    # Mock server processes data
    mock_servers = [
        MagicMock(
            pid=1000,
            info={
                'cmdline': ['python', 'main.py', '--host=127.0.0.1', '--port=8000']
            }
        )
    ]
    
    with patch("api.admin.find_running_servers", return_value=mock_servers), \
         patch("api.admin.time.time", return_value=1625100000.0), \
         patch("api.admin.psutil.Process") as mock_process:
        
        # Set up process info mock
        process_instance = mock_process.return_value
        process_instance.as_dict.return_value = {
            'pid': 1000,
            'create_time': 1625000000.0,  # 100000 seconds of uptime
            'num_threads': 4,
            'cpu_percent': 2.5,
            'memory_percent': 1.8
        }
        process_instance.pid = 1000
        
        # Call the endpoint
        response = client.get("/api/v1/admin/server/processes", headers=AUTH_HEADERS)
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert data["count"] == 1
        assert len(data["servers"]) == 1
        server = data["servers"][0]
        assert server["pid"] == 1000
        assert server["host"] == "127.0.0.1"
        assert server["port"] == "8000"
        assert "uptime" in server
        assert server["cpu_percent"] == 2.5
        assert server["memory_percent"] == 1.8

def test_admin_cache_invalidation(mock_auth):
    """Test the cache invalidation endpoint"""
    model_id = "openai-gpt-4"
    mock_removed_count = 15
    
    with patch("api.admin.response_cache.invalidate_cache_for_model", return_value=mock_removed_count):
        # Call the endpoint
        response = client.post(f"/api/v1/admin/cache/invalidate/{model_id}", headers=AUTH_HEADERS)
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        
        # Verify the response
        assert data["success"] is True
        assert data["model_id"] == model_id
        assert data["entries_removed"] == mock_removed_count
        assert "timestamp" in data

def test_admin_stop_server_endpoint(mock_auth):
    """Test the server stop endpoint"""
    pid = 1000
    
    # Mock the process functions
    with patch("api.admin.psutil.pid_exists", side_effect=[True, False]), \
         patch("api.admin.psutil.Process") as mock_process, \
         patch("api.admin.os.kill") as mock_kill, \
         patch("api.admin.platform.system", return_value="Linux"):
        
        # Mock process
        process_instance = mock_process.return_value
        process_instance.pid = pid

        # Call the endpoint
        response = client.post(f"/api/v1/admin/server/stop/{pid}", headers=AUTH_HEADERS)
        
        # Check response
        assert response.status_code == 200
        data = response.json()
        
        # Verify data
        assert data["success"] is True
        assert data["pid"] == pid
        assert "timestamp" in data
        
        # Verify the correct kill signal was sent
        import signal
        mock_kill.assert_called_once_with(pid, signal.SIGTERM)

def test_admin_access_control():
    """Test that routes require admin access."""
    # Create a non-admin user
    non_admin_user = MagicMock(is_admin=False)
    
    # Mock authentication to return a non-admin user
    with patch("api.auth.get_current_user", return_value=non_admin_user), \
         patch("security.get_current_user", return_value=non_admin_user):
        
        # Try to access an admin route - should fail with 403 Forbidden
        response = client.get("/api/v1/admin/stats", headers=AUTH_HEADERS)
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]
