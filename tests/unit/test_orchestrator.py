# tests/unit/test_orchestrator.py

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock, ANY # Import AsyncMock
from sqlalchemy.orm import Session
from typing import List, Dict, Any, AsyncGenerator

# Import the module/function under test
from core import orchestrator
# Assuming the main function is process_generation_request
from core.orchestrator import process_generation_request

# Import necessary schemas and models used by the orchestrator
# Ensure these imports are valid in your project structure
import schemas
from models.database_models import User, Project, Message, ContextStatus # Added Message, ContextStatus
# Import repository CLASSES for patching targets (but we patch where they are USED)
from repositories.message_repository import MessageRepository
from repositories.project_repository import ProjectRepository

# --- Test Fixtures ---
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
    return user

@pytest.fixture
def mock_test_project() -> MagicMock:
    """Creates a mock Project object."""
    project = MagicMock(spec=Project)
    project.id = "unit-test-project-id"
    project.owner_id = "test-user-id-unit"
    project.context_notes = "Unit test project context notes."
    project.name = "Unit Test Project"
    project.context_status = ContextStatus.READY
    return project

@pytest.fixture
def basic_user_messages() -> List[Dict[str, Any]]:
    """Provides a basic list of messages ending with a user message."""
    return [
        {"role": "user", "content": "Hello from unit test"}
    ]

# Helper async generator for mock LLM responses
async def mock_llm_client_stream(content_chunks: List[Dict[str, Any]], finish_reason: str = "stop"):
    """ Mocks the dict stream expected FROM the LLM clients """
    for chunk_dict in content_chunks:
        yield chunk_dict
    yield {"finish_reason": finish_reason}


# --- Test Cases ---

@pytest.mark.asyncio
# *** CORRECTED PATCH TARGETS ***
@patch('core.orchestrator.project_repository.ProjectRepository')
@patch('core.orchestrator.message_repository.MessageRepository')
@patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock)
async def test_orchestrator_fetches_project_and_notes(
    mock_openai_gen, mock_msg_repo_cls, mock_proj_repo_cls, # Order matches patch decorators bottom-up
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator correctly fetches project details and context notes.
    """
    # Configure mock repository instances
    mock_project_repo_instance = mock_proj_repo_cls.return_value
    mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project
    mock_msg_repo_instance = mock_msg_repo_cls.return_value

    # Configure mock client
    mock_openai_gen.return_value = mock_llm_client_stream([{"delta": "Test Response"}])

    # --- Call Orchestrator ---
    orchestrator_args = {
        "messages": basic_user_messages, "model": "openai/gpt-4", "project_id": mock_test_project.id,
        "db": mock_db_session, "user": mock_test_user, "stream": True, "temperature": None,
        "max_tokens": None, "system_prompt": None,
    }
    async for _ in orchestrator.process_generation_request(**orchestrator_args): pass

    # --- Assertions ---
    mock_proj_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_project_repo_instance.get_by_id_for_owner.assert_called_once_with(
        project_id=mock_test_project.id, owner_id=mock_test_user.id
    )
    mock_msg_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_openai_gen.assert_awaited_once()
    mock_msg_repo_instance.create.assert_called()


@pytest.mark.asyncio
# *** CORRECTED PATCH TARGETS ***
@patch('core.orchestrator.project_repository.ProjectRepository')
@patch('core.orchestrator.message_repository.MessageRepository')
@patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock)
async def test_orchestrator_saves_user_and_assistant_messages(
    mock_openai_gen, mock_msg_repo_cls, mock_proj_repo_cls,
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator correctly saves the user message and the final assistant message.
    """
    # Configure mocks
    mock_project_repo_instance = mock_proj_repo_cls.return_value
    mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project
    mock_msg_repo_instance = mock_msg_repo_cls.return_value

    final_response = "Final OpenAI response."
    mock_openai_gen.return_value = mock_llm_client_stream(
        [{"delta": final_response, "model_name": "gpt-4-mocked"}], finish_reason="stop"
    )

    # --- Call Orchestrator ---
    orchestrator_args = {
        "messages": basic_user_messages, "model": "openai/gpt-4", "project_id": mock_test_project.id,
        "db": mock_db_session, "user": mock_test_user, "stream": True, "temperature": None,
        "max_tokens": None, "system_prompt": None,
    }
    async for _ in orchestrator.process_generation_request(**orchestrator_args): pass

    # --- Assertions ---
    assert mock_msg_repo_instance.create.call_count >= 2, \
        f"Expected create count >= 2, got {mock_msg_repo_instance.create.call_count}"

    if mock_msg_repo_instance.create.call_count >= 2:
        user_save_call_args, user_save_call_kwargs = mock_msg_repo_instance.create.call_args_list[0]
        saved_user_schema = user_save_call_kwargs.get('obj_in')
        assert isinstance(saved_user_schema, schemas.MessageCreate)
        assert saved_user_schema.role == schemas.MessageRole.USER
        assert saved_user_schema.content == basic_user_messages[-1]["content"]
        assert saved_user_schema.project_id == mock_test_project.id
        assert saved_user_schema.user_id == mock_test_user.id

        assistant_save_call_args, assistant_save_call_kwargs = mock_msg_repo_instance.create.call_args_list[1]
        saved_asst_schema = assistant_save_call_kwargs.get('obj_in')
        assert isinstance(saved_asst_schema, schemas.MessageCreate)
        assert saved_asst_schema.role == schemas.MessageRole.ASSISTANT
        assert saved_asst_schema.content == final_response
        assert saved_asst_schema.project_id == mock_test_project.id
        assert saved_asst_schema.user_id == mock_test_user.id
        assert saved_asst_schema.model == "gpt-4-mocked"


@pytest.mark.asyncio
@pytest.mark.parametrize("model_id, patched_client_path, expected_client_id_part, expected_content_part", [
    ("openai/gpt-4o", 'core.orchestrator.openai_client.generate_completion', "gpt-4o", "OpenAI"),
    ("anthropic/claude-3-sonnet", 'core.orchestrator.claude_client.generate_completion', "claude-3-sonnet", "Claude"),
    ("google/gemini-1.5-flash", 'core.orchestrator.gemini_client.generate_completion', "gemini-1.5-flash", "Gemini"),
])
# *** CORRECTED PATCH TARGETS ***
@patch('core.orchestrator.project_repository.ProjectRepository')
@patch('core.orchestrator.message_repository.MessageRepository')
async def test_orchestrator_routes_to_correct_client(
    mock_msg_repo_cls, mock_proj_repo_cls, # Correct order
    model_id: str,
    patched_client_path: str,
    expected_client_id_part: str,
    expected_content_part: str,
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator routes the request to the correct client based on the model ID.
    """
    # Configure mocks
    mock_project_repo_instance = mock_proj_repo_cls.return_value
    mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project
    mock_msg_repo_instance = mock_msg_repo_cls.return_value

    # Patch the specific client within the test function
    with patch(patched_client_path, new_callable=AsyncMock) as mock_client_generate:
        # Configure the target client mock
        mock_client_generate.return_value = mock_llm_client_stream(
            [{"delta": f"{expected_content_part} response"}]
        )

        # --- Call Orchestrator ---
        orchestrator_args = {
            "messages": basic_user_messages, "model": model_id, "project_id": mock_test_project.id,
            "db": mock_db_session, "user": mock_test_user, "stream": True, "temperature": None,
            "max_tokens": None, "system_prompt": None,
        }
        results_json = []
        async for result_chunk in orchestrator.process_generation_request(**orchestrator_args):
             if result_chunk.startswith("data:"):
                 try:
                      data_part = result_chunk.strip().split("data: ")[1]
                      results_json.append(json.loads(data_part))
                 except Exception: pass

        # --- Assertions ---
        mock_client_generate.assert_awaited_once()
        call_args, call_kwargs = mock_client_generate.call_args
        assert call_kwargs.get("model") == expected_client_id_part # Check specific model name used by client

        assert any(expected_content_part in res.get("delta", "") for res in results_json if "delta" in res)
        assert mock_msg_repo_instance.create.call_count >= 2


@pytest.mark.asyncio
# *** CORRECTED PATCH TARGETS ***
@patch('core.orchestrator.project_repository.ProjectRepository')
@patch('core.orchestrator.message_repository.MessageRepository')
@patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock)
async def test_orchestrator_handles_client_error_stream(
    mock_openai_gen, mock_msg_repo_cls, mock_proj_repo_cls,
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    mock_test_project: MagicMock,
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator yields an error event if the client stream yields an error dictionary,
    and does NOT save the assistant message.
    """
    # Configure mocks
    mock_project_repo_instance = mock_proj_repo_cls.return_value
    mock_project_repo_instance.get_by_id_for_owner.return_value = mock_test_project
    mock_msg_repo_instance = mock_msg_repo_cls.return_value

    # Configure mock client to yield an error dictionary
    error_message = "Client simulation error"
    async def error_generator(*args, **kwargs):
        yield {"delta": "Some initial content"}
        yield {"error": True, "message": error_message, "type": "ClientError"}
    mock_openai_gen.return_value = error_generator()

    # --- Call Orchestrator ---
    orchestrator_args = {
        "messages": basic_user_messages, "model": "openai/gpt-4", "project_id": mock_test_project.id,
        "db": mock_db_session, "user": mock_test_user, "stream": True, "temperature": None,
        "max_tokens": None, "system_prompt": None,
    }
    results_json = []
    async for result_chunk in orchestrator.process_generation_request(**orchestrator_args):
         if result_chunk.startswith("data:"):
             try:
                  data_part = result_chunk.strip().split("data: ")[1]
                  results_json.append(json.loads(data_part))
             except Exception: pass

    # --- Assertions ---
    # 1. Check that an error event was yielded
    # *** REVISED: Check for the 'error': True key/value pair ***
    assert any(res.get("error") is True for res in results_json), \
        f"No error event (dict with 'error': True) found in results: {results_json}"
    error_event = next((res for res in results_json if res.get("error") is True), None)
    assert error_event is not None
    assert error_message in error_event.get("message", "")
    assert error_event.get("type") == "ClientError" # Check the type field if needed

    # 2. Check that assistant message was NOT saved (only user message was saved)
    assert mock_msg_repo_instance.create.call_count == 1, \
        f"Expected 1 call to create (user msg), got {mock_msg_repo_instance.create.call_count}"
    user_save_call_args, user_save_call_kwargs = mock_msg_repo_instance.create.call_args_list[0]
    saved_user_schema = user_save_call_kwargs.get('obj_in')
    assert saved_user_schema.role == schemas.MessageRole.USER


# Test Case: Project Not Found
@pytest.mark.asyncio
# *** CORRECTED PATCH TARGETS ***
@patch('core.orchestrator.project_repository.ProjectRepository')
@patch('core.orchestrator.message_repository.MessageRepository')
@patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock)
async def test_orchestrator_project_not_found(
    mock_openai_gen, mock_msg_repo_cls, mock_proj_repo_cls, # Correct order
    mock_db_session: MagicMock,
    mock_test_user: MagicMock,
    # No mock_test_project needed here
    basic_user_messages: List[Dict[str, Any]]
):
    """
    Test that the orchestrator yields an error event if the project is not found
    or not owned by the user.
    """
    # Configure ProjectRepository mock to return None
    mock_project_repo_instance = mock_proj_repo_cls.return_value
    mock_project_repo_instance.get_by_id_for_owner.return_value = None # Simulate project not found

    # Configure other mocks
    mock_msg_repo_instance = mock_msg_repo_cls.return_value
    mock_openai_gen.return_value = None

    # --- Call Orchestrator ---
    non_existent_project_id = "project-does-not-exist"
    orchestrator_args = {
        "messages": basic_user_messages, "model": "openai/gpt-4", "project_id": non_existent_project_id,
        "db": mock_db_session, "user": mock_test_user, "stream": True, "temperature": None,
        "max_tokens": None, "system_prompt": None,
    }

    results_json = []
    async for result_chunk in orchestrator.process_generation_request(**orchestrator_args):
         if result_chunk.startswith("data:"):
             try:
                  data_part = result_chunk.strip().split("data: ")[1]
                  results_json.append(json.loads(data_part))
             except Exception: pass

    # --- Assertions ---
    mock_proj_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_project_repo_instance.get_by_id_for_owner.assert_called_once_with(
        project_id=non_existent_project_id, owner_id=mock_test_user.id
    )

    assert len(results_json) == 1, f"Expected 1 event, got {len(results_json)}: {results_json}"
    error_event_data = results_json[0]
    assert error_event_data.get("error") is True
    assert error_event_data.get("type") == "NotFoundError"
    assert "Project not found" in error_event_data.get("message", "")

    # MessageRepository *instance* methods shouldn't be called
    mock_msg_repo_instance.create.assert_not_called()
    # mock_msg_repo_instance.store_conversation.assert_not_called() # If relevant

    mock_openai_gen.assert_not_awaited()


# TODO: Add tests for context notes injection logic (OpenAI vs Anthropic/Google)
# TODO: Add test for case where get_provider_from_model fails