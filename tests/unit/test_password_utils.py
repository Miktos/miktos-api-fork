# tests/unit/test_password_utils.py

import pytest
from unittest.mock import patch

# Import the functions and the context object to test against
from utils.password_utils import get_password_hash, verify_password, pwd_context

def test_get_password_hash():
    """
    Test that get_password_hash returns a non-plain string hash
    and that the hash can be verified.
    """
    plain_password = "mysecretpassword"
    hashed_password = get_password_hash(plain_password)

    assert isinstance(hashed_password, str)
    assert hashed_password != plain_password
    # Verify using the actual pwd_context to ensure hash is valid for later tests
    assert pwd_context.verify(plain_password, hashed_password) is True

def test_verify_password_success():
    """Test successful password verification."""
    plain_password = "correct_password"
    # Use the actual function to generate a valid hash for this test
    hashed_password = get_password_hash(plain_password)

    result = verify_password(plain_password, hashed_password)

    assert result is True

def test_verify_password_failure_wrong_password():
    """
    Test password verification failure due to incorrect password.
    This covers the non-match return path.
    """
    plain_password = "correct_password"
    wrong_plain_password = "wrong_password"
    hashed_password = get_password_hash(plain_password)

    # Verify with the wrong password
    result = verify_password(wrong_plain_password, hashed_password)

    assert result is False # Should return False for mismatch

def test_verify_password_failure_invalid_hash():
    """
    Test password verification failure due to invalid hash format.
    This should trigger the 'except Exception' block in verify_password.
    """
    plain_password = "any_password"
    # Provide a string that doesn't conform to the expected bcrypt hash format
    invalid_hash = "this_is_not_a_valid_bcrypt_hash_at_all"

    # Passlib's verify method raises ValueError (or similar) for invalid hash formats.
    # Our function catches this exception and should return False.
    result = verify_password(plain_password, invalid_hash)

    assert result is False # Should return False due to the exception being caught

# Optional, more explicit test for the exception block using patching:
@patch('utils.password_utils.pwd_context.verify')
def test_verify_password_verify_raises_exception(mock_verify):
    """
    Explicitly test the except block by mocking pwd_context.verify to raise an error.
    """
    # Configure the mock to raise a generic Exception
    mock_verify.side_effect = Exception("Simulated verification error")

    plain_password = "any_password"
    hashed_password = "any_hash" # Content doesn't matter since verify is mocked

    result = verify_password(plain_password, hashed_password)

    # Assert verify was called
    mock_verify.assert_called_once_with(plain_password, hashed_password)
    # Assert the function returned False due to the caught exception
    assert result is False