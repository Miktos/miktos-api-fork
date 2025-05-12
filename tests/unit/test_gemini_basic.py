#!/usr/bin/env python
"""
Simple test for gemini client function calling
"""
import pytest
import sys
import os

# Ensure the current directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from integrations import gemini_client


def test_true():
    """Always passes"""
    assert True
    
    
def test_gemini_client_import():
    """Test that we can import the gemini client"""
    assert hasattr(gemini_client, 'generate_completion')
    print("Successfully imported gemini_client module")
