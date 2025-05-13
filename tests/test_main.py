# tests/test_main.py
import pytest
from unittest.mock import patch, MagicMock, call # Import call
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError # Import a relevant exception

# Import the app instance from main.py
from main import app as main_app # Use alias

# Use TestClient with the app instance from main
client = TestClient(main_app)

def test_placeholder(): # Keep existing test
    assert True

# --- New Tests ---

def test_root_endpoint():
    """Test the root '/' endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Miktos AI Orchestration Platform API. Docs at /api/v1/docs"}

def test_root_health_check_endpoint():
    """Test the root '/health' endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

# Test router mounting indirectly by checking a known path from each router
def test_routers_mounted():
    """Check if routers are mounted by testing one path from each."""
    # Check a path from endpoints.router (mounted at /api/v1)
    response_general = client.get("/api/v1/status") # Use the /status endpoint
    assert response_general.status_code != 404, "Endpoints router not mounted correctly"

    # Check a path from auth.router (mounted at /api/v1/auth)
    # ----> FIX: Assuming '/token' is the correct path for POST login <----
    # If your path is different (e.g., /login), adjust this line.
    # Sending form data as required by OAuth2PasswordRequestFormStrict
    response_auth = client.post("/api/v1/auth/token", data={"username": "", "password": ""})
    assert response_auth.status_code != 404, f"Auth router not mounted correctly at /api/v1/auth/token (Status: {response_auth.status_code})"

    # Check a path from projects.router (mounted at /api/v1/projects)
    response_projects = client.get("/api/v1/projects/")
    assert response_projects.status_code != 404, "Projects router not mounted correctly"

# Test the exception handling in create_db_and_tables
@patch('main.Base.metadata.create_all') # Patch where create_all is called
@patch('main.logger.info') # Patch the logger.info method
@patch('main.logger.error') # Patch the logger.error method
def test_create_db_and_tables_exception(mock_logger_error: MagicMock, mock_logger_info: MagicMock, mock_create_all: MagicMock):
    """
    Test the exception handling during initial table creation by checking
    if the error is caught and logged.
    """
    test_error_message = "Simulated DB connection error"
    mock_create_all.side_effect = SQLAlchemyError(test_error_message)

    # Use importlib to reload the main module AFTER patching
    import importlib
    import main # Ensure main is imported initially

    # Reloading main should re-run create_db_and_tables()
    # The exception should be caught within create_db_and_tables
    importlib.reload(main)

    # Verify create_all was called (even though it failed)
    mock_create_all.assert_called_once()
    # Verify the error message was logged by the except block
    mock_logger_info.assert_any_call("Checking/Creating database tables...")
    mock_logger_error.assert_any_call(f"Error creating database tables: {test_error_message}")

    # Reload again without the patch to restore normal state
    mock_create_all.side_effect = None
    try:
        importlib.reload(main)
    except: pass