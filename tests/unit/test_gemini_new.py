"""
Simple test for Gemini function calling in a brand new file
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid

# Import necessary modules
from integrations import gemini_client

# Define role constants
USER_ROLE = "user"

# Sample function definition
SAMPLE_FUNCTION = [
    {
        "name": "get_weather",
        "description": "Get current weather",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }
]


@pytest.mark.asyncio
async def test_function_calling_simple():
    """Most basic function calling test."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather?",
        "role": USER_ROLE
    }
    
    # Mock response
    mock_response = MagicMock()
    mock_response.text = None
    
    # Set up function call
    function_call = {
        "name": "get_weather",
        "args": {"location": "New York"}
    }
    
    # Configure mock response
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "FUNCTION_CALL"
    
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = function_call
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    mock_response.candidates = [mock_candidate]
    mock_response.usage_metadata = MagicMock()
    
    # Mock to_thread
    mock_to_thread = AsyncMock(return_value=mock_response)
    
    # Apply patches
    with patch("integrations.gemini_client.asyncio.to_thread", mock_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set up model mock
            mock_genai.GenerativeModel = MagicMock()
            mock_genai.types = MagicMock()
            
            # Call the function
            response = await gemini_client.generate_completion(
                messages=[message],
                functions=SAMPLE_FUNCTION,
                stream=False
            )
            
            # Verify response
            assert response["error"] is False
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert response["function_call"]["name"] == "get_weather"
            
            # Verify mock was called
            mock_to_thread.assert_called_once()
