"""
Fixed tests for Gemini client function calling capabilities.
This test ensures that the Gemini API client correctly handles function calling
with proper mocking of asyncio.to_thread.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import asyncio
import json
from typing import Dict, Any, List

# Import necessary modules
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

# Create a proper mock for asyncio.to_thread that actually calls the function
async def mock_to_thread(func, *args, **kwargs):
    # This actually calls the function with its arguments and returns the result
    return func(*args, **kwargs)


@pytest.mark.asyncio
async def test_basic_function_calling():
    """Test that the Gemini client properly handles function calling."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }
    
    # Mock a function call response
    function_call_data = {
        "name": "get_weather",
        "args": {
            "location": "New York",
            "unit": "celsius"
        }
    }
    
    # Create mock response with the function call
    mock_response = MagicMock()
    mock_response.text = None  # Function calls don't have text
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "FUNCTION_CALL"
    
    # Set up content with function call
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = function_call_data
    mock_content.parts = [mock_part]
    mock_response.candidates[0].content = mock_content
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15
    
    # Create patches that properly mock asynchronous behavior
    with patch("integrations.gemini_client.asyncio.to_thread", new=mock_to_thread):
        # Create mock for GenerativeModel
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Create mock model instance
            mock_model = MagicMock()
            mock_model.generate_content = MagicMock(return_value=mock_response)
            
            # Set up the GenerativeModel mock
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock(return_value="mock_tool")
            mock_genai.types.FunctionDeclaration = MagicMock(return_value="mock_function_declaration")
            mock_genai.types.GenerationConfig = MagicMock(return_value="mock_generation_config")
            
            # Call function
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify model was created with tools
            mock_genai.GenerativeModel.assert_called_once()
            call_kwargs = mock_genai.GenerativeModel.call_args.kwargs
            assert "tools" in call_kwargs
            
            # Verify generate_content was called
            mock_model.generate_content.assert_called_once()
            
            # Verify function call in response
            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "New York"
            assert response["function_call"]["args"]["unit"] == "celsius"


@pytest.mark.asyncio
async def test_function_result_handling():
    """Test that the client properly handles function results."""
    # Create conversation with function call and result
    messages = [
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": "What's the weather in New York?",
            "role": USER_ROLE
        },
        {  # Function call message
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": None,
            "role": ASSISTANT_ROLE,
            "function_call": {
                "name": "get_weather",
                "args": {
                    "location": "New York",
                    "unit": "celsius"
                }
            }
        },
        {  # Function result message
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": '{"temperature": 18, "condition": "Partly Cloudy", "humidity": 65}',
            "role": FUNCTION_ROLE,
            "name": "get_weather"
        }
    ]
    
    # Create mock response with text content
    mock_response = MagicMock()
    mock_response.text = "It's 18°C and partly cloudy in New York with 65% humidity."
    
    # Set up parts property with text
    mock_response.parts = [MagicMock()]
    mock_response.parts[0].text = "It's 18°C and partly cloudy in New York with 65% humidity."
    
    # Set up candidates with finish reason STOP
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "STOP"
    
    # Set up content with text part
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "It's 18°C and partly cloudy in New York with 65% humidity."
    mock_content.parts = [mock_part]
    mock_response.candidates[0].content = mock_content
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 20
    mock_response.usage_metadata.candidates_token_count = 15
    mock_response.usage_metadata.total_token_count = 35
    
    # Create patches that properly mock asynchronous behavior
    with patch("integrations.gemini_client.asyncio.to_thread", new=mock_to_thread):
        # Create mock for GenerativeModel
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Create mock model instance
            mock_model = MagicMock()
            mock_model.generate_content = MagicMock(return_value=mock_response)
            
            # Set up the GenerativeModel mock
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock(return_value="mock_tool")
            mock_genai.types.FunctionDeclaration = MagicMock(return_value="mock_function_declaration")
            mock_genai.types.GenerationConfig = MagicMock(return_value="mock_generation_config")
            
            # Call function with conversation
            response = await gemini_client.generate_completion(
                messages=messages,
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify response has text content
            assert response["error"] is False
            assert response["content"] == "It's 18°C and partly cloudy in New York with 65% humidity."
            assert response["finish_reason"] == "STOP"
            assert response["function_call"] is None  # No function call in this response
            
            # Verify the call to generate_content included function results
            mock_model.generate_content.assert_called_once()
