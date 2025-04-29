# tests/unit/test_openai_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY # Import ANY for flexible matching
import sys
import os
from typing import AsyncGenerator, Dict, Any, Optional, List, Union # For type hinting generators
from openai import APIError, RateLimitError, APITimeoutError, AsyncOpenAI # Import specific errors and AsyncOpenAI
# Make sure httpx is installed if used internally by openai mocks, though MagicMock should suffice
# from httpx import Request, Response

# Add the parent directory to PYTHONPATH if needed (adjust path as necessary for your structure)
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Import the module we are testing AFTER potentially modifying path
from integrations import openai_client
from config.settings import settings # Import settings to allow modification in tests

# Define some common test data
TEST_MESSAGES_BASE = [{"role": "user", "content": "Hello OpenAI"}]
DEFAULT_MODEL = openai_client.DEFAULT_OPENAI_MODEL
DEFAULT_TEMP = openai_client.DEFAULT_TEMPERATURE
DEFAULT_TOKENS = openai_client.DEFAULT_MAX_TOKENS

# --- Mock Helpers ---

# Helper to create mock non-streaming response
def create_mock_openai_response(
    content: Optional[str] = "Default AI response.",
    finish_reason: str = "stop",
    model: str = DEFAULT_MODEL,
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
    total_tokens: int = 30,
    choices: Optional[list] = None,
    usage: Optional[bool] = True # Control if usage info exists
):
    # FIX: Remove the problematic spec argument here
    mock_response = MagicMock() # Simpler mock without spec
    mock_response.model = model

    if choices is None:
        mock_choice = MagicMock()
        # Ensure message structure matches ChatCompletionMessage
        mock_choice.message = MagicMock()
        mock_choice.message.role = "assistant" # Role needed
        mock_choice.message.content = content
        mock_choice.message.function_call = None # Add other potential attrs
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = finish_reason
        mock_response.choices = [mock_choice]
    else:
        mock_response.choices = choices # Allow providing custom choices list

    if usage:
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = prompt_tokens
        mock_usage.completion_tokens = completion_tokens
        mock_usage.total_tokens = total_tokens
        mock_response.usage = mock_usage
    else:
        mock_response.usage = None

    # Mock the model_dump method for raw response storage
    mock_response.model_dump.return_value = {"id": "chatcmpl-mockid", "content": content, "usage": usage}
    return mock_response

# Helper to create mock stream chunks (mirroring OpenAI SDK structure)
def create_mock_stream_chunk(content: Optional[str] = None, finish_reason: Optional[str] = None, model: str = DEFAULT_MODEL):
    # FIX: Remove the problematic spec argument here
    mock_chunk = MagicMock() # Simpler mock without spec
    mock_chunk.id = "chatcmpl-mockchunkid"
    mock_chunk.object = "chat.completion.chunk"
    mock_chunk.created = 1234567890
    mock_chunk.model = model
    mock_delta = MagicMock()
    mock_delta.content = content
    # Role often appears in first chunk delta or if content is None initially
    mock_delta.role = "assistant" if (content is not None or finish_reason is None) else None
    mock_delta.function_call = None
    mock_delta.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.index = 0
    mock_choice.delta = mock_delta
    mock_choice.finish_reason = finish_reason
    mock_choice.logprobs = None
    mock_chunk.choices = [mock_choice]
    mock_chunk.system_fingerprint = None # Add potential attributes
    mock_chunk.usage = None # Usage usually not in chunks
    return mock_chunk

# Mock async generator for the stream
async def mock_openai_stream_generator(chunks: List[Any]):
    """Yields chunks or raises an exception if an exception instance is in the list."""
    for chunk in chunks:
        if isinstance(chunk, Exception):
            raise chunk
        yield chunk

# --- Fixtures ---

@pytest.fixture(autouse=True)
def ensure_openai_client_initialized(monkeypatch):
    """
    Fixture to ensure the openai_client.client is mocked or properly initialized
    for most tests, preventing failures due to missing API key during testing.
    """
    if not settings.OPENAI_API_KEY:
        # If no key is set, mock the client completely
        print("\n--- Mocking OpenAI Client (No API Key) ---")
        mock_async_client = MagicMock(spec=AsyncOpenAI)
        # Ensure the nested structure exists and create is an AsyncMock
        mock_async_client.chat = MagicMock()
        mock_async_client.chat.completions = MagicMock()
        mock_async_client.chat.completions.create = AsyncMock()
        monkeypatch.setattr(openai_client, "client", mock_async_client)
    elif openai_client.client is None:
         # If key exists but client is somehow None (e.g., module loaded before settings applied)
         print("\n--- Re-initializing OpenAI Client (Key found, Client was None) ---")
         monkeypatch.setattr(openai_client, "client", AsyncOpenAI(api_key=settings.OPENAI_API_KEY))
    else:
         # If key exists and client is already initialized, just ensure create is mockable if needed by specific tests
         # We'll patch it directly in tests using patch.object where needed.
         print("\n--- Using potentially real OpenAI Client instance (API Key found) ---")
         pass # Assume client is okay

    # Safety checks after setup
    assert openai_client.client is not None, "Client should be mocked or initialized"
    assert hasattr(openai_client.client, 'chat'), "Client mock/instance missing 'chat'"
    assert hasattr(openai_client.client.chat, 'completions'), "Client mock/instance missing 'chat.completions'"
    assert hasattr(openai_client.client.chat.completions, 'create'), "Client mock/instance missing 'chat.completions.create'"
    yield # Allow test to run
    # Teardown if needed (e.g., reset client if modified directly)
    # print("\n--- Teardown ensure_openai_client_initialized ---")


# --- Test Cases ---

@pytest.mark.asyncio
async def test_generate_completion_openai_non_streaming_success():
    """
    Tests successful non-streaming completion from OpenAI client.
    """
    # --- Arrange ---
    mock_openai_response = create_mock_openai_response(content="Specific AI response.", model="gpt-4-test")
    # Use AsyncMock for the replacement method
    mock_create_method = AsyncMock(return_value=mock_openai_response)

    # Use patch.object for clarity and robustness targeting the method on the potentially mocked client
    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method) as patched_create:
        # --- Act ---
        result = await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE,
            model="gpt-4-turbo", # Override default in call
            stream=False,
            temperature=0.5,
            max_tokens=500, # Override default
            extra_param="test_value" # Test kwargs propagation
        )

        # --- Assert ---
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("model") == "gpt-4-turbo" # Model from the call
        assert call_kwargs.get("messages") == TEST_MESSAGES_BASE
        assert call_kwargs.get("stream") is False
        assert call_kwargs.get("temperature") == 0.5
        assert call_kwargs.get("max_tokens") == 500
        assert call_kwargs.get("extra_param") == "test_value" # Kwarg check

        assert isinstance(result, dict)
        assert result.get("error") is False
        assert result.get("content") == "Specific AI response."
        assert result.get("finish_reason") == "stop"
        assert result.get("model_name") == "gpt-4-test" # Model from the mock response object
        assert result.get("usage") is not None
        assert "raw_response" in result

@pytest.mark.asyncio
async def test_generate_completion_uses_defaults():
    """Tests that default parameters are used when not provided."""
    # --- Arrange ---
    mock_openai_response = create_mock_openai_response()
    mock_create_method = AsyncMock(return_value=mock_openai_response)

    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method) as patched_create:
        # --- Act ---
        await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE,
            stream=False,
            # Omit model, temperature, max_tokens
        )
        # --- Assert ---
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("model") == DEFAULT_MODEL
        assert call_kwargs.get("temperature") == DEFAULT_TEMP
        assert call_kwargs.get("max_tokens") == DEFAULT_TOKENS
        assert call_kwargs.get("stream") is False


@pytest.mark.asyncio
async def test_generate_completion_filters_empty_assistant_messages():
    """Tests that empty assistant messages are filtered out."""
    # --- Arrange ---
    messages_with_empty = [
        {"role": "user", "content": "Query 1"},
        {"role": "assistant", "content": ""}, # Empty assistant message
        {"role": "user", "content": "Query 2"},
        {"role": "assistant", "content": None}, # None content assistant message
        {"role": "assistant"}, # No content key
    ]
    expected_filtered_messages = [
        {"role": "user", "content": "Query 1"},
        {"role": "user", "content": "Query 2"},
    ]

    mock_openai_response = create_mock_openai_response()
    mock_create_method = AsyncMock(return_value=mock_openai_response)

    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method) as patched_create:
        # --- Act ---
        await openai_client.generate_completion(
            messages=messages_with_empty,
            stream=False,
        )
        # --- Assert ---
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        # Verify the messages passed to the API call were filtered
        assert call_kwargs.get("messages") == expected_filtered_messages


@pytest.mark.asyncio
async def test_generate_completion_openai_streaming_success():
    """Tests successful streaming completion from OpenAI client."""
    # --- Arrange ---
    mock_chunks_to_yield = [
        create_mock_stream_chunk(content="AI ", model="gpt-stream-test"),
        create_mock_stream_chunk(content="says ", model="gpt-stream-test"),
        create_mock_stream_chunk(content="hello!", model="gpt-stream-test"),
        create_mock_stream_chunk(content=None, finish_reason="stop", model="gpt-stream-test"),
    ]
    mock_stream = mock_openai_stream_generator(mock_chunks_to_yield)
    mock_create_method = AsyncMock(return_value=mock_stream)

    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method) as patched_create:
        # --- Act ---
        result_generator = await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE,
            model=DEFAULT_MODEL, # Model used in the API call
            stream=True,
        )
        results = [item async for item in result_generator]

        # --- Assert ---
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("model") == DEFAULT_MODEL
        assert call_kwargs.get("messages") == TEST_MESSAGES_BASE
        assert call_kwargs.get("stream") is True

        assert len(results) == 4 # 3 delta chunks + 1 final chunk
        assert results[0] == {"error": False, "delta": "AI ", "is_final": False, "accumulated_content": "AI "}
        assert results[1] == {"error": False, "delta": "says ", "is_final": False, "accumulated_content": "AI says "}
        assert results[2] == {"error": False, "delta": "hello!", "is_final": False, "accumulated_content": "AI says hello!"}
        # Check final summary chunk
        assert results[3]["error"] is False
        assert results[3]["delta"] is None
        assert results[3]["is_final"] is True
        assert results[3]["accumulated_content"] == "AI says hello!"
        assert results[3]["finish_reason"] == "stop"
        assert results[3]["usage"] is None # Usage not available in stream
        assert results[3]["model_name"] == "gpt-stream-test" # Model from the last chunk


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
@pytest.mark.parametrize("error_type, init_args, error_attrs", [
    (RateLimitError, # Type
     {"message": "Rate limit exceeded", "response": MagicMock(status_code=429), "body": {"code": "rate_limit_exceeded"}}, # Args for __init__
     {"type": "RateLimitError", "message": "Rate limit exceeded", "code": "rate_limit_exceeded", "status_code": 429}), # Expected attributes/dict keys
    (APITimeoutError, # Type
     # FIX: Provide a dummy 'request' argument for APITimeoutError init
     {"request": MagicMock()},
     {"type": "APITimeoutError", "message": "Request timed out"}), # Expected (message is standard)
    (APIError, # Type
     {"message": "Generic API error", "request": MagicMock(), "body": {"code": "server_error"}}, # Args for __init__ (Correct args for APIError)
     {"type": "APIError", "message": "Generic API error", "code": "server_error", "status_code": None}), # Expected (code is from body, status_code might be None)
    (ValueError, # Type
     ("Unexpected value error",), # Standard Exception args (tuple)
     {"type": "ValueError", "message": "Unexpected value error"}), # Expected
])
async def test_generate_completion_openai_various_errors_on_create(
    stream_flag: bool, error_type: type, init_args: Union[dict, tuple], error_attrs: dict
):
    """Tests error handling for various errors during the API call."""
    # --- Arrange ---
    print(f"\nTesting Error: {error_type.__name__} (Stream: {stream_flag})")
    print(f"Init Args: {init_args}")
    print(f"Expected Attrs: {error_attrs}")

    if issubclass(error_type, APIError):
         # Handle specific APIError subclasses based on their expected init args
        if error_type == RateLimitError:
            # RateLimitError needs message, response and body
            error_to_raise = RateLimitError(
                message=init_args["message"],
                response=init_args["response"], # httpx.Response mock
                body=init_args["body"] # Parsed JSON body
            )
        elif error_type == APITimeoutError:
             # FIX: Pass the 'request' argument from init_args
             error_to_raise = APITimeoutError(request=init_args["request"])
        elif error_type == APIError:
             # Generic APIError needs message, request, body
             error_to_raise = APIError(
                 message=init_args["message"],
                 request=init_args["request"], # httpx.Request mock
                 body=init_args["body"]
             )
        else:
             # Fallback for other potential APIErrors if added later
             # This might need adjustment if other errors have different signatures
             try:
                 error_to_raise = error_type(**init_args)
             except TypeError: # If kwargs don't match, try positional
                 error_to_raise = error_type(*init_args.values())

    else: # Standard Exception
        error_to_raise = error_type(*init_args)

    # Manually set attributes if not set by __init__ but expected by handler
    # This part might be less critical if handler relies on error type and standard attrs
    if "status_code" in error_attrs and error_attrs["status_code"] is not None and hasattr(error_to_raise, 'response') and error_to_raise.response:
         error_to_raise.response.status_code = error_attrs["status_code"] # Ensure mock response has code
    if "code" in error_attrs and error_attrs["code"] is not None and hasattr(error_to_raise, 'code') and not error_to_raise.code:
         # Set the code attribute if it exists on the error but wasn't set by init
         error_to_raise.code = error_attrs["code"]


    mock_create_method = AsyncMock(side_effect=error_to_raise)

    # Use patch.object which is often more reliable for nested attributes
    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method) as patched_create:
        # --- Act ---
        if stream_flag:
            result_generator = await openai_client.generate_completion(
                messages=TEST_MESSAGES_BASE, stream=True
            )
            results = [item async for item in result_generator]
            assert len(results) == 1, f"Expected 1 error dict, got {len(results)}"
            result = results[0]
        else:
            result = await openai_client.generate_completion(
                messages=TEST_MESSAGES_BASE, stream=False
            )

        # --- Assert ---
        patched_create.assert_awaited_once()
        assert isinstance(result, dict)
        assert result.get("error") is True
        # Check expected attributes from the error_attrs dict
        assert result.get("type") == error_attrs["type"]
        assert error_attrs["message"] in result.get("message", "") # Use 'in' for flexibility
        if "code" in error_attrs and error_attrs["code"] is not None:
             # Check the 'error_code' key our handler creates
             assert result.get("error_code") == error_attrs["code"]
        if "status_code" in error_attrs and error_attrs["status_code"] is not None:
             assert result.get("status_code") == error_attrs["status_code"]


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type, init_args, error_attrs", [
    (APIError, # Type
     {"message": "API error during stream", "request": MagicMock(), "body": {"code": "stream_issue"}}, # Args for __init__
     {"type": "APIError", "message": "API error during stream", "code": "stream_issue"}), # Expected
    (ValueError, # Type
     ("Unexpected value error during stream",), # Standard Exception args
     {"type": "ValueError", "message": "Unexpected value error during stream"}), # Expected
])
async def test_generate_completion_openai_error_during_streaming(error_type: type, init_args: Union[dict, tuple], error_attrs: dict):
    """Tests handling of errors raised *while* processing the stream."""
    # --- Arrange ---
    print(f"\nTesting Error During Stream: {error_type.__name__}")
    if isinstance(init_args, dict):
        if error_type == APIError:
             # APIError needs message, request, body
             error_to_raise = APIError(
                 message=init_args["message"],
                 request=init_args["request"], # httpx.Request mock
                 body=init_args["body"]
             )
        else: # Fallback for other APIError types
            try: error_to_raise = error_type(**init_args)
            except TypeError: error_to_raise = error_type(*init_args.values())
    else: # Standard Exception
        error_to_raise = error_type(*init_args)

    # Chunks to yield before the error occurs
    mock_chunks_with_error = [
        create_mock_stream_chunk(content="Part 1 "),
        error_to_raise # Error object inserted into the sequence
    ]
    mock_stream = mock_openai_stream_generator(mock_chunks_with_error)
    mock_create_method = AsyncMock(return_value=mock_stream)

    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method):
        # --- Act ---
        result_generator = await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE, stream=True
        )
        results = []
        # Consume the generator safely
        async for item in result_generator:
            results.append(item)

        # --- Assert ---
        assert len(results) == 2 # One valid chunk, one error chunk
        # Check the valid chunk
        assert results[0]["error"] is False
        assert results[0]["delta"] == "Part 1 "
        assert results[0]["is_final"] is False

        # Check the error chunk yielded by the handler
        error_result = results[1]
        assert error_result["error"] is True
        assert error_result["type"] == error_attrs["type"]
        assert error_attrs["message"] in error_result.get("message", "")
        if "code" in error_attrs and error_attrs["code"] is not None:
             # Check the 'error_code' key our handler creates
             assert error_result.get("error_code") == error_attrs["code"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
async def test_generate_completion_client_not_initialized(stream_flag: bool, monkeypatch):
    """Tests behavior when OpenAI client is not initialized (no API key)."""
    # --- Arrange ---
    # Explicitly set the client to None for this test, overriding autouse fixture
    monkeypatch.setattr(openai_client, "client", None)
    print("\n--- Testing Uninitialized Client ---")

    # --- Act ---
    if stream_flag:
        result_generator = await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE, stream=True
        )
        results = [item async for item in result_generator]
        assert len(results) == 1
        result = results[0]
    else:
        result = await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE, stream=False
        )

    # --- Assert ---
    assert isinstance(result, dict)
    assert result.get("error") is True
    assert "OpenAI client not initialized" in result.get("message", "")
    assert result.get("type") == "ConfigurationError"


@pytest.mark.asyncio
async def test_non_streaming_parsing_no_choices():
    """Tests non-streaming parsing when API returns no choices."""
     # --- Arrange ---
    mock_openai_response = create_mock_openai_response(choices=[]) # Empty choices list
    mock_create_method = AsyncMock(return_value=mock_openai_response)

    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method):
        # --- Act ---
        result = await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE, stream=False
        )
        # --- Assert ---
        assert result["error"] is False # Call succeeded, but no content
        assert result["content"] is None
        assert result["finish_reason"] is None
        assert result["usage"] is not None # Usage might still be present

@pytest.mark.asyncio
async def test_non_streaming_parsing_no_usage():
    """Tests non-streaming parsing when API returns no usage info."""
     # --- Arrange ---
    mock_openai_response = create_mock_openai_response(usage=False) # No usage info
    mock_create_method = AsyncMock(return_value=mock_openai_response)

    with patch.object(openai_client.client.chat.completions, 'create', mock_create_method):
        # --- Act ---
        result = await openai_client.generate_completion(
            messages=TEST_MESSAGES_BASE, stream=False
        )
        # --- Assert ---
        assert result["error"] is False
        assert result["content"] is not None # Content should still be there
        assert result["finish_reason"] == "stop"
        assert result["usage"] is None # Check usage is None