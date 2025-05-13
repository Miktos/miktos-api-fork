# tests/admin_test_helper.py
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Mock OAuth2 authentication for FastAPI
class MockOAuth2:
    def __call__(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            return None
            
        return token  # Return the token without validation

def patch_security():
    """
    Patch the security system for testing.
    This function should be called at test setup.
    """
    patches = []
    
    # Patch oauth2_scheme
    oauth2_patch = patch("security.oauth2_scheme", MockOAuth2())
    patches.append(oauth2_patch)
    
    # Start all patches
    for p in patches:
        p.start()
        
    return patches
    
def unpatch_security(patches):
    """
    Remove security patches.
    This function should be called at test teardown.
    """
    for p in patches:
        p.stop()
