# tests/unit/test_api_projects.py

import pytest
import uuid
from unittest.mock import MagicMock, patch, ANY, call
from typing import Optional, List

# Added HTTPException, BackgroundTasks imports
from fastapi import FastAPI, status, BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from pydantic import BaseModel # For creating input schemas

# Import the router, schemas, models used in the projects API
from api import projects as projects_api
from schemas.project import ProjectCreate, ProjectUpdate, ProjectRead # Use real schemas
from models.database_models import User, Project, Message, ContextStatus # Use real models for spec
# Import SessionLocal for session_factory argument check
from config.database import SessionLocal

# --- Test Setup ---

# Create app instance with the projects router
app = FastAPI()
# IMPORTANT: Mount the router without its internal prefix, TestClient needs full path
app.include_router(projects_api.router, prefix="") # Mount at root for TestClient

# Define the actual prefix for use in test requests
API_PREFIX = "/api/v1/projects"

# Mock user data
@pytest.fixture
def mock_user_instance() -> User:
    user = MagicMock(spec=User)
    user.id = "test_user_id_projects"
    user.username = "project_user"
    return user

# Mock DB session
@pytest.fixture
def mock_db_session_fixture() -> MagicMock:
    session = MagicMock(spec=Session)
    session._is_test_db = False # Default to non-test mode
    return session

# Override dependencies
def override_get_current_user_for_projects():
    user = MagicMock(spec=User)
    user.id = "test_user_id_projects"
    user.username = "project_user"
    return user

@pytest.fixture(autouse=True) # Apply this automatically
def override_dependencies(mock_db_session_fixture: MagicMock, mock_user_instance: User):
    # Ensure overrides are applied to the correct app instance
    test_app_instance = app # Use the app defined in this module
    test_app_instance.dependency_overrides[projects_api.get_db] = lambda: mock_db_session_fixture
    test_app_instance.dependency_overrides[projects_api.get_current_user] = lambda: mock_user_instance
    yield # Run the test
    # Clean up overrides after test
    test_app_instance.dependency_overrides = {}


# Client fixture using the app with overrides
@pytest.fixture
def client() -> TestClient:
     # Ensure TestClient uses the app instance with the router mounted at root
    return TestClient(app)

# --- Mocks for Repositories and Services ---

@pytest.fixture
def mock_project_repo():
    with patch('api.projects.ProjectRepository') as MockRepo:
        repo_instance = MockRepo.return_value
        yield repo_instance

@pytest.fixture
def mock_message_repo():
    with patch('api.projects.MessageRepository') as MockRepo:
        repo_instance = MockRepo.return_value
        yield repo_instance

@pytest.fixture
def mock_background_tasks():
    with patch('api.projects.git_service.clone_or_update_repository') as mock_clone, \
         patch('api.projects.git_service.remove_repository') as mock_remove:
        yield {"clone": mock_clone, "remove": mock_remove}


# --- Helper Functions (Optional) ---
def create_mock_project(
    id: uuid.UUID, owner_id: str, repo_url: Optional[str] = None, status: ContextStatus = ContextStatus.NONE
) -> MagicMock:
    proj = MagicMock(spec=Project)
    proj.id = id
    proj.owner_id = owner_id
    proj.repository_url = repo_url
    proj.context_status = status
    proj.name = "Mock Project"
    proj.description = "Mock Desc"
    proj.context_notes = "Mock Notes"
    proj.created_at = None
    proj.updated_at = None
    return proj

# --- Test Cases ---

# --- POST / (Create Project) ---

def test_create_project_no_repo(
    client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks
):
    # Arrange
    project_id = uuid.uuid4()
    input_data = ProjectCreate(name="Test Project No Repo", description="Desc")
    mock_created_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.create_with_owner.return_value = mock_created_project

    # Act - Use API_PREFIX
    response = client.post(f"{API_PREFIX}/", json=input_data.model_dump())

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    mock_project_repo.create_with_owner.assert_called_once_with(
        obj_in=input_data, owner_id=mock_user_instance.id
    )
    mock_background_tasks["clone"].assert_not_called()
    assert response.json()["id"] == str(project_id)
    assert response.json()["repository_url"] is None

def test_create_project_with_repo_pending(
    client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks
):
    # Arrange
    project_id = uuid.uuid4()
    repo_url = "http://test.repo/project.git"
    input_data = ProjectCreate(name="Test Project With Repo", repository_url=repo_url)
    mock_created_project = create_mock_project(
        id=project_id, owner_id=mock_user_instance.id, repo_url=repo_url, status=ContextStatus.PENDING
    )
    mock_project_repo.create_with_owner.return_value = mock_created_project

    # Act - Use API_PREFIX
    response = client.post(f"{API_PREFIX}/", json=input_data.model_dump())

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    mock_project_repo.create_with_owner.assert_called_once()
    mock_background_tasks["clone"].assert_called_once_with(
        project_id=str(project_id),
        repo_url=repo_url,
        session_factory=SessionLocal # Check correct factory passed
    )
    assert response.json()["id"] == str(project_id)
    assert response.json()["repository_url"] == repo_url
    assert response.json()["context_status"] == ContextStatus.PENDING.value

def test_create_project_with_repo_not_pending(
    client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks
):
    # Arrange
    project_id = uuid.uuid4()
    repo_url = "http://test.repo/project.git"
    input_data = ProjectCreate(name="Test Project With Repo", repository_url=repo_url)
    mock_created_project = create_mock_project(
        id=project_id, owner_id=mock_user_instance.id, repo_url=repo_url, status=ContextStatus.READY # Not PENDING
    )
    mock_project_repo.create_with_owner.return_value = mock_created_project

    # Act - Use API_PREFIX
    response = client.post(f"{API_PREFIX}/", json=input_data.model_dump())

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    mock_project_repo.create_with_owner.assert_called_once()
    mock_background_tasks["clone"].assert_not_called() # Status wasn't PENDING
    assert response.json()["context_status"] == ContextStatus.READY.value

def test_create_project_with_repo_test_db(
    client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks, mock_db_session_fixture: MagicMock
):
    # Arrange
    mock_db_session_fixture._is_test_db = True # Set the flag
    project_id = uuid.uuid4()
    repo_url = "http://test.repo/project.git"
    input_data = ProjectCreate(name="Test Project Test DB", repository_url=repo_url)
    mock_created_project = create_mock_project(
        id=project_id, owner_id=mock_user_instance.id, repo_url=repo_url, status=ContextStatus.PENDING
    )
    mock_project_repo.create_with_owner.return_value = mock_created_project

    # Act - Use API_PREFIX
    response = client.post(f"{API_PREFIX}/", json=input_data.model_dump())

    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    mock_background_tasks["clone"].assert_not_called() # Task skipped

def test_create_project_repo_fails(
    client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks
):
    # Arrange
    input_data = ProjectCreate(name="Fail Project")
    mock_project_repo.create_with_owner.side_effect = Exception("DB Error")

    # Act - Use API_PREFIX
    response = client.post(f"{API_PREFIX}/", json=input_data.model_dump())

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to create project" in response.json()["detail"]
    mock_background_tasks["clone"].assert_not_called()

def test_create_project_background_task_add_fails(
     client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks
):
     # Arrange
    project_id = uuid.uuid4()
    repo_url = "http://test.repo/project.git"
    input_data = ProjectCreate(name="Task Fail Project", repository_url=repo_url)
    mock_created_project = create_mock_project(
        id=project_id, owner_id=mock_user_instance.id, repo_url=repo_url, status=ContextStatus.PENDING
    )
    mock_project_repo.create_with_owner.return_value = mock_created_project
    # Patch BackgroundTasks.add_task globally for this test
    with patch('fastapi.BackgroundTasks.add_task', side_effect=Exception("Task Add Error")) as mock_add_task:
         # Act - Use API_PREFIX
         response = client.post(f"{API_PREFIX}/", json=input_data.model_dump())

    # Assert
    assert response.status_code == status.HTTP_201_CREATED # Endpoint should still succeed
    mock_add_task.assert_called_once() # Check that adding the task was attempted
    mock_background_tasks["clone"].assert_not_called() # Actual service function not called

# --- GET / (Get Projects) ---

def test_get_projects_success(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User):
    # Arrange
    mock_projects_list = [ create_mock_project(uuid.uuid4(), mock_user_instance.id), create_mock_project(uuid.uuid4(), mock_user_instance.id) ]
    mock_project_repo.get_multi_by_owner.return_value = mock_projects_list
    skip, limit = 0, 50

    # Act - Use API_PREFIX
    response = client.get(f"{API_PREFIX}/?skip={skip}&limit={limit}")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_project_repo.get_multi_by_owner.assert_called_once_with( owner_id=mock_user_instance.id, skip=skip, limit=limit )
    assert len(response.json()) == len(mock_projects_list)
    assert response.json()[0]["id"] == str(mock_projects_list[0].id)

def test_get_projects_empty(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User):
    # Arrange
    mock_project_repo.get_multi_by_owner.return_value = []
    # Act - Use API_PREFIX
    response = client.get(f"{API_PREFIX}/")
    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_project_repo.get_multi_by_owner.assert_called_once()
    assert response.json() == []

# --- GET /{project_id} (Get Project) ---

def test_get_project_success(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    mock_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.get_by_id_for_owner.return_value = mock_project
    # Act - Use API_PREFIX
    response = client.get(f"{API_PREFIX}/{project_id}")
    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_project_repo.get_by_id_for_owner.assert_called_once_with( project_id=project_id, owner_id=mock_user_instance.id )
    assert response.json()["id"] == str(project_id)

def test_get_project_not_found(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    mock_project_repo.get_by_id_for_owner.return_value = None
    # Act - Use API_PREFIX
    response = client.get(f"{API_PREFIX}/{project_id}")
    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # Check the detail from the HTTPException raised by the endpoint
    assert response.json()["detail"] == "Project not found or not owned by current user"
    mock_project_repo.get_by_id_for_owner.assert_called_once_with( project_id=project_id, owner_id=mock_user_instance.id )

# --- PATCH /{project_id} (Update Project) ---

def test_update_project_success_no_repo_change(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks):
    # Arrange
    project_id = uuid.uuid4()
    update_data = ProjectUpdate(description="New Description")
    mock_existing_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id, repo_url="http://original.url")
    mock_project_repo.get_by_id_for_owner.return_value = mock_existing_project
    mock_updated_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id, repo_url="http://original.url")
    mock_updated_project.description = "New Description"
    mock_project_repo.update_with_owner_check.return_value = mock_updated_project

    # Act - Use API_PREFIX
    response = client.patch(f"{API_PREFIX}/{project_id}", json=update_data.model_dump(exclude_unset=True))

    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_project_repo.get_by_id_for_owner.assert_called_once_with(project_id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.update_with_owner_check.assert_called_once_with( project_id=project_id, owner_id=mock_user_instance.id, obj_in=update_data )
    mock_background_tasks["clone"].assert_not_called()
    assert response.json()["description"] == "New Description"
    assert response.json()["repository_url"] == "http://original.url"

def test_update_project_add_repo_url(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks):
    # Arrange
    project_id = uuid.uuid4()
    new_repo_url = "http://new.repo"
    update_data = ProjectUpdate(repository_url=new_repo_url)
    mock_existing_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id, repo_url=None)
    mock_project_repo.get_by_id_for_owner.return_value = mock_existing_project
    mock_updated_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id, repo_url=new_repo_url, status=ContextStatus.PENDING)
    mock_project_repo.update_with_owner_check.return_value = mock_updated_project

    # Act - Use API_PREFIX
    response = client.patch(f"{API_PREFIX}/{project_id}", json=update_data.model_dump(exclude_unset=True))

    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_project_repo.update_with_owner_check.assert_called_once()
    mock_background_tasks["clone"].assert_called_once_with( project_id=str(project_id), repo_url=new_repo_url, session_factory=SessionLocal )
    assert response.json()["repository_url"] == new_repo_url
    assert response.json()["context_status"] == ContextStatus.PENDING.value

def test_update_project_change_repo_url_not_pending(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks):
    # Arrange
    project_id = uuid.uuid4()
    new_repo_url = "http://changed.repo"
    update_data = ProjectUpdate(repository_url=new_repo_url)
    mock_existing_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id, repo_url="http://original.url")
    mock_project_repo.get_by_id_for_owner.return_value = mock_existing_project
    mock_updated_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id, repo_url=new_repo_url, status=ContextStatus.READY)
    mock_project_repo.update_with_owner_check.return_value = mock_updated_project

    # Act - Use API_PREFIX
    response = client.patch(f"{API_PREFIX}/{project_id}", json=update_data.model_dump(exclude_unset=True))

    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_background_tasks["clone"].assert_not_called()
    assert response.json()["repository_url"] == new_repo_url
    assert response.json()["context_status"] == ContextStatus.READY.value


def test_update_project_not_found(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    update_data = ProjectUpdate(description="New Desc")
    mock_project_repo.get_by_id_for_owner.return_value = None

    # Act - Use API_PREFIX
    response = client.patch(f"{API_PREFIX}/{project_id}", json=update_data.model_dump(exclude_unset=True))

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # Check the specific detail message
    assert response.json()["detail"] == "Project not found or not owned by current user to update"
    mock_project_repo.get_by_id_for_owner.assert_called_once()
    mock_project_repo.update_with_owner_check.assert_not_called() # Update shouldn't be called

def test_update_project_empty_data(client: TestClient):
    # Arrange
    project_id = uuid.uuid4()
    update_data = {}

    # Act - Use API_PREFIX
    response = client.patch(f"{API_PREFIX}/{project_id}", json=update_data)

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "No update data provided" in response.json()["detail"]

def test_update_project_repo_raises_http_exception(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    update_data = ProjectUpdate(description="Trigger HTTP Error")
    mock_existing_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.get_by_id_for_owner.return_value = mock_existing_project
    mock_project_repo.update_with_owner_check.side_effect = HTTPException(status_code=409, detail="Conflict during update")

    # Act - Use API_PREFIX
    response = client.patch(f"{API_PREFIX}/{project_id}", json=update_data.model_dump(exclude_unset=True))

    # Assert
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"] == "Conflict during update"
    mock_project_repo.update_with_owner_check.assert_called_once()

def test_update_project_repo_raises_generic_exception(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    update_data = ProjectUpdate(description="Trigger Generic Error")
    mock_existing_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.get_by_id_for_owner.return_value = mock_existing_project
    mock_project_repo.update_with_owner_check.side_effect = Exception("Generic DB error during update")

    # Act - Use API_PREFIX
    response = client.patch(f"{API_PREFIX}/{project_id}", json=update_data.model_dump(exclude_unset=True))

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to process project update" in response.json()["detail"]
    mock_project_repo.update_with_owner_check.assert_called_once()


# --- DELETE /{project_id} ---

def test_delete_project_success(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks):
    # Arrange
    project_id = uuid.uuid4()
    mock_deleted_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.remove_with_owner_check.return_value = mock_deleted_project

    # Act - Use API_PREFIX
    response = client.delete(f"{API_PREFIX}/{project_id}")

    # Assert
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_project_repo.remove_with_owner_check.assert_called_once_with( project_id=project_id, owner_id=mock_user_instance.id )
    mock_background_tasks["remove"].assert_called_once_with(project_id=str(project_id))

def test_delete_project_success_test_db(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks, mock_db_session_fixture):
    # Arrange
    mock_db_session_fixture._is_test_db = True # Set flag
    project_id = uuid.uuid4()
    mock_deleted_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.remove_with_owner_check.return_value = mock_deleted_project

    # Act - Use API_PREFIX
    response = client.delete(f"{API_PREFIX}/{project_id}")

    # Assert
    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_project_repo.remove_with_owner_check.assert_called_once()
    mock_background_tasks["remove"].assert_not_called() # Task skipped

def test_delete_project_not_found(client: TestClient, mock_project_repo: MagicMock, mock_user_instance: User, mock_background_tasks):
    # Arrange
    project_id = uuid.uuid4()
    mock_project_repo.remove_with_owner_check.return_value = None

    # Act - Use API_PREFIX
    response = client.delete(f"{API_PREFIX}/{project_id}")

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # Check specific detail
    assert response.json()["detail"] == "Project not found or not owned by current user to delete"
    mock_project_repo.remove_with_owner_check.assert_called_once_with( project_id=project_id, owner_id=mock_user_instance.id )
    mock_background_tasks["remove"].assert_not_called()

# --- GET /{project_id}/messages ---

def test_get_project_messages_success(client: TestClient, mock_project_repo: MagicMock, mock_message_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    mock_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.get_by_id_for_owner.return_value = mock_project

    mock_messages_list = [MagicMock(spec=Message), MagicMock(spec=Message)]
    mock_messages_list[0].id=uuid.uuid4(); mock_messages_list[0].project_id=project_id; mock_messages_list[0].role="user"; mock_messages_list[0].content="Hi"; mock_messages_list[0].created_at=None; mock_messages_list[0].model=None; mock_messages_list[0].message_metadata=None; mock_messages_list[0].user_id=None
    mock_messages_list[1].id=uuid.uuid4(); mock_messages_list[1].project_id=project_id; mock_messages_list[1].role="assistant"; mock_messages_list[1].content="Hello"; mock_messages_list[1].created_at=None; mock_messages_list[1].model=None; mock_messages_list[1].message_metadata=None; mock_messages_list[1].user_id=None
    mock_message_repo.get_multi_by_project.return_value = mock_messages_list
    skip, limit = 5, 10

    # Act - Use API_PREFIX
    response = client.get(f"{API_PREFIX}/{project_id}/messages?skip={skip}&limit={limit}")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_project_repo.get_by_id_for_owner.assert_called_once_with(project_id=project_id, owner_id=mock_user_instance.id)
    # Corrected assertion for message repo call (now includes user_id)
    mock_message_repo.get_multi_by_project.assert_called_once_with(project_id=project_id, user_id=mock_user_instance.id, skip=skip, limit=limit)
    assert len(response.json()) == len(mock_messages_list)
    assert response.json()[0]["role"] == "user"

def test_get_project_messages_project_not_found(client: TestClient, mock_project_repo: MagicMock, mock_message_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    mock_project_repo.get_by_id_for_owner.return_value = None

    # Act - Use API_PREFIX
    response = client.get(f"{API_PREFIX}/{project_id}/messages")

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # Check specific detail
    assert response.json()["detail"] == "Project not found or not owned by current user"
    mock_project_repo.get_by_id_for_owner.assert_called_once_with(project_id=project_id, owner_id=mock_user_instance.id)
    mock_message_repo.get_multi_by_project.assert_not_called()

def test_get_project_messages_no_messages(client: TestClient, mock_project_repo: MagicMock, mock_message_repo: MagicMock, mock_user_instance: User):
    # Arrange
    project_id = uuid.uuid4()
    mock_project = create_mock_project(id=project_id, owner_id=mock_user_instance.id)
    mock_project_repo.get_by_id_for_owner.return_value = mock_project
    mock_message_repo.get_multi_by_project.return_value = []

    # Act - Use API_PREFIX
    response = client.get(f"{API_PREFIX}/{project_id}/messages")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    mock_project_repo.get_by_id_for_owner.assert_called_once()
    mock_message_repo.get_multi_by_project.assert_called_once()
    assert response.json() == []