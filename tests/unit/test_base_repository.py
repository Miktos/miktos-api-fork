# tests/unit/test_base_repository.py

import pytest
import uuid
from unittest.mock import MagicMock, call, patch
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
# Import SQLAlchemy types needed for mocking model
from sqlalchemy.orm import Session, Mapped, mapped_column
from fastapi.encoders import jsonable_encoder # Import for patching

# Import the Base class and BaseRepository
from models.database_models import Base # Make sure Base itself is correctly defined
from repositories.base_repository import BaseRepository

# --- Test Setup ---

# 1. Mock SQLAlchemy Model using SQLAlchemy 2.0 Mapped annotations
class MockUser(Base):
    # Minimal mock - __tablename__ needed for SQLAlchemy internals
    __tablename__ = "mock_users"

    # Use Mapped[] type hints and mapped_column for configuration
    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[Optional[str]] # Optional[str] becomes Mapped[Optional[str]]
    email: Mapped[Optional[str]]

    # Optional: Add __repr__ for easier debugging if needed
    def __repr__(self):
        return f"<MockUser(id={self.id!r}, name={self.name!r}, email={self.email!r})>"

    # Keep helper for mocking jsonable_encoder if used
    def as_dict(self):
        # Important: Access actual attributes, not class-level defaults
        return {"id": getattr(self, 'id', None),
                "name": getattr(self, 'name', None),
                "email": getattr(self, 'email', None)}

# 2. Mock Pydantic Schemas (These remain the same)
class MockUserCreate(BaseModel):
    name: str
    email: str

class MockUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

# 3. Fixtures (These remain the same)
@pytest.fixture
def mock_db_session() -> MagicMock:
    return MagicMock(spec=Session)

@pytest.fixture
def base_repo(mock_db_session: MagicMock) -> BaseRepository[MockUser, MockUserCreate, MockUserUpdate]:
    # Instantiate BaseRepository with our Mock types
    return BaseRepository(model=MockUser, db=mock_db_session)

# --- Test Cases (Logic remains the same, uses the corrected MockUser) ---

def test_base_get_found(base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    # Instantiate mock object for testing
    mock_user_instance = MockUser()
    mock_user_instance.id = str(uuid.uuid4()) # Set instance attributes
    mock_user_instance.name = "Test User"
    mock_user_instance.email = "test@example.com"
    item_id = mock_user_instance.id

    # Mock the query chain
    mock_query_result = MagicMock()
    mock_query_result.first.return_value = mock_user_instance
    mock_query_chain = MagicMock()
    mock_query_chain.filter.return_value = mock_query_result

    with patch.object(mock_db_session, 'query') as mock_query:
        mock_query.return_value = mock_query_chain

        # Act
        result = base_repo.get(item_id=item_id)

        # Assert
        mock_query.assert_called_once_with(MockUser)
        mock_query_chain.filter.assert_called_once()
        mock_query_result.first.assert_called_once()
        assert result is mock_user_instance
        assert result.name == "Test User" # Verify attribute access

def test_base_get_not_found(base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    item_id = str(uuid.uuid4())
    mock_query_result = MagicMock(first=MagicMock(return_value=None))
    mock_query_chain = MagicMock(filter=MagicMock(return_value=mock_query_result))

    with patch.object(mock_db_session, 'query') as mock_query:
        mock_query.return_value = mock_query_chain
        result = base_repo.get(item_id=item_id)
        mock_query.assert_called_once_with(MockUser)
        mock_query_chain.filter.assert_called_once()
        mock_query_result.first.assert_called_once()
        assert result is None

def test_base_get_multi_found(base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    mock_users = [MockUser(), MockUser()] # Instantiate
    mock_users[0].id = str(uuid.uuid4()); mock_users[0].name = "User 1"
    mock_users[1].id = str(uuid.uuid4()); mock_users[1].name = "User 2"
    skip_val = 5
    limit_val = 10

    with patch.object(mock_db_session, 'query') as mock_query:
        mock_limit = mock_query.return_value.offset.return_value.limit
        mock_all = mock_limit.return_value.all
        mock_all.return_value = mock_users

        # Act
        results = base_repo.get_multi(skip=skip_val, limit=limit_val)

        # Assert
        mock_query.assert_called_once_with(base_repo.model)
        mock_query.return_value.offset.assert_called_once_with(skip_val)
        mock_limit.assert_called_once_with(limit_val)
        mock_all.assert_called_once()
        assert results == mock_users

def test_base_get_multi_empty(base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    skip_val = 0
    limit_val = 100
    with patch.object(mock_db_session, 'query') as mock_query:
        mock_limit = mock_query.return_value.offset.return_value.limit
        mock_all = mock_limit.return_value.all
        mock_all.return_value = []

        # Act
        results = base_repo.get_multi(skip=skip_val, limit=limit_val)

        # Assert
        mock_query.assert_called_once_with(base_repo.model)
        mock_query.return_value.offset.assert_called_once_with(skip_val)
        mock_limit.assert_called_once_with(limit_val)
        mock_all.assert_called_once()
        assert results == []

def test_base_create(base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    user_in = MockUserCreate(name="New User", email="new@example.com")
    # We don't need to predict the ID if we capture the object
    created_db_obj_capture = None

    def refresh_side_effect(obj):
        nonlocal created_db_obj_capture
        # Simulate refresh maybe loading some defaults or just making it persistent
        created_db_obj_capture = obj # Capture the object passed to refresh
    mock_db_session.refresh.side_effect = refresh_side_effect

    added_obj_capture = None
    def add_side_effect(obj):
        nonlocal added_obj_capture
        added_obj_capture = obj # Capture the object passed to add
    mock_db_session.add.side_effect = add_side_effect

    # Act
    created_user = base_repo.create(obj_in=user_in)

    # Assert
    mock_db_session.add.assert_called_once()
    assert added_obj_capture is not None
    assert isinstance(added_obj_capture, MockUser)
    assert added_obj_capture.name == user_in.name # Check attributes set before add
    assert added_obj_capture.email == user_in.email

    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(added_obj_capture) # Refreshed the added obj

    # Check returned object IS the one captured during refresh
    assert created_user is created_db_obj_capture
    # Ensure attributes are correct on the returned object
    assert created_user.name == user_in.name
    assert created_user.email == user_in.email


@patch('repositories.base_repository.jsonable_encoder')
def test_base_update_with_schema(mock_jsonable_encoder: MagicMock, base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    db_obj = MockUser()
    db_obj.id="existing_id"
    db_obj.name="Old Name"
    db_obj.email="old@example.com"

    # Mock the behavior of jsonable_encoder based on the *instance* state
    mock_jsonable_encoder.return_value = {"id": db_obj.id, "name": db_obj.name, "email": db_obj.email}

    user_update = MockUserUpdate(name="Updated Name") # Email is None/unset

    # Act
    updated_user = base_repo.update(db_obj=db_obj, obj_in=user_update)

    # Assert
    mock_jsonable_encoder.assert_called_once_with(db_obj)

    # Verify instance attributes were updated directly
    assert db_obj.name == "Updated Name"
    assert db_obj.email == "old@example.com" # Should remain unchanged

    # Check DB operations
    mock_db_session.add.assert_called_once_with(db_obj)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(db_obj)
    assert updated_user is db_obj # Should return the same instance


@patch('repositories.base_repository.jsonable_encoder')
def test_base_update_with_dict(mock_jsonable_encoder: MagicMock, base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    db_obj = MockUser()
    db_obj.id="existing_id_dict"
    db_obj.name="Old Name Dict"
    db_obj.email="old_dict@example.com"

    mock_jsonable_encoder.return_value = {"id": db_obj.id, "name": db_obj.name, "email": db_obj.email}
    update_dict = {"email": "new_dict@example.com"} # Update email only

    # Act
    updated_user = base_repo.update(db_obj=db_obj, obj_in=update_dict)

    # Assert
    mock_jsonable_encoder.assert_called_once_with(db_obj)
    # Verify instance attributes
    assert db_obj.name == "Old Name Dict" # Unchanged
    assert db_obj.email == "new_dict@example.com" # Updated

    mock_db_session.add.assert_called_once_with(db_obj)
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(db_obj)
    assert updated_user is db_obj

def test_base_remove_found(base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    mock_user_instance = MockUser()
    mock_user_instance.id = "user_to_delete"
    mock_user_instance.name = "Delete Me"

    mock_query_result = MagicMock(first=MagicMock(return_value=mock_user_instance))
    mock_query_chain = MagicMock(filter=MagicMock(return_value=mock_query_result))

    with patch.object(mock_db_session, 'query') as mock_query:
        mock_query.return_value = mock_query_chain

        # Act
        deleted_user = base_repo.remove(item_id=mock_user_instance.id)

        # Assert
        mock_query.assert_called_once_with(MockUser)
        mock_query_chain.filter.assert_called_once()
        mock_query_result.first.assert_called_once()
        mock_db_session.delete.assert_called_once_with(mock_user_instance)
        mock_db_session.commit.assert_called_once()
        assert deleted_user is mock_user_instance

def test_base_remove_not_found(base_repo: BaseRepository, mock_db_session: MagicMock):
    # Arrange
    item_id_not_found = str(uuid.uuid4())
    mock_query_result = MagicMock(first=MagicMock(return_value=None))
    mock_query_chain = MagicMock(filter=MagicMock(return_value=mock_query_result))

    with patch.object(mock_db_session, 'query') as mock_query:
        mock_query.return_value = mock_query_chain

        # Act
        result = base_repo.remove(item_id=item_id_not_found)

        # Assert
        mock_query.assert_called_once_with(MockUser)
        mock_query_chain.filter.assert_called_once()
        mock_query_result.first.assert_called_once()
        mock_db_session.delete.assert_not_called()
        mock_db_session.commit.assert_not_called()
        assert result is None