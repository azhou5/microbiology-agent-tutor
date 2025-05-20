# llm_router.py
import os
# Allow duplicate OpenMP runtimes to avoid libomp initialization errors on macOS
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import re
from dotenv import load_dotenv; load_dotenv()
import config
import sys


# Make sure to use MPS device
device = torch.device("mps") if torch.backends.mps.is_built() else torch.device("cpu")



BACKEND  = config.LLM_BACKEND

if BACKEND == "azure":
    from openai import AzureOpenAI
    _client = AzureOpenAI(
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key        = os.getenv("AZURE_OPENAI_API_KEY"),
        api_version    = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    )

    def chat_complete(messages, max_new_tokens=512):
        """Return assistant string given a list of {'role','content'} dicts."""
        try: 
            model_to_use = config.API_MODEL_NAME
            rsp = _client.chat.completions.create(
                model=model_to_use,
                messages=messages
            )
            print(f"Response: {rsp.choices[0].message.content}")
            return rsp.choices[0].message.content
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

else:
    # --- Local HF model ---
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    # import torch  # already imported above

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

    def chat_complete(messages, max_new_tokens=512):
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