# Testing Gemini Client Function Calling

This document explains the proper approach to testing function calling functionality with the Gemini client in Miktos AI Orchestration Platform.

## Key Testing Considerations

### 1. Proper Mocking of `asyncio.to_thread`

When testing the Gemini client's function calling capabilities, it's important to correctly mock the `asyncio.to_thread` function since it's used to execute the synchronous Gemini API calls in an asynchronous context:

```python
# Create properly structured mock response
mock_response = MagicMock()
# Configure mock_response with appropriate attributes...

# Option 1: Simple mock that always returns the same response
mock_to_thread = AsyncMock(return_value=mock_response)
with patch("integrations.gemini_client.asyncio.to_thread", mock_to_thread):
    # Test code here
    
# Option 2: Mock with side_effect to capture arguments
async def mock_to_thread(func, *args, **kwargs):
    # Capture arguments or perform custom logic
    captured_args.append(args)
    return mock_response
    
with patch("integrations.gemini_client.asyncio.to_thread", side_effect=mock_to_thread):
    # Test code here
```

### 2. Properly Structuring Function Call Responses

For function call tests, the mock response must have the right structure with:

```python
# Function call data
function_call_data = {
    "name": "function_name",
    "args": {
        "param1": "value1",
        "param2": "value2"
    }
}

# Set up mock response with function call
mock_candidate = MagicMock()
mock_candidate.finish_reason = MagicMock()
mock_candidate.finish_reason.name = "FUNCTION_CALL"

mock_content = MagicMock()
mock_part = MagicMock()
mock_part.function_call = function_call_data
mock_content.parts = [mock_part]
mock_candidate.content = mock_content

mock_response.candidates = [mock_candidate]
```

### 3. Testing Stream Function Calls

For streaming function calls, mock the `_gemini_stream_wrapper` to return an async generator:

```python
# Create stream response with function call
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

with patch("integrations.gemini_client._gemini_stream_wrapper", 
           return_value=mock_stream_generator()):
    # Test streaming function call
```

## Sample Test Cases

The repository contains several test files demonstrating proper testing approaches:

1. `test_gemini_functions.py` - Complete tests for function calling (recommended)
2. `test_gemini_simple.py` - Simple test to verify the testing infrastructure

When adding new tests for function calling, use the approach in `test_gemini_functions.py` as a reference.

## Common Issues

- **Avoid checking function name with `__name__`**: When using `side_effect` with mock objects, don't rely on `func.__name__` as mock objects may not have this attribute.
- **Properly structure mock responses**: Ensure mock responses have all necessary attributes including `.candidates`, `.candidates[0].finish_reason`, and `.candidates[0].content.parts`.
- **Handle streaming differently**: For streaming tests, mock the `_gemini_stream_wrapper` function rather than the underlying API calls.
