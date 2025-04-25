# tests/integration/test_generate_endpoint.py
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi import Depends # Keep Depends if overriding specific dependencies directly in test
from fastapi.testclient import TestClient

# Import the app from main.py for dependency overrides
from main import app
# Import the specific dependency function to override
from api.auth import get_current_user # Assuming this is the correct path
from models.database_models import User, Project # Import actual models for type hints if desired

# NOTE: Avoid importing endpoint functions directly; test via the client

# Define a dummy user consistent with the User model structure
# We use this *instead* of the authenticated_client fixture because we manually override get_current_user
# This approach is useful when testing specific dependency interactions or when you don't need
# the full login flow overhead for every test in this file.
MOCK_USER = User(
    id="test-user-id-integration",
    email="integration@example.com",
    username="integration_user",
    hashed_password="not_needed_for_this_test" # Provide a dummy value if required by model instantiation
    # Add other fields with default or dummy values if your User model requires them
)

# Define a dummy project consistent with the Project model structure
MOCK_PROJECT = Project(
    id="test-project-id-integration",
    owner_id=MOCK_USER.id,
    name="Integration Test Project",
    context_notes="Integration test notes"
    # Add other fields with default or dummy values if your Project model requires them
    # repository_url=None,
    # context_status="NONE" # Use the enum value if you import ContextStatus
)


def test_generate_endpoint_structure(client: TestClient): # Use the 'client' fixture from conftest
    """
    Test the /api/v1/generate endpoint structure, mocking dependencies.
    Verifies request handling, dependency mocking, and response format.
    Uses manual dependency override for get_current_user.
    """
    # --- Mock Data ---
    mock_user = MOCK_USER # Use the predefined mock user
    mock_project = MOCK_PROJECT # Use the predefined mock project

    # Define the expected sequence of SSE events as strings
    mock_orchestrator_result = [
        f'data: {json.dumps({"delta": "Integration test ", "type": "content_block_delta"})}\n\n',
        f'data: {json.dumps({"delta": "response.", "type": "content_block_delta"})}\n\n',
        f'data: {json.dumps({"finish_reason": "stop", "type": "message_stop"})}\n\n',
    ]

    # --- Patching Targets ---
    # Define the string paths to the objects to be patched within the tested module's scope
    # IMPORTANT: Ensure these paths match where the objects are *used* in api/endpoints.py
    # Assuming endpoints.py has 'from core.orchestrator import orchestrator'
    orchestrator_patch_target = 'api.endpoints.orchestrator.process_generation_request'
    # Assuming endpoints.py has 'from repositories.project_repository import ProjectRepository'
    # and uses it like 'repo = ProjectRepository(db)'
    project_repo_patch_target = 'api.endpoints.ProjectRepository'
    # Get the actual dependency function object for overriding
    user_dependency_target = get_current_user

    # --- Test Setup with Patching & Dependency Override ---
    # Override the get_current_user dependency to return our mock user
    app.dependency_overrides[user_dependency_target] = lambda: mock_user
    print("\nIntegration Test: Overrode get_current_user dependency.")

    try:
        # Use context managers for patching other dependencies
        with patch(orchestrator_patch_target) as mock_process_request, \
             patch(project_repo_patch_target) as MockProjectRepo: # Patch the class

            # --- Configure Mocks ---
            # 1. Configure the mock ProjectRepository *instance* that will be created
            #    when ProjectRepository(db) is called inside the endpoint.
            mock_project_repo_instance = MockProjectRepo.return_value
            # Set the return value for the method called by the endpoint
            mock_project_repo_instance.get_by_id_for_owner.return_value = mock_project
            print("Integration Test: Configured mock ProjectRepository instance.")

            # 2. Configure the mock orchestrator function's return value
            # It must return an object that can be awaited and iterated asynchronously (async generator)
            async def mock_orchestrator_generator(*args, **kwargs):
                print("Integration Test: Mock orchestrator generator called.")
                for event in mock_orchestrator_result:
                    # print(f"Integration Test: Mock orchestrator yielding: {event.strip()}") # Optional detailed log
                    yield event
                print("Integration Test: Mock orchestrator generator finished.")
            # Assign the *result* of calling the async generator function
            mock_process_request.return_value = mock_orchestrator_generator()
            print("Integration Test: Configured mock orchestrator.")

            # --- Prepare Request Data ---
            # Ensure this matches the GenerateRequest schema used in api/endpoints.py
            request_data = {
                "model": "mock/test-model", # Use a distinct name for testing
                "messages": [{"role": "user", "content": "Integration test hello"}],
                "project_id": mock_project.id,
                # Optional fields if defined in schema:
                # "stream": True, # Endpoint likely forces this
                # "temperature": 0.5,
                # "max_tokens": 100,
                # "system_prompt": "Test system prompt" # Note: orchestrator might ignore this now
            }

            # --- Make API Request using the Test Client ---
            print(f"Integration Test: Calling POST /api/v1/generate with data: {request_data}")
            # *** THE FIX IS HERE: Use the 'client' fixture passed into the function ***
            response = client.post(
                "/api/v1/generate", # Ensure this matches the actual endpoint path in api/endpoints.py
                json=request_data
                # Note: Authentication header is NOT needed here because we manually overrode get_current_user
            )
            print(f"Integration Test: Response Status Code: {response.status_code}")
            # print(f"Integration Test: Response Text: {response.text}") # Can be noisy

            # --- Assertions ---
            # 1. Check response status and headers
            assert response.status_code == 200, f"Expected status 200, got {response.status_code}. Response: {response.text}"
            assert response.headers['content-type'] == 'text/event-stream; charset=utf-8'

            # 2. Check the streamed response text matches the mock generator output
            expected_text = "".join(mock_orchestrator_result)
            assert response.text == expected_text, f"Expected text '{expected_text}', got '{response.text}'"

            # 3. Check that mocks were interacted with as expected
            # Verify ProjectRepository class was instantiated (implicitly checks db session was passed)
            MockProjectRepo.assert_called_once()
            # Verify the method on the instance was called correctly by the endpoint logic
            mock_project_repo_instance.get_by_id_for_owner.assert_called_once_with(
                project_id=mock_project.id, owner_id=mock_user.id
            )

            # Verify the orchestrator function was called
            mock_process_request.assert_called_once()
            # Optionally, assert specific arguments passed to the orchestrator
            call_args, call_kwargs = mock_process_request.call_args
            assert call_kwargs.get("project_id") == mock_project.id
            assert call_kwargs.get("model") == request_data["model"]
            # Make sure the user object passed is the one we provided via override
            assert call_kwargs.get("user") is mock_user
            assert call_kwargs.get("stream") is True # Endpoint should force stream=True
            # Check if db session was passed (it's injected by FastAPI into the endpoint)
            assert "db" in call_kwargs
            # Assert messages match (or check specific content)
            assert call_kwargs.get("messages") == request_data["messages"]

    finally:
        # --- Cleanup ---
        # IMPORTANT: Only remove the specific dependency override added by this test
        if user_dependency_target in app.dependency_overrides:
            del app.dependency_overrides[user_dependency_target]
            print("Integration Test: get_current_user dependency override removed.")
        else:
             # Indent this line correctly
             print("Integration Test: get_current_user dependency override was already removed (unexpected).") 