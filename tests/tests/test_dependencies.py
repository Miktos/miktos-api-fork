# tests/test_dependencies.py
import pytest
from unittest.mock import MagicMock # Or just use mocker

# IMPORTANT: Adjust this import based on your project structure
# If dependencies.py is at the root level with main.py, this should work.
# If it's inside a sub-package, adjust accordingly (e.g., from src.dependencies import get_db)
from dependencies import get_db

# Assuming SessionLocal is imported into dependencies.py like:
# from core.database import SessionLocal
# The target for patching is where get_db looks for SessionLocal
PATCH_TARGET = 'dependencies.SessionLocal'

def test_get_db_dependency(mocker): # 'mocker' fixture comes from pytest-mock
    """
    Tests the get_db dependency generator.
    Verifies that it creates a session, yields it, and closes it.
    """
    # 1. Create a mock object to represent the session
    mock_session = MagicMock()
    mock_session.close = MagicMock() # Ensure the mock session has a close method we can track

    # 2. Create a mock for SessionLocal itself
    # This mock will be returned when SessionLocal() is called in get_db
    mock_session_local = MagicMock(return_value=mock_session)

    # 3. Patch SessionLocal within the dependencies module
    # When get_db calls SessionLocal(), it will call our mock_session_local instead.
    mocker.patch(PATCH_TARGET, new=mock_session_local)

    # 4. Call the generator function get_db()
    db_generator = get_db()

    # 5. Simulate entering the 'with' block / consuming the dependency
    # Get the yielded value (the session) by calling next()
    yielded_session = next(db_generator)

    # --- Assertions ---

    # Assert that SessionLocal() was called exactly once
    mock_session_local.assert_called_once()

    # Assert that the yielded value is our mock session object
    assert yielded_session is mock_session

    # Assert that the session's close method has NOT been called yet
    mock_session.close.assert_not_called()

    # 6. Simulate exiting the 'with' block / finishing with the dependency
    # This is done by trying to get the next item, which should raise StopIteration
    # and trigger the 'finally' block in get_db
    with pytest.raises(StopIteration):
        next(db_generator)

    # Assert that the session's close() method WAS called exactly once in the finally block
    mock_session.close.assert_called_once()