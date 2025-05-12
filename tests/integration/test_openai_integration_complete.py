"""
Fixed integration tests for OpenAI client function calling capabilities
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import json
from typing import Dict, Any, List

# Import the client
from integrations import openai_client

# Define role constants for easier reference
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
    },
    {
        "name": "search_database",
        "description": "Search for information in the database",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results"
                }
            },
            "required": ["query"]
        }
    }
]

@pytest.mark.asyncio
async def test_openai_function_calling():
    """Test that OpenAI client properly formats function calling."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }
    
    # System message should be included in the messages list, not as a separate parameter
    system_message = {
        "role": SYSTEM_ROLE,
        "content": "You are a weather assistant."
    }
    
    # Mock OpenAI's function call response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "function_call"
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = None
    mock_response.choices[0].message.function_call = {
        "name": "get_weather",
        "arguments": '{"location": "San Francisco", "unit": "celsius"}'
    }
    
    # Mock usage data
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 15
    mock_response.usage.completion_tokens = 25
    mock_response.usage.total_tokens = 40
    
    # Create mock OpenAI client
    mock_openai = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # Setup patches with API key mock
    with patch("integrations.openai_client.AsyncOpenAI", return_value=mock_openai), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"), \
         patch("integrations.openai_client.get_current_client", return_value=mock_openai):
        
        # Call the function with function definitions - use messages parameter for system prompt
        response = await openai_client.generate_completion(
            messages=[system_message, message],
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify function call response is correctly formatted
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "function_call"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        
        # Verify args - the response["function_call"] should have "args" not "arguments"
        assert "args" in response["function_call"]
        args = response["function_call"]["args"]
        assert args["location"] == "San Francisco"
        assert args["unit"] == "celsius"
        
        # Verify OpenAI client was called with correct parameters
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        
        # Check that required parameters were passed
        assert "messages" in call_kwargs
        assert "functions" in call_kwargs
        assert len(call_kwargs["functions"]) == len(SAMPLE_FUNCTIONS)

@pytest.mark.asyncio
async def test_openai_function_result_handling():
    """Test that OpenAI client properly handles function result messages."""
    # Create system message
    system_message = {
        "role": SYSTEM_ROLE,
        "content": "You are a weather assistant."
    }
    
    # Create message conversation with function call and result
    messages = [
        system_message,
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": "What's the weather in San Francisco?",
            "role": USER_ROLE
        },
        {  # This is a function call message
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": None,
            "role": ASSISTANT_ROLE,
            "function_call": {
                "name": "get_weather",
                "args": {
                    "location": "San Francisco",
                    "unit": "celsius"
                }
            }
        },
        {  # This is a function result message
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": '{"temperature": 18, "condition": "Partly Cloudy", "humidity": 65}',
            "role": FUNCTION_ROLE,
            "name": "get_weather"
        }
    ]
    
    # Mock normal text response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    
    # Mock usage data
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 25
    mock_response.usage.completion_tokens = 15
    mock_response.usage.total_tokens = 40
    
    # Create mock OpenAI client
    mock_openai = MagicMock()
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # Setup patches
    with patch("integrations.openai_client.AsyncOpenAI", return_value=mock_openai), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"), \
         patch("integrations.openai_client.get_current_client", return_value=mock_openai):
        
        # Call the function with the conversation including function result
        response = await openai_client.generate_completion(
            messages=messages,
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify regular text response after function call
        assert response is not None
        assert response["error"] is False
        assert response["content"] == "It's 18°C and partly cloudy in San Francisco with 65% humidity."
        assert response["finish_reason"] == "stop"
        
        # Verify OpenAI client was called with correct parameters
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        
        # Check that messages were properly formatted for OpenAI
        assert "messages" in call_kwargs
        assert len(call_kwargs["messages"]) >= 3  # System message, user message, and function result
        
        # Check that the function result was included
        has_function_message = False
        for msg in call_kwargs["messages"]:
            if msg.get("role") == "function":
                has_function_message = True
                break
                
        assert has_function_message
