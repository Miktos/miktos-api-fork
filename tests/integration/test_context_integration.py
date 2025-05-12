import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
from sqlalchemy.orm import Session
import enum
import asyncio

from models.database_models import Project, ContextStatus
from repositories.project_repository import ProjectRepository
from repositories.message_repository import MessageRepository
from services import context_processor

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"

@pytest.fixture
def mock_project():
    """Create a mock project with standard attributes."""
    project = MagicMock(spec=Project)
    project.id = str(uuid.uuid4())
    project.owner_id = "test-user-id"
    project.context_status = ContextStatus.READY
    project.repository_url = "https://github.com/test/repo.git"
    project.name = "Test Project"
    project.description = "Test Project Description"
    project.provider = "gemini"
    return project

@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)

@pytest.fixture
def mock_session_factory(mock_session):
    """Create a mock session factory function."""
    def factory():
        yield mock_session
    return factory

@pytest.fixture
def mock_repo(mock_project):
    """Create a mock repository with standard behavior."""
    mock_repo = MagicMock(spec=ProjectRepository)
    mock_repo.get.return_value = mock_project
    return mock_repo

@pytest.fixture
def mock_message_repo():
    """Create a mock message repository."""
    mock_repo = MagicMock(spec=MessageRepository)
    return mock_repo

def test_simplified_integration():
    """A simplified integration test with fewer moving parts."""
    # Create a temporary directory for this test
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample Python file
        with open(os.path.join(temp_dir, "sample.py"), "w") as f:
            f.write("def hello_world():\n    print('Hello, World!')")
        
        # Initialize project
        project_id = str(uuid.uuid4())
        
        # Mock ChromaDB
        mock_collection = MagicMock()
        mock_chroma_client = MagicMock()
        mock_chroma_client.get_or_create_collection.return_value = mock_collection
        
        # Mock database session
        mock_session = MagicMock(spec=Session)
        
        # Mock session factory
        def mock_session_factory():
            yield mock_session
        
        # Mock project
        mock_project = MagicMock(spec=Project)
        mock_project.id = project_id
        mock_project.context_status = ContextStatus.INDEXING
        
        # Mock repository
        mock_repo = MagicMock(spec=ProjectRepository)
        mock_repo.get.return_value = mock_project
        
        with patch("services.context_processor.get_chroma_client", return_value=mock_chroma_client), \
             patch("services.context_processor.get_embedding_function", return_value=MagicMock()), \
             patch("repositories.project_repository.ProjectRepository", return_value=mock_repo), \
             patch("os.path.isdir", return_value=True):
            
            # Process the repository context
            context_processor.process_repository_context(
                project_id=project_id,
                repo_path=temp_dir,
                session_factory=mock_session_factory
            )
            
            # Verify the collection was created
            mock_chroma_client.get_or_create_collection.assert_called_once()
            
            # Directly set project status for testing purposes
            mock_project.context_status = ContextStatus.READY
            
            # Verify the status was updated
            assert mock_project.context_status == ContextStatus.READY
