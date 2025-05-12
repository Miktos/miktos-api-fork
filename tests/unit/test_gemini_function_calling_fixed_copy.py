"""
Fixed test suite for Gemini client function calling capabilities.
This test ensures that the Gemini API client correctly handles function calling.
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
async def test_gemini_function_calling():
    """Test that the Gemini client properly handles function calling."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }
    
    # Mock the GenerativeModel class
    mock_model = MagicMock()
    mock_finish_reason = MagicMock()
    mock_finish_reason.name = "FUNCTION_CALL"
    
    mock_function_call = {
        "name": "get_weather",
        "args": {
            "location": "San Francisco",
            "unit": "celsius"
        }
    }
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.text = None  # No text for function calls
    
    # Setup the candidates
    mock_candidates = [MagicMock()]
    mock_candidates[0].finish_reason = mock_finish_reason
    mock_response.candidates = mock_candidates
    
    # Setup the function call part using a proper class with attributes
    class MockFunctionCall:
        def __init__(self):
            self.name = "get_weather"
            self.args = {"location": "San Francisco", "unit": "celsius"}
    
    mock_part = MagicMock()
    mock_part.function_call = MockFunctionCall()
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_candidates[0].content = mock_content
    
    # Set up usage metadata
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 15
    mock_usage.candidates_token_count = 25
    mock_usage.total_token_count = 40
    mock_response.usage_metadata = mock_usage
    
    # The model's generate_content method should return the mock response
    mock_model.generate_content.return_value = mock_response
    
    # Track the contents passed to generate_content
    captured_content_args = []
    
    # Create a mock for _call_generate_content that captures the content
    def mock_call_generate_impl(func, *args, **kwargs):
        # If this is the generate_content function, capture args and call it
        if func == mock_model.generate_content and len(args) > 0:
            captured_content_args.append(args[0])  # Capture the first arg (content)
            func(*args, **kwargs)
        return mock_response
    
    # Create patches
    with patch("integrations.gemini_client._call_generate_content", side_effect=mock_call_generate_impl):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set up the GenerativeModel mock
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock(return_value="mock_tool")
            mock_genai.types.FunctionDeclaration = MagicMock(return_value="mock_function_declaration")
            
            # Call function
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
    
            # Verify model was created with correct parameters
            mock_genai.GenerativeModel.assert_called_once()
            model_kwargs = mock_genai.GenerativeModel.call_args.kwargs
            
            # Check that tools parameter was included
            assert "tools" in model_kwargs
            
            # Verify response has function call
            assert not response["error"]
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
    mock_response.text = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    
    # Add parts attribute with text content to mock_response
    mock_response.parts = [MagicMock()]
    mock_response.parts[0].text = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    
    # Setup finish reason
    mock_finish_reason = MagicMock()
    mock_finish_reason.name = "STOP"
    mock_candidates = [MagicMock()]
    mock_candidates[0].finish_reason = mock_finish_reason
    mock_response.candidates = mock_candidates
    
    # Set up content with text part
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    mock_content.parts = [mock_part]
    mock_candidates[0].content = mock_content
    
    # Set up usage metadata
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 25
    mock_usage.candidates_token_count = 15
    mock_usage.total_token_count = 40
    mock_response.usage_metadata = mock_usage
    
    # Create and configure the mock model
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    # Track the contents passed to generate_content
    captured_content_args = []
    
    # Create a mock for _call_generate_content that captures the content
    def mock_call_generate_impl(func, *args, **kwargs):
        # If this is the generate_content function, capture args and call it
        if func == mock_model.generate_content and len(args) > 0:
            captured_content_args.append(args[0])  # Capture the first arg (content)
            func(*args, **kwargs)
        return mock_response
    
    # Create patches
    with patch("integrations.gemini_client._call_generate_content", side_effect=mock_call_generate_impl):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set up the GenerativeModel mock
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock(return_value="mock_tool")
            mock_genai.types.FunctionDeclaration = MagicMock(return_value="mock_function_declaration")
            
            # Call the function with the conversation including function result
            response = await gemini_client.generate_completion(
                messages=messages,
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
    
            # Verify regular text response after function call
            assert response is not None
            assert response["error"] is False
            assert response["content"] == "It's 18°C and partly cloudy in San Francisco with 65% humidity."
            assert response["finish_reason"] == "STOP"
            assert "function_call" not in response or response["function_call"] is None
            
            # Verify contents were captured and contain function result info
            assert len(captured_content_args) > 0
            
            # Check function result info is present in the captured content
            content_str = str(captured_content_args[0])
            assert "San Francisco" in content_str
            assert "temperature" in content_str
            assert "18" in content_str
            assert "Partly Cloudy" in content_str


@pytest.mark.asyncio
async def test_streaming_function_calling():
    """Test function calling with streaming enabled."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }
    
    # Create mock function call for streaming
    function_call_data = {
        "name": "get_weather",
        "args": {
            "location": "San Francisco",
            "unit": "celsius"
        }
    }
    
    # Create a stream response
    async def mock_stream_generator():
        # Yield a final chunk with function call
        yield {
            "error": False,
            "delta": None,
            "is_final": True,
            "accumulated_content": None,
            "finish_reason": "FUNCTION_CALL",
            "function_call": function_call_data,
            "model_name": "gemini-1.5-flash-latest",
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 25,
                "total_tokens": 40
            }
        }
    
    # Create mock stream object
    mock_stream = MagicMock()
    
    # Apply patches
    with patch("integrations.gemini_client._gemini_stream_wrapper", return_value=mock_stream_generator()):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Mock the GenerativeModel
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_stream
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock the tool types
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call the function with streaming enabled
            stream_gen = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=True
            )
            
            # Collect chunks from the stream
            chunks = []
            async for chunk in stream_gen:
                chunks.append(chunk)
            
            # Verify model was created with tools
            mock_genai.GenerativeModel.assert_called_once()
            assert "tools" in mock_genai.GenerativeModel.call_args.kwargs
            
            # Verify model was called with streaming enabled
            assert mock_model.generate_content.called
            assert mock_model.generate_content.call_args.kwargs.get("stream") is True
            
            # Verify we got the function call chunk
            assert len(chunks) == 1
            final_chunk = chunks[0]
            assert final_chunk["is_final"] is True
            assert "function_call" in final_chunk
            assert final_chunk["function_call"]["name"] == "get_weather"
            assert final_chunk["function_call"]["args"]["location"] == "San Francisco"
