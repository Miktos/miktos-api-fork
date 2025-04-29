# tests/unit/test_gemini_client_coverage.py
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from typing import AsyncGenerator, Dict, Any, Optional, List, Union, Iterable

# Import Google exceptions and types for mocking
import google.generativeai as genai
from google.api_core.exceptions import InvalidArgument, ResourceExhausted, ServiceUnavailable

# Import the client we're testing
import integrations.gemini_client as gemini_client
from config.settings import settings

# Create a version-agnostic safety feedback mock
class MockSafetyFeedback:
    """Version-independent mock for SafetyFeedback class."""
    def __init__(self, category, probability):
        self.category = category
        self.probability = probability

# Helper function to create a mock response with customizable attributes
def create_mock_response(text="Test response", parts=None, candidates=None, prompt_feedback=None):
    """Create a flexible mock response that can be configured for different test scenarios."""
    mock_resp = MagicMock()
    mock_resp.text = text
    
    if parts is None:
        # Default parts with the same text
        mock_part = MagicMock()
        mock_part.text = text
        mock_resp.parts = [mock_part]
    else:
        mock_resp.parts = parts
    
    # Add candidates if specified
    if candidates is not None:
        mock_resp.candidates = candidates
    
    # Add prompt_feedback if specified
    if prompt_feedback is not None:
        mock_resp.prompt_feedback = prompt_feedback
    
    return mock_resp

# ============= Tests for fallback error handling in generate_completion =============

@pytest.mark.asyncio
async def test_generate_completion_fallback_error_non_streaming():
    """Test the fallback error path in non-streaming mode when neither normal path nor error_data is set."""
    with patch('integrations.gemini_client.settings', MagicMock(GOOGLE_API_KEY="test-key")), \
         patch.object(genai, 'GenerativeModel') as mock_gen_model_class:
        
        # Setup a mock that will neither complete normally nor set error_data
        mock_model = MagicMock()
        
        # Make generate_content raise a custom exception that won't be caught by _handle_google_error
        class CustomUnhandledException(Exception):
            pass
        
        # This exception should bypass normal error handling but not set error_data
        mock_model.generate_content = AsyncMock(side_effect=CustomUnhandledException("Custom unhandled exception"))
        mock_gen_model_class.return_value = mock_model
        
        # Patch _handle_google_error to not set error_data
        with patch.object(gemini_client, '_handle_google_error', return_value=None):
            # Execute
            result = await gemini_client.generate_completion(
                messages=[{"role": "user", "content": "Test"}],
                stream=False
            )
            
            # Verify fallback error
            assert result is not None
            assert result["error"] is True
            assert result["message"] == "Unknown error state in Gemini client"
            assert result["type"] == "InternalError"

@pytest.mark.asyncio
async def test_generate_completion_fallback_error_streaming():
    """Test the fallback error path in streaming mode when neither normal path nor error_data is set."""
    with patch('integrations.gemini_client.settings', MagicMock(GOOGLE_API_KEY="test-key")), \
         patch.object(genai, 'GenerativeModel') as mock_gen_model_class:
        
        # Setup a mock that will neither complete normally nor set error_data
        mock_model = MagicMock()
        
        # Make generate_content raise a custom exception that won't be caught by _handle_google_error
        class CustomUnhandledException(Exception):
            pass
        
        # This exception should bypass normal error handling but not set error_data
        mock_model.generate_content = AsyncMock(side_effect=CustomUnhandledException("Custom unhandled exception"))
        mock_gen_model_class.return_value = mock_model
        
        # Patch _handle_google_error to not set error_data
        with patch.object(gemini_client, '_handle_google_error', return_value=None):
            # Execute
            result_generator = await gemini_client.generate_completion(
                messages=[{"role": "user", "content": "Test"}],
                stream=True
            )
            
            # Verify it's a generator
            assert hasattr(result_generator, '__aiter__')
            
            # Consume the generator
            results = []
            async for chunk in result_generator:
                results.append(chunk)
            
            # Verify exactly one result with the fallback error
            assert len(results) == 1
            assert results[0]["error"] is True
            assert results[0]["message"] == "Unknown error state in Gemini client"
            assert results[0]["type"] == "InternalError"

# ============= Tests for stream wrapper error handling =============

@pytest.mark.asyncio
async def test_gemini_stream_wrapper_generic_exception():
    """Test error handling in the stream wrapper when a generic exception occurs during iteration."""
    # Create a mock stream that raises exception during iteration
    class MockErrorStream:
        def __iter__(self):
            # Yield one valid chunk, then raise exception
            mock_chunk = create_mock_response("Valid response")
            yield mock_chunk
            raise Exception("Unexpected stream processing error")
    
    # Execute
    result_generator = gemini_client._gemini_stream_wrapper(MockErrorStream(), "test-model")
    
    # Collect all yielded items
    results = []
    async for item in result_generator:
        results.append(item)
    
    # Verify we got two items - the valid chunk and the error
    assert len(results) == 2
    
    # First item should be the valid chunk
    assert "delta" in results[0]
    assert results[0]["delta"] == "Valid response"
    assert "model" in results[0]
    assert results[0]["model"] == "test-model"
    
    # Second item should be the error
    assert "error" in results[1]
    assert results[1]["error"] is True
    assert "message" in results[1]
    assert "Unexpected stream processing error" in results[1]["message"]
    assert "type" in results[1]
    assert results[1]["type"] == "StreamProcessingError"

@pytest.mark.asyncio
async def test_gemini_stream_wrapper_chunk_with_no_text():
    """Test handling chunks that don't have a text attribute."""
    # Create a mock stream with a problematic chunk
    class MockChunkWithoutText:
        def __init__(self):
            # Chunk without text attribute
            self.parts = [MagicMock()]
            # parts[0] has no text attribute

    class MockStream:
        def __iter__(self):
            yield MockChunkWithoutText()
    
    # Execute
    result_generator = gemini_client._gemini_stream_wrapper(MockStream(), "test-model")
    
    # Collect all yielded items
    results = []
    async for item in result_generator:
        results.append(item)
    
    # Verify we got an error item
    assert len(results) == 1
    assert "error" in results[0]
    assert results[0]["error"] is True
    assert "message" in results[0]
    assert "Error processing stream chunk" in results[0]["message"]
    assert "type" in results[0]
    assert "ChunkProcessingError" in results[0]["type"]

@pytest.mark.asyncio
async def test_gemini_stream_wrapper_chunk_with_no_parts():
    """Test handling chunks that don't have a parts attribute."""
    # Create a mock stream with a problematic chunk
    class MockChunkWithoutParts:
        def __init__(self):
            # Chunk with text but no parts
            self.text = "Response text"
            # No parts attribute
    
    class MockStream:
        def __iter__(self):
            yield MockChunkWithoutParts()
    
    # Execute
    result_generator = gemini_client._gemini_stream_wrapper(MockStream(), "test-model")
    
    # Collect all yielded items
    results = []
    async for item in result_generator:
        results.append(item)
    
    # Verify we still got a valid response using the top-level text
    assert len(results) == 1
    assert "delta" in results[0]
    assert results[0]["delta"] == "Response text"
    assert "model" in results[0]
    assert results[0]["model"] == "test-model"

@pytest.mark.asyncio
async def test_gemini_stream_wrapper_parts_attribute_error():
    """Test handling chunks where accessing parts raises AttributeError."""
    # Create a mock stream with a chunk that raises AttributeError
    mock_chunk = MagicMock()
    
    # Configure parts to raise AttributeError
    type(mock_chunk).parts = property(side_effect=AttributeError("'MockChunk' object has no attribute 'parts'"))
    mock_chunk.text = "Fallback text"
    
    class MockStream:
        def __iter__(self):
            yield mock_chunk
    
    # Execute
    result_generator = gemini_client._gemini_stream_wrapper(MockStream(), "test-model")
    
    # Collect all yielded items
    results = []
    async for item in result_generator:
        results.append(item)
    
    # Verify we still got a valid response using the top-level text
    assert len(results) == 1
    assert "delta" in results[0]
    assert results[0]["delta"] == "Fallback text"
    assert "model" in results[0]
    assert results[0]["model"] == "test-model"

@pytest.mark.asyncio
async def test_gemini_stream_wrapper_empty_chunks():
    """Test handling empty or None chunks in the stream."""
    class MockStream:
        def __iter__(self):
            # First yield None, then an empty object
            yield None
            yield MagicMock(text="", parts=[])
    
    # Execute
    result_generator = gemini_client._gemini_stream_wrapper(MockStream(), "test-model")
    
    # Collect all yielded items
    results = []
    async for item in result_generator:
        results.append(item)
    
    # Verify we got meaningful error responses
    assert len(results) == 2
    
    # Check first item (None chunk)
    assert results[0]["error"] is True
    assert "None chunk" in results[0]["message"]
    
    # Check second item (empty chunk)
    assert results[1]["delta"] == ""  # Empty but valid

# Add more tests as needed for any other uncovered code paths