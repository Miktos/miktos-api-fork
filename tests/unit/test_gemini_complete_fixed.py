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
async def test_basic_function_calling():
    """Test that function calling works correctly."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in New York?",
        "role": USER_ROLE
    }

    # Set up a proper function call object with attributes
    class MockFunctionCall:
        def __init__(self):
            self.name = "get_weather"
            self.args = {"location": "New York", "unit": "celsius"}
    
    function_call_data = MockFunctionCall()

    # Create mock response object with all the expected attributes
    mock_response = MagicMock(name="mock_gemini_response_basic_MANUAL_FIX")
    mock_response.text = None

    # Set up the candidate with function call
    mock_candidate = MagicMock(name="mock_candidate_basic_MANUAL_FIX")
    mock_candidate.finish_reason = MagicMock(name="mock_finish_reason_basic_MANUAL_FIX")
    mock_candidate.finish_reason.name = "FUNCTION_CALL"

    # Set up content with function call part
    mock_content = MagicMock(name="mock_content_basic_MANUAL_FIX")
    mock_part = MagicMock(name="mock_part_basic_MANUAL_FIX")
    mock_part.function_call = function_call_data
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content

    # Add candidate to response
    mock_response.candidates = [mock_candidate]

    # Set up usage metadata
    mock_response.usage_metadata = MagicMock(name="mock_usage_metadata_basic_MANUAL_FIX")
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15

    # Create model mock first - this is what genai.GenerativeModel() will return
    mock_model = MagicMock(name="gemini_model_mock_basic_MANUAL_FIX")
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
    
    with patch("integrations.gemini_client._call_generate_content", side_effect=mock_call_generate_impl) as mock_call_generate:
        with patch("integrations.gemini_client.genai") as mock_genai_module:
            mock_genai_module.GenerativeModel = MagicMock(return_value=mock_model)
            mock_genai_module.types = MagicMock()
            mock_genai_module.types.Tool = MagicMock()
            mock_genai_module.types.FunctionDeclaration = MagicMock()
            mock_genai_module.types.GenerationConfig = MagicMock()

            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are an assistant",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )

            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "New York"
            assert response["function_call"]["args"]["unit"] == "celsius"
            
            # Verify model.generate_content was called
            mock_model.generate_content.assert_called_once()
            
            # Verify _call_generate_content was called
            mock_call_generate.assert_called_once()
            
            # Verify that we captured content args
            assert len(captured_content_args) > 0


@pytest.mark.asyncio
async def test_function_result_handling():
    """Test that the client properly handles function results in conversations."""
    messages = [
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": "What's the weather in New York?",
            "role": USER_ROLE
        },
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": None,
            "role": ASSISTANT_ROLE,
            "function_call": {
                "name": "get_weather",
                "args": {"location": "New York", "unit": "celsius"}
            }
        },
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": '{"temperature": 18, "condition": "Partly Cloudy", "humidity": 65}',
            "role": FUNCTION_ROLE,
            "name": "get_weather"
        }
    ]
    
    response_text = "It's 18°C and partly cloudy in New York with 65% humidity."
    
    mock_response = MagicMock(name="mock_gemini_response_func_result")
    mock_response.text = response_text
    
    mock_candidate = MagicMock(name="mock_candidate_func_result")
    mock_candidate.finish_reason = MagicMock(name="mock_finish_reason_func_result")
    mock_candidate.finish_reason.name = "STOP"
    
    mock_content = MagicMock(name="mock_content_func_result")
    mock_part = MagicMock(name="mock_part_func_result")
    mock_part.text = response_text
    mock_part.function_call = None
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    mock_response.candidates = [mock_candidate]
    
    mock_response.usage_metadata = MagicMock(name="mock_usage_metadata_func_result")
    mock_response.usage_metadata.prompt_token_count = 20
    mock_response.usage_metadata.candidates_token_count = 15
    mock_response.usage_metadata.total_token_count = 35
    
    mock_model = MagicMock(name="gemini_model_mock_func_result")
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
    
    with patch("integrations.gemini_client._call_generate_content", side_effect=mock_call_generate_impl) as mock_call_generate:
        with patch("integrations.gemini_client.genai") as mock_genai_func_result:
            mock_genai_func_result.GenerativeModel = MagicMock(return_value=mock_model)
            mock_genai_func_result.types = MagicMock()
            mock_genai_func_result.types.Tool = MagicMock()
            mock_genai_func_result.types.FunctionDeclaration = MagicMock()
            
            response = await gemini_client.generate_completion(
                messages=messages,
                system_prompt="You are an assistant",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            assert response["error"] is False
            assert response["content"] == response_text
            assert response["finish_reason"] == "STOP"
            assert "function_call" not in response or response["function_call"] is None
            
            # Verify model.generate_content was called
            mock_model.generate_content.assert_called_once()
            
            # Verify _call_generate_content was called
            mock_call_generate.assert_called_once()
            
            # Verify that we captured content args and they contain the function result
            assert len(captured_content_args) > 0
            
            # Convert the content args to string to check for the presence of function result info
            contents_str = str(captured_content_args[0])
            assert "temperature" in contents_str
            assert "Partly Cloudy" in contents_str
            assert "humidity" in contents_str


@pytest.mark.asyncio
async def test_streaming_function_calling():
    """Test that function calling works with streaming enabled."""
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "Search for information about Mars",
        "role": USER_ROLE
    }
    
    async def mock_stream_generator():
        # Use a dictionary directly for the function call in streaming mode
        yield {
            "error": False,
            "delta": None,
            "is_final": True,
            "accumulated_content": None,
            "finish_reason": "FUNCTION_CALL",
            "function_call": {
                "name": "search_database", 
                "args": {"query": "Mars planet", "limit": 5}
            },
            "model_name": "gemini-1.5-flash-latest"
        }
    
    mock_model_stream = MagicMock(name="gemini_model_mock_stream")
    
    with patch("integrations.gemini_client.genai") as mock_genai_stream:
        mock_genai_stream.GenerativeModel = MagicMock(return_value=mock_model_stream)
        mock_genai_stream.types = MagicMock()
        mock_genai_stream.types.Tool = MagicMock()
        mock_genai_stream.types.FunctionDeclaration = MagicMock()
        
        with patch("integrations.gemini_client._gemini_stream_wrapper", return_value=mock_stream_generator()) as mock_stream_wrapper:
            stream_gen = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a search assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=True
            )
            
            chunks = []
            async for chunk in stream_gen:
                chunks.append(chunk)
            
            assert len(chunks) >= 1
            
            final_chunk = chunks[-1]
            assert final_chunk["is_final"] is True
            assert "function_call" in final_chunk
            assert final_chunk["function_call"]["name"] == "search_database"
            assert final_chunk["function_call"]["args"]["query"] == "Mars planet"
            assert final_chunk["function_call"]["args"]["limit"] == 5
            
            mock_stream_wrapper.assert_called_once()