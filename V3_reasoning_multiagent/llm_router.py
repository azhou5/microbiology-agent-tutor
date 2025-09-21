# llm_router.py
import os
# Allow duplicate OpenMP runtimes to avoid libomp initialization errors on macOS
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import re
from dotenv import load_dotenv
import config
import sys
from LLM_utils import LLMManager

BACKEND = config.LLM_BACKEND

# Initialize LLM manager based on backend
if BACKEND == "azure":
    llm_manager = LLMManager(model=config.API_MODEL_NAME, use_azure=True)
elif BACKEND == "openai":
    llm_manager = LLMManager(model=config.API_MODEL_NAME, use_azure=False)
else:
    raise ValueError(f"Unsupported LLM backend: {BACKEND}. Supported backends: 'azure', 'openai'")

def chat_complete(system_prompt: str, user_prompt: str, model: str = None, max_new_tokens: int = 512, max_retries: int = 3):
    """
    Return assistant string given a system and user prompt.
    Retries up to `max_retries` times if the LLM returns an empty response.
    """
    for attempt in range(max_retries):
        try:
            model_to_use = model or config.API_MODEL_NAME
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = llm_manager.generate_response(
                message=messages,
                model=model_to_use,
                max_tokens=max_new_tokens
            )
            # Return the response if it's a non-empty string.
            if response and response.strip():
                # print(f"Response: {response}") # Optional: keep for debugging
                return response
            else:
                print(f"Warning: LLM returned an empty or whitespace response. Retrying... (Attempt {attempt + 1}/{max_retries})")
                # Optional: Add a small delay before retrying
                # time.sleep(0.5) 

        except Exception as e:
            print(f"Error in chat_complete on attempt {attempt + 1}/{max_retries}: {e}")
    
    print(f"Error: LLM failed to return a valid response after {max_retries} attempts.")
    return None # Signal failure to the caller after all retries fail


if __name__ == "__main__":
    # Test the LLM connection
    print("=== Testing LLM Connection ===")
    print(f"Backend: {BACKEND}")
    print(f"Model: {config.API_MODEL_NAME}")
    
    try:
        response = chat_complete(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Connection test successful' and nothing else.",
            max_new_tokens=10
        )
        print(f"Response: {response}")
        print("✅ LLM connection test successful!")
    except Exception as e:
        print(f"❌ LLM connection test failed: {e}")
    
    print("\n=== Entering interactive mode (type 'exit' or 'quit' to stop) ===")
    
    # Interactive loop
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
                system_prompt="You are a helpful assistant.",
                user_prompt=user_input
            )
            print("Assistant:", response)
        except Exception as e:
            print("Error generating response:", e)