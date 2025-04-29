# tests/unit/test_security.py

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from fastapi import HTTPException, status

# Import functions and objects to test
from security import (
    create_access_token,
    get_current_user,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    oauth2_scheme,
)
# We need to patch settings where it's *used*, which is inside the security module
# from config import settings # Don't import real settings directly if patching
from models.database_models import User
from schemas import TokenData

# --- Fixtures ---

@pytest.fixture
def mock_db_session() -> MagicMock:
    return MagicMock()

@pytest.fixture
def test_user_id() -> str:
    return "user_abc_123"

@pytest.fixture
def token_payload(test_user_id: str) -> dict:
    return {"sub": test_user_id, "custom_claim": "value"}

# --- Tests for create_access_token ---

def test_create_access_token_default_expiry(token_payload: dict):
    # Patch settings within the 'security' module's namespace
    with patch('security.settings', MagicMock(JWT_SECRET="testsecret")) as mock_settings:
        token = create_access_token(data=token_payload.copy())
        assert isinstance(token, str)
        decoded = jwt.decode(token, mock_settings.JWT_SECRET, algorithms=[ALGORITHM], options={"verify_signature": False, "verify_exp": False})
        assert decoded["sub"] == token_payload["sub"]
        assert "exp" in decoded
        expected_exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        actual_exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        assert abs(actual_exp - expected_exp) < timedelta(seconds=5)

def test_create_access_token_custom_expiry(token_payload: dict):
    custom_delta = timedelta(hours=1)
    with patch('security.settings', MagicMock(JWT_SECRET="testsecret")) as mock_settings:
        token = create_access_token(data=token_payload.copy(), expires_delta=custom_delta)
        assert isinstance(token, str)
        decoded = jwt.decode(token, mock_settings.JWT_SECRET, algorithms=[ALGORITHM], options={"verify_signature": False, "verify_exp": False})
        assert "exp" in decoded
        expected_exp = datetime.now(timezone.utc) + custom_delta
        actual_exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        assert abs(actual_exp - expected_exp) < timedelta(seconds=5)

def test_create_access_token_missing_secret(token_payload: dict):
    with patch('security.settings', MagicMock(JWT_SECRET=None)) as mock_settings:
        with pytest.raises(ValueError, match="JWT_SECRET is not configured correctly"):
            create_access_token(data=token_payload.copy())

def test_create_access_token_invalid_secret_type(token_payload: dict):
    with patch('security.settings', MagicMock(JWT_SECRET=12345)) as mock_settings:
        with pytest.raises(ValueError, match="JWT_SECRET is not configured correctly"):
            create_access_token(data=token_payload.copy())


# --- Tests for get_current_user ---

@pytest.mark.asyncio
async def test_get_current_user_success(mock_db_session: MagicMock, test_user_id: str):
    # Arrange
    mock_user = MagicMock(spec=User); mock_user.id = test_user_id
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_user
    token_payload = {"sub": test_user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}

    # ---> FIX: Patch settings for token creation/decoding <---
    with patch('security.settings', MagicMock(JWT_SECRET="testsecret")) as mock_settings:
        valid_token = jwt.encode(token_payload, mock_settings.JWT_SECRET, algorithm=ALGORITHM)

        # Act
        retrieved_user = await get_current_user(token=valid_token, db=mock_db_session)

        # Assert
        assert retrieved_user is mock_user
        mock_db_session.query.assert_called_once_with(User)
        mock_db_session.query.return_value.filter.assert_called_once()
        mock_db_session.query.return_value.filter.return_value.first.assert_called_once()

@pytest.mark.asyncio
async def test_get_current_user_invalid_token_signature(mock_db_session: MagicMock):
    invalid_token = "this.is.not_a_valid_token_structure"
    # ---> FIX: Patch settings for decoding attempt <---
    with patch('security.settings', MagicMock(JWT_SECRET="testsecret")) as mock_settings:
        # Patch jwt.decode to raise JWTError
        with patch('security.jwt.decode', side_effect=JWTError("Invalid signature")) as mock_decode:
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token=invalid_token, db=mock_db_session)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Could not validate credentials" in exc_info.value.detail
            # Check decode was called with the MOCKED secret
            mock_decode.assert_called_once_with(invalid_token, mock_settings.JWT_SECRET, algorithms=[ALGORITHM])
            mock_db_session.query.assert_not_called()

@pytest.mark.asyncio
async def test_get_current_user_expired_token(mock_db_session: MagicMock, test_user_id: str):
    token_payload = {"sub": test_user_id, "exp": datetime.now(timezone.utc) - timedelta(minutes=5)}
    # ---> FIX: Patch settings for token creation/decoding <---
    with patch('security.settings', MagicMock(JWT_SECRET="testsecret")) as mock_settings:
        expired_token = jwt.encode(token_payload, mock_settings.JWT_SECRET, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            # get_current_user uses the same patched settings for decoding
            await get_current_user(token=expired_token, db=mock_db_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail
        mock_db_session.query.assert_not_called()

@pytest.mark.asyncio
async def test_get_current_user_missing_sub(mock_db_session: MagicMock):
    token_payload = {"user_name": "test", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    # ---> FIX: Patch settings for token creation/decoding <---
    with patch('security.settings', MagicMock(JWT_SECRET="testsecret")) as mock_settings:
        token_no_sub = jwt.encode(token_payload, mock_settings.JWT_SECRET, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token_no_sub, db=mock_db_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail
        mock_db_session.query.assert_not_called()

@pytest.mark.asyncio
async def test_get_current_user_user_not_in_db(mock_db_session: MagicMock, test_user_id: str):
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    token_payload = {"sub": test_user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    # ---> FIX: Patch settings for token creation/decoding <---
    with patch('security.settings', MagicMock(JWT_SECRET="testsecret")) as mock_settings:
        valid_token_for_nonexistent_user = jwt.encode(token_payload, mock_settings.JWT_SECRET, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=valid_token_for_nonexistent_user, db=mock_db_session)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail
        mock_db_session.query.assert_called_once_with(User)
        mock_db_session.query.return_value.filter.assert_called_once()
        mock_db_session.query.return_value.filter.return_value.first.assert_called_once()