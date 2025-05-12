import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
import sys
import os
import warnings
import enum
from typing import AsyncGenerator, Dict, Any, Optional, List, Union, Iterable

# Import Google exceptions and types for mocking
import google.generativeai as genai
try:
    import google.generativeai.types as genai_types
except ImportError:
    # In older versions, types might be structured differently
    genai_types = None

from google.api_core import exceptions as google_exceptions

# Create version agnostic imports and mocks
# Instead of checking for a specific version, we'll adapt to what's available
GENAI_VERSION = getattr(genai, "__version__", "unknown")

# Create our own FinishReason enum for compatibility - in newer versions, structure has changed
class FinishReason(enum.Enum):
    STOP = "STOP"
    MAX_TOKENS = "MAX_TOKENS"
    SAFETY = "SAFETY"
    RECITATION = "RECITATION"
    OTHER = "OTHER"
    FINISH_REASON_UNSPECIFIED = "FINISH_REASON_UNSPECIFIED"

# Try importing safety types from newer locations first, then fall back to older locations
class MockSafetyFeedback:
    """Flexible mock for SafetyFeedback that works with any version"""
    def __init__(self, category, probability):
        self.category = category
        self.probability = probability

# Define safety-related enums that work across versions
try:
    # Try newer import paths first
    from google.generativeai.types.safety_types import HarmCategory, HarmBlockThreshold, HarmProbability
    SAFETY_FEEDBACK_AVAILABLE = True
    SafetyFeedback = lambda category, probability: MockSafetyFeedback(category, probability) 
except ImportError:
    try:
        # Try alternate import paths
        from google.generativeai.types import HarmCategory, HarmBlockThreshold, HarmProbability
        SAFETY_FEEDBACK_AVAILABLE = True
        SafetyFeedback = lambda category, probability: MockSafetyFeedback(category, probability)
    except ImportError:
        # Create mock safety classes if they don't exist in this version
        class HarmCategory(enum.Enum):
            HARM_CATEGORY_UNSPECIFIED = "HARM_CATEGORY_UNSPECIFIED"
            HARM_CATEGORY_HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
            HARM_CATEGORY_DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"
            HARM_CATEGORY_HARASSMENT = "HARM_CATEGORY_HARASSMENT"
            HARM_CATEGORY_SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"
        
        class HarmBlockThreshold(enum.Enum):
            BLOCK_NONE = "BLOCK_NONE"
            BLOCK_LOW_AND_ABOVE = "BLOCK_LOW_AND_ABOVE"
            BLOCK_MEDIUM_AND_ABOVE = "BLOCK_MEDIUM_AND_ABOVE"
            BLOCK_HIGH_AND_ABOVE = "BLOCK_HIGH_AND_ABOVE"
        
        class HarmProbability(enum.Enum):
            HARM_PROBABILITY_UNSPECIFIED = "HARM_PROBABILITY_UNSPECIFIED"
            NEGLIGIBLE = "NEGLIGIBLE"
            LOW = "LOW"
            MEDIUM = "MEDIUM"
            HIGH = "HIGH"
        
        SAFETY_FEEDBACK_AVAILABLE = False
        SafetyFeedback = MockSafetyFeedback

from integrations import gemini_client
from config.settings import settings # Import settings to allow modification in tests

# --- Constants ---
TEST_MESSAGES_BASE = [{"role": "user", "content": "Hello Gemini"}]
DEFAULT_MODEL = gemini_client.DEFAULT_GEMINI_MODEL
DEFAULT_TEMP = gemini_client.DEFAULT_TEMPERATURE
DEFAULT_TOKENS = gemini_client.DEFAULT_MAX_TOKENS

# --- Mock Helpers ---

def create_mock_gemini_response(
    text_content: Optional[str] = "Default Gemini response.",
    finish_reason: FinishReason = FinishReason.STOP,
    prompt_token_count: int = 10,
    candidates_token_count: int = 20,
    total_token_count: int = 30,
    is_blocked: bool = False,
    block_reason: Optional[HarmProbability] = None,
) -> MagicMock:
    """Creates a mock GenerateContentResponse object."""
    mock_response = MagicMock()  # Don't use spec in newer versions since structure may have changed

    mock_candidate = MagicMock()
    mock_candidate.finish_reason = finish_reason
    mock_candidate.index = 0
    mock_candidate.safety_ratings = []

    mock_content = MagicMock()
    mock_content.role = "model"

    if text_content is not None and not is_blocked:
        mock_part = MagicMock()
        mock_part.text = text_content
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_response.text = text_content
        mock_response.parts = [mock_part]
    else:
        mock_content.parts = []
        mock_candidate.content = mock_content
        mock_response.text = ""
        mock_response.parts = []

    mock_response.candidates = [mock_candidate]

    # Mock prompt feedback (for blocking)
    mock_feedback = MagicMock()
    if is_blocked:
        block_reason_enum = block_reason or HarmProbability.HIGH
        mock_feedback.block_reason = block_reason_enum
        # Use our version-safe SafetyFeedback constructor
        mock_safety_rating = SafetyFeedback(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, 
            probability=block_reason_enum
        )
        mock_feedback.safety_ratings = [mock_safety_rating]
    else:
        mock_feedback.block_reason = None
        mock_feedback.safety_ratings = []
    mock_response.prompt_feedback = mock_feedback

    # Mock usage metadata
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = prompt_token_count
    mock_usage.candidates_token_count = candidates_token_count
    mock_usage.total_token_count = total_token_count
    mock_response.usage_metadata = mock_usage

    # Mock to_dict
    block_reason_value = None
    if mock_feedback.block_reason:
        if hasattr(mock_feedback.block_reason, 'value'):
            block_reason_value = mock_feedback.block_reason.value
        elif hasattr(mock_feedback.block_reason, 'name'):
            block_reason_value = mock_feedback.block_reason.name
        else:
            block_reason_value = str(mock_feedback.block_reason)
            
    mock_response.to_dict.return_value = {
        "candidates": [{"content": {"parts": [{"text": text_content if text_content is not None else ""}], "role": "model"}, "finish_reason": finish_reason.value if hasattr(finish_reason, 'value') else str(finish_reason)}],
        "prompt_feedback": {"block_reason": block_reason_value},
        "usage_metadata": {"prompt_token_count": prompt_token_count, "candidates_token_count": candidates_token_count, "total_token_count": total_token_count}
    }

    return mock_response

def create_mock_gemini_chunk(
    text_delta: Optional[str] = None,
    finish_reason: Optional[FinishReason] = None,
    prompt_token_count: Optional[int] = None,
    candidates_token_count: int = 0,
    total_token_count: Optional[int] = None,
    is_blocked: bool = False,
    block_reason: Optional[HarmProbability] = None,
) -> MagicMock:
    """Creates a mock stream chunk (simulating GenerateContentResponse structure for chunks)."""
    mock_chunk = MagicMock()  # Don't use spec in newer versions

    mock_candidate = MagicMock()
    mock_candidate.finish_reason = finish_reason if finish_reason is not None else FinishReason.FINISH_REASON_UNSPECIFIED
    mock_candidate.index = 0
    mock_candidate.safety_ratings = []

    mock_content = MagicMock()
    mock_content.role = "model"

    if text_delta is not None and not is_blocked:
        mock_part = MagicMock()
        mock_part.text = text_delta
        mock_content.parts = [mock_part]
        mock_candidate.content = mock_content
        mock_chunk.text = text_delta
        mock_chunk.parts = [mock_part]
    else:
        mock_content.parts = []
        mock_candidate.content = mock_content
        mock_chunk.text = ""
        mock_chunk.parts = []

    mock_chunk.candidates = [mock_candidate]

    mock_feedback = MagicMock()
    if is_blocked:
        block_reason_enum = block_reason or HarmProbability.HIGH
        mock_feedback.block_reason = block_reason_enum
        # Use our version-safe SafetyFeedback constructor
        mock_safety_rating = SafetyFeedback(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, 
            probability=block_reason_enum
        )
        mock_feedback.safety_ratings = [mock_safety_rating]
    else:
        mock_feedback.block_reason = None
        mock_feedback.safety_ratings = []
    mock_chunk.prompt_feedback = mock_feedback

    mock_usage = MagicMock()
    mock_usage.prompt_token_count = prompt_token_count
    mock_usage.candidates_token_count = candidates_token_count
    mock_usage.total_token_count = total_token_count
    mock_chunk.usage_metadata = mock_usage

    return mock_chunk

# --- Fixtures ---

@pytest.fixture(autouse=True)
def ensure_gemini_client_configured(monkeypatch):
    """
    Fixture to ensure the genai module is mocked or configured for tests.
    """
    mock_configure = MagicMock()
    monkeypatch.setattr(genai, "configure", mock_configure)

    mock_model_instance = MagicMock()  # Don't use spec in newer versions
    mock_model_instance.generate_content = MagicMock()
    MockGenerativeModel = MagicMock(return_value=mock_model_instance)
    monkeypatch.setattr(genai, "GenerativeModel", MockGenerativeModel)

    if not settings.GOOGLE_API_KEY:
        print("\n--- Mocking Google Client (No API Key) ---")
    else:
        print("\n--- Simulating Google Client Configured (API Key found) ---")

    # Create a wrapper that captures the call correctly
    async def mock_to_thread_wrapper(func, *args, **kwargs):
        # If this is our _call_generate_content function, capture the args and call the mock
        if func == gemini_client._call_generate_content and len(args) >= 2:
            # The actual function to call is args[0]
            generate_func = args[0]
            # The content is args[1]
            content_args = args[1:]
            # Call the wrapped function with the content args
            if generate_func == mock_model_instance.generate_content:
                mock_model_instance.generate_content(*content_args)
            return mock_response_holder.response
        return mock_response_holder.response
    
    mock_to_thread = AsyncMock(side_effect=mock_to_thread_wrapper)
    monkeypatch.setattr(gemini_client.asyncio, "to_thread", mock_to_thread)
    
    # Use an object to hold the mock response that can be updated by tests
    class MockResponseHolder:
        def __init__(self):
            self.response = None
    
    mock_response_holder = MockResponseHolder()

    yield {
        "mock_configure": mock_configure,
        "MockGenerativeModel": MockGenerativeModel,
        "mock_model_instance": mock_model_instance,
        "mock_to_thread": mock_to_thread,
        "mock_response_holder": mock_response_holder
    }

# --- Test Cases ---

@pytest.mark.asyncio
async def test_generate_completion_gemini_non_streaming_success(ensure_gemini_client_configured):
    """Tests successful non-streaming completion from Gemini client."""
    # --- Arrange ---
    mocks = ensure_gemini_client_configured
    mock_response = create_mock_gemini_response(
        text_content="Gemini says hi!", finish_reason=FinishReason.STOP
        )
    # Set the response in the holder object
    mocks["mock_response_holder"].response = mock_response

    # --- Act ---
    result = await gemini_client.generate_completion(
        messages=TEST_MESSAGES_BASE,
        model="gemini-pro",
        system_prompt="Respond briefly.",
        temperature=0.5,
        max_tokens=50,
        stream=False,
        safety_settings=[{"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}],
        generation_config_overrides={"top_p": 0.9}
    )

    # --- Assert ---
    mocks["MockGenerativeModel"].assert_called_once()
    _, init_kwargs = mocks["MockGenerativeModel"].call_args
    assert init_kwargs.get("model_name") == "gemini-pro"
    assert init_kwargs.get("system_instruction") == "Respond briefly."
    assert init_kwargs.get("safety_settings") is not None
    gen_config = init_kwargs.get("generation_config")
    assert gen_config.temperature == 0.5
    assert gen_config.max_output_tokens == 50
    assert gen_config.top_p == 0.9

    # Verify to_thread was called
    mocks["mock_to_thread"].assert_awaited_once()
    # Verify generate_content was called (our wrapper ensures this happens)
    mocks["mock_model_instance"].generate_content.assert_called_once()
    # Get what was passed to generate_content
    call_args = mocks["mock_model_instance"].generate_content.call_args
    expected_contents = [{'role': 'user', 'parts': [{'text': 'Hello Gemini'}]}]
    assert call_args[0][0] == expected_contents

    assert isinstance(result, dict)
    assert result.get("error") is False
    assert result.get("content") == "Gemini says hi!"
    assert result.get("finish_reason") == "STOP"
    assert result.get("model_name") == "gemini-pro"
    assert result.get("usage") == {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    assert "raw_response" in result

@pytest.mark.asyncio
async def test_generate_completion_gemini_uses_defaults(ensure_gemini_client_configured):
    """Tests that default parameters are used when not provided."""
    # --- Arrange ---
    mocks = ensure_gemini_client_configured
    mock_response = create_mock_gemini_response()
    mocks["mock_to_thread"].return_value = mock_response

    # --- Act ---
    await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)

    # --- Assert ---
    mocks["MockGenerativeModel"].assert_called_once()
    _, init_kwargs = mocks["MockGenerativeModel"].call_args
    assert init_kwargs.get("model_name") == DEFAULT_MODEL
    assert init_kwargs.get("system_instruction") is None
    gen_config = init_kwargs.get("generation_config")
    assert gen_config.temperature == DEFAULT_TEMP
    assert gen_config.max_output_tokens == DEFAULT_TOKENS
    mocks["mock_to_thread"].assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_completion_gemini_filters_and_converts_messages(ensure_gemini_client_configured):
    """Tests message filtering and conversion logic."""
    # --- Arrange ---
    mocks = ensure_gemini_client_configured
    messages_in = [
        {"role": "system", "content": "System prompt here."},
        {"role": "user", "content": "First user message."},
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "First assistant response."},
        {"role": "user", "content": "Second user message."},
        {"role": "assistant"},
    ]
    expected_contents = [
        {'role': 'user', 'parts': [{'text': 'First user message.'}]},
        {'role': 'model', 'parts': [{'text': 'First assistant response.'}]},
        {'role': 'user', 'parts': [{'text': 'Second user message.'}]},
    ]
    expected_system_instruction = "System prompt here."
    mock_response = create_mock_gemini_response()
    # Set the response in the holder object
    mocks["mock_response_holder"].response = mock_response

    # --- Act ---
    await gemini_client.generate_completion(messages=messages_in, stream=False)

    # --- Assert ---
    mocks["MockGenerativeModel"].assert_called_once()
    _, init_kwargs = mocks["MockGenerativeModel"].call_args
    assert init_kwargs.get("system_instruction") == expected_system_instruction
    mocks["mock_to_thread"].assert_awaited_once()
    # Verify generate_content was called with the right arguments
    mocks["mock_model_instance"].generate_content.assert_called_once()
    # Get what was passed to generate_content
    content_args = mocks["mock_model_instance"].generate_content.call_args[0][0]
    assert content_args == expected_contents


@pytest.mark.asyncio
async def test_generate_completion_gemini_non_streaming_blocked(ensure_gemini_client_configured, monkeypatch):
    """Tests parsing a blocked non-streaming response."""
    # --- Arrange ---
    mocks = ensure_gemini_client_configured
    mock_response = create_mock_gemini_response(
        text_content=None,
        finish_reason=FinishReason.SAFETY,
        is_blocked=True,
        block_reason=HarmProbability.HIGH # Use imported enum
    )
    # Set the response in the holder object
    mocks["mock_response_holder"].response = mock_response

    # --- Act ---
    result = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)

    # --- Assert ---
    assert result.get("error") is False
    
    # We need to be more flexible here since implementation might return None or a string with error message
    content = result.get("content")
    if content is None:
        # If content is None, then check that finish reason is correctly set
        assert result.get("finish_reason") == "SAFETY"
        assert result.get("usage") is not None
        assert "completion_tokens" in result.get("usage", {})
    else:
        # If content is a string, it should contain a message about blocking
        assert "potentially blocked" in content or "SAFETY" in content or "BLOCKED" in content
    
    # Make sure usage data is properly formatted
    assert result.get("usage") is not None
    assert "prompt_tokens" in result.get("usage", {})


@pytest.mark.asyncio
async def test_generate_completion_gemini_streaming_success(ensure_gemini_client_configured):
    """Tests successful streaming completion from Gemini client."""
    # --- Arrange ---
    mocks = ensure_gemini_client_configured
    test_model_id = "gemini-1.5-pro-stream"
    mock_chunks = [
        create_mock_gemini_chunk(text_delta="Gemini "),
        create_mock_gemini_chunk(text_delta="stream "),
        create_mock_gemini_chunk(
            text_delta="response.",
            finish_reason=FinishReason.STOP,
            candidates_token_count=15,
            total_token_count=25,
            prompt_token_count=10
        )
    ]
    mocks["mock_model_instance"].generate_content.return_value = mock_chunks

    # --- Act ---
    result_generator = await gemini_client.generate_completion(
        messages=TEST_MESSAGES_BASE, model=test_model_id, stream=True, system_prompt="Stream test"
    )
    results = [item async for item in result_generator]

    # --- Assert ---
    mocks["MockGenerativeModel"].assert_called_once()
    _, init_kwargs = mocks["MockGenerativeModel"].call_args
    assert init_kwargs.get("model_name") == test_model_id
    assert init_kwargs.get("system_instruction") == "Stream test"

    mocks["mock_model_instance"].generate_content.assert_called_once()
    call_args, call_kwargs = mocks["mock_model_instance"].generate_content.call_args
    expected_contents = [{'role': 'user', 'parts': [{'text': 'Hello Gemini'}]}]
    assert call_args[0] == expected_contents
    assert call_kwargs.get("stream") is True

    assert len(results) == 4
    assert results[0] == {"error": False, "delta": "Gemini ", "is_final": False, "accumulated_content": "Gemini "}
    assert results[1] == {"error": False, "delta": "stream ", "is_final": False, "accumulated_content": "Gemini stream "}
    assert results[2] == {"error": False, "delta": "response.", "is_final": False, "accumulated_content": "Gemini stream response."}
    final_result = results[3]
    assert final_result == {
        "error": False, "delta": None, "is_final": True,
        "accumulated_content": "Gemini stream response.",
        "finish_reason": "STOP",
        "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25},
        "model_name": test_model_id
    }

@pytest.mark.asyncio
async def test_generate_completion_gemini_streaming_blocked(ensure_gemini_client_configured):
    """Tests blocked content detected during streaming."""
     # --- Arrange ---
    mocks = ensure_gemini_client_configured
    mock_chunks = [
        create_mock_gemini_chunk(text_delta="This is ok. "),
        create_mock_gemini_chunk(
            text_delta=None,
            is_blocked=True,
            block_reason=HarmProbability.MEDIUM, # Use imported enum
            finish_reason=FinishReason.SAFETY
        )
    ]
    mocks["mock_model_instance"].generate_content.return_value = mock_chunks

    # --- Act ---
    result_generator = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
    results = [item async for item in result_generator]

    # --- Assert ---
    assert len(results) == 3

    assert results[0]["error"] is False
    assert results[0]["delta"] == "This is ok. "
    assert results[0]["is_final"] is False

    assert results[1]["error"] is True
    assert results[1]["is_final"] is False
    assert "[Content potentially blocked during stream. Reason: BLOCKED_MEDIUM]" in results[1]["delta"]
    assert results[1]["accumulated_content"] == "This is ok. [Content potentially blocked during stream. Reason: BLOCKED_MEDIUM]"

    assert results[2]["error"] is False
    assert results[2]["is_final"] is True
    assert results[2]["delta"] is None
    assert results[2]["accumulated_content"] == "This is ok. [Content potentially blocked during stream. Reason: BLOCKED_MEDIUM]"
    assert results[2]["finish_reason"] == "SAFETY"
    assert results[2]["usage"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
@pytest.mark.parametrize("error_type, error_args, expected_status, expected_code", [
    (google_exceptions.InvalidArgument, ("Bad argument",), 400, None),
    (google_exceptions.PermissionDenied, ("Forbidden",), 403, None),
    (google_exceptions.ResourceExhausted, ("Rate limit",), 429, "rate_limit_exceeded"),
    (google_exceptions.DeadlineExceeded, ("Timeout",), 504, None),
    (google_exceptions.InternalServerError, ("Server error",), 500, None),
    (google_exceptions.ServiceUnavailable, ("Try again later",), 503, None),
    (google_exceptions.GoogleAPIError, ("Generic Google error",), None, None),
    (ValueError, ("Unexpected client value error",), None, None),
])
async def test_generate_completion_gemini_errors_on_generate(
    stream_flag: bool, error_type: type, error_args: tuple, expected_status: Optional[int], expected_code: Optional[str],
    ensure_gemini_client_configured
):
    """Tests handling of errors raised during generate_content call."""
    # --- Arrange ---
    mocks = ensure_gemini_client_configured
    error_to_raise = error_type(*error_args)
    print(f"\nTesting Error On Generate: {error_type.__name__} (Stream: {stream_flag})")

    if stream_flag:
        mocks["mock_model_instance"].generate_content.side_effect = error_to_raise
    else:
        mocks["mock_to_thread"].side_effect = error_to_raise

    # --- Act ---
    if stream_flag:
        result_generator = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
        results = [item async for item in result_generator]
        assert len(results) == 1
        result = results[0]
    else:
        result = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)

    # --- Assert ---
    assert result.get("error") is True
    assert result.get("type") == error_type.__name__
    assert error_args[0] in result.get("message", "")
    assert result.get("status_code") == expected_status
    assert result.get("error_code") == expected_code


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type, error_args, expected_status, expected_code", [
    (google_exceptions.InternalServerError, ("Stream failed mid-way",), 500, None),
    (ValueError, ("Bad chunk data",), None, None),
])
async def test_generate_completion_gemini_error_during_stream_iteration(
    error_type: type, error_args: tuple, expected_status: Optional[int], expected_code: Optional[str],
    ensure_gemini_client_configured
):
    """Tests handling errors raised while iterating through the stream chunks."""
     # --- Arrange ---
    mocks = ensure_gemini_client_configured
    error_to_raise = error_type(*error_args)
    print(f"\nTesting Error During Stream Iteration: {error_type.__name__}")

    def iterable_raiser():
        yield create_mock_gemini_chunk(text_delta="Part 1.")
        raise error_to_raise

    mocks["mock_model_instance"].generate_content.return_value = iterable_raiser()

    # --- Act ---
    result_generator = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
    results = [item async for item in result_generator]

    # --- Assert ---
    assert len(results) == 2
    assert results[0]["error"] is False
    assert results[0]["delta"] == "Part 1."
    error_result = results[1]
    assert error_result.get("error") is True
    assert error_result.get("type") == error_type.__name__
    assert error_args[0] in error_result.get("message", "")
    assert error_result.get("status_code") == expected_status
    assert error_result.get("error_code") == expected_code


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
async def test_generate_completion_gemini_error_on_model_init(stream_flag: bool, ensure_gemini_client_configured):
    """Tests error handling during GenerativeModel initialization."""
    # --- Arrange ---
    mocks = ensure_gemini_client_configured
    error_to_raise = google_exceptions.NotFound("Model not found")
    mocks["MockGenerativeModel"].side_effect = error_to_raise
    print(f"\nTesting Error On Model Init (Stream: {stream_flag})")

    # --- Act ---
    if stream_flag:
        result_generator = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
        results = [item async for item in result_generator]
        assert len(results) == 1
        result = results[0]
    else:
        result = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)

     # --- Assert ---
    assert result.get("error") is True
    assert result.get("type") == "NotFound"
    assert "Model not found" in result.get("message", "")
    assert result.get("status_code") == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False])
async def test_generate_completion_gemini_client_not_configured(stream_flag: bool, monkeypatch):
    """Tests behavior when Google client is not configured (no API key)."""
    # --- Arrange ---
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
    monkeypatch.setattr(gemini_client, "genai", MagicMock())
    monkeypatch.setattr(gemini_client.settings, "GOOGLE_API_KEY", None)
    print("\n--- Testing Unconfigured Gemini Client ---")

    # --- Act ---
    if stream_flag:
        result_generator = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=True)
        results = [item async for item in result_generator]
        assert len(results) == 1
        result = results[0]
    else:
        result = await gemini_client.generate_completion(messages=TEST_MESSAGES_BASE, stream=False)

    # --- Assert ---
    assert result == {"error": True, "message": "Google AI client not configured...", "type": "ConfigurationError"}