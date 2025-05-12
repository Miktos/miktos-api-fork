import pytest
from unittest.mock import MagicMock, patch

from integrations import gemini_client

@pytest.mark.asyncio
async def test_basic_function():
    """Minimal test to verify the testing infrastructure."""
    mock_response = MagicMock()
    mock_response.text = "Test response"
    
    with patch("integrations.gemini_client.asyncio.to_thread", return_value=mock_response):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Configure mock
            mock_genai.GenerativeModel = MagicMock()
            
            # Call function
            response = await gemini_client.generate_completion(
                messages=[{"content": "test", "role": "user"}],
                stream=False
            )
            
            # Basic assertion
            assert "error" in response
            assert "content" in response
