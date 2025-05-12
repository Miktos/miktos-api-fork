"""
Integration tests for OpenAI client
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import asyncio
from typing import Dict, Any, List

# Import necessary modules
from integrations import openai_client
from config import settings

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definitions
SAMPLE_FUNCTIONS = [
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
    },
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
async def test_openai_function_calling():
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
        
        # Call the function with function definitions
        response = await openai_client.generate_completion(
            messages=[message],
            system_prompt="You are a weather assistant.",
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify model was called with correct parameters
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        
        # Verify functions were passed to the API
        assert "functions" in call_kwargs
        assert len(call_kwargs["functions"]) == len(SAMPLE_FUNCTIONS)
        
        # Verify function call response is correctly formatted
        assert response is not None
        assert response["error"] is False
        assert response["content"] is None  # No text content for function calls
        assert response["finish_reason"] == "function_call"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        assert "args" in response["function_call"]
        assert "location" in response["function_call"]["args"]
        assert response["function_call"]["args"]["location"] == "San Francisco"


@pytest.mark.asyncio
async def test_openai_function_result_handling():
    """Test that OpenAI client properly handles function result messages."""
    # Create message conversation with function call and result
    messages = [
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
            system_prompt="You are a weather assistant.",
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify regular text response after function call
        assert response is not None
        assert response["error"] is False
        assert response["content"] == "It's 18°C and partly cloudy in San Francisco with 65% humidity."
        assert response["finish_reason"] == "stop"
        
        # Verify function results were included in the API call
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        messages_passed = call_kwargs["messages"]
        
        # Ensure function result message was included
        function_messages = [msg for msg in messages_passed if msg.get("role") == "function"]
        assert len(function_messages) > 0
        assert any("get_weather" in str(msg) for msg in function_messages)
        assert any("temperature" in str(msg) for msg in function_messages)
        assert any("18" in str(msg) for msg in function_messages)
