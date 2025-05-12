# tests/unit/test_endpoints_extended.py
import os
import pytest
import json
import sys
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
import asyncio
from typing import AsyncGenerator, Generator

# Add the root directory to the Python path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the main app
from main import app

# Import endpoint functions to test
from api.endpoints import generate_completion_endpoint, health_check, check_status

# Import models
from api.models import GenerateRequest
from models.database_models import User, Project

# Import repositories
from repositories.project_repository import ProjectRepository

# Import the core orchestrator
from core import orchestrator

# Test client
client = TestClient(app)

@pytest.mark.asyncio
async def test_health_check_endpoint():
    """Test the health check endpoint returns correctly formatted data."""
    response = await health_check()
    assert "status" in response
    assert response["status"] == "ok"
    assert "timestamp" in response

@pytest.mark.asyncio
async def test_check_status_endpoint():
    """Test the status check endpoint returns correctly formatted data."""
    response = await check_status()
    assert "status" in response
    assert response["status"] == "ok"
    assert "version" in response
    assert response["version"] == "0.2.0"

@pytest.mark.asyncio
async def test_generate_completion_project_not_found():
    """Test generate endpoint when project not found."""
    # Mock the repository
    mock_repo = MagicMock(spec=ProjectRepository)
    mock_repo.get_by_id_for_owner.return_value = None
    
    # Mock the DB and user
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = "test-user-id"

    # Create request payload
    payload = GenerateRequest(
        messages=[{"role": "user", "content": "Test message"}],
        model="openai/gpt-4o",
        project_id="non-existent-project-id",
        temperature=0.7,
        max_tokens=1000,
        system_prompt="Test system prompt"
    )
    
    # Patch the repository constructor to return our mock
    with patch("api.endpoints.ProjectRepository", return_value=mock_repo):
        # Call the endpoint
        response = await generate_completion_endpoint(payload, mock_user, mock_db)
        
        # Verify response
        assert isinstance(response, StreamingResponse)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        
        # Get the content from the streaming response
        content = []
        async for chunk in response.body_iterator:
            # Handle both string and bytes chunks
            if isinstance(chunk, bytes):
                content.append(chunk.decode("utf-8"))
            else:
                content.append(chunk)
        
        content_str = ''.join(content)
        assert 'data: ' in content_str
        
        # Parse the JSON data from the SSE format
        json_data = json.loads(content_str.replace('data: ', '').strip())
        assert json_data.get('error') is True
        assert 'not found' in json_data.get('message')

@pytest.mark.asyncio
async def test_generate_completion_success():
    """Test generate endpoint when successful."""
    # Mock the project repository
    mock_project = MagicMock(spec=Project)
    mock_project.id = "test-project-id"
    mock_project.owner_id = "test-user-id"
    
    mock_repo = MagicMock(spec=ProjectRepository)
    mock_repo.get_by_id_for_owner.return_value = mock_project
    
    # Mock the DB and user
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = "test-user-id"

    # Create request payload
    payload = GenerateRequest(
        messages=[{"role": "user", "content": "Test message"}],
        model="openai/gpt-4o",
        project_id="test-project-id",
        temperature=0.7,
        max_tokens=1000,
        system_prompt="Test system prompt"
    )
    
    # Mock the orchestrator response
    async def mock_generator():
        yield 'data: {"delta": "Test", "error": false, "is_final": false}\n\n'
        yield 'data: {"delta": " response", "error": false, "is_final": false}\n\n'
        yield 'data: {"delta": null, "error": false, "is_final": true, "finish_reason": "stop"}\n\n'
    
    # Patch both the repository constructor and the orchestrator function
    with patch("api.endpoints.ProjectRepository", return_value=mock_repo), \
         patch("api.endpoints.orchestrator.process_generation_request", return_value=mock_generator()):
        
        # Call the endpoint
        response = await generate_completion_endpoint(payload, mock_user, mock_db)
        
        # Verify response
        assert isinstance(response, StreamingResponse)
        assert response.status_code == 200
        assert response.media_type == "text/event-stream"

@pytest.mark.asyncio
async def test_generate_completion_exception_handling():
    """Test generate endpoint exception handling."""
    # Mock the project repository
    mock_project = MagicMock(spec=Project)
    mock_project.id = "test-project-id"
    mock_project.owner_id = "test-user-id"
    
    mock_repo = MagicMock(spec=ProjectRepository)
    mock_repo.get_by_id_for_owner.return_value = mock_project
    
    # Mock the DB and user
    mock_db = MagicMock()
    mock_user = MagicMock(spec=User)
    mock_user.id = "test-user-id"

    # Create request payload
    payload = GenerateRequest(
        messages=[{"role": "user", "content": "Test message"}],
        model="openai/gpt-4o",
        project_id="test-project-id",
        temperature=0.7,
        max_tokens=1000,
        system_prompt="Test system prompt"
    )
    
    # Make orchestrator raise an exception
    with patch("api.endpoints.ProjectRepository", return_value=mock_repo), \
         patch("api.endpoints.orchestrator.process_generation_request", side_effect=Exception("Test exception")):
        
        # Call the endpoint
        response = await generate_completion_endpoint(payload, mock_user, mock_db)
        
        # Verify response - note that API returns 200 with error in the stream
        assert isinstance(response, StreamingResponse)
        assert response.status_code == 200
        
        # Get the content from the streaming response
        content = []
        async for chunk in response.body_iterator:
            # Handle both string and bytes chunks
            if isinstance(chunk, bytes):
                content.append(chunk.decode("utf-8"))
            else:
                content.append(chunk)
        
        content_str = ''.join(content)
        assert 'data: ' in content_str
        
        # Parse the JSON data from the SSE format
        json_data = json.loads(content_str.replace('data: ', '').strip())
        assert json_data.get('error') is True
        assert 'Test exception' in json_data.get('message')

# Add to existing test suite
if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
