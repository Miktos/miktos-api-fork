# Testing Gemini Function Calling

This README documents the proper approach for writing tests for the Gemini client function calling capabilities.

## Key Findings

1. When testing the Gemini client's function calling capabilities, the correct mocking approach is crucial.
2. The main issue encountered was that direct patching of `mock_model.generate_content` doesn't work because the client uses `asyncio.to_thread` to call it.

## Recommended Testing Strategy

### 1. Proper Mocking Structure for Non-Streaming Function Calls

```python
# Create a properly structured mock response
mock_response = MagicMock()
mock_response.text = None  # No text for function calls

# Create mock candidates with function call
mock_candidate = MagicMock()
mock_candidate.finish_reason = MagicMock()
mock_candidate.finish_reason.name = "FUNCTION_CALL"

# Create content with function call
mock_content = MagicMock()
mock_part = MagicMock()
mock_part.function_call = {
    "name": "get_weather",
    "args": {
        "location": "San Francisco",
        "unit": "celsius"
    }
}
mock_content.parts = [mock_part]
mock_candidate.content = mock_content

# Add candidate to response
mock_response.candidates = [mock_candidate]

# Add usage metadata
mock_response.usage_metadata = MagicMock()
mock_response.usage_metadata.prompt_token_count = 15
mock_response.usage_metadata.candidates_token_count = 25
mock_response.usage_metadata.total_token_count = 40

# Create a mock for tracking calls
generate_content_mock = MagicMock(return_value=mock_response)

# Key part: Define a fake to_thread function that will track calls
async def fake_to_thread(func, *args, **kwargs):
    # Call the tracking mock to record the call
    generate_content_mock(*args, **kwargs)
    # Return our prepared mock response
    return mock_response

# Apply patches in the correct order
with patch("integrations.gemini_client.asyncio.to_thread", side_effect=fake_to_thread):
    with patch("integrations.gemini_client.genai") as mock_genai:
        # Set up model and tools
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types = MagicMock()
```

### 2. Proper Mocking for Streaming Function Calls

```python
# Create function call data
function_call_data = {
    "name": "search_database",
    "args": {
        "query": "Mars planet",
        "limit": 5
    }
}

# Create a mock async generator
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

# Patch the stream wrapper directly
with patch("integrations.gemini_client._gemini_stream_wrapper", return_value=mock_stream_generator()):
    with patch("integrations.gemini_client.genai") as mock_genai:
        # Set up model
        mock_model = MagicMock()
        mock_stream = MagicMock()
        mock_model.generate_content.return_value = mock_stream
        mock_genai.GenerativeModel.return_value = mock_model
```

## Common Issues

1. **Incorrect Mocking Strategy**: Don't patch `genai.GenerativeModel.return_value.generate_content` directly and expect it to be called. Instead, patch `asyncio.to_thread` with either an `AsyncMock` or a custom side effect function.
   
2. **Testing Generate Content Calls**: To verify that `generate_content` was called, use a tracking mock as shown above instead of checking `mock_model.generate_content.called`.

3. **File Creation Issues**: When creating test files with tools, verify that the content was properly written to the file.

## Testing Function Call Response Handling

When asserting the correct function call response, ensure that:

```python
assert response["error"] is False
assert response["content"] is None  # Function calls have no text content
assert response["finish_reason"] == "FUNCTION_CALL"
assert "function_call" in response
assert response["function_call"]["name"] == expected_function_name
# Assert any other expected arguments
```

## Testing Function Result Handling

For tests that involve function results being returned to the model:

1. Create a conversation history with a user message, function call message, and function result message
2. Set up a mock text response (not a function call)
3. Capture the args passed to `generate_content` to verify the conversation is properly formatted
