"""
Simple test for OpenAI function calling.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid

from integrations import openai_client

# Define roles
USER_ROLE = "user"

@pytest.mark.asyncio
async def test_openai_simple():
    # Create a message
    message = {"id": str(uuid.uuid4()), "content": "Test", "role": USER_ROLE}
    
    # Create a mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Hello world"
    
    # Create mock client
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # Setup patches
    with patch("integrations.openai_client.get_client", return_value=mock_client), \
         patch("integrations.openai_client.client", mock_client), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-key"):
            # Call the function
            response = await openai_client.generate_completion(
                messages=[message], 
                stream=False
            )
            
            # Verify response
            assert response["error"] is False
            assert response["content"] == "Hello world"
            mock_client.chat.completions.create.assert_called_once()
