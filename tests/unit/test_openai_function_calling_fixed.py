"""
Fixed OpenAI function calling tests that properly mock the client.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
import json
import asyncio
from typing import Dict, Any, List

# Import necessary modules
from integrations import openai_client

# Define role constants
USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"
SYSTEM_ROLE = "system"
FUNCTION_ROLE = "function"

# Sample function definitions
SAMPLE_FUNCTIONS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit"
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "search_database",
        "description": "Search for information in the database",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results"
                }
            },
            "required": ["query"]
        }
    }
]


@pytest.mark.asyncio
async def test_openai_function_calling_fixed():
    """Test that OpenAI client properly formats function calling with fixed mocking."""
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }
    
    # Mock OpenAI's function call response
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "function_call"
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = None
    mock_response.choices[0].message.function_call = MagicMock()
    mock_response.choices[0].message.function_call.name = "get_weather"
    mock_response.choices[0].message.function_call.arguments = '{"location": "San Francisco", "unit": "celsius"}'
    
    # Mock usage data
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 15
    mock_response.usage.completion_tokens = 25
    mock_response.usage.total_tokens = 40
    
    # Model dump for raw response
    mock_response.model_dump = MagicMock(return_value={
        "id": "chatcmpl-123",
        "choices": [{
            "finish_reason": "function_call",
            "message": {
                "content": None,
                "function_call": {
                    "name": "get_weather",
                    "arguments": '{"location": "San Francisco", "unit": "celsius"}'
                }
            }
        }]
    })
    
    # Create mock OpenAI client that actually calls the mocked function
    mock_create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    
    # Setup patches with client and API key mocks
    with patch("integrations.openai_client.get_client", return_value=mock_client), \
         patch("integrations.openai_client.client", mock_client), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"):
        
        # Call the function with function definitions
        response = await openai_client.generate_completion(
            messages=[message],
            system_prompt="You are a weather assistant.",
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify model was called with correct parameters
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert "functions" in call_kwargs
        assert len(call_kwargs["functions"]) == len(SAMPLE_FUNCTIONS)
        
        # Verify function call response is correctly formatted
        assert response["error"] is False
        assert response["content"] is None
        assert response["finish_reason"] == "function_call"
        assert "function_call" in response
        assert response["function_call"]["name"] == "get_weather"
        
        # Check the arguments
        args = response["function_call"]["args"]
        assert args["location"] == "San Francisco"
        assert args["unit"] == "celsius"


@pytest.mark.asyncio
async def test_openai_function_result_handling_fixed():
    """Test that OpenAI client properly handles function result messages - fixed version."""
    # Create message conversation with function call and result
    messages = [
        {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": "What's the weather in San Francisco?",
            "role": USER_ROLE
        },
        {  # This is a function call message
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": None,
            "role": ASSISTANT_ROLE,
            "function_call": {
                "name": "get_weather",
                "args": {
                    "location": "San Francisco",
                    "unit": "celsius"
                }
            }
        },
        {  # This is a function result message
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "content": '{"temperature": 18, "condition": "Partly Cloudy", "humidity": 65}',
            "role": FUNCTION_ROLE,
            "name": "get_weather"
        }
    ]
    
    # Create expected response text
    expected_text = "It's 18°C and partly cloudy in San Francisco with 65% humidity."
    
    # Mock normal text response
    mock_response = MagicMock()
    mock_response.model = "gpt-4o"
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = expected_text
    mock_response.choices[0].message.function_call = None
    
    # Mock usage data
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 25
    mock_response.usage.completion_tokens = 15
    mock_response.usage.total_tokens = 40
    
    # Model dump for raw response
    mock_response.model_dump = MagicMock(return_value={
        "id": "chatcmpl-123",
        "choices": [{
            "finish_reason": "stop",
            "message": {
                "content": expected_text,
                "function_call": None
            }
        }]
    })
    
    # Create mock OpenAI client
    mock_create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    
    # Setup patches
    with patch("integrations.openai_client.get_client", return_value=mock_client), \
         patch("integrations.openai_client.client", mock_client), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"):
        
        # Call the function with the conversation including function result
        response = await openai_client.generate_completion(
            messages=messages,
            system_prompt="You are a weather assistant.",
            functions=SAMPLE_FUNCTIONS,
            stream=False
        )
        
        # Verify the client was called with the correct messages
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert len(call_kwargs["messages"]) >= len(messages)
        
        # Verify regular text response after function call
        assert response is not None
        assert response["error"] is False
        assert response["content"] == expected_text
        assert response["finish_reason"] == "stop"
        assert "function_call" not in response or response["function_call"] is None
        
        # Verify usage info
        assert "usage" in response
        assert response["usage"]["prompt_tokens"] == 25
        assert response["usage"]["completion_tokens"] == 15
        assert response["usage"]["total_tokens"] == 40


@pytest.mark.asyncio
async def test_openai_streaming_function_call_fixed():
    """Test OpenAI function calling with streaming enabled - fixed version."""
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in Paris?",
        "role": USER_ROLE
    }

    # Custom async generator that behaves like OpenAI's streaming response
    async def mock_stream_generator():
        # Create mock chunks similar to what OpenAI returns
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta = MagicMock()
        chunk1.choices[0].delta.content = "thinking..."
        chunk1.choices[0].finish_reason = None
        chunk1.model = "gpt-4o"
        yield chunk1
        
        # Final chunk with function call
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta = MagicMock()
        chunk2.choices[0].delta.content = None
        
        # Need to mock the function_call on the delta
        func_call = MagicMock()
        func_call.name = "get_weather"
        func_call.arguments = '{"location": "Paris", "unit": "celsius"}'
        chunk2.choices[0].delta.function_call = func_call
        
        chunk2.choices[0].finish_reason = "function_call"
        chunk2.model = "gpt-4o"
        yield chunk2

    # Create mock OpenAI client
    mock_create = AsyncMock(return_value=mock_stream_generator())
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    
    # Setup patches
    with patch("integrations.openai_client.get_client", return_value=mock_client), \
         patch("integrations.openai_client.client", mock_client), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"):
        
        # Call the function with streaming
        stream_gen = await openai_client.generate_completion(
            messages=[message],
            system_prompt="You are a weather assistant.",
            functions=SAMPLE_FUNCTIONS,
            stream=True
        )
        
        # Process the stream
        chunks = []
        async for chunk in stream_gen:
            chunks.append(chunk)
            
        # Print the chunks for debugging
        print(f"Got {len(chunks)} chunks from the stream")
        for i, chunk in enumerate(chunks):
            print(f"Chunk {i}: {chunk}")
        
        # We expect:
        # 1. A chunk with the content "thinking..."
        # 2. Function call chunks (one or more) - implementation specific
        # 3. A final chunk with function call and finish_reason
        
        # Check the first chunk (should have content)
        first_chunk = chunks[0]
        assert first_chunk["is_final"] is False
        assert first_chunk["delta"] == "thinking..."
        assert first_chunk["error"] is False
        
        # Get the last chunk (should be final)
        final_chunk = chunks[-1]
        assert final_chunk["is_final"] is True
        assert final_chunk["finish_reason"] == "function_call"
        assert "function_call" in final_chunk
        assert final_chunk["function_call"]["name"] == "get_weather"
        assert final_chunk["function_call"]["args"]["location"] == "Paris"
        assert final_chunk["function_call"]["args"]["unit"] == "celsius"
        
        # Verify stream was requested properly
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["stream"] is True
