# tests/unit/test_orchestrator.py
import pytest
from unittest.mock import patch, AsyncMock
import sys
import os

# Add the parent directory to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core import orchestrator

@pytest.mark.asyncio
async def test_process_generation_request_model_selection():
    """Test that orchestrator routes to the correct model client"""
    
    # Setup test data
    test_messages = [{"role": "user", "content": "Hello"}]
    
    # Test OpenAI routing
    with patch('core.orchestrator.openai_client.generate', new_callable=AsyncMock) as mock_openai:
        mock_openai.return_value = {"content": "OpenAI response"}
        
        result = await orchestrator.process_generation_request(
            messages=test_messages,
            model="openai/gpt-4o",
            stream=False
        )
        
        mock_openai.assert_called_once()
        assert "content" in result
        
    # Test Claude routing
    with patch('core.orchestrator.claude_client.generate', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = {"content": "Claude response"}
        
        result = await orchestrator.process_generation_request(
            messages=test_messages,
            model="anthropic/claude-3",
            stream=False
        )
        
        mock_claude.assert_called_once()
        assert "content" in result