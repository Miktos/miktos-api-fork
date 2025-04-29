# tests/unit/test_claude_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import sys
import os
from typing import AsyncGenerator, Dict, Any, Optional, List, Union
from anthropic import APIError, RateLimitError, APITimeoutError, AsyncAnthropic
from anthropic.types import Message, TextBlock, Usage, MessageStartEvent, ContentBlockDeltaEvent, TextDelta, MessageDeltaEvent, MessageStopEvent

# Add project root to path if necessary (adjust as needed)
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from integrations import claude_client
from config.settings import settings # Import settings to allow modification in tests

# --- Constants ---
TEST_MESSAGES_BASE = [{"role": "user", "content": "Hello Claude"}]
DEFAULT_MODEL = claude_client.DEFAULT_CLAUDE_MODEL
DEFAULT_TEMP = claude_client.DEFAULT_TEMPERATURE
DEFAULT_TOKENS = claude_client.DEFAULT_MAX_TOKENS

# --- Mock Helpers ---

def create_mock_anthropic_message(
    content_text: Optional[str] = "Default Claude response.",
    stop_reason: str = "end_turn",
    model: str = DEFAULT_MODEL,
    input_tokens: int = 15,
    output_tokens: int = 25
) -> MagicMock:
    """Creates a mock Anthropic Message object."""
    mock_message = MagicMock(spec=Message)
    mock_message.id = "msg_mock123"
    mock_message.type = "message"
    mock_message.role = "assistant"

    if content_text is not None:
        mock_content_block = MagicMock(spec=TextBlock)
        mock_content_block.type = "text"
        mock_content_block.text = content_text
        mock_message.content = [mock_content_block]
    else:
        mock_message.content = [] # Simulate no content block

    mock_message.model = model
    mock_message.stop_reason = stop_reason
    mock_message.stop_sequence = None
    mock_usage = MagicMock(spec=Usage)
    mock_usage.input_tokens = input_tokens
    mock_usage.output_tokens = output_tokens
    mock_message.usage = mock_usage

    # Mock the model_dump method for raw response storage
    mock_message.model_dump.return_value = {
        "id": mock_message.id, "type": mock_message.type, "role": mock_message.role,
        "content": [{"type": "text", "text": content_text}] if content_text else [],
        "model": model, "stop_reason": stop_reason, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
    }
    return mock_message

def create_mock_anthropic_stream_event(
    event_type: str,
    text_delta: Optional[str] = None,
    stop_reason: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None, # Note: Anthropic SDK provides cumulative output tokens in message_delta
    model: str = DEFAULT_MODEL,
    message_id: str = "msg_mock123",
) -> MagicMock:
    """Creates a mock Anthropic stream event."""
    if event_type == "message_start":
        mock_event = MagicMock(spec=MessageStartEvent)
        mock_event.type = "message_start"
        mock_message_data = {
            "id": message_id, "type": "message", "role": "assistant", "content": [],
            "model": model, "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": input_tokens or 0, "output_tokens": 0}
        }
        # Create a message mock that correctly includes a usage mock
        message_mock = MagicMock(spec=Message)
        message_mock.id = message_id
        message_mock.type = "message"
        message_mock.role = "assistant"
        message_mock.content = []
        message_mock.model = model
        message_mock.stop_reason = None
        message_mock.stop_sequence = None
        message_mock.usage = MagicMock(spec=Usage)
        message_mock.usage.input_tokens=input_tokens or 0
        message_mock.usage.output_tokens=0

        mock_event.message = message_mock
        return mock_event
    elif event_type == "content_block_delta":
        mock_event = MagicMock(spec=ContentBlockDeltaEvent)
        mock_event.type = "content_block_delta"
        mock_event.index = 0
        mock_event.delta = MagicMock(spec=TextDelta)
        mock_event.delta.type = "text_delta"
        mock_event.delta.text = text_delta or ""
        return mock_event
    elif event_type == "message_delta":
        mock_event = MagicMock(spec=MessageDeltaEvent)
        mock_event.type = "message_delta"
        mock_event.delta = MagicMock()
        mock_event.delta.stop_reason = stop_reason
        mock_event.delta.stop_sequence = None
        # Usage in message_delta contains output_tokens for the delta event
        mock_usage = MagicMock(spec=Usage)
        # input tokens not present in message_delta usage
        mock_usage.output_tokens = output_tokens or 0
        mock_event.usage = mock_usage
        return mock_event
    elif event_type == "message_stop":
        mock_event = MagicMock(spec=MessageStopEvent)
        mock_event.type = "message_stop"
        return mock_event
    else:
        raise ValueError(f"Unsupported mock event type: {event_type}")


# Mock async generator for the stream events
async def mock_anthropic_event_generator(events: List[Any]):
    """Yields mock events or raises an exception."""
    for event in events:
        if isinstance(event, Exception):
            raise event
        yield event

# Mock async context manager for the stream
class MockAsyncStreamManager:
    def __init__(self, events_or_error: Union[List[Any], Exception]):
        self._events_or_error = events_or_error

    async def __aenter__(self):
        print(f"--- Mock Stream Manager __aenter__ ({'Error' if isinstance(self._events_or_error, Exception) else 'Events'}) ---")
        if isinstance(self._events_or_error, Exception):
            raise self._events_or_error # Raise error on entering context if specified
        # Return the async generator that yields events
        return mock_anthropic_event_generator(self._events_or_error)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print("--- Mock Stream Manager __aexit__ ---")
        # Simulate cleanup or do nothing
        pass


# --- Fixtures ---
@pytest.fixture(autouse=True)
def ensure_anthropic_client_initialized(monkeypatch):
    """
    Fixture to ensure the claude_client.client is mocked or properly initialized
    for most tests, preventing failures due to missing API key during testing.
    """
    if not settings.ANTHROPIC_API_KEY:
        print("\n--- Mocking Anthropic Client (No API Key) ---")
        mock_async_client = MagicMock(spec=AsyncAnthropic)
        mock_async_client.messages = MagicMock()
        mock_async_client.messages.create = AsyncMock()
        # stream() needs careful mocking as it returns a context manager
        mock_async_client.messages.stream = MagicMock()
        monkeypatch.setattr(claude_client, "client", mock_async_client)
    elif claude_client.client is None:
         print("\n--- Re-initializing Anthropic Client (Key found, Client was None) ---")
         monkeypatch.setattr(claude_client, "client", AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY))
    else:
         print("\n--- Using potentially real Anthropic Client instance (API Key found) ---")
         pass

    assert claude_client.client is not None, "Client should be mocked or initialized"
    assert hasattr(claude_client.client, 'messages'), "Client mock/instance missing 'messages'"
    assert hasattr(claude_client.client.messages, 'create'), "Client mock/instance missing 'messages.create'"
    assert hasattr(claude_client.client.messages, 'stream'), "Client mock/instance missing 'messages.stream'"
    yield
    # print("\n--- Teardown ensure_anthropic_client_initialized ---")

# --- Test Cases ---

@pytest.mark.asyncio
async def test_generate_completion_claude_non_streaming_success():
    """Tests successful non-streaming completion from Claude client."""
    # --- Arrange ---
    mock_response = create_mock_anthropic_message(
        content_text="Claude says hello.", model="claude-3-opus-test"
    )
    mock_create_method = AsyncMock(return_value=mock_response)

    with patch.object(claude_client.client.messages, 'create', mock_create_method) as patched_create:
        # --- Act ---
        result = await claude_client.generate_completion(
            messages=TEST_MESSAGES_BASE,
            model="claude-3-opus-20240229", # Call with specific model
            system_prompt="You are helpful.",
            temperature=0.6,
            max_tokens=555,
            stream=False,
            extra_arg="value1" # Test kwargs
        )

        # --- Assert ---
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("model") == "claude-3-opus-20240229"
        assert call_kwargs.get("messages") == TEST_MESSAGES_BASE
        assert call_kwargs.get("system") == "You are helpful."
        assert call_kwargs.get("temperature") == 0.6
        assert call_kwargs.get("max_tokens") == 555
        assert call_kwargs.get("extra_arg") == "value1"
        assert "stream" not in call_kwargs # Stream passed to method, not API args

        assert isinstance(result, dict)
        assert result.get("error") is False
        assert result.get("content") == "Claude says hello."
        assert result.get("finish_reason") == "end_turn"
        assert result.get("model_name") == "claude-3-opus-test" # From mock response
        assert result.get("usage") == {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}
        assert "raw_response" in result

@pytest.mark.asyncio
async def test_generate_completion_claude_uses_defaults():
    """Tests that default parameters are used when not provided."""
    # --- Arrange ---
    mock_response = create_mock_anthropic_message()
    mock_create_method = AsyncMock(return_value=mock_response)

    with patch.object(claude_client.client.messages, 'create', mock_create_method) as patched_create:
        # --- Act ---
        await claude_client.generate_completion(
            messages=TEST_MESSAGES_BASE,
            stream=False,
            # Omit model, system_prompt, temperature, max_tokens
        )
        # --- Assert ---
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("model") == DEFAULT_MODEL
        assert call_kwargs.get("temperature") == DEFAULT_TEMP
        assert call_kwargs.get("max_tokens") == DEFAULT_TOKENS
        assert "system" not in call_kwargs # No system prompt by default


@pytest.mark.asyncio
async def test_generate_completion_claude_filters_empty_assistant():
    """Tests that empty assistant messages are filtered out."""
    # --- Arrange ---
    messages_with_empty = [
        {"role": "user", "content": "Query 1"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "Query 2"},
        {"role": "assistant", "content": None},
        {"role": "assistant"},
    ]
    expected_filtered = [
        {"role": "user", "content": "Query 1"},
        {"role": "user", "content": "Query 2"},
    ]
    mock_response = create_mock_anthropic_message()
    mock_create_method = AsyncMock(return_value=mock_response)

    with patch.object(claude_client.client.messages, 'create', mock_create_method) as patched_create:
        # --- Act ---
        await claude_client.generate_completion(messages=messages_with_empty, stream=False)
        # --- Assert ---
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("messages") == expected_filtered

@pytest.mark.asyncio
async def test_generate_completion_claude_streaming_success():
    """Tests successful streaming completion from Claude client."""
    # --- Arrange ---
    test_model = "claude-stream-test"
    mock_events = [
        create_mock_anthropic_stream_event("message_start", input_tokens=10, model=test_model),
        create_mock_anthropic_stream_event("content_block_delta", text_delta="Hello "),
        create_mock_anthropic_stream_event("content_block_delta", text_delta="from "),
        create_mock_anthropic_stream_event("message_delta", output_tokens=5), # Cumulative output tokens
        create_mock_anthropic_stream_event("content_block_delta", text_delta="Claude!"),
        create_mock_anthropic_stream_event("message_delta", stop_reason="stop_sequence", output_tokens=12),
        create_mock_anthropic_stream_event("message_stop"),
    ]
    # Mock the stream method to return our context manager
    mock_stream_method = MagicMock(return_value=MockAsyncStreamManager(mock_events))

    with patch.object(claude_client.client.messages, 'stream', mock_stream_method) as patched_stream:
        # --- Act ---
        result_generator = await claude_client.generate_completion(
            messages=TEST_MESSAGES_BASE,
            model="claude-3-sonnet", # Model passed to func
            stream=True,
            system_prompt="Be concise."
        )
        results = [item async for item in result_generator]

        # --- Assert ---
        # 1. Check API call
        patched_stream.assert_called_once()
        call_args, call_kwargs = patched_stream.call_args
        assert call_kwargs.get("model") == "claude-3-sonnet"
        assert call_kwargs.get("messages") == TEST_MESSAGES_BASE
        assert call_kwargs.get("system") == "Be concise."
        assert call_kwargs.get("max_tokens") == DEFAULT_TOKENS # Default used

        # 2. Check yielded results (3 deltas + 1 final)
        assert len(results) == 4
        # Deltas
        assert results[0] == {"error": False, "delta": "Hello ", "is_final": False, "accumulated_content": "Hello "}
        assert results[1] == {"error": False, "delta": "from ", "is_final": False, "accumulated_content": "Hello from "}
        assert results[2] == {"error": False, "delta": "Claude!", "is_final": False, "accumulated_content": "Hello from Claude!"}
        # Final
        final_result = results[3]
        assert final_result["error"] is False
        assert final_result["delta"] is None
        assert final_result["is_final"] is True
        assert final_result["accumulated_content"] == "Hello from Claude!"
        assert final_result["finish_reason"] == "stop_sequence"
        assert final_result["model_name"] == test_model # Model from message_start
        assert final_result["usage"] == {"prompt_tokens": 10, "completion_tokens": 12, "total_tokens": 22}


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
@pytest.mark.parametrize("error_type, init_args, error_attrs", [
    (RateLimitError, # Type
     # FIX: RateLimitError needs message, response, body
     {"message": "Claude rate limit", "response": MagicMock(status_code=429), "body": {"type": "error", "error": {"type": "rate_limit_error"}}},
     {"type": "RateLimitError", "message": "Claude rate limit", "status_code": 429}),
    (APITimeoutError, # Type
     # FIX: APITimeoutError needs request
     {"request": MagicMock()},
     {"type": "APITimeoutError", "message": "Request timed out"}), # Default message from SDK might be different
    (APIError, # Type
     # FIX: APIError needs message, request, body. status_code comes via response mock.
     {"message": "Claude API error", "request": MagicMock(), "body": {"type": "error", "error": {"type": "api_error"}}},
     {"type": "APIError", "message": "Claude API error", "status_code": 500}), # We'll mock the status code onto the response
    (ValueError, # Type
     ("Unexpected value",), # Standard Exception args (tuple)
     {"type": "ValueError", "message": "Unexpected value"}), # Expected
])
async def test_generate_completion_claude_errors_on_call(
    stream_flag: bool, error_type: type, init_args: Union[dict, tuple], error_attrs: dict
):
    """Tests handling of API errors during the initial create/stream call."""
    # --- Arrange ---
    print(f"\nTesting Error On Call: {error_type.__name__} (Stream: {stream_flag})")
    mock_request = MagicMock() # Create mock request for errors needing it

    if issubclass(error_type, APIError):
        # Common setup for APIError subclasses
        mock_response = init_args.get("response") # Get response if provided
        # Ensure response exists and has status_code if needed for testing
        if "status_code" in error_attrs and error_attrs["status_code"]:
             if not mock_response:
                 mock_response = MagicMock()
                 # Add response back to init_args if it wasn't there originally
                 if isinstance(init_args, dict): init_args["response"] = mock_response
             mock_response.status_code = error_attrs["status_code"]

        # FIX: Instantiate based on corrected signatures
        if error_type == RateLimitError:
            error_to_raise = RateLimitError(
                message=init_args["message"],
                response=init_args["response"], # Must have status_code set
                body=init_args["body"]
            )
        elif error_type == APITimeoutError:
             error_to_raise = APITimeoutError(request=init_args["request"])
        elif error_type == APIError:
             error_to_raise = APIError(
                 message=init_args["message"],
                 request=init_args["request"],
                 body=init_args["body"]
             )
             # Manually assign response if it exists and has status_code
             if mock_response: error_to_raise.response = mock_response
        else: # Fallback for other potential APIErrors
            try: error_to_raise = error_type(**init_args)
            except TypeError: error_to_raise = error_type(*init_args.values())

    else: # Standard Exception
        error_to_raise = error_type(*init_args)

    # --- Mocking the API call ---
    if stream_flag:
        mock_stream_method = MagicMock(return_value=MockAsyncStreamManager(error_to_raise))
        patch_target = patch.object(claude_client.client.messages, 'stream', mock_stream_method)
    else:
        mock_create_method = AsyncMock(side_effect=error_to_raise)
        patch_target = patch.object(claude_client.client.messages, 'create', mock_create_method)

    with patch_target as patched_call:
        # --- Act ---
        if stream_flag:
            # The wrapper needs to handle the error raised by __aenter__
            result_generator = await claude_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
            results = [item async for item in result_generator]
            assert len(results) == 1
            result = results[0]
        else:
            result = await claude_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)

        # --- Assert ---
        patched_call.assert_called_once() # Check call was attempted
        assert isinstance(result, dict)
        assert result.get("error") is True
        assert result.get("type") == error_attrs["type"]
        # Use 'in' for message check due to potential variations (like request details)
        assert error_attrs["message"] in result.get("message", "")
        if "status_code" in error_attrs and error_attrs["status_code"]:
            assert result.get("status_code") == error_attrs["status_code"]


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type, init_args, error_attrs", [
     # FIX: Adjust APIError instantiation args and expected status code handling
    (APIError, {"message": "Claude stream processing error", "request": MagicMock(), "body": {"type": "error", "error": {"type": "internal_server_error"}}}, {"type": "APIError", "message": "Claude stream processing error", "status_code": 502}), # Add expected status code
    (TypeError, ("Bad data received",), {"type": "TypeError", "message": "Bad data received"}),
])
async def test_generate_completion_claude_error_during_stream_processing(
     error_type: type, init_args: Union[dict, tuple], error_attrs: dict
):
    """Tests handling errors raised while iterating through stream events."""
    # --- Arrange ---
    print(f"\nTesting Error During Stream Processing: {error_type.__name__}")
    if isinstance(init_args, dict):
        # FIX: Correct instantiation for APIError
        if error_type == APIError:
             error_to_raise = APIError(
                 message=init_args["message"],
                 request=init_args["request"],
                 body=init_args["body"]
             )
        else: # Fallback
             try: error_to_raise = error_type(**init_args)
             except TypeError: error_to_raise = error_type(*init_args.values())
    else:
        error_to_raise = error_type(*init_args)

    # FIX: Manually set status_code on a mock response if needed for testing _handle_anthropic_error
    if "status_code" in error_attrs and error_attrs["status_code"]:
        # Ensure the error object can hold a response
        if not hasattr(error_to_raise, 'response') or not error_to_raise.response:
             error_to_raise.response = MagicMock()
        error_to_raise.response.status_code = error_attrs["status_code"]


    mock_events_with_error = [
        create_mock_anthropic_stream_event("message_start", input_tokens=5),
        create_mock_anthropic_stream_event("content_block_delta", text_delta="OK "),
        error_to_raise # Error injected into the event stream
    ]
    mock_stream_method = MagicMock(return_value=MockAsyncStreamManager(mock_events_with_error))

    with patch.object(claude_client.client.messages, 'stream', mock_stream_method):
        # --- Act ---
        result_generator = await claude_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
        results = []
        # Consume the generator safely
        async for item in result_generator:
            results.append(item)

        # --- Assert ---
        assert len(results) == 2 # One delta, one error
        # Check delta
        assert results[0]["error"] is False
        assert results[0]["delta"] == "OK "
        # Check error
        error_result = results[1]
        assert error_result["error"] is True
        assert error_result["type"] == error_attrs["type"]
        assert error_attrs["message"] in error_result["message"]
        if "status_code" in error_attrs and error_attrs["status_code"]:
            assert error_result.get("status_code") == error_attrs["status_code"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
async def test_generate_completion_claude_client_not_initialized(stream_flag: bool, monkeypatch):
    """Tests behavior when Anthropic client is not initialized."""
    # --- Arrange ---
    monkeypatch.setattr(claude_client, "client", None)
    print("\n--- Testing Uninitialized Claude Client ---")
    # --- Act ---
    if stream_flag:
        result_generator = await claude_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
        results = [item async for item in result_generator]
        assert len(results) == 1
        result = results[0]
    else:
        result = await claude_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)
    # --- Assert ---
    assert result == {"error": True, "message": "Anthropic client not initialized...", "type": "ConfigurationError"}


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
async def test_generate_completion_claude_uses_default_max_tokens(stream_flag: bool): # FIX: Renamed test
    """Tests that default max_tokens is used when None is passed.""" # FIX: Updated docstring
    # --- Arrange ---
    mock_create_method = AsyncMock(return_value=create_mock_anthropic_message())
    # Need a mock stream manager for the streaming case
    mock_events = [
        create_mock_anthropic_stream_event("message_start", input_tokens=5),
        create_mock_anthropic_stream_event("content_block_delta", text_delta="Default"),
        create_mock_anthropic_stream_event("message_delta", stop_reason="stop_sequence", output_tokens=1),
        create_mock_anthropic_stream_event("message_stop"),
    ]
    mock_stream_method = MagicMock(return_value=MockAsyncStreamManager(mock_events))

    patch_create = patch.object(claude_client.client.messages, 'create', mock_create_method)
    patch_stream = patch.object(claude_client.client.messages, 'stream', mock_stream_method)

    with patch_create as patched_create, patch_stream as patched_stream:
        # --- Act ---
        # Explicitly pass max_tokens=None to the function
        if stream_flag:
            result_generator = await claude_client.generate_completion(
                messages=TEST_MESSAGES_BASE, max_tokens=None, stream=True
            )
            # Consume generator to ensure call happens
            results = [item async for item in result_generator]
            # We don't need to assert the results content here, just the call args
            patched_stream.assert_called_once()
            call_args, call_kwargs = patched_stream.call_args
            # Assert non-error in results (optional but good practice)
            assert results[-1].get("error") is False
        else:
             result = await claude_client.generate_completion(
                 messages=TEST_MESSAGES_BASE, max_tokens=None, stream=False
             )
             # Assert non-streaming result is not an error
             assert result.get("error") is False
             patched_create.assert_awaited_once()
             call_args, call_kwargs = patched_create.call_args

        # --- Assert ---
        # Check that the default max_tokens was included in the API call parameters
        assert "max_tokens" in call_kwargs
        assert call_kwargs.get("max_tokens") == DEFAULT_TOKENS # Check against the default

@pytest.mark.asyncio
async def test_non_streaming_claude_parsing_no_content():
    """Tests non-streaming parsing when API returns no content block."""
     # --- Arrange ---
    mock_response = create_mock_anthropic_message(content_text=None) # No text content
    mock_create_method = AsyncMock(return_value=mock_response)

    with patch.object(claude_client.client.messages, 'create', mock_create_method):
        # --- Act ---
        result = await claude_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)
        # --- Assert ---
        assert result["error"] is False
        assert result["content"] is None # Should be None if no text block
        assert result["finish_reason"] == "end_turn"
        assert result["usage"] is not None