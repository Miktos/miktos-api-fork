"""
Tests for Gemini client streaming function calling - fixed implementation
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import asyncio

# Import necessary modules
from integrations import gemini_client

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definition
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
async def test_gemini_streaming_function_call():
    """Test function calling with streaming enabled - fixed implementation."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in Paris?",
        "role": USER_ROLE
    }

    # Create a custom stream generator
    async def mock_stream_generator():
        # First yield an intermediate chunk
        yield {
            "error": False,
            "delta": "thinking...",
            "is_final": False,
            "accumulated_content": "thinking..."
        }
        
        # Then yield the final chunk with function call
        yield {
            "error": False,
            "delta": None,
            "is_final": True,
            "accumulated_content": None,
            "finish_reason": "FUNCTION_CALL",
            "function_call": {
                "name": "get_weather",
                "args": {
                    "location": "Paris",
                    "unit": "celsius"
                }
            },
            "model_name": "gemini-1.5-flash-latest",
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30
            }
        }

    # Create mock model
    mock_model = MagicMock()
    
    # Set up patches
    with patch("integrations.gemini_client.genai.GenerativeModel", return_value=mock_model), \
         patch("integrations.gemini_client._gemini_stream_wrapper", return_value=mock_stream_generator()), \
         patch("integrations.gemini_client.settings.GOOGLE_API_KEY", "fake-api-key"):

        # Call the function with streaming
        stream_gen = await gemini_client.generate_completion(
            messages=[message],
            system_prompt="You are a weather assistant.",
            functions=[SAMPLE_FUNCTION],
            stream=True
        )

        # Process the stream
        chunks = []
        async for chunk in stream_gen:
            chunks.append(chunk)

        # Check that we got both chunks
        assert len(chunks) == 2
        
        # Check the first chunk (intermediate)
        assert chunks[0]["is_final"] is False
        assert chunks[0]["delta"] == "thinking..."
        assert chunks[0]["error"] is False
        
        # Check the final chunk with function call
        final_chunk = chunks[1]
        assert final_chunk["is_final"] is True
        assert final_chunk["finish_reason"] == "FUNCTION_CALL"
        assert "function_call" in final_chunk
        assert final_chunk["function_call"]["name"] == "get_weather"
        assert final_chunk["function_call"]["args"]["location"] == "Paris"
        assert final_chunk["function_call"]["args"]["unit"] == "celsius"
        
        # Verify usage information
        assert "usage" in final_chunk
        assert final_chunk["usage"]["prompt_tokens"] == 20
        assert final_chunk["usage"]["completion_tokens"] == 10
        assert final_chunk["usage"]["total_tokens"] == 30
