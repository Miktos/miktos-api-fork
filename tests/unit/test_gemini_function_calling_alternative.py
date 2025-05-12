"""
Tests for Gemini client function calling in a new file
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid

# Import necessary modules
from integrations import gemini_client

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definitions
SAMPLE_FUNCTIONS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city name"
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
]


@pytest.mark.asyncio
async def test_gemini_function_calling_alternative():
    """Test that Gemini client correctly formats function calls - alternative implementation."""
    # Create a simple user message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in Paris?",
        "role": USER_ROLE
    }
    
    # Create a mock response with function call
    mock_response = MagicMock()
    mock_response.text = None  # No text content for function calls
    
    # Function call data
    function_call_data = {
        "name": "get_weather",
        "args": {
            "location": "Paris",
            "unit": "celsius"
        }
    }
    
    # Set up candidates with function call
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "FUNCTION_CALL"
    
    # Set up content with function call part
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = function_call_data
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidate to response
    mock_response.candidates = [mock_candidate]
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15
    
    # Mock the to_thread function to return our mock response
    mock_to_thread = AsyncMock(return_value=mock_response)
    
    # Apply patches
    with patch("integrations.gemini_client.asyncio.to_thread", mock_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Mock the GenerativeModel
            mock_genai.GenerativeModel = MagicMock()
            
            # Set up types for tools
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call the function with streaming disabled
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify the response format
            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "Paris"
            assert response["function_call"]["args"]["unit"] == "celsius"
            
            # Verify the to_thread mock was called
            mock_to_thread.assert_called_once()
