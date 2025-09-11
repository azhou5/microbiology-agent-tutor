from LLM_utils import run_LLM

system_prompt = 'You are a helpful assistant'
input_prompt = "what's the captal of france?"

# We now call 'o3-mini', and LLM_utils will map it to your 
# 'o3-mini-0131' deployment on Azure.
response, _ = run_LLM(system_prompt, input_prompt, 1, model="o3-mini", azure_openai=True, log_file="llm_interactions.log")
print(response)