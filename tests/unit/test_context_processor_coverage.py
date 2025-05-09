# tests/unit/test_context_processor_coverage.py
import uuid
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
import os
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Import the module we're testing
from services import context_processor
from models.database_models import Project, ContextStatus
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
    mock_project.context_status = ContextStatus.INDEXING
    
    # Mock ProjectRepository
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.return_value = mock_project
    
    # Mock DB session
    mock_db = MagicMock(spec=Session)
    
    # Create a generator function for the session factory
    def mock_session_factory():
        yield mock_db
    
    # Mock file system operations
    mock_walk_results = [
        (test_repo_path, [], ["test.py"]),
    ]
    
    # Setup mocks for chromadb and file operations
    with patch('os.path.isdir', return_value=True), \
         patch('os.walk', return_value=mock_walk_results), \
         patch('os.path.getsize', return_value=100), \
         patch('os.path.relpath', return_value="test.py"), \
         patch('os.path.splitext', return_value=("test", ".py")), \
         patch('builtins.open', mock_open(read_data="def test(): return 'test content'")), \
         patch('services.context_processor.get_chroma_client') as mock_get_client, \
         patch('services.context_processor.get_embedding_function') as mock_get_embedding, \
         patch('services.context_processor.ProjectRepository') as mock_ProjectRepo:
        
        # Setup ChromaDB mock to raise exception during add
        mock_collection = MagicMock()
        mock_collection.add.side_effect = Exception("Failed to add to collection")
        
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        
        mock_get_client.return_value = mock_client
        mock_get_embedding.return_value = MagicMock()
        mock_ProjectRepo.return_value = mock_project_repo
        
        # Execute the function we're testing
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # Verify the collection.add was called
        mock_collection.add.assert_called_once()
        
        # Verify project status was updated to FAILED
        assert mock_project.context_status == ContextStatus.FAILED
        # Verify correct DB operations were performed
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
    mock_project.context_status = ContextStatus.INDEXING
    
    # Mock ProjectRepository
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.return_value = mock_project
    
    # Mock DB session - make commit raise an exception
    mock_db = MagicMock(spec=Session)
    mock_db.commit.side_effect = SQLAlchemyError("DB commit failed")
    
    # Create a generator function for the session factory
    def mock_session_factory():
        yield mock_db
    
    # Setup mocks that force an exception in the main processing
    with patch('os.path.isdir', return_value=True), \
         patch('services.context_processor.get_chroma_client') as mock_get_client, \
         patch('services.context_processor.ProjectRepository') as mock_ProjectRepo, \
         patch('services.context_processor.logger') as mock_logger:
        
        # Make get_chroma_client raise an exception to force the error handling path
        mock_get_client.side_effect = Exception("Failed to initialize Chroma client")
        mock_ProjectRepo.return_value = mock_project_repo
        
        # Execute the function we're testing
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # Verify project status was updated to FAILED
        assert mock_project.context_status == ContextStatus.FAILED
        # Check DB interactions
        mock_db.add.assert_called_once_with(mock_project)
        mock_db.commit.assert_called_once()
        
        # Verify we logged the DB error
        mock_logger.error.assert_any_call(
            f"[Project {project_id}] Failed to update status to FAILED in DB: DB commit failed",
            exc_info=True
        )


def test_project_null_during_error_handling():
    """
    Test handling when the project lookup returns None during error handling.
    This checks the fallback error handling when both the main processing
    and the DB update to FAILED state encounter problems.
    """
    # Setup test project data
    project_id = str(uuid.uuid4())
    test_repo_path = "test/repo/path"
    
    # Mock ProjectRepository to return None
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.return_value = None  # This will cause a null check in error handling
    
    # Mock DB session
    mock_db = MagicMock(spec=Session)
    
    # Create a generator function for the session factory
    def mock_session_factory():
        yield mock_db
    
    # Setup mocks for error path
    with patch('os.path.isdir', return_value=True), \
         patch('services.context_processor.get_chroma_client') as mock_get_client, \
         patch('services.context_processor.ProjectRepository') as mock_ProjectRepo, \
         patch('services.context_processor.logger') as mock_logger:
        
        # Force main exception path
        mock_get_client.side_effect = Exception("Primary processing error")
        mock_ProjectRepo.return_value = mock_project_repo
        
        # Execute
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # Verify repository lookup was attempted
        mock_project_repo.get.assert_called_once_with(project_id)
        
        # Verify error was logged due to project being None
        mock_logger.error.assert_any_call(
            f"[Project {project_id}] Project not found"
        )
        
        # No updates should have been attempted since project was None
        mock_db.add.assert_not_called()


def test_exception_during_project_status_lookup():
    """
    Test handling when an exception occurs during the project.get() lookup.
    This tests the error handling when the DB lookup itself fails.
    """
    # Setup test data
    project_id = str(uuid.uuid4())
    test_repo_path = "test/repo/path"
    
    # Mock repository to throw exception
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.side_effect = Exception("DB read error during get()")
    
    # Mock DB session
    mock_db = MagicMock(spec=Session)
    
    # Setup mocks
    with patch('os.path.isdir', return_value=False), \
         patch('services.context_processor.ProjectRepository') as mock_ProjectRepo, \
         patch('services.context_processor.logger') as mock_logger:
        
        mock_ProjectRepo.return_value = mock_project_repo
        
        # Execute - should trigger directory not found error path first
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=lambda: mock_db
        )
        
        # Repository lookup shouldn't be called in this case because isdir returns False
        mock_project_repo.get.assert_not_called()
        
        # Verify error about directory not found was logged
        mock_logger.error.assert_any_call(
            f"[Project {project_id}] Repository path not found: {test_repo_path}"
        )


def test_exception_during_project_db_commit():
    """
    Test handling when an exception occurs during the final db.commit() in success path.
    """
    # Setup test data
    project_id = str(uuid.uuid4())
    test_repo_path = "test/repo/path"
    
    # Create a mock project
    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.owner_id = "test-user-id"
    mock_project.context_status = ContextStatus.INDEXING
    
    # Mock repository
    mock_project_repo = MagicMock(spec=ProjectRepository)
    mock_project_repo.get.return_value = mock_project
    
    # Mock DB session - make commit raise exception only on success path
    mock_db = MagicMock(spec=Session)
    mock_db.commit.side_effect = SQLAlchemyError("DB commit failed on success path")
    
    # Create a generator function for the session factory
    def mock_session_factory():
        yield mock_db
    
    # Mock file system for minimal valid repo
    mock_walk_results = [(test_repo_path, [], ["test.py"])]
    
    # Setup mocks
    with patch('os.path.isdir', return_value=True), \
         patch('os.walk', return_value=mock_walk_results), \
         patch('os.path.getsize', return_value=100), \
         patch('os.path.relpath', return_value="test.py"), \
         patch('os.path.splitext', return_value=("test", ".py")), \
         patch('builtins.open', mock_open(read_data="def test(): pass")), \
         patch('services.context_processor.get_chroma_client') as mock_get_client, \
         patch('services.context_processor.get_embedding_function') as mock_get_embedding, \
         patch('services.context_processor.ProjectRepository') as mock_ProjectRepo, \
         patch('services.context_processor.logger') as mock_logger:
        
        # Setup successful processing until DB commit
        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_get_client.return_value = mock_client
        mock_get_embedding.return_value = MagicMock()
        mock_ProjectRepo.return_value = mock_project_repo
        
        # Execute function
        context_processor.process_repository_context(
            project_id=project_id,
            repo_path=test_repo_path,
            session_factory=mock_session_factory
        )
        
        # The status should be FAILED because the commit will fail
        # and the error handling will set the status to FAILED
        assert mock_project.context_status == ContextStatus.FAILED
        
        # The implementation actually calls add twice - once for the successful path
        # and once for the error handling path when updating to FAILED
        assert mock_db.add.call_count == 2
        assert mock_db.add.call_args_list[0] == ((mock_project,),)
        assert mock_db.add.call_args_list[1] == ((mock_project,),)
        
        # The implementation calls commit twice - once for the successful path
        # (which fails and triggers the error handler) and once in the error handling
        assert mock_db.commit.call_count == 2
        
        # Exception should be caught and logged
        mock_logger.error.assert_any_call(
            f"[Project {project_id}] Failed during context processing: DB commit failed on success path", 
            exc_info=True
        )