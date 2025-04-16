# tests/unit/test_openai_client.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
from typing import AsyncGenerator, Dict, Any # For type hinting generators

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