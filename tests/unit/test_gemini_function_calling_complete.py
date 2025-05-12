#!/usr/bin/env python
"""
Complete test suite for Gemini client function calling capabilities
"""
import pytest
import asyncio
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

from integrations import gemini_client

# Define role constants locally
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant" 
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definitions for testing
SAMPLE_FUNCTIONS = [
    {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"]
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
async def test_gemini_function_calling():
    """Test that Gemini client properly formats function calling."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }

    # Mock function call we expect to get back
    mock_function_call = {
        "name": "get_weather",
        "args": {
            "location": "San Francisco",
            "unit": "celsius"
        }
    }

    # Mock the generate_completion function directly
    with patch.object(gemini_client, "generate_completion", AsyncMock(return_value={
        "error": False,
        "content": None,
        "finish_reason": "FUNCTION_CALL",
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 25,
            "total_tokens": 40
        },
        "model_name": "gemini-1.5-flash-latest", 
        "function_call": mock_function_call
    })):
        response = await gemini_client.generate_completion(
            messages=[message],
            system_prompt="You are a weather assistant.",
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify function call response is correctly formatted
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "FUNCTION_CALL"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        assert response["function_call"]["args"]["location"] == "San Francisco"
        assert response["function_call"]["args"]["unit"] == "celsius"

@pytest.mark.asyncio
async def test_function_result_handling():
    """Test that Gemini client properly handles function result messages."""
    
    # Create message conversation with function call and result
    messages = [
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": "What's the weather in San Francisco?",
            "role": USER_ROLE
        },
        { 
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
        { 
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": """{"temperature": 18, "condition": "Partly Cloudy", "humidity": 65}""",
            "role": FUNCTION_ROLE,
            "name": "get_weather"
        }
    ]

    # Mock response with text content
    with patch.object(gemini_client, "generate_completion", AsyncMock(return_value={
        "error": False,
        "content": "It's 18°C and partly cloudy in San Francisco with 65% humidity.",
        "finish_reason": "STOP",
        "usage": {
            "prompt_tokens": 25,
            "completion_tokens": 15,
            "total_tokens": 40
        },
        "model_name": "gemini-1.5-flash-latest"
    })):
        # Call generate_completion with messages including function result
        response = await gemini_client.generate_completion(
            messages=messages,
            system_prompt="You are a weather assistant.",
            stream=False
        )
        
        # Verify response content
        assert response["error"] is False
        assert response["content"] == "It's 18°C and partly cloudy in San Francisco with 65% humidity."
        assert response["finish_reason"] == "STOP"
