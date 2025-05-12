#!/usr/bin/env python
"""
Super simple test to verify pytest discovery
"""
import pytest


class TestSimple:
    """Simple test class"""
    
    def test_true(self):
        """Always passes"""
        assert True
        
    def test_simple_addition(self):
        """Basic addition test"""
        assert 1 + 1 == 2
