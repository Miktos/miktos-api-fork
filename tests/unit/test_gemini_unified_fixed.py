"""
This test is to fix issues with function calling in gemini_client.py
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import asyncio
from integrations import gemini_client

# Constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample test function
SAMPLE_FUNCTION = {
    "name": "get_weather",
    "description": "Get weather for a location",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
        },
        "required": ["location"]
    }
}

def test_gemini_single_function_call():
    """Basic test to ensure function call formatting."""
    # Create mock response with function call
    mock_function_call = {
        "name": "get_weather", 
        "args": {"location": "Paris"}
    }
    
    # Test that our format_function_call method works correctly
    result = gemini_client.format_function_call(mock_function_call)
    assert result["name"] == "get_weather"
    assert result["args"]["location"] == "Paris"


@pytest.mark.asyncio
async def test_gemini_function_calling_fixed_direct():
    """Test directly mocking function calls to verify correct handling."""
    message = {"content": "What's the weather?", "role": USER_ROLE}
    
    # Mock direct dict response that would normally be sent by to_thread
    mock_response = {
        "error": False,
        "content": None,
        "finish_reason": "FUNCTION_CALL",
        "function_call": {
            "name": "get_weather",
            "args": {"location": "Paris"}
        }
    }
    
    # Create a mock for to_thread that returns our mock_response
    async def mock_to_thread(func, *args, **kwargs):
        return mock_response
    
    # Apply patches
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=mock_to_thread), \
         patch("integrations.gemini_client.settings.GOOGLE_API_KEY", "fake-api-key"):
        
        # Call the function
        result = await gemini_client.generate_completion(
            messages=[message],
            functions=[SAMPLE_FUNCTION],
            stream=False
        )
        
        # Verify function call is passed through
        assert result["function_call"]["name"] == "get_weather"
        assert result["function_call"]["args"]["location"] == "Paris"
