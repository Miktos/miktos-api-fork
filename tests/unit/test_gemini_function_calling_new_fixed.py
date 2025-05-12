"""
Fixed test suite for Gemini client function calling capabilities.
This test uses the _call_generate_content helper for mocking.
"""

import pytest
from unittest.mock import MagicMock, patch
import uuid
import sys
print(f"Python version: {sys.version}")
print(f"Test file is being loaded!")

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
async def test_fixed_function_calling():
    """Test that the Gemini client properly handles function calling."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }
    
    # Mock a function call response
    function_call_data = {
        "name": "get_weather",
        "args": {
            "location": "New York",
            "unit": "celsius"
        }
    }
    
    # Create mock response with the function call
    mock_response = MagicMock()
    mock_response.text = None  # Function calls don't have text
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "FUNCTION_CALL"
    
    # Set up content with function call
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = function_call_data
    mock_content.parts = [mock_part]
    mock_response.candidates[0].content = mock_content
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15
    
    # Mock _call_generate_content to call generate_content and return the mock response
    def mock_call_generate_impl(func, *args, **kwargs):
        # If this is the generate_content function, capture the call
        mock_model.generate_content(*args, **kwargs)
        return mock_response
    
    # Create patches
    with patch("integrations.gemini_client._call_generate_content", side_effect=mock_call_generate_impl):
        # Create mock for GenerativeModel
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Create mock model instance
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            
            # Set up the GenerativeModel mock
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock(return_value="mock_tool")
            mock_genai.types.FunctionDeclaration = MagicMock(return_value="mock_function_declaration")
            
            # Call function
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify model was created with tools
            mock_genai.GenerativeModel.assert_called_once()
            call_kwargs = mock_genai.GenerativeModel.call_args.kwargs
            assert "tools" in call_kwargs
            
            # Verify generate_content was called
            mock_model.generate_content.assert_called_once()
            
            # Verify function call in response
            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "New York"
            assert response["function_call"]["args"]["unit"] == "celsius"
