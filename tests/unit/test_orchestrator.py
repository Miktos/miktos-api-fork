# tests/unit/test_orchestrator.py

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session
from typing import List, Dict, Any, AsyncGenerator

# Import the module/function under test
from core import orchestrator

# Import necessary schemas and models used by the orchestrator
import schemas
from models.database_models import User # Import User model for type hints
from repositories.message_repository import MessageRepository # Import class for patching
from repositories.project_repository import ProjectRepository # Import class for patching

# --- Test Fixtures (Optional but Recommended) ---
# You might define these in conftest.py later for reuse
@pytest.fixture
def mock_db_session() -> MagicMock:
    """Creates a mock SQLAlchemy Session."""
    return MagicMock(spec=Session)

@pytest.fixture
def mock_test_user() -> MagicMock:
    """Creates a mock User object."""
    user = MagicMock(spec=User)
    user.id = "test-user-id-unit"
    user.email = "unit-test@example.com"
    # Add other necessary attributes if orchestrator uses them
    return user

@pytest.fixture
def mock_test_project() -> MagicMock:
    """Creates a mock Project object."""
    project = MagicMock()
    project.id = "unit-test-project-id"
    project.owner_id = "test-user-id-unit" # Match mock_test_user.id
    project.context_notes = "Unit test project context notes."
    project.name = "Unit Test Project"
    return project

@pytest.fixture
def basic_user_messages() -> List[Dict[str, Any]]:
    """Provides a basic list of messages ending with a user message."""
    return [
        {"role": "user", "content": "Hello from unit test"}
    ]

# --- Test Cases ---

@pytest.mark.asyncio
async def test_orchestrator_fetches_project_and_notes(
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator correctly fetches project details and context notes.
    """
    # --- Patch Dependencies ---
    # Patch the repository classes where they are imported in orchestrator.py
    with patch('core.orchestrator.project_repository.ProjectRepository') as MockProjectRepo, \
         patch('core.orchestrator.message_repository.MessageRepository') as MockMessageRepo, \
         patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock) as mock_openai: # Mock the client too

        # Configure mock repository instances
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project

        mock_msg_repo_instance = MockMessageRepo.return_value

        # Configure mock client to return a simple generator
        async def simple_mock_generator(*args, **kwargs):
            yield {"delta": "Test Response"}
            # Don't need more for this specific test focus
        mock_openai.return_value = simple_mock_generator()

        # --- Call Orchestrator ---
        orchestrator_args = {
            "messages": basic_user_messages,
            "model": "openai/gpt-4", # Route to openai
            "project_id": mock_test_project.id,
            "db": mock_db_session,
            "user": mock_test_user
        }
        # Consume the generator fully
        async for _ in orchestrator.process_generation_request(**orchestrator_args):
            pass

        # --- Assertions ---
        # 1. Assert ProjectRepository was instantiated correctly
        MockProjectRepo.assert_called_once_with(db=mock_db_session)
        # 2. Assert get_by_id_for_owner was called correctly
        mock_project_repo_instance.get_by_id_for_owner.assert_called_once_with(
            project_id=mock_test_project.id, owner_id=mock_test_user.id
        )
        # 3. Assert MessageRepository was instantiated correctly
        MockMessageRepo.assert_called_once_with(db=mock_db_session)

@pytest.mark.asyncio
async def test_orchestrator_saves_user_and_assistant_messages(
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator correctly saves the user message and the final assistant message.
    """
    # --- Patch Dependencies ---
    with patch('core.orchestrator.project_repository.ProjectRepository') as MockProjectRepo, \
         patch('core.orchestrator.message_repository.MessageRepository') as MockMessageRepo, \
         patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock) as mock_openai:

        # Configure mocks
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project

        mock_msg_repo_instance = MockMessageRepo.return_value
        # We will assert calls on mock_msg_repo_instance.create

        final_response = "Final OpenAI response."
        async def mock_generator(*args, **kwargs):
            yield {"delta": final_response, "model_name": "gpt-4-mocked"} # Simulate final chunk
            yield {"finish_reason": "stop"} # Simulate end
        mock_openai.return_value = mock_generator()

        # --- Call Orchestrator ---
        orchestrator_args = {
            "messages": basic_user_messages,
            "model": "openai/gpt-4",
            "project_id": mock_test_project.id,
            "db": mock_db_session,
            "user": mock_test_user
        }
        async for _ in orchestrator.process_generation_request(**orchestrator_args):
            pass

        # --- Assertions ---
        # 1. Check that MessageRepository.create was called at least twice
        assert mock_msg_repo_instance.create.call_count >= 2

        # 2. Check the user message save call
        user_save_call_args, user_save_call_kwargs = mock_msg_repo_instance.create.call_args_list[0]
        saved_user_schema = user_save_call_kwargs.get('obj_in') or user_save_call_args[0]
        assert isinstance(saved_user_schema, schemas.MessageCreate)
        assert saved_user_schema.role == schemas.MessageRole.USER
        assert saved_user_schema.content == basic_user_messages[-1]["content"]
        assert saved_user_schema.project_id == mock_test_project.id
        assert saved_user_schema.user_id == mock_test_user.id

        # 3. Check the assistant message save call
        assistant_save_call_args, assistant_save_call_kwargs = mock_msg_repo_instance.create.call_args_list[1]
        saved_asst_schema = assistant_save_call_kwargs.get('obj_in') or assistant_save_call_args[0]
        assert isinstance(saved_asst_schema, schemas.MessageCreate)
        assert saved_asst_schema.role == schemas.MessageRole.ASSISTANT
        assert saved_asst_schema.content == final_response # Check full accumulated content
        assert saved_asst_schema.project_id == mock_test_project.id
        assert saved_asst_schema.user_id == mock_test_user.id
        assert saved_asst_schema.model == "gpt-4-mocked" # Check model name used


@pytest.mark.asyncio
@pytest.mark.parametrize("model_id, patched_client_path, expected_content_part", [
    ("openai/gpt-4o", 'core.orchestrator.openai_client.generate_completion', "OpenAI"),
    ("anthropic/claude-3-sonnet", 'core.orchestrator.claude_client.generate_completion', "Claude"),
    ("google/gemini-1.5-flash", 'core.orchestrator.gemini_client.generate_completion', "Gemini"),
])
async def test_orchestrator_routes_to_correct_client(
    model_id: str,
    patched_client_path: str,
    expected_content_part: str,
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator routes the request to the correct client based on the model ID.
    """
    # --- Patch Dependencies ---
    with patch('core.orchestrator.project_repository.ProjectRepository') as MockProjectRepo, \
         patch('core.orchestrator.message_repository.MessageRepository') as MockMessageRepo, \
         patch(patched_client_path, new_callable=AsyncMock) as mock_client_generate: # Patch the specific client

        # Configure mocks
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project

        mock_msg_repo_instance = MockMessageRepo.return_value # Mock create method

        # Configure the target client mock to return a distinctive response
        async def mock_generator(*args, **kwargs):
            yield {"delta": f"{expected_content_part} response"}
            yield {"finish_reason": "stop"}
        mock_client_generate.return_value = mock_generator()

        # --- Call Orchestrator ---
        orchestrator_args = {
            "messages": basic_user_messages,
            "model": model_id, # Use the parameterized model ID
            "project_id": mock_test_project.id,
            "db": mock_db_session,
            "user": mock_test_user
        }
        results = []
        async for result_chunk in orchestrator.process_generation_request(**orchestrator_args):
             if result_chunk.startswith("data:"):
                 try:
                      data_part = result_chunk.strip().split("data: ")[1]
                      results.append(json.loads(data_part))
                 except Exception: pass # Ignore parsing errors for this test focus

        # --- Assertions ---
        # 1. Assert the correct client was called
        mock_client_generate.assert_awaited_once()

        # 2. Assert the response contains the expected content part
        assert any(expected_content_part in res.get("delta", "") for res in results if "delta" in res)

        # 3. Assert message repo create was called (at least user + assistant)
        assert mock_msg_repo_instance.create.call_count >= 2


@pytest.mark.asyncio
async def test_orchestrator_handles_client_error_stream(
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator yields an error event if the client stream yields an error dictionary,
    and does NOT save the assistant message.
    """
    # --- Patch Dependencies ---
    with patch('core.orchestrator.project_repository.ProjectRepository') as MockProjectRepo, \
         patch('core.orchestrator.message_repository.MessageRepository') as MockMessageRepo, \
         patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock) as mock_openai:

        # Configure mocks
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project

        mock_msg_repo_instance = MockMessageRepo.return_value

        # Configure mock client to yield an error
        error_message = "Client simulation error"
        async def error_generator(*args, **kwargs):
            yield {"delta": "Some initial content"}
            yield {"error": True, "message": error_message, "type": "ClientError"} # Simulate error
        mock_openai.return_value = error_generator()

        # --- Call Orchestrator ---
        orchestrator_args = {
            "messages": basic_user_messages,
            "model": "openai/gpt-4",
            "project_id": mock_test_project.id,
            "db": mock_db_session,
            "user": mock_test_user
        }
        results = []
        async for result_chunk in orchestrator.process_generation_request(**orchestrator_args):
             if result_chunk.startswith("data:"):
                 try:
                      data_part = result_chunk.strip().split("data: ")[1]
                      results.append(json.loads(data_part))
                 except Exception: pass

        # --- Assertions ---
        # 1. Check that an error event was yielded
        assert any(res.get("error") is True for res in results)
        assert any(error_message in res.get("message", "") for res in results if res.get("error"))

        # 2. Check that assistant message was NOT saved (only user message was saved)
        assert mock_msg_repo_instance.create.call_count == 1
        user_save_call_args, user_save_call_kwargs = mock_msg_repo_instance.create.call_args_list[0]
        saved_user_schema = user_save_call_kwargs.get('obj_in') or user_save_call_args[0]
        assert saved_user_schema.role == schemas.MessageRole.USER

# TODO: Add tests for context notes injection logic (OpenAI vs Anthropic/Google)
# TODO: Add test for case where project is not found
# TODO: Add test for case where get_provider_from_model fails