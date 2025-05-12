# Gemini Function Calling Test Template

## Successful Non-Streaming Function Call Test

```python
@pytest.mark.asyncio
async def test_successful_function_call():
    # Create message dictionary
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "What's the weather in San Francisco?",
        "role": USER_ROLE
    }
    
    # Define function call data
    function_call_data = {
        "name": "get_weather",
        "args": {
            "location": "San Francisco",
            "unit": "celsius"
        }
    }
    
    # Create a properly structured mock response
    mock_response = MagicMock()
    mock_response.text = None  # No text for function calls
    
    # Set up candidates with function call
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "FUNCTION_CALL"
    
    # Set up content with function call part
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.function_call = function_call_data
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    
    # Add candidates to response
    mock_response.candidates = [mock_candidate]
    
    # Set up usage metadata
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 5
    mock_response.usage_metadata.total_token_count = 15
    
    # Define a side effect function for asyncio.to_thread
    async def fake_to_thread(func, *args, **kwargs):
        # Call the function to track it
        func(*args, **kwargs)
        # Return the prepared mock response
        return mock_response
    
    # Create the model mock
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    # Apply patches in the correct order
    with patch("integrations.gemini_client.asyncio.to_thread", side_effect=fake_to_thread):
        with patch("integrations.gemini_client.genai") as mock_genai:
            # Set up the GenerativeModel mock
            mock_genai.GenerativeModel = MagicMock(return_value=mock_model)
            
            # Set up types for tools
            mock_genai.types = MagicMock()
            mock_genai.types.Tool = MagicMock()
            mock_genai.types.FunctionDeclaration = MagicMock()
            mock_genai.types.GenerationConfig = MagicMock()
            
            # Call the function with streaming disabled
            response = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a weather assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=False
            )
            
            # Verify function call response
            assert response["error"] is False
            assert response["content"] is None
            assert response["finish_reason"] == "FUNCTION_CALL"
            assert "function_call" in response
            assert response["function_call"]["name"] == "get_weather"
            
            # Verify model was called
            assert mock_model.generate_content.called
```

## Successful Streaming Function Call Test

```python
@pytest.mark.asyncio
async def test_successful_streaming_function_call():
    # Create message
    message = {
        "id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "content": "Search for information about Mars",
        "role": USER_ROLE
    }
    
    # Create the function call data
    function_call_data = {
        "name": "search_database",
        "args": {
            "query": "Mars planet",
            "limit": 5
        }
    }
    
    # Create a mock async generator for streaming
    async def mock_stream_generator():
        yield {
            "error": False,
            "delta": None,
            "is_final": True,
            "accumulated_content": None,
            "finish_reason": "FUNCTION_CALL",
            "function_call": function_call_data,
            "model_name": "gemini-1.5-flash-latest"
        }
    
    # Create mock model for setup
    mock_model = MagicMock()
    
    # Apply patches
    with patch("integrations.gemini_client.genai") as mock_genai:
        # Set up model mock
        mock_genai.GenerativeModel = MagicMock(return_value=mock_model)
        mock_genai.types = MagicMock()
        
        # Patch the stream wrapper directly
        with patch("integrations.gemini_client._gemini_stream_wrapper", return_value=mock_stream_generator()):
            # Call the function
            stream_gen = await gemini_client.generate_completion(
                messages=[message],
                system_prompt="You are a search assistant.",
                functions=SAMPLE_FUNCTIONS,
                stream=True
            )
            
            # Process the stream
            chunks = []
            async for chunk in stream_gen:
                chunks.append(chunk)
            
            # Verify function call chunk
            assert len(chunks) >= 1
            final_chunk = chunks[-1]
            
            assert final_chunk["is_final"] is True
            assert "function_call" in final_chunk
            assert final_chunk["function_call"]["name"] == "search_database"
```
