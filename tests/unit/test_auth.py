# tests/unit/test_auth.py
import pytest
from unittest.mock import patch, MagicMock, call
from fastapi import status, HTTPException, Depends # Import Depends
from fastapi.security import OAuth2PasswordRequestForm # Import form type
from sqlalchemy.orm import Session

# Import items being tested or needed
from api import auth as auth_api
from models.database_models import User
from schemas.user import UserCreate, UserRead
from schemas.token import Token
from repositories.user_repository import UserRepository
from security import create_access_token

# --- Reusable Mock Objects ---
MOCK_DB_USER = User(
    id="test-auth-user-id",
    username="testauthuser",
    email="auth@test.com",
    hashed_password="hashed_password_for_auth_test",
    is_active=True,
    created_at=MagicMock()
)

# --- Test Fixtures ---
@pytest.fixture
def mock_db_session() -> MagicMock:
    return MagicMock(spec=Session)

# --- Test Cases for login_for_access_token ---

@pytest.mark.asyncio
@patch('api.auth.UserRepository')
@patch('api.auth.security.create_access_token') # Patch where create_access_token is used
async def test_login_success_direct_call(
    mock_create_token: MagicMock,
    mock_user_repo_cls: MagicMock,
    mock_db_session: MagicMock
):
    """Test successful login by calling the endpoint function directly."""
    # Arrange
    mock_user_repo_instance = mock_user_repo_cls.return_value
    mock_user_repo_instance.authenticate.return_value = MOCK_DB_USER
    mock_create_token.return_value = "mock_access_token"

    # Mock the form data dependency
    mock_form_data = OAuth2PasswordRequestForm(
        grant_type="password",
        username="auth@test.com",
        password="correct_password",
        scope="", client_id=None, client_secret=None
    )

    # Act
    # Call the function directly, passing mocked dependencies
    token_result = await auth_api.login_for_access_token(
        form_data=mock_form_data, db=mock_db_session
    )

    # Assert
    mock_user_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_user_repo_instance.authenticate.assert_called_once_with(
        identifier=mock_form_data.username, password=mock_form_data.password
    )
    mock_create_token.assert_called_once()
    call_args, call_kwargs = mock_create_token.call_args
    assert call_kwargs['data'] == {"sub": MOCK_DB_USER.id}
    assert isinstance(token_result, Token) # Check type if endpoint returns it directly
    assert token_result.access_token == "mock_access_token"
    assert token_result.token_type == "bearer"


@pytest.mark.asyncio
@patch('api.auth.UserRepository')
async def test_login_failure_direct_call(
    mock_user_repo_cls: MagicMock,
    mock_db_session: MagicMock
):
    """Test failed login by calling the endpoint function directly."""
    # Arrange
    mock_user_repo_instance = mock_user_repo_cls.return_value
    mock_user_repo_instance.authenticate.return_value = None # Auth fails

    mock_form_data = OAuth2PasswordRequestForm(
        grant_type="password",
        username="auth@test.com",
        password="wrong_password",
        scope="", client_id=None, client_secret=None
    )

    # Act & Assert Exception
    with pytest.raises(HTTPException) as exc_info:
        await auth_api.login_for_access_token(form_data=mock_form_data, db=mock_db_session)

    # Assert exception details
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Incorrect username or password" in exc_info.value.detail
    # Check repo calls
    mock_user_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_user_repo_instance.authenticate.assert_called_once_with(
        identifier=mock_form_data.username, password=mock_form_data.password
    )

# --- Test Cases for register_user ---

@pytest.mark.asyncio
@patch('api.auth.UserRepository')
async def test_register_success_direct_call(
    mock_user_repo_cls: MagicMock,
    mock_db_session: MagicMock
):
    """Test successful user registration by calling the function directly."""
    # Arrange
    mock_user_repo_instance = mock_user_repo_cls.return_value
    mock_user_repo_instance.get_by_email.return_value = None
    mock_user_repo_instance.get_by_username.return_value = None

    created_user_mock = MOCK_DB_USER # Use the mock user

    mock_user_repo_instance.create.return_value = created_user_mock

    # Create the input schema object
    user_in_schema = UserCreate(
        username="newuser", email="register@test.com",
        password="password123"
    )

    # Act
    registered_user = await auth_api.register_user(user_in=user_in_schema, db=mock_db_session)

    # Assert
    mock_user_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_user_repo_instance.get_by_email.assert_called_once_with(email=user_in_schema.email)
    mock_user_repo_instance.get_by_username.assert_called_once_with(username=user_in_schema.username)
    mock_user_repo_instance.create.assert_called_once_with(obj_in=user_in_schema)
    # Check returned object matches mocked one
    assert registered_user == created_user_mock


@pytest.mark.asyncio
@patch('api.auth.UserRepository')
async def test_register_failure_email_exists_direct_call(
    mock_user_repo_cls: MagicMock,
    mock_db_session: MagicMock
):
    """Test failed registration (email exists) by calling function directly."""
    # Arrange
    mock_user_repo_instance = mock_user_repo_cls.return_value
    mock_user_repo_instance.get_by_email.return_value = MOCK_DB_USER # Email exists

    user_in_schema = UserCreate(
        username="newuser_dup_email", email=MOCK_DB_USER.email,
        password="password123"
    )

    # Act & Assert Exception
    with pytest.raises(HTTPException) as exc_info:
        await auth_api.register_user(user_in=user_in_schema, db=mock_db_session)

    # Assert exception details
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Email already registered" in exc_info.value.detail
    # Check repo calls
    mock_user_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_user_repo_instance.get_by_email.assert_called_once_with(email=user_in_schema.email)
    mock_user_repo_instance.get_by_username.assert_not_called()
    mock_user_repo_instance.create.assert_not_called()


@pytest.mark.asyncio
@patch('api.auth.UserRepository')
async def test_register_failure_username_exists_direct_call(
    mock_user_repo_cls: MagicMock,
    mock_db_session: MagicMock
):
    """Test failed registration (username exists) by calling function directly."""
    # Arrange
    mock_user_repo_instance = mock_user_repo_cls.return_value
    mock_user_repo_instance.get_by_email.return_value = None # Email unique
    mock_user_repo_instance.get_by_username.return_value = MOCK_DB_USER # Username exists

    user_in_schema = UserCreate(
        username=MOCK_DB_USER.username, email="unique@test.com",
        password="password123"
    )

    # Act & Assert Exception
    with pytest.raises(HTTPException) as exc_info:
        await auth_api.register_user(user_in=user_in_schema, db=mock_db_session)

    # Assert exception details
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Username already registered" in exc_info.value.detail
    # Check repo calls
    mock_user_repo_cls.assert_called_once_with(db=mock_db_session)
    mock_user_repo_instance.get_by_email.assert_called_once_with(email=user_in_schema.email)
    mock_user_repo_instance.get_by_username.assert_called_once_with(username=user_in_schema.username)
    mock_user_repo_instance.create.assert_not_called()