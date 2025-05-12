"""
Fixed implementation test for OpenAI client function calling capabilities.
This test ensures that the OpenAI API client correctly handles function calling
with proper mocking of async responses.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import json
from typing import Dict, Any, List

# Import client module
from integrations import openai_client

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definitions for testing
SAMPLE_FUNCTIONS = [
    {
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
]

@pytest.mark.asyncio
async def test_openai_function_calling_mocked():
    """Test that OpenAI client properly formats function calling."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }
    
    # Mock OpenAI's function call response
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.model_dump = MagicMock(return_value={
        "id": "chatcmpl-123",
        "choices": [{
            "finish_reason": "function_call",
            "message": {
                "content": None,
                "function_call": {
                    "name": "get_weather",
                    "arguments": '{"location": "San Francisco", "unit": "celsius"}'
                }
            }
        }]
    })
    
    # Set up choices properly
    mock_message = MagicMock()
    mock_message.content = None
    mock_message.function_call = MagicMock()
    mock_message.function_call.name = "get_weather"
    mock_message.function_call.arguments = '{"location": "San Francisco", "unit": "celsius"}'
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "function_call"
    
    mock_response.choices = [mock_choice]
    
    # Mock usage data
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 15
    mock_response.usage.completion_tokens = 25
    mock_response.usage.total_tokens = 40
    
    # Create mock OpenAI client
    mock_create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    
    # Setup patches with API key mock
    with patch("integrations.openai_client.get_client", return_value=mock_client), \
         patch("integrations.openai_client.client", mock_client), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"):
        
        # Call the function with function definitions
        response = await openai_client.generate_completion(
            messages=[message],
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify function call response is correctly formatted
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "function_call"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        
        # Check the arguments directly
        args = response["function_call"]["args"]
        assert args["location"] == "San Francisco"
        assert args["unit"] == "celsius"
        
        # Verify OpenAI client was called with correct parameters
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        
        # Check that required parameters were passed
        assert "messages" in call_kwargs
        assert "functions" in call_kwargs
        assert len(call_kwargs["functions"]) == len(SAMPLE_FUNCTIONS)
