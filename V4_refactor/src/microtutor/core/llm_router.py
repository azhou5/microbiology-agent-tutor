"""
LLM Router - Public API for LLM interactions.

Provides simple interface: chat_complete() with optional tool support.
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # macOS OpenMP fix

from typing import List, Dict, Optional, Union
from dotenv import load_dotenv

from microtutor.core.llm_client import LLMClient
from microtutor.core.config_helper import config

# Load environment
load_dotenv()

# Initialize global client
BACKEND = config.LLM_BACKEND
llm_client = LLMClient(model=config.API_MODEL_NAME, use_azure=(BACKEND == "azure"))


def chat_complete(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    tools: Optional[List[Dict]] = None,
    max_retries: int = 10,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    fallback_model: Optional[str] = None,
    use_azure: Optional[bool] = None
) -> Union[str, Dict]:
    """
    Generate LLM response with optional tool support and fallback model.
    
    Args:
        system_prompt: System prompt
        user_prompt: User prompt
        model: Model to use (optional, defaults to config)
        tools: Optional tool schemas for native function calling
        max_retries: Number of retry attempts
        conversation_history: Optional full conversation history
        fallback_model: Fallback model to try if primary model fails
        use_azure: Whether to use Azure OpenAI (None = use config default)
    
    Returns:
        str: Text response (if no tool calls)
        Dict: {'content': str, 'tool_calls': list} (if tool called)
        None: If all retries failed on both models
        """
    if conversation_history:
        # Use full conversation history if provided
        messages = conversation_history
    else:
        # Fallback to simple system + user format
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    # Determine which client to use
    if use_azure is not None:
        # Use specific provider as requested
        client = LLMClient(model=model or config.API_MODEL_NAME, use_azure=use_azure)
    else:
        # Use global client (backward compatibility)
        client = llm_client
    
    # The LLM client now handles retries internally, so we just need to call it once
    response = client.generate(
        messages=messages,
        model=model,
        tools=tools,
        retries=max_retries,
        fallback_model=fallback_model
    )
    
    # Success
    if response:
        if isinstance(response, dict):
            return response  # Tool call response
        if isinstance(response, str) and response.strip():
            return response  # Text response
    
    print(f"Error: LLM returned empty response after {max_retries} attempts")
    return None


# Global access to client for cost tracking
def get_llm_client() -> LLMClient:
    """Get the global LLM client (for cost tracking, etc.)."""
    return llm_client


# Backward compatibility alias
llm_manager = llm_client


if __name__ == "__main__":
    # Test
    print("=== Testing LLM Connection ===")
    print(f"Backend: {BACKEND}")
    print(f"Model: {config.API_MODEL_NAME}")
    
    try:
        response = chat_complete(
            system_prompt="You are helpful.",
            user_prompt="Say 'test successful' and nothing else."
        )
        print(f"Response: {response}")
        print("✅ Connection successful!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    
    print("\n=== Interactive mode (type 'exit' to quit) ===")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        
        if not user_input or user_input.lower() in ("exit", "quit"):
            print("Exiting.")
            break
        
        try:
            response = chat_complete(
                system_prompt="You are helpful.",
                user_prompt=user_input
            )
            print(f"Assistant: {response}")
        except Exception as e:
            print(f"Error: {e}")
