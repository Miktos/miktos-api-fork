"""
Test OpenAI client with proper mocking approach.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import json
import asyncio

from integrations import openai_client

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Fix for the mocking approach
@pytest.fixture
def mock_openai_client():
    """Create a properly mocked OpenAI client."""
    # Create a complete mock response
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "This is a mocked response"
    mock_response.choices[0].message.function_call = None

    # Add usage data
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 10 
    mock_response.usage.completion_tokens = 5
    mock_response.usage.total_tokens = 15

    # Add model_dump method
    mock_response.model_dump = MagicMock(return_value={
        "id": "mock-id",
        "model": "gpt-4o",
        "choices": [{"message": {"content": "This is a mocked response"}}]
    })

    # Create the mock client with the mock response
    mock_create = AsyncMock(return_value=mock_response)
    mock_chat = MagicMock()
    mock_chat.completions.create = mock_create
    
    mock_client = MagicMock()
    mock_client.chat = mock_chat

    return mock_client, mock_response, mock_create

@pytest.mark.asyncio
async def test_openai_basic(mock_openai_client):
    """Test basic OpenAI response with proper mocking."""
    mock_client, mock_response, mock_create = mock_openai_client
    
    # Create a message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "Hello",
        "role": USER_ROLE
    }
    
    # Apply the patch at module level to ensure proper mocking
    with patch.object(openai_client, "client", mock_client):
        # Call the function
        response = await openai_client.generate_completion(
            messages=[message],
            stream=False
        )
        
        # Verify mock was called
        mock_create.assert_called_once()
        
        # Check response
        assert response["error"] is False
        assert response["content"] == "This is a mocked response"
        assert "usage" in response
        assert response["usage"]["prompt_tokens"] == 10

@pytest.mark.asyncio
async def test_openai_function_calling(mock_openai_client):
    """Test OpenAI function calling with proper mocking."""
    mock_client, _, mock_create = mock_openai_client
    
    # Override the mock response for function calling
    function_call_mock = MagicMock()
    function_call_mock.name = "get_weather"
    function_call_mock.arguments = '{"location": "New York", "unit": "celsius"}'
    
    function_response = MagicMock()
    function_response.model = "gpt-4o"
    function_response.choices = [MagicMock()]
    function_response.choices[0].finish_reason = "function_call"
    function_response.choices[0].message = MagicMock()
    function_response.choices[0].message.content = None
    function_response.choices[0].message.function_call = function_call_mock
    
    function_response.usage = MagicMock()
    function_response.usage.prompt_tokens = 15
    function_response.usage.completion_tokens = 10
    function_response.usage.total_tokens = 25
    
    function_response.model_dump = MagicMock(return_value={
        "id": "mock-id",
        "model": "gpt-4o",
        "choices": [{
            "finish_reason": "function_call",
            "message": {
                "content": None,
                "function_call": {
                    "name": "get_weather",
                    "arguments": '{"location": "New York", "unit": "celsius"}'
                }
            }
        }]
    })
    
    # Update the mock to return our function call response
    mock_create.return_value = function_response
    
    # Create a message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }
    
    # Sample function definition
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
    
    # Apply the patch at module level
    with patch.object(openai_client, "client", mock_client):
        # Call the function with function definitions
        response = await openai_client.generate_completion(
            messages=[message],
            functions=[weather_function],
            stream=False
        )
        
        # Verify mock was called
        mock_create.assert_called_once()
        
        # Check function call response
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "function_call"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        assert response["function_call"]["args"]["location"] == "New York"
        assert response["function_call"]["args"]["unit"] == "celsius"
