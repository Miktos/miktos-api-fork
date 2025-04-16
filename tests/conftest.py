# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
# import sys # Likely not needed now
# import os  # Likely not needed now

# Import your FastAPI app instance
from main import app

@pytest.fixture(scope="module")
def client() -> TestClient:
    """
    Pytest fixture to create a FastAPI TestClient instance.
    """
    test_client = TestClient(app)
    return test_client

# Optional: Import mocker if needed, though usually not required here
# from pytest_mock import MockerFixture