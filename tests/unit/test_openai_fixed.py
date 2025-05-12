"""
Fixed OpenAI function calling tests.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import asyncio
import json

from integrations import openai_client

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
async def test_openai_function_call_simple():
    """Simple test for OpenAI function calling."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?", 
        "role": USER_ROLE
    }
    
    # Mock response with function call
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "function_call"
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = None
    mock_response.choices[0].message.function_call = MagicMock()
    mock_response.choices[0].message.function_call.name = "get_weather"
    mock_response.choices[0].message.function_call.arguments = '{"location": "New York", "unit": "celsius"}'
    
    # Setup usage info
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 15
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 25
    
    # Add model_dump for raw response
    mock_response.model_dump = MagicMock(return_value={
        "id": "chatcmpl-123",
        "choices": [{
            "finish_reason": "function_call",
            "message": {
                "content": None,
                "function_call": {
                    "name": "get_weather",
                    "arguments": '{"location": "New York", "unit": "celsius"}'
                }
            }
        }],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 10,
            "total_tokens": 25
        },
        "model": "gpt-4o"
    })
    
    # Create mock completion create function
    mock_create = AsyncMock(return_value=mock_response)
    mock_chat = MagicMock()
    mock_chat.completions.create = mock_create
    mock_client = MagicMock()
    mock_client.chat = mock_chat
    
    # Setup patches - patch the client directly
    with patch("integrations.openai_client.get_client", return_value=mock_client), \
         patch("integrations.openai_client.client", mock_client), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"):
        
        # Call the function
        response = await openai_client.generate_completion(
            messages=[message],
            system_prompt="You are a weather assistant.",
            functions=[SAMPLE_FUNCTION],
            stream=False
        )
        
        # Verify the mock was called correctly
        mock_create.assert_called_once()
        
        # Check function call response
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "function_call"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        assert response["function_call"]["args"]["location"] == "New York"
        assert response["function_call"]["args"]["unit"] == "celsius"
