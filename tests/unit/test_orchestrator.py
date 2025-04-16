# tests/unit/test_orchestrator.py
import pytest
from unittest.mock import patch, AsyncMock
import sys
import os

# Add the parent directory to PYTHONPATH

from core import orchestrator

@pytest.mark.asyncio
async def test_process_generation_request_model_selection():
    """Test that orchestrator routes to the correct model client"""
    
    # Setup test data
    test_messages = [{"role": "user", "content": "Hello"}]
    
    # Test OpenAI routing
    # Patch 'generate_completion' NOT 'generate'
    with patch('core.orchestrator.openai_client.generate_completion', new_callable=AsyncMock) as mock_openai:
        mock_openai.return_value = {"content": "OpenAI response"}
        
        result = await orchestrator.process_generation_request(
            messages=test_messages,
            model="openai/gpt-4o",
            stream=False
        )
        
        mock_openai.assert_called_once()
        assert "content" in result
        
    # Test Claude routing
    # Patch 'generate_completion' NOT 'generate'
    with patch('core.orchestrator.claude_client.generate_completion', new_callable=AsyncMock) as mock_claude:
        mock_claude.return_value = {"content": "Claude response"}
        
        result = await orchestrator.process_generation_request(
            messages=test_messages,
            model="anthropic/claude-3",
            stream=False
        )
        
        mock_claude.assert_called_once()
        assert "content" in result

    # Test Gemini routing
    # Patch 'generate_completion' NOT 'generate'
    with patch('core.orchestrator.gemini_client.generate_completion', new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = {"content": "Gemini response"}

        result = await orchestrator.process_generation_request(
            messages=test_messages,
            model="google/gemini-pro", # Or similar gemini model ID
            stream=False
        )
        mock_gemini.assert_called_once()
        assert "content" in result