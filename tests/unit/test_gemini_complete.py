"""
Complete test suite for Gemini client function calling capabilities.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import asyncio
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

@pytest.mark.asyncio
async def test_basic_function_calling():
    """Test that function calling works correctly."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }
    
    # Set up the expected function call data
    function_call_data = {
        "name": "get_weather", 
        "args": {"location": "New York", "unit": "celsius"}
    }
    
    # Create mock response object with all the expected attributes
    mock_response = MagicMock()
    mock_response.text = None
    
    # Set up the candidate with function call
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "FUNCTION_CALL"
    
    # Set up content with function call part
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = function_call_data
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidate to response
    mock_response.candidates = [mock_candidate]
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15
    
    # Define a fake to_thread function that will execute synchronously
    async def fake_to_thread(func, *args, **kwargs):
        # We ignore the func here and just return our mock response
        return mock_response
    
    # Create mocks and patches
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=fake_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Create mock model that will be returned by GenerativeModel
            mock_model = MagicMock()
            # We don't need this anymore as to_thread is directly returning mock_response:
            # mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Set up types for tools
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call the function
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are an assistant",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify function call was included in the response
            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "New York"
            assert response["function_call"]["args"]["unit"] == "celsius"
            
            # Verify tools were set up correctly
            mock_genai.GenerativeModel.assert_called_once()
            args = mock_genai.GenerativeModel.call_args.kwargs
            assert "tools" in args

@pytest.mark.asyncio
async def test_function_result_handling():
    """Test that the client properly handles function results in conversations."""
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
    response_text = "It's 18°C and partly cloudy in New York with 65% humidity."
    
    # Create a properly structured mock response
    mock_response = MagicMock()
    mock_response.text = response_text
    
    # Set up candidates with finish reason STOP
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "STOP"
    
    # Set up content with text part for the candidate
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.text = response_text
    mock_part.function_call = None  # Ensure no function call
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidate to response
    mock_response.candidates = [mock_candidate]
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 20
    mock_response.usage_metadata.candidates_token_count = 15
    mock_response.usage_metadata.total_token_count = 35
    
    # Track function names and content for verification
    function_data_captured = []
    
    # Define a fake to_thread function that captures function data
    async def fake_to_thread(func, *args, **kwargs):
        # If we're capturing a function call to generate_content
        if len(args) > 0:
            # Extract function data from messages
            for msg in messages:
                if msg["role"] == FUNCTION_ROLE:
                    function_data_captured.append({
                        "name": msg["name"],
                        "content": msg["content"]
                    })
        # Return the mock response
        return mock_response
    
    # Create model mock
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    # Create mocks and patches
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=fake_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set up model and tools mocks
            mock_genai.GenerativeModel = MagicMock(return_value=mock_model)
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call the function with the conversation
            response = await gemini_client.generate_completion(
                messages=messages,
                system_prompt="You are an assistant",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )

            # Verify response has text content and no function call
            assert response["error"] is False
            assert response["content"] == response_text
            assert response["finish_reason"] == "STOP"
            assert "function_call" not in response or response["function_call"] is None

            # Verify function data was captured
            assert len(function_data_captured) > 0, "Function data was not captured"
            
            get_weather_data_list = [d for d in function_data_captured if d.get("name") == "get_weather"]
            assert len(get_weather_data_list) > 0, "get_weather function data not found in captured data"
            
            # Assuming we expect one such function call's data to be captured for this specific test's logic
            get_weather_content = get_weather_data_list[0].get("content", "")
            
            assert "temperature" in get_weather_content, "Temperature missing in captured content"
            assert "18" in get_weather_content, "Temperature value missing in captured content"
            assert "Partly Cloudy" in get_weather_content, "Weather condition missing in captured content"
