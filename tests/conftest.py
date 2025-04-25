# tests/conftest.py
import pytest
import os
from typing import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Import app and models
from main import app
from config.database import Base, get_db
from models.database_models import User
from security import get_password_hash
from repositories.user_repository import UserRepository
import schemas

# Use Synchronous DB URL
TEST_DATABASE_URL = "sqlite:///./test_db.sqlite"

# --- ADD THIS CONSTANT BACK ---
TEST_USER_CREDENTIALS = {
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpassword"
}
# --- END ADDED CONSTANT ---

# Use Synchronous Engine
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Setup Fixture (Sync) ---
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    # ... (rest of fixture) ...
    if os.path.exists("./test_db.sqlite"): os.remove("./test_db.sqlite"); print("Removed existing test database.")
    print("Creating test database tables..."); Base.metadata.create_all(bind=engine); print("Test database tables created.")
    yield
    print("Tests finished, test database file remains.")

@pytest.fixture(scope="function")
def db_session(setup_test_database) -> Generator[Session, None, None]:
    """Creates a fresh database session with transaction rollback for each test function."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    print(f"\n[DB Fixture] Transaction started for session {id(session)}.")
    yield session
    session.close()
    # --- Ensure using ROLLBACK for isolation ---
    transaction.rollback()
    print(f"[DB Fixture] Transaction rolled back for session {id(session)}.")
    # --- END Ensure using ROLLBACK ---
    connection.close()
    print("[DB Fixture] Connection closed.")


@pytest.fixture(scope="function")
def override_get_db(db_session: Session) -> Generator[None, None, None]:
    # ... (rest of fixture) ...
    def _get_test_db_override() -> Generator[Session, None, None]:
        print(f"[Override Dependency] Yielding session {id(db_session)}")
        yield db_session
    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_test_db_override
    print("[Dependency Override] get_db overridden.")
    yield
    if original_override: app.dependency_overrides[get_db] = original_override; print("[Dependency Override] get_db restored.")
    else: del app.dependency_overrides[get_db]; print("[Dependency Override] get_db override removed.")


# --- Test User Fixture (Sync) ---
@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Ensures the test user exists, commits the user, returns the User model."""
    user_repo = UserRepository(db=db_session)
    existing_user = user_repo.get_by_email(email=TEST_USER_CREDENTIALS["email"])
    if existing_user:
        print(f"[Test User Fixture] Found existing test user {existing_user.id}")
        # It's already committed from a previous run or this session's attempt
        # Make sure it's refreshed in the current session context
        try:
            db_session.refresh(existing_user)
        except Exception:
             # If refresh fails (e.g., object detached), requery
             existing_user = user_repo.get_by_email(email=TEST_USER_CREDENTIALS["email"])
        return existing_user

    print(f"[Test User Fixture] Creating new test user {TEST_USER_CREDENTIALS['email']}")
    hashed_password = get_password_hash(TEST_USER_CREDENTIALS["password"])
    new_user = User(username=TEST_USER_CREDENTIALS["username"], email=TEST_USER_CREDENTIALS["email"], hashed_password=hashed_password, is_active=True)
    db_session.add(new_user)
    try:
        db_session.flush() # Assign ID
        db_session.commit() # Commit user creation ONLY
        db_session.refresh(new_user) # Refresh after commit
        print(f"[Test User Fixture] Committed new test user with ID: {new_user.id}")
    except Exception as e:
        db_session.rollback()
        pytest.fail(f"Failed to create test user: {e}")
    return new_user


# --- Test Client Fixtures (Sync) ---
@pytest.fixture(scope="function")
def client(override_get_db) -> Generator[TestClient, None, None]:
    # ... (rest of fixture) ...
    print("[Client Fixture] Creating basic TestClient.")
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def authenticated_client(client: TestClient, test_user: User) -> Generator[TestClient, None, None]:
    # ... (fixture uses TEST_USER_CREDENTIALS - should now be defined) ...
    print(f"[Auth Client Fixture] Attempting login for user: {test_user.username} (ID: {test_user.id})")
    login_data = {"username": test_user.username, "password": TEST_USER_CREDENTIALS["password"]}
    response = client.post("/api/v1/auth/token", data=login_data)
    if response.status_code != 200:
        print(f"[Auth Client Fixture] LOGIN FAILED! Status: {response.status_code}, Response: {response.text}")
        pytest.fail(f"Could not authenticate test user '{test_user.username}'. Status: {response.status_code}, Detail: {response.text}")
    token_data = response.json(); token = token_data.get("access_token")
    if not token: pytest.fail(f"Login response did not contain 'access_token'. Response: {token_data}")
    print(f"[Auth Client Fixture] Authentication successful for user: {test_user.id}")
    client.headers = {"Authorization": f"Bearer {token}"}
    client.user_id_for_test = test_user.id
    yield client