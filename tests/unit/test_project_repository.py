# tests/unit/test_project_repository.py

import pytest
import uuid
from unittest.mock import MagicMock, patch, call, ANY
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # For simulating DB errors

# Import models and schemas used by the repository
from models.database_models import Project, ContextStatus, Base # Import Base if needed for spec
from schemas.project import ProjectCreate, ProjectUpdate

# Import the repository to test
from repositories.project_repository import ProjectRepository

# --- Fixtures ---

@pytest.fixture
def mock_db_session() -> MagicMock:
    return MagicMock(spec=Session)

@pytest.fixture
def project_repo(mock_db_session: MagicMock) -> ProjectRepository:
    # Correct: ProjectRepository.__init__ only takes db
    return ProjectRepository(db=mock_db_session)

# Removed project_repo_with_mock_model fixture

@pytest.fixture
def test_owner_id() -> str:
    return str(uuid.uuid4())

@pytest.fixture
def test_project_id() -> str:
    return str(uuid.uuid4())

@pytest.fixture
def mock_project_instance(test_project_id: str, test_owner_id: str) -> MagicMock:
    proj = MagicMock(spec=Project)
    proj.id = test_project_id
    proj.owner_id = test_owner_id
    proj.name = "Original Name"
    proj.repository_url = None
    proj.context_status = ContextStatus.NONE
    return proj

# --- Test Cases ---

# --- get_by_id_for_owner ---
def test_get_by_id_for_owner_found(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_project_id: str, test_owner_id: str):
    mock_query_result = MagicMock(first=MagicMock(return_value=mock_project_instance))
    mock_filter = mock_db_session.query.return_value.filter
    mock_filter.return_value = mock_query_result
    result = project_repo.get_by_id_for_owner(project_id=test_project_id, owner_id=test_owner_id)
    mock_db_session.query.assert_called_once_with(Project)
    mock_filter.assert_called_once()
    mock_query_result.first.assert_called_once()
    assert result is mock_project_instance

def test_get_by_id_for_owner_not_found(project_repo: ProjectRepository, mock_db_session: MagicMock, test_project_id: str, test_owner_id: str):
    mock_query_result = MagicMock(first=MagicMock(return_value=None))
    mock_db_session.query.return_value.filter.return_value = mock_query_result
    result = project_repo.get_by_id_for_owner(project_id=test_project_id, owner_id=test_owner_id)
    mock_db_session.query.assert_called_once_with(Project)
    mock_db_session.query.return_value.filter.assert_called_once()
    mock_query_result.first.assert_called_once()
    assert result is None

# --- get_multi_by_owner ---
def test_get_multi_by_owner_found(project_repo: ProjectRepository, mock_db_session: MagicMock, test_owner_id: str):
    # Arrange
    mock_projects = [MagicMock(spec=Project), MagicMock(spec=Project)]
    skip, limit = 5, 10

    # ---> FIX: Explicit chain definition using return_value <---
    mock_query = mock_db_session.query.return_value
    mock_filter = mock_query.filter.return_value
    mock_order_by = mock_filter.order_by.return_value
    mock_offset = mock_order_by.offset.return_value
    mock_limit = mock_offset.limit.return_value
    # Set the final return value on the mock for the 'all' method
    mock_limit.all.return_value = mock_projects

    # Act
    results = project_repo.get_multi_by_owner(owner_id=test_owner_id, skip=skip, limit=limit)

    # Assert
    mock_db_session.query.assert_called_once_with(Project)
    mock_query.filter.assert_called_once()
    # Optionally check filter arguments if needed:
    # filter_call_args = mock_query.filter.call_args[0]
    # assert str(test_owner_id) in str(filter_call_args[0])
    mock_filter.order_by.assert_called_once()
    mock_order_by.offset.assert_called_once_with(skip) # Check the call on the correct mock
    mock_offset.limit.assert_called_once_with(limit)
    mock_limit.all.assert_called_once()
    # <--- END FIX ---

    assert results == mock_projects

def test_get_multi_by_owner_empty(project_repo: ProjectRepository, mock_db_session: MagicMock, test_owner_id: str):
    mock_all_method = MagicMock(return_value=[])
    mock_limit_method = mock_db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value
    mock_limit_method.all = mock_all_method # Attach the mock 'all' method
    results = project_repo.get_multi_by_owner(owner_id=test_owner_id)
    assert results == []
    mock_all_method.assert_called_once()

# --- create_with_owner ---
def test_create_with_owner_no_repo(project_repo: ProjectRepository, mock_db_session: MagicMock, test_owner_id: str):
    create_schema = ProjectCreate(name="Test No Repo", description="Desc")
    created_obj_capture = None
    def add_side_effect(obj):
        nonlocal created_obj_capture
        assert isinstance(obj, Project)
        assert obj.name == create_schema.name and obj.repository_url is None and obj.owner_id == test_owner_id and obj.context_status == ContextStatus.NONE
        created_obj_capture = obj
    mock_db_session.add.side_effect = add_side_effect
    created_project = project_repo.create_with_owner(obj_in=create_schema, owner_id=test_owner_id)
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(created_obj_capture)
    assert created_project is created_obj_capture

def test_create_with_owner_with_repo(project_repo: ProjectRepository, mock_db_session: MagicMock, test_owner_id: str):
    repo_url = "http://github.com/test/repo"
    create_schema = ProjectCreate(name="Test With Repo", repository_url=repo_url)
    created_obj_capture = None
    def add_side_effect(obj):
        nonlocal created_obj_capture
        assert isinstance(obj, Project)
        assert obj.repository_url == repo_url and obj.owner_id == test_owner_id and obj.context_status == ContextStatus.PENDING
        created_obj_capture = obj
    mock_db_session.add.side_effect = add_side_effect
    created_project = project_repo.create_with_owner(obj_in=create_schema, owner_id=test_owner_id)
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(created_obj_capture)
    assert created_project is created_obj_capture

def test_create_with_owner_db_error(project_repo: ProjectRepository, mock_db_session: MagicMock, test_owner_id: str):
    create_schema = ProjectCreate(name="DB Error Test")
    db_error = SQLAlchemyError("Simulated DB commit error")
    mock_db_session.commit.side_effect = db_error
    with pytest.raises(SQLAlchemyError, match="Simulated DB commit error"):
        project_repo.create_with_owner(obj_in=create_schema, owner_id=test_owner_id)
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_called_once()
    mock_db_session.refresh.assert_not_called()

# FIX: Use patch.object on the repo instance's 'model' attribute
def test_create_with_owner_model_init_error(
    project_repo: ProjectRepository, # Use standard repo fixture
    mock_db_session: MagicMock,
    test_owner_id: str
):
    # Arrange
    create_schema = ProjectCreate(name="Init Error Test")
    init_error = TypeError("Simulated model init error")

    # Create a mock for the Project class specifically for this test
    mock_project_class_for_test = MagicMock(spec=Project)
    # Configure its instantiation (__call__) to raise the error
    mock_project_class_for_test.side_effect = init_error

    # Patch the 'model' attribute ON THE INSTANCE of the repo
    with patch.object(project_repo, 'model', mock_project_class_for_test):
        # Act & Assert
        with pytest.raises(TypeError, match="Simulated model init error"):
            # This call will now use the patched self.model
            project_repo.create_with_owner(obj_in=create_schema, owner_id=test_owner_id)

        # Assert the mocked model class was called (instantiation attempted)
        mock_project_class_for_test.assert_called_once()
        # Assert DB not touched
        mock_db_session.add.assert_not_called()
        mock_db_session.commit.assert_not_called()
        mock_db_session.rollback.assert_not_called()
# END FIX

# --- update_with_owner_check ---
def test_update_with_owner_check_not_found(project_repo: ProjectRepository, test_project_id: str, test_owner_id: str):
    update_schema = ProjectUpdate(name="New Name")
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=None) as mock_get:
        result = project_repo.update_with_owner_check(project_id=test_project_id, owner_id=test_owner_id, obj_in=update_schema)
        mock_get.assert_called_once_with(project_id=test_project_id, owner_id=test_owner_id)
        assert result is None

def test_update_with_owner_check_dict_input(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    update_dict = {"name": "Updated via Dict"}
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance):
        result = project_repo.update_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id, obj_in=update_dict)
    assert mock_project_instance.name == "Updated via Dict"
    mock_db_session.add.assert_called_once_with(mock_project_instance)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(mock_project_instance)
    assert result is mock_project_instance

def test_update_with_owner_check_schema_input(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    update_schema = ProjectUpdate(name="Updated via Schema")
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance):
        result = project_repo.update_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id, obj_in=update_schema)
    assert mock_project_instance.name == "Updated via Schema"
    mock_db_session.commit.assert_called_once()
    assert result is mock_project_instance

def test_update_with_owner_check_add_repo_url(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    assert mock_project_instance.repository_url is None
    assert mock_project_instance.context_status == ContextStatus.NONE
    new_repo_url = "http://example.com/new"
    update_schema = ProjectUpdate(repository_url=new_repo_url)
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance):
        result = project_repo.update_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id, obj_in=update_schema)
    assert mock_project_instance.repository_url == new_repo_url
    assert mock_project_instance.context_status == ContextStatus.PENDING
    mock_db_session.commit.assert_called_once()
    assert result is mock_project_instance

def test_update_with_owner_check_change_repo_url(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    mock_project_instance.repository_url = "http://original.url"
    mock_project_instance.context_status = ContextStatus.READY
    new_repo_url = "http://changed.url"
    update_schema = ProjectUpdate(repository_url=new_repo_url)
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance):
        result = project_repo.update_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id, obj_in=update_schema)
    assert mock_project_instance.repository_url == new_repo_url
    assert mock_project_instance.context_status == ContextStatus.PENDING
    mock_db_session.commit.assert_called_once()
    assert result is mock_project_instance

def test_update_with_owner_check_already_pending(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    mock_project_instance.repository_url = "http://original.url"
    mock_project_instance.context_status = ContextStatus.PENDING
    new_repo_url = "http://changed.url"
    update_schema = ProjectUpdate(repository_url=new_repo_url)
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance):
        result = project_repo.update_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id, obj_in=update_schema)
    assert mock_project_instance.repository_url == new_repo_url
    assert mock_project_instance.context_status == ContextStatus.PENDING
    mock_db_session.commit.assert_called_once()
    assert result is mock_project_instance

def test_update_with_owner_check_no_changes(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    mock_project_instance.name = "Same Name"
    update_schema = ProjectUpdate(name="Same Name")
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance):
        result = project_repo.update_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id, obj_in=update_schema)
    assert mock_project_instance.name == "Same Name"
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_called()
    mock_db_session.refresh.assert_not_called()
    assert result is mock_project_instance

def test_update_with_owner_check_db_error(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    update_schema = ProjectUpdate(name="Update triggers error")
    db_error = SQLAlchemyError("Simulated update commit error")
    mock_db_session.commit.side_effect = db_error
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance):
        with pytest.raises(SQLAlchemyError, match="Simulated update commit error"):
            project_repo.update_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id, obj_in=update_schema)
    mock_db_session.add.assert_called_once_with(mock_project_instance)
    mock_db_session.commit.assert_called_once()
    mock_db_session.rollback.assert_called_once()
    mock_db_session.refresh.assert_not_called()

# --- remove_with_owner_check ---

def test_remove_with_owner_check_success(project_repo: ProjectRepository, mock_db_session: MagicMock, mock_project_instance: MagicMock, test_owner_id: str):
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=mock_project_instance) as mock_get:
        deleted_project = project_repo.remove_with_owner_check(project_id=mock_project_instance.id, owner_id=test_owner_id)
    mock_get.assert_called_once_with(project_id=mock_project_instance.id, owner_id=test_owner_id)
    mock_db_session.delete.assert_called_once_with(mock_project_instance)
    mock_db_session.commit.assert_called_once()
    assert deleted_project is mock_project_instance

def test_remove_with_owner_check_not_found(project_repo: ProjectRepository, mock_db_session: MagicMock, test_project_id: str, test_owner_id: str):
    with patch.object(project_repo, 'get_by_id_for_owner', return_value=None) as mock_get:
        result = project_repo.remove_with_owner_check(project_id=test_project_id, owner_id=test_owner_id)
    mock_get.assert_called_once_with(project_id=test_project_id, owner_id=test_owner_id)
    mock_db_session.delete.assert_not_called()
    mock_db_session.commit.assert_not_called()
    assert result is None