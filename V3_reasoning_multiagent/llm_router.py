# llm_router.py
import os
# Allow duplicate OpenMP runtimes to avoid libomp initialization errors on macOS
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import re
from dotenv import load_dotenv
import config
import sys
from LLM_utils import LLMManager



BACKEND  = config.LLM_BACKEND

if BACKEND == "azure":
    llm_manager = LLMManager(use_azure=True)

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

else:
    # --- Local HF model ---
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    
    device = torch.device("mps") if torch.backends.mps.is_built() else torch.device("cpu")


    MODEL_NAME = config.LOCAL_MODEL_NAME

    print(f"[LLM] Loading {MODEL_NAME} …")
    _tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    # device_map="auto" will shard the model across CPU / disk if needed.
    # Do NOT call .to(device) afterwards, or Accelerate will error.
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto"           # let accelerate decide placement
    )
    _END = _tok.eos_token or ""

    def _history_to_prompt(msgs):
        """Very simple role→text converter; customise if you need system separators."""
        parts = []
        for m in msgs:
            role = m["role"]
            txt  = m["content"].strip()
            parts.append(f"{role.title()}: {txt}")
        parts.append("Assistant:")           # queue for next answer
        return "\n".join(parts)

    def chat_complete(messages, model=None, max_new_tokens=512):
        """Return assistant string given a list of {'role','content'} dicts."""
        prompt = _history_to_prompt(messages)
        tokens = _tok(prompt, return_tensors="pt")
        # Move inputs to the same device as model shards (MPS)
        tokens = {k: v.to(device) for k, v in tokens.items()}
        # Use sampling with a small temperature and ensure pad_token_id is set
        out = _model.generate(
            **tokens,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=0.7,
            pad_token_id=_tok.eos_token_id
        )
        full = _tok.decode(out[0], skip_special_tokens=True)
        # return only the part after the last "Assistant:"
        return re.split(r"Assistant:\s*", full)[-1].strip()
    


def test_local_model():
    tok   = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto"
    )

    prompt = "Hello, world! how are you?"
    inputs = tok(prompt, return_tensors="pt").to(device)
    out    = model.generate(**inputs, max_new_tokens=20)

    print(tok.decode(out[0], skip_special_tokens=True))


if __name__ == "__main__":
    # First, run the test to confirm model loads correctly
    print("=== Running smoke test ===")
    test_local_model()
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
        
        # Build minimal conversation for a single-turn response
        messages = [{"role": "user", "content": user_input}]
        try:
            response = chat_complete(messages)
            print("Assistant:", response)
        except Exception as e:
            print("Error generating response:", e)