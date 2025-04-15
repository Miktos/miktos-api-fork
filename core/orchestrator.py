# miktos_backend/core/orchestrator.py

import asyncio
from typing import List, Dict, Any, Generator, Optional, Union, AsyncGenerator # Added AsyncGenerator

# Import the generation functions from our integration clients
# Use absolute imports relative to the miktos_backend package root
# Assume these client functions are now defined as 'async def'
from miktos_backend.integrations import openai_client
from miktos_backend.integrations import claude_client
from miktos_backend.integrations import gemini_client

# --- Model Provider Mapping (Simple Approach for MVP) ---
def get_provider_from_model(model_id: str) -> Optional[str]:
    """Determines the likely provider based on the model ID prefix."""
    model_id_lower = model_id.lower()
    if model_id_lower.startswith("gpt-"):
        return "openai"
    elif model_id_lower.startswith("claude-"):
        return "anthropic"
    elif model_id_lower.startswith("gemini-"):
        return "google"
    elif "/" in model_id_lower: # Handle models like 'openai/gpt-4o', 'google/gemini...'
        provider = model_id_lower.split('/')[0]
        if provider in ["openai", "google", "anthropic", "mistralai", "meta-llama"]: # Add known provider prefixes
             # Map specific known provider names if needed
             if provider == "google": return "google"
             if provider == "anthropic": return "anthropic"
             if provider == "openai": return "openai"
             # Add mappings for others if we implement clients for them
        return provider # Return the inferred provider name
    return None

# --- Main Orchestration Function - ASYNC ---
async def process_generation_request(
    messages: List[Dict[str, Any]],
    model: str, # Full model ID like "openai/gpt-4o" or just "gpt-4o"
    stream: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    system_prompt: Optional[str] = None,
    **provider_specific_kwargs
# Correct Return Type Hint: Union of Dict or AsyncGenerator
) -> Union[Dict[str, Any], AsyncGenerator[Dict[str, Any], None]]:
    """
    Orchestrates the request to the appropriate AI model provider client.

    Args:
        messages: List of message dictionaries.
        model: The target model ID (used to determine the provider).
        stream: Whether to stream the response.
        temperature: Sampling temperature.
        max_tokens: Max tokens for the completion.
        system_prompt: System prompt/instruction.
        **provider_specific_kwargs: Additional arguments specific to the target provider's API.

    Returns:
        A dictionary (for non-streaming) or an async generator (for streaming)
        containing the response or error details from the client.
    """
    print(f"Orchestrator received request for model: {model}, stream: {stream}")

    provider = get_provider_from_model(model)
    actual_model_id = model.split('/')[-1] if '/' in model else model

    if not provider:
        print(f"Error: Could not determine provider for model: {model}")
        error_msg = f"Could not determine provider for model: {model}"
        if stream:
            async def error_generator_prov(): yield {"error": True, "message": error_msg, "type": "RoutingError"}
            return error_generator_prov()
        else:
            return {"error": True, "message": error_msg, "type": "RoutingError"}

    client_func = None
    client_args = {
        "messages": messages,
        "model": actual_model_id,
        "stream": stream, # Pass stream flag to client
        "temperature": temperature,
        "max_tokens": max_tokens,
        **provider_specific_kwargs
    }

    # Select the appropriate client function and add provider-specific args
    if provider == "openai":
        print(f"Routing to OpenAI client with model: {actual_model_id}...")
        client_func = openai_client.generate_completion
        # Note: system_prompt handled by ensuring it's in messages list before this call
    elif provider == "anthropic":
        print(f"Routing to Anthropic client with model: {actual_model_id}...")
        client_func = claude_client.generate_completion
        client_args["system_prompt"] = system_prompt # Pass system prompt explicitly
    elif provider == "google":
        print(f"Routing to Google client with model: {actual_model_id}...")
        client_func = gemini_client.generate_completion
        client_args["system_prompt"] = system_prompt # Pass system prompt explicitly
    else:
        print(f"Error: No integration client implemented for provider: {provider}")
        error_msg = f"No integration client implemented for provider: {provider} (model: {model})"
        if stream:
            async def error_generator_unk(): yield {"error": True, "message": error_msg, "type": "RoutingError"}
            return error_generator_unk()
        else:
            return {"error": True, "message": error_msg, "type": "RoutingError"}

    # Execute the chosen client function and handle its result
    try:
        # IMPORTANT: Await the call since the client functions are async def
        result = await client_func(**client_args)

        # Now check the type of the awaited result based on the stream flag
        if stream:
            # If streaming, we expect an async generator.
            if not hasattr(result, '__aiter__'):
                 # This handles cases where the client might return an error dict even for stream=True
                 print(f"Warning: Stream expected but got non-generator type after await: {type(result)}")
                 async def single_item_gen(): yield result # Wrap the dict in a generator
                 return single_item_gen()
            # Return the async generator object directly
            return result
        else:
            # If not streaming, we expect a dict after awaiting.
            if not isinstance(result, dict):
                 print(f"Error: Non-streaming call returned unexpected type after await: {type(result)}")
                 # Return a standard error dictionary
                 return {"error": True, "message": f"Orchestrator received unexpected type post-await: {type(result)}", "type": "OrchestrationError"}
            # Return the dictionary directly
            return result

    except Exception as e:
        # Catch unexpected errors during the client call itself
        print(f"Unexpected Error calling client for {provider}: {e}")
        # Optionally include traceback for detailed server logs
        # import traceback
        # traceback.print_exc()
        error_msg = f"An unexpected error occurred calling client for {provider}: {str(e)}"
        if stream:
            async def error_generator_exc(): yield {"error": True, "message": error_msg, "type": type(e).__name__}
            return error_generator_exc()
        else:
            return {"error": True, "message": error_msg, "type": type(e).__name__}