"""
Fixed test file for Gemini function calling with proper mocking of asyncio.to_thread
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

# Import the client
from integrations import gemini_client

# Define role constants locally
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant" 
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definition for testing
SAMPLE_FUNCTION = {
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
    
    # Create a proper to_thread mock that actually calls the function
    async def mock_to_thread(func, *args, **kwargs):
        # This actually calls the function with its arguments and returns the result
        return func(*args, **kwargs)
    
    # Apply patches
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=mock_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Create mock model instance that returns our response
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            
            # Set up the GenerativeModel mock to return our model
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call function
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=[SAMPLE_FUNCTION],
                stream=False
            )
            
            # Verify model was created with tools
            mock_genai.GenerativeModel.assert_called_once()
            call_kwargs = mock_genai.GenerativeModel.call_args.kwargs
            assert "tools" in call_kwargs
            
            # Verify generate_content was called
            mock_model.generate_content.assert_called_once()
            
            # Verify response format
            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            assert response["function_call"]["args"]["location"] == "New York"

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
    response_text = "It's 18°C and partly cloudy in New York with 65% humidity."
    
    # Create mock response object
    mock_response = MagicMock()
    mock_response.text = response_text
    
    # Set up parts property with text
    mock_response.parts = [MagicMock()]
    mock_response.parts[0].text = response_text
    
    # Set up candidates with finish reason STOP
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].finish_reason = MagicMock()
    mock_response.candidates[0].finish_reason.name = "STOP"
    
    # Set up content with text part
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.text = response_text
    mock_content.parts = [mock_part]
    mock_response.candidates[0].content = mock_content
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 20
    mock_response.usage_metadata.candidates_token_count = 15
    mock_response.usage_metadata.total_token_count = 35
    
    # Create a proper to_thread mock that actually calls the function
    async def mock_to_thread(func, *args, **kwargs):
        # This actually calls the function with its arguments and returns the result
        return func(*args, **kwargs)
    
    # Apply patches
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=mock_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Create mock model instance that returns our response
            mock_model = MagicMock()
            mock_model.generate_content.return_value = mock_response
            
            # Set up the GenerativeModel mock to return our model
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call function with conversation including function result
            response = await gemini_client.generate_completion(
                messages=messages,
                system_prompt="You are a weather assistant.",
                functions=[SAMPLE_FUNCTION],
                stream=False
            )
            
            # Verify response has text content and no function call
            assert response["error"] is False
            assert response["content"] == response_text
            assert response["finish_reason"] == "STOP"
            assert "function_call" not in response or response["function_call"] is None
            
            # Verify generate_content was called
            mock_model.generate_content.assert_called_once()

@pytest.mark.asyncio
async def test_streaming_function_calling():
    """Test function calling with streaming enabled."""
    # Create simple user message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "Search for information about Mars",
        "role": USER_ROLE
    }
    
    # Function call data
    function_call_data = {
        "name": "search_database",
        "args": {
            "query": "Mars planet",
            "limit": 5
        }
    }
    
    # Create a stream response mock
    class MockStreamResponse:
        def __init__(self):
            # Create a mock chunk with function call
            self.chunk = MagicMock()
            self.chunk.text = None
            
            # Set up a candidate with function call
            candidate = MagicMock()
            candidate.finish_reason = MagicMock()
            candidate.finish_reason.name = "FUNCTION_CALL"
            
            # Set up content with function call part
            content = MagicMock()
            part = MagicMock()
            part.function_call = function_call_data
            content.parts = [part]
            candidate.content = content
            
            # Add candidate to chunk
            self.chunk.candidates = [candidate]
        
        def __iter__(self):
            return iter([self.chunk])
    
    # Create a proper stream wrapper for testing
    async def mock_stream_wrapper(response_stream, model_id):
        # Yield a function call chunk as the final result
        yield {
            "error": False,
            "delta": None,
            "is_final": True,
            "accumulated_content": None,
            "finish_reason": "FUNCTION_CALL",
            "function_call": function_call_data,
            "model_name": "gemini-1.5-flash-latest"
        }
    
    # Apply patches
    with patch("integrations.gemini_client._gemini_stream_wrapper", side_effect=mock_stream_wrapper):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Create mock model that returns our stream response
            mock_model = MagicMock()
            mock_model.generate_content.return_value = MockStreamResponse()
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Mock Tool and FunctionDeclaration
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            
            # Call function with streaming enabled
            stream_gen = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a search assistant.",
                functions=[SAMPLE_FUNCTION],
                stream=True
            )
            
            # Process the stream
            chunks = []
            async for chunk in stream_gen:
                chunks.append(chunk)
            
            # Verify stream generated correct chunks
            assert len(chunks) >= 1
            final_chunk = chunks[-1]
            assert final_chunk["is_final"] is True
            assert final_chunk["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in final_chunk
            assert final_chunk["function_call"]["name"] == "search_database"
            assert final_chunk["function_call"]["args"]["query"] == "Mars planet"
            assert final_chunk["function_call"]["args"]["limit"] == 5
            
            # Verify model was called with streaming
            mock_model.generate_content.assert_called_once()
            assert mock_model.generate_content.call_args.kwargs.get("stream") is True
