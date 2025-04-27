# tests/unit/test_openai_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
from typing import AsyncGenerator, Dict, Any, Optional, List # For type hinting generators
from openai import RateLimitError # Import specific error

# Add the parent directory to PYTHONPATH (if needed, same as in test_orchestrator.py)
# Consider if there's a better way to handle path/discovery for your project setup

# Import the module we are testing
from integrations import openai_client

# Define some common test data
TEST_MESSAGES = [{"role": "user", "content": "Hello OpenAI"}]
DEFAULT_MODEL = openai_client.DEFAULT_OPENAI_MODEL

@pytest.mark.asyncio
async def test_generate_completion_openai_non_streaming_success():
    """
    Tests successful non-streaming completion from OpenAI client.
    """
    # --- Arrange ---
    # Mock the response object OpenAI SDK would return
    mock_openai_response = MagicMock()
    mock_openai_response.model = DEFAULT_MODEL
    # Mock the 'choices' attribute
    mock_choice = MagicMock()
    mock_choice.message.content = "This is the AI response."
    mock_choice.finish_reason = "stop"
    mock_openai_response.choices = [mock_choice]
    # Mock the 'usage' attribute
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 20
    mock_usage.total_tokens = 30
    mock_openai_response.usage = mock_usage
    # Mock the model_dump method for raw response storage
    mock_openai_response.model_dump.return_value = {"id": "chatcmpl-xxxx", "...": "..."}

    # Create an AsyncMock to represent the 'create' method
    mock_create_method = AsyncMock(return_value=mock_openai_response)

    # Patch the 'client' object within the 'openai_client' module
    # Specifically target the 'chat.completions.create' method path
    with patch('integrations.openai_client.client.chat.completions.create', mock_create_method) as patched_create:

        # --- Act ---
        result = await openai_client.generate_completion(
            messages=TEST_MESSAGES,
            model=DEFAULT_MODEL,
            stream=False,
            temperature=0.5 # Example override
        )

        # --- Assert ---
        # 1. Check if the mock was called correctly
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("model") == DEFAULT_MODEL
        assert call_kwargs.get("messages") == TEST_MESSAGES
        assert call_kwargs.get("stream") is False
        assert call_kwargs.get("temperature") == 0.5

        # 2. Check the structure and content of the returned dictionary
        assert isinstance(result, dict)
        assert result.get("error") is False
        assert result.get("content") == "This is the AI response."
        assert result.get("finish_reason") == "stop"
        assert result.get("model_name") == DEFAULT_MODEL
        assert result.get("usage") == {
            "prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30
        }
        assert "raw_response" in result
        assert result["raw_response"] == {"id": "chatcmpl-xxxx", "...": "..."}

# Helper to create mock stream chunks (mirroring OpenAI SDK structure)
def create_mock_stream_chunk(content: Optional[str] = None, finish_reason: Optional[str] = None, model: str = DEFAULT_MODEL):
    mock_chunk = MagicMock()
    mock_chunk.model = model
    mock_delta = MagicMock()
    mock_delta.content = content
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    mock_choice.finish_reason = finish_reason
    mock_chunk.choices = [mock_choice]
    return mock_chunk

# Mock async generator for the stream
async def mock_openai_stream_generator(chunks: List[MagicMock]):
    for chunk in chunks:
        yield chunk

@pytest.mark.asyncio
async def test_generate_completion_openai_streaming_success():
    """Tests successful streaming completion from OpenAI client."""
    # --- Arrange ---
    # Define the chunks the mock stream will yield
    mock_chunks_to_yield = [
        create_mock_stream_chunk(content="AI "),
        create_mock_stream_chunk(content="says "),
        create_mock_stream_chunk(content="hello!"),
        create_mock_stream_chunk(content=None, finish_reason="stop"), # Finish reason chunk
    ]
    mock_stream = mock_openai_stream_generator(mock_chunks_to_yield)

    # Create an AsyncMock for the 'create' method, returning the mock stream
    mock_create_method = AsyncMock(return_value=mock_stream)

    # Patch the 'create' method
    with patch('integrations.openai_client.client.chat.completions.create', mock_create_method) as patched_create:

        # --- Act ---
        # Call the function expecting a stream
        result_generator = await openai_client.generate_completion(
            messages=TEST_MESSAGES,
            model=DEFAULT_MODEL,
            stream=True,
        )

        # Consume the generator from our client function
        results = [item async for item in result_generator]

        # --- Assert ---
        # 1. Check API call
        patched_create.assert_awaited_once()
        call_args, call_kwargs = patched_create.call_args
        assert call_kwargs.get("model") == DEFAULT_MODEL
        assert call_kwargs.get("messages") == TEST_MESSAGES
        assert call_kwargs.get("stream") is True

        # 2. Check yielded results
        assert len(results) == 4 # 3 delta chunks + 1 final chunk
        # Check first delta chunk
        assert results[0] == {"error": False, "delta": "AI ", "is_final": False, "accumulated_content": "AI "}
        # Check second
        assert results[1] == {"error": False, "delta": "says ", "is_final": False, "accumulated_content": "AI says "}
        # Check third
        assert results[2] == {"error": False, "delta": "hello!", "is_final": False, "accumulated_content": "AI says hello!"}
        # Check final summary chunk
        assert results[3]["error"] is False
        assert results[3]["delta"] is None
        assert results[3]["is_final"] is True
        assert results[3]["accumulated_content"] == "AI says hello!"
        assert results[3]["finish_reason"] == "stop"
        assert results[3]["usage"] is None # Usage not available in stream
        assert results[3]["model_name"] == DEFAULT_MODEL

@pytest.mark.asyncio
@pytest.mark.parametrize("stream_flag", [True, False]) # Test both stream/non-stream
async def test_generate_completion_openai_api_error(stream_flag: bool):
    """Tests error handling for OpenAI API errors (e.g., RateLimitError)."""
    # --- Arrange ---
    error_to_raise = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(), # Mock response object if needed by error handler
        body={"code": "rate_limit_exceeded"} # Mock body if needed
    )
    # Set status_code if your handler uses it
    # error_to_raise.status_code = 429

    # Mock the 'create' method to raise the error
    mock_create_method = AsyncMock(side_effect=error_to_raise)

    with patch('integrations.openai_client.client.chat.completions.create', mock_create_method) as patched_create:

        # --- Act ---
        if stream_flag:
            result_generator = await openai_client.generate_completion(
                messages=TEST_MESSAGES, stream=True
            )
            results = [item async for item in result_generator]
            # Expecting a single error dictionary yielded
            assert len(results) == 1
            result = results[0]
        else:
            result = await openai_client.generate_completion(
                messages=TEST_MESSAGES, stream=False
            )

        # --- Assert ---
        # 1. Check API call was attempted
        patched_create.assert_awaited_once()

        # 2. Check the returned/yielded error dictionary
        assert isinstance(result, dict)
        assert result.get("error") is True
        assert "Rate limit exceeded" in result.get("message", "")
        assert result.get("type") == "RateLimitError"
        assert result.get("error_code") == "rate_limit_exceeded"
        # Assert status code if applicable and mocked
        # assert result.get("status_code") == 429