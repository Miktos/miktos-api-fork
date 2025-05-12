# tests/unit/test_context_processor_extended.py
import uuid
import os
import sys
import pytest
from unittest.mock import MagicMock, patch, mock_open
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Add the root directory to the Python path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the module we're testing
from services import context_processor
from models.database_models import Project, ContextStatus
from repositories.project_repository import ProjectRepository

@pytest.fixture
def mock_project():
    """Create a mock project with standard attributes."""
    mock_project = MagicMock(spec=Project)
    mock_project.id = str(uuid.uuid4())
    mock_project.owner_id = "test-user-id"
    mock_project.context_status = ContextStatus.INDEXING
    mock_project.repository_url = "https://github.com/test/repo.git"
    return mock_project

@pytest.fixture
def mock_repo():
    """Create a mock repository with standard behavior."""
    mock_repo = MagicMock(spec=ProjectRepository)
    return mock_repo

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

def test_process_repository_context_minimal_success(mock_project, mock_repo, mock_session_factory):
    """Test minimal success case for context processing with reduced mocking."""
    # Setup mocks
    mock_repo.get.return_value = mock_project
    
    # Create minimal patches
    with patch("os.path.isdir", return_value=False):  # Short-circuit the processing
        # Call the function - should exit early with no errors
        context_processor.process_repository_context(
            project_id=mock_project.id,
            repo_path="/nonexistent/path",
            session_factory=mock_session_factory
        )
        
        # If we get here without exceptions, the test passes
        # Note: collection.add may not be called if no valid chunks are found

def test_process_repository_context_chroma_error(mock_project, mock_repo, mock_session_factory):
    """Test handling of ChromaDB errors."""
    # Setup mocks
    mock_repo.get.return_value = mock_project
    
    # Create patches
    with patch("os.path.exists", return_value=True), \
         patch('services.context_processor.get_chroma_client') as mock_get_client, \
         patch('services.context_processor.ProjectRepository', return_value=mock_repo):
        
        # Setup ChromaDB mock to raise exception
        mock_client = MagicMock()
        mock_client.get_or_create_collection.side_effect = Exception("ChromaDB error")
        mock_get_client.return_value = mock_client
        
        # Call the function - should handle the exception
        context_processor.process_repository_context(
            project_id=mock_project.id,
            repo_path="/fake/repo/path",
            session_factory=mock_session_factory
        )
        
        # The function should catch the exception and not raise

def test_process_repository_context_repository_not_found(mock_project, mock_repo, mock_session_factory):
    """Test handling when repository directory does not exist."""
    # Setup mocks
    mock_repo.get.return_value = mock_project
    
    # Create patches - path doesn't exist
    with patch("os.path.exists", return_value=False), \
         patch('services.context_processor.ProjectRepository', return_value=mock_repo):
        
        # Call the function
        context_processor.process_repository_context(
            project_id=mock_project.id,
            repo_path="/nonexistent/path",
            session_factory=mock_session_factory
        )
        
        # Should handle gracefully without raising exception

def test_process_repository_context_db_error_fetching_project(mock_repo, mock_session_factory):
    """Test handling of database errors when fetching the project."""
    # Setup mocks - project repo returns None for project
    mock_repo.get.return_value = None
    
    # Create patches
    with patch('services.context_processor.ProjectRepository', return_value=mock_repo):
        
        # Call the function - should not raise an exception
        context_processor.process_repository_context(
            project_id="test-project-id",
            repo_path="/fake/repo/path",
            session_factory=mock_session_factory
        )
        
        # Function should handle the error gracefully

# Add to existing test suite
if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
