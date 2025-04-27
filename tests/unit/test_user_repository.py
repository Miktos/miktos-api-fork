# tests/unit/test_user_repository.py
import pytest
from unittest.mock import patch, MagicMock, call
from sqlalchemy.orm import Session
from typing import Optional

# Import the repository and model/schemas it uses
from repositories.user_repository import UserRepository
from models.database_models import User
from schemas.user import UserCreate, UserUpdate

# Import password utils for mocking and verification
from utils import password_utils

# --- Fixtures ---
@pytest.fixture
def mock_db_session() -> MagicMock:
    """Provides a mock SQLAlchemy session."""
    # Mock the query chain
    mock_session = MagicMock(spec=Session)
    mock_query = MagicMock()
    mock_filtered_query = MagicMock()
    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_filtered_query
    # first() and all() will be configured per test
    return mock_session

@pytest.fixture
def user_repo(mock_db_session: MagicMock) -> UserRepository:
    """Provides an instance of UserRepository with a mock session."""
    return UserRepository(db=mock_db_session)

# --- Test Cases ---

# Test Getters
def test_get_by_id(user_repo: UserRepository, mock_db_session: MagicMock):
    """Test retrieving a user by their ID."""
    mock_user = User(id="user-1", username="test", email="test@get.com", hashed_password="abc")
    # Configure the final step of the query chain for this test
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user

    # Act
    result = user_repo.get_by_id("user-1")

    # Assert
    mock_db_session.query.assert_called_once_with(User)
    # Check the filter condition (more complex, may need ANY or specific checks)
    # For simplicity, just check first() was called
    mock_db_session.query.return_value.filter.return_value.first.assert_called_once()
    assert result == mock_user

def test_get_by_id_not_found(user_repo: UserRepository, mock_db_session: MagicMock):
    """Test retrieving a non-existent user by ID."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    result = user_repo.get_by_id("non-existent")
    assert result is None

def test_get_by_username(user_repo: UserRepository, mock_db_session: MagicMock):
    """Test retrieving a user by username."""
    mock_user = User(id="user-2", username="get_user", email="get@user.com", hashed_password="abc")
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user
    result = user_repo.get_by_username("get_user")
    mock_db_session.query.return_value.filter.return_value.first.assert_called_once()
    assert result == mock_user

def test_get_by_email(user_repo: UserRepository, mock_db_session: MagicMock):
    """Test retrieving a user by email."""
    mock_user = User(id="user-3", username="get_email", email="get@email.com", hashed_password="abc")
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user
    result = user_repo.get_by_email("get@email.com")
    mock_db_session.query.return_value.filter.return_value.first.assert_called_once()
    assert result == mock_user

# Test Create
# Patch the password hashing function used within the repository method
@patch('repositories.user_repository.get_password_hash')
def test_create_user(mock_get_hash: MagicMock, user_repo: UserRepository, mock_db_session: MagicMock):
    """Test creating a new user, verifying password hashing."""
    # Arrange
    mock_get_hash.return_value = "hashed_password_from_mock"
    user_in = UserCreate(username="newuser", email="new@user.com", password="password123")

    # Act
    created_user = user_repo.create(obj_in=user_in)

    # Assert
    mock_get_hash.assert_called_once_with("password123")
    # Check db.add was called with a User object having the hashed password
    assert mock_db_session.add.call_count == 1
    added_obj = mock_db_session.add.call_args[0][0] # Get the object passed to add()
    assert isinstance(added_obj, User)
    assert added_obj.username == "newuser"
    assert added_obj.email == "new@user.com"
    assert added_obj.hashed_password == "hashed_password_from_mock"
    assert added_obj.is_active is True # Check default activation
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(added_obj)
    assert created_user == added_obj # Should return the created object

# Test Update
@patch('repositories.user_repository.get_password_hash')
def test_update_user_with_password(mock_get_hash: MagicMock, user_repo: UserRepository, mock_db_session: MagicMock):
    """Test updating a user, including hashing a new password."""
    # Arrange
    mock_get_hash.return_value = "new_hashed_password"
    existing_user_db_obj = User(id="user-update", username="orig_user", email="orig@user.com", hashed_password="old_hash", is_active=True)
    user_update_schema = UserUpdate(username="updated_user", password="new_password123")

    # Act
    updated_user = user_repo.update(db_obj=existing_user_db_obj, obj_in=user_update_schema)

    # Assert
    mock_get_hash.assert_called_once_with("new_password123")
    # Check attributes were updated on the original object
    assert existing_user_db_obj.username == "updated_user"
    assert existing_user_db_obj.email == "orig@user.com" # Not updated
    assert existing_user_db_obj.hashed_password == "new_hashed_password"
    assert existing_user_db_obj.is_active is True # Not updated
    # Check DB operations
    mock_db_session.add.assert_called_once_with(existing_user_db_obj)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(existing_user_db_obj)
    assert updated_user == existing_user_db_obj

def test_update_user_without_password(user_repo: UserRepository, mock_db_session: MagicMock):
    """Test updating a user without changing the password."""
    # Arrange
    existing_user_db_obj = User(id="user-update-np", username="orig_user_np", email="orig_np@user.com", hashed_password="old_hash_np", is_active=True)
    user_update_schema = UserUpdate(email="updated_np@user.com", is_active=False)

    # Act
    with patch('repositories.user_repository.get_password_hash') as mock_get_hash_not_called:
        updated_user = user_repo.update(db_obj=existing_user_db_obj, obj_in=user_update_schema)

    # Assert
    mock_get_hash_not_called.assert_not_called() # Password hash function should not be called
    assert existing_user_db_obj.username == "orig_user_np" # Not updated
    assert existing_user_db_obj.email == "updated_np@user.com"
    assert existing_user_db_obj.hashed_password == "old_hash_np" # Unchanged
    assert existing_user_db_obj.is_active is False
    mock_db_session.add.assert_called_once_with(existing_user_db_obj)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(existing_user_db_obj)
    assert updated_user == existing_user_db_obj

# Test Authenticate
# Patch the verify_password function used within the repository method
@patch('repositories.user_repository.verify_password')
def test_authenticate_success_email(mock_verify_pwd: MagicMock, user_repo: UserRepository, mock_db_session: MagicMock):
    """Test successful authentication using email."""
    # Arrange
    mock_user = User(id="auth-user-1", username="auth_user", email="auth@test.com", hashed_password="correct_hash")
    # Mock get_by_email to return the user, get_by_username returns None
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        mock_user, # First call (get_by_email) returns user
        None       # Second call (get_by_username) returns None
    ]
    mock_verify_pwd.return_value = True # Simulate correct password

    # Act
    authenticated_user = user_repo.authenticate(identifier="auth@test.com", password="correct_password")

    # Assert
    assert mock_db_session.query.return_value.filter.call_count == 1 # Only filtered by email
    mock_verify_pwd.assert_called_once_with("correct_password", "correct_hash")
    assert authenticated_user == mock_user

@patch('repositories.user_repository.verify_password')
def test_authenticate_success_username(mock_verify_pwd: MagicMock, user_repo: UserRepository, mock_db_session: MagicMock):
    """Test successful authentication using username."""
    # Arrange
    mock_user = User(id="auth-user-2", username="auth_user_name", email="auth_name@test.com", hashed_password="correct_hash_2")
    # Mock get_by_email returns None, get_by_username returns user
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        None,      # First call (get_by_email) returns None
        mock_user  # Second call (get_by_username) returns user
    ]
    mock_verify_pwd.return_value = True

    # Act
    authenticated_user = user_repo.authenticate(identifier="auth_user_name", password="correct_password")

    # Assert
    assert mock_db_session.query.return_value.filter.call_count == 2 # Filtered by email then username
    mock_verify_pwd.assert_called_once_with("correct_password", "correct_hash_2")
    assert authenticated_user == mock_user

@patch('repositories.user_repository.verify_password')
def test_authenticate_incorrect_password(mock_verify_pwd: MagicMock, user_repo: UserRepository, mock_db_session: MagicMock):
    """Test authentication failure due to incorrect password."""
    # Arrange
    mock_user = User(id="auth-user-3", username="wrong_pass", email="wrong@pass.com", hashed_password="correct_hash_3")
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [mock_user, None] # Found by email
    mock_verify_pwd.return_value = False # Simulate incorrect password

    # Act
    authenticated_user = user_repo.authenticate(identifier="wrong@pass.com", password="incorrect_password")

    # Assert
    assert mock_db_session.query.return_value.filter.call_count == 1
    mock_verify_pwd.assert_called_once_with("incorrect_password", "correct_hash_3")
    assert authenticated_user is None

def test_authenticate_user_not_found(user_repo: UserRepository, mock_db_session: MagicMock):
    """Test authentication failure due to user not found."""
    # Arrange
    # Mock get_by_email and get_by_username to return None
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [None, None]

    # Act
    authenticated_user = user_repo.authenticate(identifier="notfound@user.com", password="any_password")

    # Assert
    assert mock_db_session.query.return_value.filter.call_count == 2 # Checked email then username
    # Verify password function should not be called
    # (No easy way to assert this without patching verify_password unnecessarily)
    assert authenticated_user is None