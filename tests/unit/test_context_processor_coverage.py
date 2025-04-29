# tests/unit/test_context_processor_coverage.py
import os
import uuid
import pytest
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Import the module we're testing
import services.context_processor as context_processor
from models.database_models import Project, ProjectStatus
from repositories.project_repository import ProjectRepository

def test_process_repository_context_chroma_add_failure():
    """
    Test handling when ChromaDB collection.add raises an exception.
    This targets the error handling in the try/except block where Chroma operations occur.
    """
    # Setup test project data
    project_id = str(uuid.uuid4())
    test_repo_path = "test/repo/path"
    
    # Create a mock project
    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = "test-user-id"
    mock_project.status = ProjectStatus.INDEXING
    
    # Mock ProjectRepository
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.return_value = mock_project
    
    # Mock DB session
    mock_db = MagicMock(spec=Session)
    mock_session_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_db)))
    
    # Mock file system operations
    mock_walk_results = [
        (test_repo_path, [], ["test.py"]),
    ]
    
    # Setup mocks for chromadb and file operations
    with patch('os.walk', return_value=mock_walk_results), \
         patch('builtins.open', mock_open(read_data="def test(): return 'test content'")), \
         patch.object(context_processor, 'get_chroma_client') as mock_get_client, \
         patch.object(context_processor, 'get_embedding_function') as mock_get_embedding, \
         patch.object(context_processor, 'ProjectRepository', return_value=mock_project_repo):
        
        # Setup ChromaDB mock to raise exception during add
        mock_collection = MagicMock()
        mock_collection.add.side_effect = Exception("Failed to add to collection")
        
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        
        mock_get_client.return_value = mock_client
        mock_get_embedding.return_value = MagicMock()
        
        # Execute the function we're testing
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # Verify the collection.add was called
        mock_collection.add.assert_called_once()
        
        # Verify project status was updated to FAILED
        assert mock_project.status == ProjectStatus.FAILED
        mock_db.add.assert_called_once_with(mock_project)
        mock_db.commit.assert_called_once()

def test_process_repository_context_db_error_during_failure_handling():
    """
    Test handling when DB throws exception during project status update to FAILED.
    This targets the nested exception handling in the error handling section.
    """
    # Setup test project data
    project_id = str(uuid.uuid4())
    test_repo_path = "test/repo/path"
    
    # Create a mock project
    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = "test-user-id"
    mock_project.status = ProjectStatus.INDEXING
    
    # Mock ProjectRepository
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.return_value = mock_project
    
    # Mock DB session - make commit raise an exception
    mock_db = MagicMock(spec=Session)
    mock_db.commit.side_effect = SQLAlchemyError("DB commit failed")
    mock_session_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_db)))
    
    # Setup mocks that force an exception in the main processing
    with patch.object(context_processor, 'get_chroma_client') as mock_get_client, \
         patch.object(context_processor, 'ProjectRepository', return_value=mock_project_repo), \
         patch('services.context_processor.logger') as mock_logger:
        
        # Make get_chroma_client raise an exception to force the error handling path
        mock_get_client.side_effect = Exception("Failed to initialize Chroma client")
        
        # Execute the function we're testing
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # Verify project status was updated to FAILED
        assert mock_project.status == ProjectStatus.FAILED
        mock_db.add.assert_called_once_with(mock_project)
        
        # Verify DB commit was called and failed
        mock_db.commit.assert_called_once()
        
        # Verify error was logged - both for the main exception and the DB commit exception
        assert mock_logger.error.call_count >= 2
        
        # Look for the DB commit error in the logs
        db_error_logged = False
        for call in mock_logger.error.call_args_list:
            if any("DB commit failed" in str(arg) for arg in call[0]):
                db_error_logged = True
                break
        
        assert db_error_logged, "DB commit error should be logged"

def test_project_null_during_error_handling():
    """
    Test the case where project is None during error handling.
    This covers the project = None check in the error handling section.
    """
    # Setup test project data
    project_id = str(uuid.uuid4())
    test_repo_path = "test/repo/path"
    
    # Mock ProjectRepository to return None
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.return_value = None
    
    # Mock DB session
    mock_db = MagicMock(spec=Session)
    mock_session_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_db)))
    
    # Setup mocks that force an exception in the main processing
    with patch.object(context_processor, 'get_chroma_client') as mock_get_client, \
         patch.object(context_processor, 'ProjectRepository', return_value=mock_project_repo), \
         patch('services.context_processor.logger') as mock_logger:
        
        # Make get_chroma_client raise an exception to force the error handling path
        mock_get_client.side_effect = Exception("Failed to initialize Chroma client")
        
        # Execute the function we're testing
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # Verify the project was looked up
        mock_project_repo.get.assert_called_once_with(project_id)
        
        # Verify we logged that the project wasn't found
        project_not_found_logged = False
        for call in mock_logger.error.call_args_list:
            if any("Project not found" in str(arg) for arg in call[0]):
                project_not_found_logged = True
                break
        
        assert project_not_found_logged, "Missing project should be logged"
        
        # Ensure we didn't try to update a non-existent project
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

def test_exception_during_project_status_lookup():
    """
    Test the case where looking up the project raises an exception during error handling.
    This covers the try/except around project_repo.get in the error handling section.
    """
    # Setup test project data
    project_id = str(uuid.uuid4())
    test_repo_path = "test/repo/path"
    
    # Mock ProjectRepository to raise exception on get
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.side_effect = Exception("Failed to get project")
    
    # Mock DB session
    mock_db = MagicMock(spec=Session)
    mock_session_factory = MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=mock_db)))
    
    # Setup mocks that force an exception in the main processing
    with patch.object(context_processor, 'get_chroma_client') as mock_get_client, \
         patch.object(context_processor, 'ProjectRepository', return_value=mock_project_repo), \
         patch('services.context_processor.logger') as mock_logger:
        
        # Make get_chroma_client raise an exception to force the error handling path
        mock_get_client.side_effect = Exception("Failed to initialize Chroma client")
        
        # Execute the function we're testing
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # Verify the project lookup was attempted
        mock_project_repo.get.assert_called_once_with(project_id)
        
        # Verify we logged both the main exception and the project lookup exception
        assert mock_logger.error.call_count >= 2
        
        # Ensure we didn't try to update a non-existent project
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()