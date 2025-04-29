# tests/unit/test_api_endpoints.py

import pytest
import json
import uuid
from unittest.mock import MagicMock, AsyncMock, patch # AsyncMock for async generator

from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Import the router and models/schemas from the API module
from api import endpoints, models as api_models # Use alias for clarity
from models.database_models import User, Project # Import actual models for spec/return
from core import orchestrator # Import orchestrator to check its path

# --- Test Setup ---

# Create a minimal FastAPI app instance including the router for testing
app = FastAPI()
app.include_router(endpoints.router)

# Mock user data for dependency override
@pytest.fixture
def mock_user_data() -> User:
    user = MagicMock(spec=User)
    user.id = str(uuid.uuid4())
    user.username = "testuser"
    user.email = "test@example.com"
    return user

# Mock DB session for dependency override
@pytest.fixture
def mock_db_session_fixture() -> MagicMock:
    return MagicMock(spec=Session)

# Override dependencies for testing
# Note: These overrides apply to ALL tests using the 'client' fixture via this app instance
def override_get_current_user():
    # Must return the same structure as the actual dependency
    user = MagicMock(spec=User)
    user.id = "test_user_id_override"
    user.username = "override_user"
    user.email = "override@example.com"
    return user

def override_get_db():
    # Return a new mock session for each test if needed, or a shared one
    return MagicMock(spec=Session)

app.dependency_overrides[endpoints.get_current_user] = override_get_current_user
app.dependency_overrides[endpoints.get_db] = override_get_db

# Create the TestClient using the app with overrides
@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

# --- Helper to consume SSE stream ---
async def consume_sse_stream(response) -> list[dict]:
    """Reads SSE events from a TestClient response and parses the JSON data."""
    events = []
    buffer = ""
    async for line_bytes in response.aiter_bytes():
        line = line_bytes.decode('utf-8')
        buffer += line
        # Process buffer line by line (SSE lines end with \n\n)
        while '\n\n' in buffer:
            event_str, buffer = buffer.split('\n\n', 1)
            if event_str.startswith('data: '):
                try:
                    data_json = event_str[len('data: '):]
                    events.append(json.loads(data_json))
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON: {data_json}")
                    # Decide how to handle invalid JSON, maybe append raw string?
                    events.append({"raw_data": data_json}) # Example handling
    return events


# --- Test Cases ---

@pytest.mark.asyncio
@patch('api.endpoints.ProjectRepository') # Patch where it's imported/used
@patch('api.endpoints.orchestrator.process_generation_request') # Patch where it's imported/used
async def test_generate_success(
    mock_process_request: AsyncMock, # Mock for the orchestrator call
    mock_proj_repo_class: MagicMock, # Mock for the ProjectRepository class
    client: TestClient, # TestClient fixture
):
    # Arrange
    # --- Mock ProjectRepository behavior ---
    mock_project_instance = MagicMock(spec=Project) # Simulate found project
    mock_repo_instance = MagicMock()
    mock_repo_instance.get_by_id_for_owner.return_value = mock_project_instance
    mock_proj_repo_class.return_value = mock_repo_instance # Constructor returns our mock instance

    # --- Mock Orchestrator behavior ---
    # Must return an AsyncGenerator yielding SSE formatted strings
    async def mock_sse_generator():
        yield 'data: {"content": "Hello"}\n\n'
        yield 'data: {"content": " World"}\n\n'
        yield 'data: {"final": true, "usage": {"in": 10, "out": 2}}\n\n'

    mock_process_request.return_value = mock_sse_generator()

    # --- Prepare Request Payload ---
    payload = {
        "project_id": str(uuid.uuid4()),
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hi"}],
        "temperature": 0.5,
        "max_tokens": 50
        # system_prompt is optional
    }

    # Act
    response = client.post("/generate", json=payload)

    # Assert
    # 1. Status Code
    assert response.status_code == status.HTTP_200_OK
    assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'

    # 2. Check ProjectRepository was called correctly
    mock_proj_repo_class.assert_called_once() # Check instantiation
    mock_repo_instance.get_by_id_for_owner.assert_called_once()
    # Check args passed to get_by_id_for_owner (user_id comes from override)
    call_args, call_kwargs = mock_repo_instance.get_by_id_for_owner.call_args
    assert call_kwargs.get('project_id') == payload['project_id']
    assert call_kwargs.get('owner_id') == "test_user_id_override" # From dependency override

    # 3. Check Orchestrator was called correctly
    mock_process_request.assert_called_once()
    call_args, call_kwargs = mock_process_request.call_args
    # Check some key args passed to orchestrator
    assert call_kwargs.get('project_id') == payload['project_id']
    assert call_kwargs.get('model') == payload['model']
    assert call_kwargs.get('messages') == payload['messages']
    assert call_kwargs.get('stream') is True # Endpoint forces stream=True
    assert isinstance(call_kwargs.get('user'), MagicMock) # Check user obj passed
    assert call_kwargs.get('user').id == "test_user_id_override"
    assert isinstance(call_kwargs.get('db'), MagicMock) # Check db obj passed

    # 4. Consume and check stream content
    streamed_events = await consume_sse_stream(response)
    assert streamed_events == [
        {"content": "Hello"},
        {"content": " World"},
        {"final": True, "usage": {"in": 10, "out": 2}}
    ]


@pytest.mark.asyncio
@patch('api.endpoints.ProjectRepository') # Patch where it's imported/used
@patch('api.endpoints.orchestrator.process_generation_request') # Patch orchestrator even if not called
async def test_generate_project_not_found(
    mock_process_request: AsyncMock, # Mock for the orchestrator call
    mock_proj_repo_class: MagicMock, # Mock for the ProjectRepository class
    client: TestClient,
):
    # Arrange
    # --- Mock ProjectRepository to return None ---
    mock_repo_instance = MagicMock()
    mock_repo_instance.get_by_id_for_owner.return_value = None # Simulate project not found/owned
    mock_proj_repo_class.return_value = mock_repo_instance

    # --- Prepare Request Payload ---
    payload = {
        "project_id": str(uuid.uuid4()),
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hi"}],
    }

    # Act
    response = client.post("/generate", json=payload)

    # Assert
    # 1. Status Code
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'

    # 2. Check ProjectRepository was called
    mock_proj_repo_class.assert_called_once()
    mock_repo_instance.get_by_id_for_owner.assert_called_once()
    call_args, call_kwargs = mock_repo_instance.get_by_id_for_owner.call_args
    assert call_kwargs.get('project_id') == payload['project_id']
    assert call_kwargs.get('owner_id') == "test_user_id_override"

    # 3. Check Orchestrator was NOT called
    mock_process_request.assert_not_called()

    # 4. Consume and check error stream content
    streamed_events = await consume_sse_stream(response)
    assert len(streamed_events) == 1
    expected_error_data = {
        "error": True,
        "message": "Project not found or not owned by user",
        "type": "NotFoundError"
    }
    assert streamed_events[0] == expected_error_data


@pytest.mark.asyncio
@patch('api.endpoints.ProjectRepository') # Patch where it's imported/used
@patch('api.endpoints.orchestrator.process_generation_request') # Patch where it's imported/used
async def test_generate_orchestrator_exception(
    mock_process_request: AsyncMock, # Mock for the orchestrator call
    mock_proj_repo_class: MagicMock, # Mock for the ProjectRepository class
    client: TestClient,
):
    # Arrange
    # --- Mock ProjectRepository behavior ---
    mock_project_instance = MagicMock(spec=Project) # Simulate found project
    mock_repo_instance = MagicMock()
    mock_repo_instance.get_by_id_for_owner.return_value = mock_project_instance
    mock_proj_repo_class.return_value = mock_repo_instance

    # --- Mock Orchestrator to raise an exception ---
    test_exception = ValueError("Orchestrator failed during setup!")
    mock_process_request.side_effect = test_exception

    # --- Prepare Request Payload ---
    payload = {
        "project_id": str(uuid.uuid4()),
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hi"}],
    }

    # Act
    response = client.post("/generate", json=payload)

    # Assert
    # 1. Status Code - Should be 200 OK because error happens before stream return
    # FastAPI returns StreamingResponse successfully, the content indicates the error.
    # If we wanted a 500, the endpoint itself would need to raise HTTPException before returning StreamingResponse.
    assert response.status_code == status.HTTP_200_OK # Or check if FastAPI changed this behavior
    assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'

    # 2. Check ProjectRepository was called
    mock_proj_repo_class.assert_called_once()
    mock_repo_instance.get_by_id_for_owner.assert_called_once()

    # 3. Check Orchestrator was called (and raised exception)
    mock_process_request.assert_called_once()

    # 4. Consume and check error stream content
    streamed_events = await consume_sse_stream(response)
    assert len(streamed_events) == 1
    expected_error_data = {
        "error": True,
        "message": f"Internal Server Error setting up generation stream: {str(test_exception)}",
        "type": "ValueError" # Type of the exception raised
    }
    assert streamed_events[0] == expected_error_data

# Optional: Add simple tests for health/status if needed, although likely covered elsewhere
def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "timestamp" in response.json()

def test_status_check(client: TestClient):
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0"}