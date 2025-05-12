"""
Final fixed version of OpenAI function calling tests.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import json
import asyncio

from integrations import openai_client

# Define role constants
USER_ROLE = "user"

@pytest.mark.asyncio
async def test_openai_function_call_final():
    """Test OpenAI function calling with proper mocking."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }
    
    # Define the function call arguments as a JSON string (exactly as OpenAI returns it)
    function_args_json = '{"location":"New York","unit":"celsius"}'
    
    # Create mock objects
    mock_function_call = MagicMock()
    mock_function_call.name = "get_weather"
    mock_function_call.arguments = function_args_json
    
    mock_message = MagicMock()
    mock_message.content = None
    mock_message.function_call = mock_function_call
    
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "function_call"
    
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.choices = [mock_choice]
    
    # Add usage info
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 15
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 25
    
    # Add model_dump method that matches the OpenAI response format
    mock_response.model_dump = MagicMock(return_value={
        "id": "mock-id",
        "model": "gpt-4o",
        "choices": [
            {
                "finish_reason": "function_call",
                "message": {
                    "content": None,
                    "function_call": {
                        "name": "get_weather",
                        "arguments": function_args_json
                    }
                }
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 10,
            "total_tokens": 25
        }
    })

    # Create the function definition
    weather_function = {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "The city name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["location"]
        }
    }
    
    # Create a fully mocked client that returns our prepared response
    mock_create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    
    # Apply the patch to replace the actual OpenAI client with our mock
    with patch.object(openai_client, "client", mock_client):
        # Verify our patch worked by checking the client
        assert openai_client.client == mock_client
        
        # Call the function with function definition
        response = await openai_client.generate_completion(
            messages=[message],
            functions=[weather_function],
            stream=False
        )
        
        # Verify that our mock was called
        mock_create.assert_called_once()
        
        # Now check the response
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "function_call"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        assert response["function_call"]["args"] == {"location": "New York", "unit": "celsius"}
        
        # Verify that the arguments are properly parsed
        assert isinstance(response["function_call"]["args"], dict)
        assert "location" in response["function_call"]["args"]
        assert response["function_call"]["args"]["location"] == "New York"
        assert response["function_call"]["args"]["unit"] == "celsius"
        
        # Verify usage info
        assert "usage" in response
        assert response["usage"]["prompt_tokens"] == 15
        assert response["usage"]["completion_tokens"] == 10
        assert response["usage"]["total_tokens"] == 25
