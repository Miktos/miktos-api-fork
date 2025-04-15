# tests/integration/test_generate_endpoint.py
import json
import pytest
from unittest.mock import patch, MagicMock

def test_generate_endpoint_structure(client):
    """Test that the generate endpoint accepts proper structure"""
    with patch('api.endpoints.orchestrator.process_generation_request') as mock_process:
        # Setup mock to return a simple response
        mock_process.return_value = {
            "content": "Test response",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model_name": "test-model"
        }
        
        # Test data
        request_data = {
            "model": "openai/gpt-4o",
            "messages": [{"role": "user", "content": "Hello, world"}],
            "stream": False,
            "temperature": 0.7
        }
        
        # Make request
        response = client.post(
            "/api/v1/generate",
            json=request_data
        )
        
        # Verify response
        assert response.status_code == 200
        assert "content" in response.json()
        assert "finish_reason" in response.json()
        
        # Verify mock was called with expected args
        mock_process.assert_called_once()