# tests/unit/test_message_repository.py

import pytest
import uuid
from unittest.mock import MagicMock, call, patch
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import UnaryExpression, desc, asc
from sqlalchemy.sql import operators

from fastapi import HTTPException, status
from typing import List, Dict, Any

# Models and Schemas
from models.database_models import Message, Project, User
from schemas.message import MessageCreate, MessageRole

# Repository to test
from repositories.message_repository import MessageRepository

# --- Fixtures ---

@pytest.fixture
def mock_db_session() -> MagicMock:
    """Provides a basic mock SQLAlchemy Session."""
    # Important: Keep spec=Session so the instance *has* a 'query' attribute to patch
    return MagicMock(spec=Session)

@pytest.fixture
def mock_user() -> MagicMock:
    user = MagicMock(spec=User)
    user.id = str(uuid.uuid4())
    return user

@pytest.fixture
def mock_project(mock_user: User) -> MagicMock:
    project = MagicMock(spec=Project)
    project.id = str(uuid.uuid4())
    project.owner_id = mock_user.id
    return project

@pytest.fixture
def message_repo(mock_db_session: MagicMock) -> MessageRepository:
    # The message_repo instance gets the mock_db_session injected.
    # Calls to self.db within the repo methods will use this mock session.
    return MessageRepository(db=mock_db_session)


# --- Test Cases ---

# All tests will now use patch.object instead of the decorator approach
def test_get_multi_by_project_success_asc(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project,
    mock_user: User
):
    # Arrange
    mock_messages = [MagicMock(spec=Message), MagicMock(spec=Message)]
    project_id = mock_project.id
    user_id = mock_user.id
    skip_val = 0
    limit_val = 10

    # -- Configure Mocks for the Chains --
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=mock_project))
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    mock_message_chain_all = MagicMock(all=MagicMock(return_value=mock_messages))
    mock_message_chain_limit = MagicMock(limit=MagicMock(return_value=mock_message_chain_all))
    mock_message_chain_offset = MagicMock(offset=MagicMock(return_value=mock_message_chain_limit))
    mock_message_chain_order_by = MagicMock(order_by=MagicMock(return_value=mock_message_chain_offset))
    mock_message_chain_start = MagicMock(filter=MagicMock(return_value=mock_message_chain_order_by))

    # Use patch.object targeting the 'query' attribute of the specific mock_db_session instance
    with patch.object(mock_db_session, 'query') as mock_query_on_instance:
        # -- Configure the side effect for this specific mock --
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project:
                print(f"--- [patch.object] Mocking db.query({model_class.__name__}) -> Returning Project Chain ---")
                return mock_project_chain_start
            elif model_class == Message:
                print(f"--- [patch.object] Mocking db.query({model_class.__name__}) -> Returning Message Chain ---")
                return mock_message_chain_start
            else:
                print(f"--- [patch.object] WARNING: Unexpected db.query({model_class}) ---")
                return MagicMock()
        mock_query_on_instance.side_effect = query_side_effect

        # Act
        result = message_repo.get_multi_by_project(
            project_id=project_id, user_id=user_id, skip=skip_val, limit=limit_val, ascending=True
        )

        # Assert
        # 1. Check the mock created by patch.object was called correctly
        mock_query_on_instance.assert_has_calls([
            call(Project),
            call(Message)
        ], any_order=False)

        # 2. Check Project query chain calls
        mock_project_chain_start.filter.assert_called_once()
        mock_project_chain_end.first.assert_called_once()

        # 3. Check Message query chain calls
        mock_message_chain_start.filter.assert_called_once()
        message_order_by_mock = mock_message_chain_order_by.order_by
        message_offset_mock = mock_message_chain_offset.offset
        message_limit_mock = mock_message_chain_limit.limit
        message_all_mock = mock_message_chain_all.all

        message_order_by_mock.assert_called_once()
        order_by_arg = message_order_by_mock.call_args[0][0]
        assert isinstance(order_by_arg, UnaryExpression)
        assert order_by_arg.modifier is operators.asc_op

        message_offset_mock.assert_called_once_with(skip_val)
        message_limit_mock.assert_called_once_with(limit_val)
        message_all_mock.assert_called_once()

        # 4. Check final result
        assert result == mock_messages


def test_get_multi_by_project_success_desc(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project,
    mock_user: User
):
    # Arrange
    mock_messages = [MagicMock(spec=Message)]
    project_id = mock_project.id
    user_id = mock_user.id
    skip_val = 0 # Default skip
    limit_val = 100 # Default limit

    # Project Chain
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=mock_project))
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Message Chain
    mock_message_chain_all = MagicMock(all=MagicMock(return_value=mock_messages))
    mock_message_chain_limit = MagicMock(limit=MagicMock(return_value=mock_message_chain_all))
    mock_message_chain_offset = MagicMock(offset=MagicMock(return_value=mock_message_chain_limit))
    mock_message_chain_order_by = MagicMock(order_by=MagicMock(return_value=mock_message_chain_offset))
    mock_message_chain_start = MagicMock(filter=MagicMock(return_value=mock_message_chain_order_by))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project: return mock_project_chain_start
            if model_class == Message: return mock_message_chain_start
            return MagicMock()
        mock_query.side_effect = query_side_effect

        # Act
        result = message_repo.get_multi_by_project(
            project_id=project_id, user_id=user_id, ascending=False # DESCENDING
        )

        # Assert
        mock_query.assert_has_calls([call(Project), call(Message)])
        mock_project_chain_end.first.assert_called_once()

        message_order_by_mock = mock_message_chain_start.filter.return_value.order_by
        message_offset_mock = message_order_by_mock.return_value.offset
        message_limit_mock = message_offset_mock.return_value.limit
        message_all_mock = message_limit_mock.return_value.all

        message_order_by_mock.assert_called_once()
        order_by_arg = message_order_by_mock.call_args[0][0]
        assert isinstance(order_by_arg, UnaryExpression)
        assert order_by_arg.modifier is operators.desc_op # Check for descending

        message_offset_mock.assert_called_once_with(skip_val)
        message_limit_mock.assert_called_once_with(limit_val)
        message_all_mock.assert_called_once()

        assert result == mock_messages


def test_get_multi_by_project_pagination(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project,
    mock_user: User
):
    # Arrange
    skip_val = 5
    limit_val = 15
    project_id = mock_project.id
    user_id = mock_user.id

    # Project Chain
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=mock_project))
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Message Chain (returning empty list)
    mock_message_chain_all = MagicMock(all=MagicMock(return_value=[]))
    mock_message_chain_limit = MagicMock(limit=MagicMock(return_value=mock_message_chain_all))
    mock_message_chain_offset = MagicMock(offset=MagicMock(return_value=mock_message_chain_limit))
    mock_message_chain_order_by = MagicMock(order_by=MagicMock(return_value=mock_message_chain_offset))
    mock_message_chain_start = MagicMock(filter=MagicMock(return_value=mock_message_chain_order_by))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project: return mock_project_chain_start
            if model_class == Message: return mock_message_chain_start
            return MagicMock()
        mock_query.side_effect = query_side_effect

        # Act
        message_repo.get_multi_by_project(
            project_id=project_id, user_id=user_id, skip=skip_val, limit=limit_val
        )

        # Assert
        mock_query.assert_has_calls([call(Project), call(Message)])
        mock_project_chain_end.first.assert_called_once()

        # Check offset and limit values were used correctly
        message_order_by_mock = mock_message_chain_start.filter.return_value.order_by
        message_offset_mock = message_order_by_mock.return_value.offset
        message_limit_mock = message_offset_mock.return_value.limit
        message_all_mock = message_limit_mock.return_value.all

        message_offset_mock.assert_called_once_with(skip_val)
        message_limit_mock.assert_called_once_with(limit_val)
        message_all_mock.assert_called_once() # Ensure the chain completed


def test_get_multi_by_project_not_found(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_user: User
):
    # Arrange
    project_id = str(uuid.uuid4())
    user_id = mock_user.id

    # -- Configure Mocks for the Project Query Chain to return None --
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=None)) # Simulate not found
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project:
                return mock_project_chain_start
            # We shouldn't get here for Message if Project not found
            print(f"--- WARNING: Unexpected Session.query({model_class}) in not_found test ---")
            return MagicMock()
        mock_query.side_effect = query_side_effect

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            message_repo.get_multi_by_project(project_id=project_id, user_id=user_id)

        # Assertions
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        # Check detail message matches the one in the repository code
        assert "Project not found or you do not have permission" in exc_info.value.detail

        # Check only the Project query was attempted
        mock_query.assert_called_once_with(Project)
        mock_project_chain_start.filter.assert_called_once()
        mock_project_chain_end.first.assert_called_once()


def test_get_multi_by_project_not_owned(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project # Use this to get a valid project ID
):
     # Arrange
    project_id = mock_project.id # A real project ID
    wrong_user_id = str(uuid.uuid4()) # But the wrong user

    # -- Configure Mocks for the Project Query Chain to return None --
    # The query filter includes owner_id, so if the wrong user asks, .first() returns None.
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=None)) # Simulate not found
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project: return mock_project_chain_start
            print(f"--- WARNING: Unexpected Session.query({model_class}) in not_owned test ---")
            return MagicMock()
        mock_query.side_effect = query_side_effect

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            # Call with the valid project ID but wrong user ID
            message_repo.get_multi_by_project(project_id=project_id, user_id=wrong_user_id)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Project not found or you do not have permission" in exc_info.value.detail

        # Check only the Project query was attempted
        mock_query.assert_called_once_with(Project)
        mock_project_chain_start.filter.assert_called_once() # Check filter was called
        mock_project_chain_end.first.assert_called_once() # Check first was called


def test_get_multi_by_project_no_messages(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project,
    mock_user: User
):
    # Arrange
    project_id = mock_project.id
    user_id = mock_user.id

    # Project Chain (Successful)
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=mock_project))
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Message Chain (Returns empty list from .all())
    mock_message_chain_all = MagicMock(all=MagicMock(return_value=[])) # No messages found
    mock_message_chain_limit = MagicMock(limit=MagicMock(return_value=mock_message_chain_all))
    mock_message_chain_offset = MagicMock(offset=MagicMock(return_value=mock_message_chain_limit))
    mock_message_chain_order_by = MagicMock(order_by=MagicMock(return_value=mock_message_chain_offset))
    mock_message_chain_start = MagicMock(filter=MagicMock(return_value=mock_message_chain_order_by))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project: return mock_project_chain_start
            if model_class == Message: return mock_message_chain_start
            return MagicMock()
        mock_query.side_effect = query_side_effect

        # Act
        result = message_repo.get_multi_by_project(
            project_id=project_id, user_id=user_id
        )

        # Assert
        # Check full chain executed
        mock_query.assert_has_calls([call(Project), call(Message)])
        mock_project_chain_end.first.assert_called_once()
        mock_message_chain_all.all.assert_called_once()
        # Check result is empty list
        assert result == []


# --- Test store_conversation ---

def test_store_conversation_success(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project,
    mock_user: User
):
    # Arrange
    project_id = mock_project.id
    user_id = mock_user.id
    messages_data = [ {"role": "user", "content": "M1"}, {"role": "assistant", "content": "R1", "model": "M-A"} ]
    default_model = "default-fallback"

    # Configure Mocks for the Project Query Chain (Successful)
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=mock_project))
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project: return mock_project_chain_start
            print(f"--- WARNING: Unexpected Session.query({model_class}) in store_conversation test ---")
            return MagicMock() # Should only query Project
        mock_query.side_effect = query_side_effect

        # Act
        created_messages = message_repo.store_conversation(
            project_id=project_id, user_id=user_id, messages_data=messages_data, default_model=default_model
        )

        # Assert
        # 1. Check Project query happened
        mock_query.assert_called_once_with(Project)
        mock_project_chain_start.filter.assert_called_once()
        mock_project_chain_end.first.assert_called_once()

        # 2. Check DB operations (on the injected mock_db_session)
        mock_db_session.add_all.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # 3. Check added objects
        added_objects = mock_db_session.add_all.call_args[0][0]
        assert isinstance(added_objects, list)
        assert len(added_objects) == len(messages_data)
        assert all(isinstance(m, Message) for m in added_objects)
        assert added_objects[0].project_id == project_id
        assert added_objects[0].user_id == user_id
        assert added_objects[0].role == MessageRole.USER
        assert added_objects[0].content == "M1"
        assert added_objects[0].model is None # Uses default only if needed and role==assistant
        assert added_objects[1].role == MessageRole.ASSISTANT
        assert added_objects[1].content == "R1"
        assert added_objects[1].model == "M-A" # Takes model from data if present

        # 4. Check return value
        assert created_messages == added_objects


def test_store_conversation_project_not_found(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_user: User
):
    # Arrange
    project_id = str(uuid.uuid4())
    user_id = mock_user.id
    messages_data = [{"role": "user", "content": "Test"}]

    # Configure Mocks for the Project Query Chain (Not Found)
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=None)) # Not Found
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project: return mock_project_chain_start
            print(f"--- WARNING: Unexpected Session.query({model_class}) in store_conversation_not_found ---")
            return MagicMock()
        mock_query.side_effect = query_side_effect

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            message_repo.store_conversation(project_id=project_id, user_id=user_id, messages_data=messages_data)

        # Assertions
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Project not found or you do not have permission" in exc_info.value.detail

        # Check query was attempted
        mock_query.assert_called_once_with(Project)
        mock_project_chain_start.filter.assert_called_once()
        mock_project_chain_end.first.assert_called_once()

        # Check DB operations were NOT called
        mock_db_session.add_all.assert_not_called()
        mock_db_session.commit.assert_not_called()


def test_store_conversation_empty_list(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project,
    mock_user: User
):
     # Arrange
    project_id = mock_project.id
    user_id = mock_user.id
    messages_data = [] # Empty list

    # Configure Mocks for the Project Query Chain (Successful, but won't matter much)
    mock_project_chain_end = MagicMock(first=MagicMock(return_value=mock_project))
    mock_project_chain_start = MagicMock(filter=MagicMock(return_value=mock_project_chain_end))

    # Use patch.object instead of decorator
    with patch.object(mock_db_session, 'query') as mock_query:
        def query_side_effect(model_class, *args, **kwargs):
            if model_class == Project: return mock_project_chain_start
            print(f"--- WARNING: Unexpected Session.query({model_class}) in store_conversation_empty ---")
            return MagicMock()
        mock_query.side_effect = query_side_effect

        # Act
        created_messages = message_repo.store_conversation(
            project_id=project_id, user_id=user_id, messages_data=messages_data
        )

        # Assert
        # Check Project query still happens (for validation)
        mock_query.assert_called_once_with(Project)
        mock_project_chain_start.filter.assert_called_once()
        mock_project_chain_end.first.assert_called_once()

        # Check DB operations were NOT called because list was empty
        mock_db_session.add_all.assert_not_called()
        mock_db_session.commit.assert_not_called()

        # Check result is empty list
        assert created_messages == []


# Test inherited create method (basic check) - No query patching needed here
def test_create_message(
    message_repo: MessageRepository,
    mock_db_session: MagicMock,
    mock_project: Project,
    mock_user: User
):
    # Arrange
    message_in = MessageCreate(
        project_id=mock_project.id,
        user_id=mock_user.id,
        role=MessageRole.USER,
        content="A single message"
    )
    # Mock the return value of add to simulate DB behavior
    # We need to ensure the object passed to refresh is the same one added
    added_obj_instance = None
    def add_side_effect(obj):
        nonlocal added_obj_instance
        # In a real scenario, the obj passed might be modified by SQLAlchemy before refresh
        # For mock, just capture it. Ensure it's the right type.
        assert isinstance(obj, Message)
        added_obj_instance = obj
    mock_db_session.add.side_effect = add_side_effect

    # Simulate that refresh does nothing to the object for the test
    mock_db_session.refresh = MagicMock()

    # Act
    # The create method calls add, commit, refresh.
    created_obj = message_repo.create(obj_in=message_in)

    # Assert
    # 1. Check DB operations
    mock_db_session.add.assert_called_once()
    # Check the object added has the correct data
    assert added_obj_instance is not None
    assert added_obj_instance.project_id == message_in.project_id
    assert added_obj_instance.user_id == message_in.user_id
    assert added_obj_instance.role == message_in.role
    assert added_obj_instance.content == message_in.content

    mock_db_session.commit.assert_called_once()
    # Ensure refresh is called with the object that was added
    mock_db_session.refresh.assert_called_once_with(added_obj_instance)

    # 2. Check return value (BaseRepository.create returns the object passed to add/refresh)
    assert created_obj is added_obj_instance