"""
Tests for Gemini client function calling capabilities - basic test with fixed mocking
"""

import pytest
from unittest.mock import MagicMock, patch
import uuid
import asyncio
import json

# Import necessary modules
from integrations import gemini_client

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definition
SAMPLE_FUNCTION = {
    "name": "get_weather",
    "description": "Get current weather for a location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city and state"
            },
            "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit"
            }
        },
        "required": ["location"]
    }
}

@pytest.mark.asyncio
async def test_gemini_function_call_simple():
    """A basic test for function calling with proper mocking."""
    # Create simple message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }

    # Create a mock function call response
    mock_response = MagicMock()

    # Set up the function call data
    mock_function_call = {
        "name": "get_weather",
        "args": {
            "location": "New York"
        }
    }

    # Set up the response objects
    mock_finish_reason = MagicMock()
    mock_finish_reason.name = "FUNCTION_CALL"

    # Set up content parts with function call
    mock_part = MagicMock()
    mock_part.function_call = mock_function_call
    mock_part.text = None

    # Create content object
    mock_content = MagicMock()
    mock_content.parts = [mock_part]

    # Create candidate
    mock_candidate = MagicMock()
    mock_candidate.content = mock_content
    mock_candidate.finish_reason = mock_finish_reason

    # Add candidates to response
    mock_response.candidates = [mock_candidate]
    mock_response.text = None

    # Add usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15

    # Create mock model - we need to ensure the function is called properly
    mock_model = MagicMock()  
    mock_model.generate_content.return_value = mock_response
    
    # Custom mock for to_thread that ensures the function gets called
    async def mock_to_thread(func, *args, **kwargs):
        # Call the generate_content function and then return the mock
        if args and len(args) > 0:
            mock_model.generate_content(*args, **kwargs)
        return mock_response  # Return the pre-configured mock response
    
    # Patch all necessary dependencies
    with patch("integrations.gemini_client.genai", autospec=True) as mock_genai, \
         patch("integrations.gemini_client.asyncio.to_thread", side_effect=mock_to_thread), \
         patch("integrations.gemini_client.settings.GOOGLE_API_KEY", "fake-api-key"):

        # Set up the GenerativeModel mock
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types = MagicMock()

        # Call the function with function definition
        response = await gemini_client.generate_completion(
            messages=[message],
            system_prompt="You are a weather assistant.",
            functions=[SAMPLE_FUNCTION],
            stream=False
        )

        # Basic assertions
        assert response is not None
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "FUNCTION_CALL"

        # Verify function call information
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        assert response["function_call"]["args"]["location"] == "New York"

        # Verify the model was called
        assert mock_model.generate_content.called
