"""
Simple test for function calling with Gemini
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import asyncio
from typing import Dict, Any, List

# Import necessary modules
from integrations import gemini_client

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Create a simple test function
SAMPLE_FUNCTION = {
    "name": "get_weather",
    "description": "Get current weather for a location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The city name"
            }
        },
        "required": ["location"]
    }
}

@pytest.mark.asyncio
async def test_gemini_function_call_simple():
    """A basic test for function calling."""
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
    
    # Create mock model
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    # Create a mock for _call_generate_content that properly tracks calls
    def mock_call_generate_impl(func, *args, **kwargs):
        # If this is the generate_content function, make the call to track it
        if func == mock_model.generate_content:
            func(*args, **kwargs)
        return mock_response
    
    # Patch all necessary dependencies
    with patch("integrations.gemini_client._call_generate_content", side_effect=mock_call_generate_impl), \
         patch("integrations.gemini_client.genai", autospec=True) as mock_genai, \
         patch("integrations.gemini_client.is_configured", True), \
         patch("integrations.gemini_client.configure_genai", return_value=True), \
         patch("integrations.gemini_client.settings.GOOGLE_API_KEY", "fake-api-key"):
        
        # Set up the GenerativeModel mock
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types = MagicMock()
        mock_genai.types.FunctionDeclaration = MagicMock()
        mock_genai.types.Tool = MagicMock()
        mock_genai.types.GenerationConfig = MagicMock()
        
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
