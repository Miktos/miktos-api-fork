"""
Unit tests for the Gemini client focusing on function calling capabilities.
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

# Import the Gemini client
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
    """Test that Gemini client correctly handles function calls."""
    # Create a simple user message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in Paris?",
        "role": USER_ROLE
    }
    
    # Create a mock response with function call
    mock_response = MagicMock()
    mock_response.text = None  # No text content for function calls
    
    # Function call data
    function_call_data = {
        "name": "get_weather",
        "args": {
            "location": "Paris",
            "unit": "celsius"
        }
    }
    
    # Set up candidates with function call
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
    
    # Mock the to_thread function to return our mock response
    mock_to_thread = AsyncMock(return_value=mock_response)
    
    # Apply patches
    with patch("integrations.gemini_client.asyncio.to_thread", mock_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Mock the GenerativeModel
            mock_genai.GenerativeModel = MagicMock()
            
            # Set up types for tools
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call the function with streaming disabled
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify the function call is included in the response
            assert not response["error"]
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "Paris"
            
            # Verify GenerativeModel was created with tools
            assert mock_genai.GenerativeModel.called
            kwargs = mock_genai.GenerativeModel.call_args.kwargs
            assert "tools" in kwargs


@pytest.mark.asyncio
async def test_function_result_handling():
    """Test that Gemini client correctly handles function results in a conversation."""
    # Create a conversation with function call and result
    messages = [
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": "What's the weather in Tokyo?",
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
                    "location": "Tokyo",
                    "unit": "celsius"
                }
            }
        },
        {  # Function result message
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": '{"temperature": 22, "condition": "Sunny", "humidity": 60}',
            "role": FUNCTION_ROLE,
            "name": "get_weather"
        }
    ]
    
    # Create mock response with text content
    response_text = "It's 22°C and sunny in Tokyo with 60% humidity."
    
    # Create a properly structured mock response
    mock_response = MagicMock()
    mock_response.text = response_text
    
    # Set up candidates with finish reason STOP
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "STOP"
    
    # Set up content with text part
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.text = response_text
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidate to response
    mock_response.candidates = [mock_candidate]
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 20
    mock_response.usage_metadata.candidates_token_count = 15
    mock_response.usage_metadata.total_token_count = 35
    
    # Track calls to generate_content
    captured_contents = []
    
    # Mock to_thread to capture the generate_content arguments
    async def mock_to_thread(func, *args, **kwargs):
        # Capture the contents argument
        if args and len(args) > 0:
            captured_contents.append(args[0])
        return mock_response
    
    # Apply patches
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=mock_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Mock the GenerativeModel
            mock_genai.GenerativeModel = MagicMock()
            
            # Set up types for tools
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call the function with streaming disabled
            response = await gemini_client.generate_completion(
                messages=messages,
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify the response has text content and no function call
            assert not response["error"]
            assert response["content"] == response_text
            assert response["finish_reason"] == "STOP"
            assert "function_call" not in response or response["function_call"] is None
            
            # Verify contents were captured
            assert len(captured_contents) > 0


@pytest.mark.asyncio
async def test_streaming_function_calling():
    """Test function calling with streaming enabled."""
    # Create a simple message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "Search for information about Jupiter",
        "role": USER_ROLE
    }
    
    # Function call data
    function_call_data = {
        "name": "search_database",
        "args": {
            "query": "Jupiter planet",
            "limit": 3
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
            "model_name": "gemini-1.5-flash-latest"
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
                system_prompt="You are a search assistant.",
                functions=[
                    {
                        "name": "search_database",
                        "description": "Search for information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "limit": {"type": "integer"}
                            },
                            "required": ["query"]
                        }
                    }
                ],
                stream=True
            )
            
            # Collect chunks from the stream
            chunks = []
            async for chunk in stream_gen:
                chunks.append(chunk)
            
            # Verify model was created with tools
            assert mock_genai.GenerativeModel.called
            assert "tools" in mock_genai.GenerativeModel.call_args.kwargs
            
            # Verify model was called with streaming enabled
            assert mock_model.generate_content.called
            assert mock_model.generate_content.call_args.kwargs.get("stream") is True
            
            # Verify we got the function call chunk
            assert len(chunks) >= 1
            final_chunk = chunks[-1]
            assert final_chunk["is_final"] is True
            assert "function_call" in final_chunk
            assert final_chunk["function_call"]["name"] == "search_database"
            assert final_chunk["function_call"]["args"]["query"] == "Jupiter planet"
            assert final_chunk["function_call"]["args"]["limit"] == 3
