#!/usr/bin/env python
"""
Test file for Gemini function calling
"""
import pytest
import uuid
from unittest.mock import patch, AsyncMock

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
    }
]

@pytest.mark.asyncio
async def test_gemini_function_calling_simple():
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
