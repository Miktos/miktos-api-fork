import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid

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
                }
            },
            "required": ["location"]
        }
    }
]

@pytest.mark.asyncio
async def test_gemini_function_calling():
    """Test that function calling works properly with the Gemini client."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }
    
    # Create a mock function call response
    mock_function_call = {
        "name": "get_weather",
        "args": {
            "location": "New York"
        }
    }
    
    # Create a properly structured mock response
    mock_response = MagicMock()
    mock_response.text = None  # No text for function calls
    
    # Create mock candidates with function call
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "FUNCTION_CALL"
    
    # Create content with function call
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = mock_function_call
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidates to response
    mock_response.candidates = [mock_candidate]
    
    # Add usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15
    
    with patch("integrations.gemini_client.asyncio.to_thread", return_value=mock_response):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set up the genai module mocks
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Call the function with function definition
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify model was created with tools
            assert mock_genai.GenerativeModel.called
            
            # Verify response structure
            assert response is not None
            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            
            # Verify function call information
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "New York"
