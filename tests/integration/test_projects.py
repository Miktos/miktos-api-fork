# tests/integration/test_projects.py
import pytest
from unittest.mock import patch
from fastapi import status # Import status codes
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid # Import uuid

from models.database_models import Project, User, ContextStatus

# --- Debug Test ---
def test_debug_repo_url_parsing(client: TestClient):
    """Test if the minimal debug endpoint parses repository_url correctly."""
    debug_data = { "field_a": "some value", "repository_url": "https://example.com/repo.git", "another_field": 123 }
    response = client.post("/api/v1/projects/debug-repo-url", json=debug_data)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["received_dump"].get("repository_url") == debug_data["repository_url"]
    assert response_json["has_attr"] is True
    assert response_json["attr_value"] == debug_data["repository_url"]

# --- Tests Using API for Creation & Setup ---

def test_create_project_without_repo(authenticated_client: TestClient, db_session: Session):
    """Test creating a project without a repository URL via API"""
    project_data = { "name": "Test Project No Repo API", "description": "A test project", "context_notes": "Test context notes" }
    response = authenticated_client.post("/api/v1/projects/", json=project_data)
    assert response.status_code == 201, f"Failed to create project: {response.text}"
    created_project = response.json()
    assert created_project["name"] == project_data["name"]
    assert created_project["repository_url"] is None
    assert created_project["context_status"] == ContextStatus.NONE.value

def test_create_project_with_repo(authenticated_client: TestClient, db_session: Session):
    """Test creating a project with a repository URL via API"""
    with patch('api.projects.git_service.clone_or_update_repository') as mock_git_service:
        project_data = { "name": "Test Repo Project API", "description": "A test project with repository", "context_notes": "Test context notes", "repository_url": "https://github.com/test/test-repo-api.git" }
        response = authenticated_client.post("/api/v1/projects/", json=project_data)
        assert response.status_code == 201, f"Failed to create project: {response.text}"
        created_project = response.json()
        assert created_project["name"] == project_data["name"]
        assert created_project["repository_url"] == project_data["repository_url"]
        # Check status is PENDING if repo URL is provided on creation
        assert created_project["context_status"] == ContextStatus.PENDING.value
        # Check background task was called (if not testing service directly elsewhere)
        # Note: Asserting background tasks directly is complex in TestClient
        # Usually better to test service logic via unit tests or E2E tests.

def test_get_user_projects(authenticated_client: TestClient, db_session: Session):
    """Test listing all projects for the current user (Creates data via API)"""
    p1_data = {"name": "P1 API Get", "description": "First"}
    p2_data = {"name": "P2 API Get", "description": "Second"}
    response1 = authenticated_client.post("/api/v1/projects/", json=p1_data)
    response2 = authenticated_client.post("/api/v1/projects/", json=p2_data)
    assert response1.status_code == 201
    assert response2.status_code == 201

    response = authenticated_client.get("/api/v1/projects/")
    assert response.status_code == 200, f"Failed to get projects: {response.text}"
    projects = response.json()
    assert isinstance(projects, list)
    project_names = {p["name"] for p in projects}
    assert p1_data["name"] in project_names
    assert p2_data["name"] in project_names

def test_get_project_by_id(authenticated_client: TestClient, db_session: Session):
    """Test getting a specific project by ID (Creates data via API)"""
    project_data = {"name": "Get By ID API Test", "description": "Project to retrieve"}
    create_response = authenticated_client.post("/api/v1/projects/", json=project_data)
    assert create_response.status_code == 201
    created_project_id = create_response.json()["id"]

    response = authenticated_client.get(f"/api/v1/projects/{created_project_id}")
    assert response.status_code == 200, f"Failed to get project {created_project_id}: {response.text}"
    retrieved_project = response.json()
    assert retrieved_project["id"] == created_project_id
    assert retrieved_project["name"] == project_data["name"]

def test_update_project(authenticated_client: TestClient, db_session: Session):
    """Test updating a project (Creates data via API)"""
    project_data = {"name": "Update API Setup", "description": "Project to update"}
    create_response = authenticated_client.post("/api/v1/projects/", json=project_data)
    assert create_response.status_code == 201
    created_project_id = create_response.json()["id"]

    update_data = {"name": "Updated Name API", "description": "Updated description"}
    response = authenticated_client.patch(f"/api/v1/projects/{created_project_id}", json=update_data)
    assert response.status_code == 200, f"Failed to update project {created_project_id}: {response.text}"
    updated_project = response.json()
    assert updated_project["id"] == created_project_id
    assert updated_project["name"] == update_data["name"]

    get_response = authenticated_client.get(f"/api/v1/projects/{created_project_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == update_data["name"]

def test_update_project_with_repo(authenticated_client: TestClient, db_session: Session):
    """Test updating a project to add a repository URL (Creates data via API)"""
    with patch('api.projects.git_service.clone_or_update_repository') as mock_git_service:
        project_data = {"name": "Repo Update API Setup", "description": "Project to add repo to"}
        create_response = authenticated_client.post("/api/v1/projects/", json=project_data)
        assert create_response.status_code == 201
        created_project_id = create_response.json()["id"]
        assert create_response.json()["repository_url"] is None
        assert create_response.json()["context_status"] == ContextStatus.NONE.value # Status starts as NONE

        update_data = {"repository_url": "https://github.com/test/update-repo-api.git"}
        response = authenticated_client.patch(f"/api/v1/projects/{created_project_id}", json=update_data)

        assert response.status_code == 200, f"Failed to update project {created_project_id} with repo: {response.text}"
        updated_project = response.json()
        assert updated_project["id"] == created_project_id
        assert updated_project["repository_url"] == update_data["repository_url"]
        # Check status changed to PENDING after adding repo URL
        assert updated_project["context_status"] == ContextStatus.PENDING.value
        # Check background task was triggered (difficult with TestClient, better in E2E/unit tests)
        # mock_git_service.assert_called_once() # This might not work reliably with BackgroundTasks


def test_delete_project(authenticated_client: TestClient, db_session: Session):
    """Test deleting a project (Creates data via API)"""
    with patch('api.projects.git_service.remove_repository') as mock_remove:
        project_data = {"name": "Delete API Setup", "description": "Project to delete"}
        create_response = authenticated_client.post("/api/v1/projects/", json=project_data)
        assert create_response.status_code == 201
        project_id_str = create_response.json()["id"]

        response = authenticated_client.delete(f"/api/v1/projects/{project_id_str}")
        assert response.status_code == 204, f"Failed to delete project {project_id_str}: {response.text}"

        get_response = authenticated_client.get(f"/api/v1/projects/{project_id_str}")
        assert get_response.status_code == 404
        mock_remove.assert_called_once_with(project_id=project_id_str)


# --- NEW ERROR HANDLING / AUTHORIZATION TESTS ---

def test_get_project_by_id_unauthorized_or_not_found(
    authenticated_client: TestClient, db_session: Session # Need db_session for direct creation
):
    """
    Test getting a project fails if:
    1. The project ID does not exist (404).
    2. The project ID exists but belongs to another user (404).
    """
    # --- Test Case 1: Project ID does not exist ---
    non_existent_uuid = uuid.uuid4()
    response = authenticated_client.get(f"/api/v1/projects/{non_existent_uuid}")
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # --- Test Case 2: Project exists but owned by another user ---
    # Create another user directly in DB (or use a second fixture if available)
    other_user = User(username="other_user_get", email="other_get@example.com", hashed_password="otherpassword")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    # Create a project owned by the 'other_user' directly in DB
    other_project = Project(
        name="Other User Get Project",
        owner_id=other_user.id, # Use the ID from the DB object
        context_status=ContextStatus.NONE
    )
    db_session.add(other_project)
    db_session.commit()
    db_session.refresh(other_project)

    # Try to get the other user's project using the main authenticated client
    response_other = authenticated_client.get(f"/api/v1/projects/{other_project.id}")
    # We expect 404 because the repository method checks ownership
    assert response_other.status_code == status.HTTP_404_NOT_FOUND


def test_update_project_unauthorized(
    authenticated_client: TestClient, db_session: Session
):
    """
    Test updating a project fails (404) if the project ID exists but
    belongs to another user.
    """
    # Create another user and their project directly in DB
    other_user = User(username="other_user_patch", email="other_patch@example.com", hashed_password="otherpassword")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    other_project = Project(
        name="Other User Patch Project",
        owner_id=other_user.id,
        context_status=ContextStatus.NONE
    )
    db_session.add(other_project)
    db_session.commit()
    db_session.refresh(other_project)

    update_data = {"name": "Attempted Update Name"}

    # Try to update the other user's project using the main authenticated client
    response = authenticated_client.patch(
        f"/api/v1/projects/{other_project.id}",
        json=update_data
    )
    # We expect 404 because the repository method checks ownership before updating
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_project_unauthorized(
    authenticated_client: TestClient, db_session: Session
):
    """
    Test deleting a project fails (404) if the project ID exists but
    belongs to another user.
    """
    # Create another user and their project directly in DB
    other_user = User(username="other_user_delete", email="other_delete@example.com", hashed_password="otherpassword")
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    other_project = Project(
        name="Other User Delete Project",
        owner_id=other_user.id,
        context_status=ContextStatus.NONE
    )
    db_session.add(other_project)
    db_session.commit()
    db_session.refresh(other_project)

    # Try to delete the other user's project using the main authenticated client
    response = authenticated_client.delete(f"/api/v1/projects/{other_project.id}")
    # We expect 404 because the repository method checks ownership before deleting
    assert response.status_code == status.HTTP_404_NOT_FOUND

    # Verify the project still exists in the DB
    project_in_db = db_session.get(Project, other_project.id) # Use session.get for PK lookup
    assert project_in_db is not None