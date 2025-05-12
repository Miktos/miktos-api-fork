# Testing API Clients in Miktos Backend

This guide explains how to properly test the OpenAI and Gemini API clients in the Miktos backend project.

## Overview of Changes

We've made the following improvements to the client code to make it more testable:

1. Made client initialization more mockable
2. Added helper functions that can be replaced during tests
3. Fixed the testing approach to properly mock external API calls

## Testing OpenAI Client

### Key Components to Mock

When testing the OpenAI client, you should mock:

1. `client` - The main AsyncOpenAI client instance
2. `get_client()` - The function that creates the client
3. `settings.OPENAI_API_KEY` - The API key setting

### Example Test Pattern

```python
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

@pytest.mark.asyncio
async def test_openai_function():
    # Create your mock response object
    mock_response = MagicMock()
    # Configure the mock as needed
    
    # Create a mock client
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    # Patch both the get_client function and the client variable
    with patch("integrations.openai_client.get_client", return_value=mock_client), \
         patch("integrations.openai_client.client", mock_client), \
         patch("integrations.openai_client.settings.OPENAI_API_KEY", "fake-api-key"):
        
        # Call your function and make assertions
        # ...
```

## Testing Gemini Client

### Key Components to Mock

When testing the Gemini client, you should mock:

1. `genai` - The Google Generative AI module
2. `configure_genai()` - The function that configures the genai module
3. `is_configured` - The global flag indicating whether genai is configured
4. `create_generative_model()` - The function that creates the model
5. `settings.GOOGLE_API_KEY` - The API key setting
6. `asyncio.to_thread` - For handling async behavior in tests

### Example Test Pattern

```python
import pytest
from unittest.mock import MagicMock, patch

@pytest.mark.asyncio
async def test_gemini_function():
    # Create your mock response object
    mock_response = MagicMock()
    # Configure the mock as needed
    
    # Create a mock model
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    
    # Patch all necessary dependencies
    with patch("integrations.gemini_client.genai", autospec=True) as mock_genai, \
         patch("integrations.gemini_client.asyncio.to_thread", return_value=mock_response), \
         patch("integrations.gemini_client.is_configured", True), \
         patch("integrations.gemini_client.configure_genai", return_value=True), \
         patch("integrations.gemini_client.create_generative_model", return_value=mock_model), \
         patch("integrations.gemini_client.settings.GOOGLE_API_KEY", "fake-api-key"):
        
        # Set up the GenerativeModel mock
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types = MagicMock()
        mock_genai.types.FunctionDeclaration = MagicMock()
        mock_genai.types.Tool = MagicMock()
        mock_genai.types.GenerationConfig = MagicMock()
        
        # Call your function and make assertions
        # ...
```

## Common Testing Tips

1. Always mock external API calls to avoid actual network requests during tests
2. Make sure your mocks return appropriate objects that match the expected structure
3. When testing function calling, ensure the function calls are properly structured
4. For streaming tests, remember to mock the async generator behavior

## Troubleshooting

If your tests are still calling real APIs:

1. Check that all relevant client objects are mocked
2. Ensure generator functions are properly mocked for streaming tests
3. Verify that patching is applied at the correct module level
4. Check for any side effects from test setup or teardown
