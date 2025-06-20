import openai
from openai import AzureOpenAI, OpenAI
import os
import time
import copy
import json
import pickle
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from openai import OpenAI
import json
import os
from datetime import datetime


from dotenv import load_dotenv

# Try to load environment variables if not already done
try:
    # Get the path to the current file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, "dot_env_microtutor.txt")
    
    if os.path.exists(env_path):
        print(f"LLM_utils: Loading environment variables from {env_path}")
        load_dotenv(env_path)
    else:
        print(f"LLM_utils: Warning - Environment file not found at {env_path}")
except Exception as e:
    print(f"LLM_utils: Error loading environment variables: {str(e)}")


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

@dataclass
class CostTracker:
    """Tracks token usage and costs for OpenAI API calls"""
    # Cost per 1K tokens for different models (as of March 2024)
    COST_PER_1K_TOKENS = {
        "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "o3-mini": {"input": 0.0011, "output": 0.0044},
        "o4-mini-0416": {"input": 0.00015, "output": 0.0006},
        "text-embedding-3-small": {"input": 0.00002, "output": 0},
        "text-embedding-3-large": {"input": 0.00013, "output": 0},
    }
    
    total_cost: float = 0.0
    token_usage: Dict[str, TokenUsage] = field(default_factory=dict)
    call_history: List[Dict] = field(default_factory=list)
    log_file: str = "llm_interactions.log"
    
    def log_interaction(self, model: str, input_text: str, output_text: str, cost: float, tokens: int):
        """Log an LLM interaction to the log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Truncate input and output for readability
        input_preview = input_text[:100] + "..." if len(input_text) > 100 else input_text
        output_preview = output_text[:100] + "..." if len(output_text) > 100 else output_text
        
        log_entry = (
            f"\n{'='*80}\n"
            f"Timestamp: {timestamp}\n"
            f"Model: {model}\n"
            f"Cost: ${cost:.4f}\n"
            f"Tokens: {tokens:,}\n"
            f"Input: {input_preview}\n"
            f"Output: {output_preview}\n"
            f"{'='*80}\n"
        )
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Warning: Could not write to log file: {str(e)}")
    
    def calculate_cost(self, model: str, usage: TokenUsage) -> float:
        """Calculate cost for a specific API call"""
        if model not in self.COST_PER_1K_TOKENS:
            print(f"Warning: Cost data for model '{model}' not found. Cost calculation may be inaccurate.")
            return 0.0
            
        costs = self.COST_PER_1K_TOKENS[model]
        input_cost = (usage.prompt_tokens / 1000) * costs["input"]
        output_cost = (usage.completion_tokens / 1000) * costs["output"]
        return input_cost + output_cost
    
    def add_usage(self, model: str, usage: TokenUsage, input_text: str = "", output_text: str = ""):
        if model not in self.token_usage:
            self.token_usage[model] = TokenUsage()
            
        # Update token counts
        self.token_usage[model].prompt_tokens += usage.prompt_tokens
        self.token_usage[model].completion_tokens += usage.completion_tokens
        self.token_usage[model].total_tokens += usage.total_tokens
        
        call_cost = self.calculate_cost(model, TokenUsage(prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens))
        this_call_record = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            },
            "cost": call_cost 
        }
        self.call_history.append(this_call_record)
        self.total_cost += call_cost
        
        # Log the interaction if input and output are provided
        if input_text and output_text:
            self.log_interaction(
                model=model,
                input_text=input_text,
                output_text=output_text,
                cost=call_cost,
                tokens=usage.total_tokens
            )
        
        return this_call_record
    
    def get_summary(self) -> Dict:
        summary_token_usage = {}
        for model_name, usage_stats in self.token_usage.items():
            summary_token_usage[model_name] = {
                "prompt_tokens": usage_stats.prompt_tokens,
                "completion_tokens": usage_stats.completion_tokens,
                "total_tokens": usage_stats.total_tokens,
                "cost": self.calculate_cost(model_name, usage_stats)
            }
        return {
            "total_overall_cost": self.total_cost,
            "token_usage_by_model": summary_token_usage,
            "call_history": self.call_history
        }
    
    def get_formatted_summary(self) -> str:
        """Returns a human-readable formatted summary of costs and usage"""
        summary = self.get_summary()
        output = []
        output.append("\n=== Cost Summary ===")
        output.append(f"Total Cost: ${summary['total_overall_cost']:.4f}")
        
        if summary['token_usage_by_model']:
            output.append("\nUsage by Model:")
            for model, stats in summary['token_usage_by_model'].items():
                output.append(f"\n{model}:")
                output.append(f"  Prompt Tokens: {stats['prompt_tokens']:,}")
                output.append(f"  Completion Tokens: {stats['completion_tokens']:,}")
                output.append(f"  Total Tokens: {stats['total_tokens']:,}")
                output.append(f"  Cost: ${stats['cost']:.4f}")
        
        if summary['call_history']:
            output.append("\nRecent Calls:")
            for call in summary['call_history'][-5:]:  # Show last 5 calls
                timestamp = datetime.fromisoformat(call['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                output.append(f"\n{timestamp} - {call['model']}:")
                output.append(f"  Tokens: {call['usage']['total_tokens']:,} (${call['cost']:.4f})")
        
        return "\n".join(output)
    
    def save_summary(self, filepath: str):
        """Save usage summary to a JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.get_summary(), f, indent=2)
        print(f"Cost summary saved to {filepath}")

def create_chat_completion_with_cost_tracking(
    client: OpenAI,
    cost_tracker: CostTracker,
    model: str,
    messages: List[Dict],
    deployment_id: Optional[str] = None,
    **kwargs
) -> tuple:
    """
    Wrapper for OpenAI's chat.completions.create that tracks costs.
    
    Args:
        client: OpenAI client instance
        cost_tracker: CostTracker instance
        model: Model name (used for cost tracking)
        messages: List of message dictionaries
        deployment_id: Optional Azure deployment ID. If provided, used for the API call.
        **kwargs: Additional arguments for chat.completions.create
        
    Returns:
        tuple: (response, cost_info)
    """

    api_model = deployment_id if deployment_id else model
    response = None
    try:
        response = client.chat.completions.create(
            model=api_model,
            messages=messages,
            #response_format={"type": "json_object"},
            #temperature=0.1,
            **kwargs
        )
    except Exception as e:
        with open('error_log.txt', 'a') as f:
            f.write(f"\nError occurred at: {datetime.now()}\n")
            f.write(f"Error message: {str(e)}\n")
            f.write("Messages sent:\n")
            f.write(str(messages))
            f.write("\nFull response:\n")
            f.write(str(response) if response is not None else "No response received")
            f.write("\n-------------------\n")
        raise
 
    # Extract token usage
    usage = TokenUsage(
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens
    )
    
    # Get input and output text for logging
    input_text = messages[-1]["content"] if messages else ""
    output_text = response.choices[0].message.content if response.choices else ""
    
    # Track usage and get cost info
    cost_info = cost_tracker.add_usage(model, usage, input_text=input_text, output_text=output_text)
    
    return response, cost_info

class LLMManager:
   
    def __init__(self, use_azure=True, log_file: str = "llm_interactions.log"):
        self.use_azure = use_azure
        self.client = None
        self.cost_tracker = CostTracker(log_file=log_file)
        self.azure_deployment_map = {}

        if self.use_azure:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview") #api_version="2024-12-01-preview"
            if azure_endpoint and azure_api_key:
                try:
                    self.client = AzureOpenAI(
                        azure_endpoint=azure_endpoint,
                        api_key=azure_api_key,
                        api_version=api_version
                    )
                    print("LLM_utils: Azure OpenAI client initialized for LLMManager.")

                    # Map standard model names to specific Azure deployment names from .env file
                    o3_mini_deployment = os.getenv("AZURE_OPENAI_O3_MINI_DEPLOYMENT")
                    if o3_mini_deployment:
                        self.azure_deployment_map['o3-mini'] = o3_mini_deployment
                        print(f"LLM_utils: Mapped model 'o3-mini' to Azure deployment '{o3_mini_deployment}'")

                except Exception as e:
                    print(f"LLM_utils: Error initializing Azure OpenAI client: {str(e)}")
            else:
                print("LLM_utils: WARNING - Missing Azure OpenAI credentials. Azure client not initialized.")
                if not azure_endpoint: print("  AZURE_OPENAI_ENDPOINT: ❌")
                if not azure_api_key: print("  AZURE_OPENAI_API_KEY: ❌")
        else:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if openai_api_key:
                try:
                    self.client = OpenAI(api_key=openai_api_key)
                    print("LLM_utils: Standard OpenAI client initialized for LLMManager.")
                except Exception as e:
                    print(f"LLM_utils: Error initializing OpenAI client: {str(e)}")
            else:
                print("LLM_utils: WARNING - Missing OpenAI API key. Standard OpenAI client not initialized.")

    def generate_response(self, message, model, retries=3, backoff_factor=2, max_tokens=40000):
        if not self.client:
            client_type = "Azure OpenAI" if self.use_azure else "Standard OpenAI"
            raise Exception(f"{client_type} client not initialized. Cannot proceed.")

        deployment_name = model
        if self.use_azure and model in self.azure_deployment_map:
            deployment_name = self.azure_deployment_map[model]

        for attempt in range(retries):
            try:
                # Use max_tokens for all models
                kwargs = {"max_completion_tokens": max_tokens}

                api_response_object, _ = create_chat_completion_with_cost_tracking(
                    client=self.client,
                    cost_tracker=self.cost_tracker,
                    model=model,
                    messages=message,
                    deployment_id=deployment_name,
                    **kwargs
                )
                return api_response_object.choices[0].message.content
            except openai.APIError as e:
                print(f"OpenAI API returned an API Error: {e} (attempt {attempt + 1}/{retries})")
            except openai.APIConnectionError as e:
                print(f"Failed to connect to OpenAI API: {e} (attempt {attempt + 1}/{retries})")
            except openai.RateLimitError as e:
                print(f"OpenAI API request exceeded rate limit: {e} (attempt {attempt + 1}/{retries})")
            except Exception as e:
                print(f"An unexpected error occurred: {e} (attempt {attempt + 1}/{retries})")
            
            if attempt < retries - 1:
                wait_time = backoff_factor ** attempt
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        print("All retry attempts failed.")
        return None

    def GPT_api(self, system_prompt, prompt, n_responses=1, model="o3-mini", max_tokens=40000):
        responses = []
        message = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        for _ in range(n_responses):
            response_content = self.generate_response(message, model=model, max_tokens=max_tokens)
            responses.append(response_content)
        return responses

    def print_cost_summary(self):
        """Print a formatted summary of costs and usage"""
        print(self.cost_tracker.get_formatted_summary())

    def save_cost_summary(self, filepath: str = None):
        """Save cost summary to a file. If no filepath provided, uses timestamp."""
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = f"cost_summary_{timestamp}.json"
        self.cost_tracker.save_summary(filepath)

    def get_cost_summary(self) -> Dict:
        """Get the raw cost summary data"""
        return self.cost_tracker.get_summary()

    def get_formatted_cost_summary(self) -> str:
        """Get a formatted string of the cost summary"""
        return self.cost_tracker.get_formatted_summary()

def run_LLM(system_prompt, input_prompt, iterations, model="o3-mini", azure_openai=True, log_file="llm_interactions.log"):
    llm_manager = LLMManager(use_azure=azure_openai, log_file=log_file)
    max_empty_retries = 2
    empty_retry_count = 0

    print("---"*100)
    print("System Prompt:")
    print(system_prompt)
    print("---"*100)
    print("Input Prompt:")
    print(input_prompt)
    print("---"*100)
    
    while empty_retry_count <= max_empty_retries:
        LLM_answer_list = llm_manager.GPT_api(system_prompt, input_prompt, iterations, model)

        if isinstance(LLM_answer_list, list):
            if not LLM_answer_list or LLM_answer_list[0] is None:
                print("Error: LLM returned an empty list or None response.")
                empty_retry_count += 1
                if empty_retry_count <= max_empty_retries:
                    print(f"Retrying due to empty/None response (attempt {empty_retry_count}/{max_empty_retries})...")
                    continue
                # LLM_answer remains None, will be returned with cost summary
                break # Exit retry loop
            LLM_answer = LLM_answer_list[0]
        else: 
             print(f"Error: Unexpected response type from GPT_api: {type(LLM_answer_list)}")
             # LLM_answer remains None, will be returned with cost summary
             break # Exit retry loop

        if not isinstance(LLM_answer, str) or LLM_answer.strip() == "":
            print(f"Error: Invalid LLM response type or empty string: {LLM_answer}")
            LLM_answer = None # Ensure LLM_answer is None if invalid
            empty_retry_count += 1
            if empty_retry_count <= max_empty_retries:
                print(f"Retrying due to invalid/empty response (attempt {empty_retry_count}/{max_empty_retries})...")
                continue
            break # Exit retry loop
        
        # Valid LLM_answer obtained
        cost_summary = llm_manager.cost_tracker.get_summary()
        return LLM_answer, cost_summary

    # If loop finishes due to retries exhausted or error without valid answer
    cost_summary = llm_manager.cost_tracker.get_summary()
    return LLM_answer, cost_summary # LLM_answer will be None here


def parse_llm_output_text_format(output: str) -> dict:
    """
    Parses LLM output in the specified text format:
    Each line should be: OUTCOME: <time_in_days> <event_observed>
    Example:
      DEATH: 100 1
      PROGRESSION: 200 0
      ...
    Returns a dict with keys for each outcome.
    """
    predictions = {}
    for line in output.strip().splitlines():
        try:
            key, rest = line.strip().split(":")
            time_str, event_str = rest.strip().split()
            predictions[key.strip()] = {
                "time_in_days": int(time_str),
                "event_observed": int(event_str)
            }
        except Exception as e:
            raise ValueError(f"Invalid line format: '{line}' – {e}")
    expected_keys = {"DEATH", "PROGRESSION", "ANY_METS", "LIVER_METS", "LUNG_METS", "BONE_METS"}
    if set(predictions.keys()) != expected_keys:
        raise ValueError(f"Parsed keys {predictions.keys()} do not match expected outcome names.")
    return predictions



__all__ = [
    'run_LLM',
    'LLMManager',
    'CostTracker',
    'TokenUsage',
    'create_chat_completion_with_cost_tracking',
    'parse_llm_output_text_format'
]
    
    