# Function Calling Testing Guide

## Overview

This guide explains how to properly test function calling in both the OpenAI and Gemini clients in the Miktos AI Orchestration Platform.

## Root Issue

The original test failures occurred because:

1. Different mocking approaches created inconsistent response structures
2. Some tests used dictionaries, others used objects with attributes
3. Mock objects were not properly serialized/deserialized
4. The function call arguments in OpenAI and Gemini have different formats

## Key Fixes Implemented

1. Created a standardized `format_function_call` helper in both clients that:
   - Handles both dictionary and class-based objects
   - Properly processes function call arguments
   - Deals with special cases like MagicMock objects
   - Ensures consistent output format

2. Improved mock response handling:
   - Proper JSON parsing for function call arguments
   - Mock objects with appropriate attributes
   - Direct patching of client objects

3. Updated test approach:
   - Use direct client patching instead of module-level patching
   - Ensure mocks properly replicate API response structure
   - Standardize assertions

## Proper Testing Approach

### For OpenAI Function Call Tests

```python
@pytest.mark.asyncio
async def test_openai_function_calling():
    # 1. Create mock function call with arguments as a string
    mock_function_call = MagicMock()
    mock_function_call.name = "get_weather"
    mock_function_call.arguments = '{"location":"New York","unit":"celsius"}'
    
    # 2. Create proper mock response structure
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].finish_reason = "function_call"
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.function_call = mock_function_call
    
    # 3. Mock the client at module level
    mock_create = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.chat.completions.create = mock_create
    
    # 4. Apply patch at client level
    with patch.object(openai_client, "client", mock_client):
        # 5. Call the function
        response = await openai_client.generate_completion(...)
        
        # 6. Assert response has proper function call format
        assert response["function_call"]["name"] == "get_weather"
        assert response["function_call"]["args"]["location"] == "New York"
```

### For Gemini Function Call Tests

```python
@pytest.mark.asyncio
async def test_gemini_function_calling():
    # 1. Create function call data as dictionary
    mock_function_call = {
        "name": "get_weather",
        "args": {"location": "New York", "unit": "celsius"}
    }
    
    # 2. Build mock part with function call
    mock_part = MagicMock()
    mock_part.function_call = mock_function_call
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    
    # 3. Add to candidate with proper finish reason
    mock_candidate = MagicMock()
    mock_candidate.finish_reason = MagicMock()
    mock_candidate.finish_reason.name = "FUNCTION_CALL"
    mock_candidate.content = mock_content
    
    # 4. Create complete response object 
    mock_response = MagicMock()
    mock_response.candidates = [mock_candidate]
    
    # 5. Mock asyncio.to_thread to return our response
    with patch("integrations.gemini_client.asyncio.to_thread", return_value=mock_response):
        # 6. Call the function
        response = await gemini_client.generate_completion(...)
        
        # 7. Assert response has proper function call format
        assert response["function_call"]["name"] == "get_weather"
        assert response["function_call"]["args"]["location"] == "New York"
```

## Common Pitfalls to Avoid

1. **MagicMock serialization issues**: Mock objects don't always serialize properly, ensure response format matches real responses
2. **Incorrect patching**: Patch at client level to ensure mock is used
3. **Mixing dictionary and object attributes**: Be consistent with how you create mock data
4. **Function call arguments format**: OpenAI uses `arguments` (string), Gemini uses `args` (dictionary)

## Next Steps

If you need to create new tests involving function calling:

1. Use existing tests as templates
2. Use direct client patching to avoid hitting real APIs
3. Verify mocks with assertions before checking responses
4. Be careful with string vs dictionary formats for function call arguments
