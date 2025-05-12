"""
Complete test suite for Gemini client function calling capabilities
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
async def test_gemini_function_calling():
    """Test that Gemini client properly formats function calling."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }
    
    # Mock a function call response from Gemini
    mock_function_call = {
        "name": "get_weather",
        "args": {
            "location": "San Francisco",
            "unit": "celsius"
        }
    }
    
    # Create a proper mock response
    mock_response = MagicMock()
    mock_response.text = None  # No text for function calls
    
    # Create mock candidates with function call
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "FUNCTION_CALL"
    
    # Create content with function call
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = mock_function_call
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidates to response
    mock_response.candidates = [mock_candidate]
    
    # Add usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 15
    mock_response.usage_metadata.candidates_token_count = 25
    mock_response.usage_metadata.total_token_count = 40
    
    # Create the final mock model
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    # Mock to_thread with AsyncMock
    mock_to_thread = AsyncMock(return_value=mock_response)
    
    # Setup proper patches 
    with patch("integrations.gemini_client.asyncio.to_thread", mock_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set up model mock
            mock_genai.GenerativeModel = MagicMock(return_value=mock_model)
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            mock_genai.types.GenerationConfig = MagicMock()
            
            # Call the function with function definitions
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
            
            # Verify the model was called through to_thread
            mock_to_thread.assert_called_once()
            
            # Verify tools parameter was passed correctly to the model constructor
            mock_genai.GenerativeModel.assert_called_once()
            _, kwargs = mock_genai.GenerativeModel.call_args
            assert "tools" in kwargs
            assert len(kwargs["tools"]) == len(SAMPLE_FUNCTIONS)


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
    
    # Create a properly structured mock response
    mock_response = MagicMock()
    
    # Setup the text content - important for both response.text and parts[].text
    mock_response.text = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    mock_response.parts = [MagicMock()]
    mock_response.parts[0].text = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    
    # Create mock candidates with a normal text response
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "STOP"
    
    # Add text part to the candidate's content
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidates to response
    mock_response.candidates = [mock_candidate]
    
    # Add usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 25
    mock_response.usage_metadata.candidates_token_count = 15
    mock_response.usage_metadata.total_token_count = 40
    
    # Create the final mock model with tracking
    mock_model = MagicMock()
    mock_generate_content = MagicMock(return_value=mock_response)
    mock_model.generate_content = mock_generate_content
    
    # Define a function that tracks the call and returns the mock response
    async def fake_to_thread(func, *args, **kwargs):
        func(*args, **kwargs)  # Actually call the function to record args
        return mock_response
    
    # Setup proper patches
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=fake_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set the GenerativeModel mock to return our mock model
            mock_genai.GenerativeModel = MagicMock(return_value=mock_model)
            
            # Mock the tool types for function calling
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            mock_genai.types.GenerationConfig = MagicMock()
            
            # Call the function with the conversation including function result
            response = await gemini_client.generate_completion(
                messages=messages,
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify regular text response after function call
            assert response["error"] is False
            assert response["content"] == "It's 18°C and partly cloudy in San Francisco with 65% humidity."
            assert response["finish_reason"] == "STOP"
            
            # Verify model was called
            assert mock_generate_content.called
            
            # Verify the content of the response
            assert response["content"] is not None
            assert "18°C" in response["content"]
            assert "partly cloudy" in response["content"]


@pytest.mark.asyncio
async def test_streaming_function_calling():
    """Test function calling with streaming enabled."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "Search for information about Mars",
        "role": USER_ROLE
    }
    
    # Create mock model that will be used for streaming
    mock_model = MagicMock()
    
    # Create a wrapper to convert the real async generator to one we can mock
    async def mock_gemini_stream_wrapper(*args, **kwargs):
        # Create the expected response format for a function call
        yield {
            "error": False,
            "delta": None,
            "is_final": True,
            "accumulated_content": None,
            "finish_reason": "FUNCTION_CALL",
            "function_call": {
                "name": "search_database",
                "args": {
                    "query": "Mars planet",
                    "limit": 5
                }
            },
            "model_name": "gemini-1.5-flash-latest"
        }

    # Setup proper patches
    with patch("integrations.gemini_client.genai") as mock_genai:
        # Set the GenerativeModel mock to return our mock model
        mock_genai.GenerativeModel = MagicMock(return_value=mock_model)
        
        # Mock the tool types for function calling
        mock_genai.types = MagicMock()
        mock_genai.types.Tool = MagicMock()
        mock_genai.types.FunctionDeclaration = MagicMock()
        mock_genai.types.GenerationConfig = MagicMock()
        
        # Override the _gemini_stream_wrapper function to return our mock generator
        with patch("integrations.gemini_client._gemini_stream_wrapper", return_value=mock_gemini_stream_wrapper()):
            # Call the function with streaming
            stream_gen = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a search assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=True
            )
            
            # Process the stream
            chunks = []
            async for chunk in stream_gen:
                chunks.append(chunk)
            
            # Check that we got the function call chunk
            assert len(chunks) >= 1
            final_chunk = chunks[-1]
            
            # Verify function call data is in the final chunk
            assert final_chunk["is_final"] is True
            assert "function_call" in final_chunk
            assert final_chunk["function_call"]["name"] == "search_database"
            assert final_chunk["function_call"]["args"]["query"] == "Mars planet"
