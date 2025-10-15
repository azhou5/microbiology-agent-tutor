"""
LLM Client Management - Handles Azure and OpenAI clients.

Provides unified interface for both Azure and standard OpenAI APIs.
"""

import os
import time
from typing import Dict, List, Optional, Union
from openai import AzureOpenAI, OpenAI
import openai

from microtutor.core.cost_tracker import CostTracker, TokenUsage
from microtutor.core.config_helper import config


class LLMClient:
    """Unified client for Azure and OpenAI APIs with cost tracking."""
    
    def __init__(self, model: Optional[str] = None, use_azure: bool = True):
        """Initialize LLM client."""
        self.model = model or config.API_MODEL_NAME
        self.cost_tracker = CostTracker()
        
        # Check environment override
        use_azure_env = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
        self.use_azure = use_azure_env
        
        # Initialize appropriate client
        if self.use_azure:
            self._init_azure_client()
        else:
            self._init_openai_client()
    
    def _init_azure_client(self):
        """Initialize Azure OpenAI client."""
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
        
        if not endpoint or not api_key:
            print("Warning: Missing Azure credentials")
            self.client = None
            return
        
        try:
            self.client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version
            )
            
            # Load deployment mapping
            self.deployment_map = {}
            deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            if deployment_name:
                # Map both the old name and the actual deployment name
                self.deployment_map['o4-mini-0416'] = deployment_name
                self.deployment_map[deployment_name] = deployment_name
            
            print(f"Azure OpenAI client initialized (API version: {api_version})")
        except Exception as e:
            print(f"Error initializing Azure client: {e}")
            self.client = None
    
    def _init_openai_client(self):
        """Initialize standard OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            print("Warning: Missing OpenAI API key")
            self.client = None
            return
        
        try:
            self.client = OpenAI(api_key=api_key)
            print("OpenAI client initialized")
        except Exception as e:
            print(f"Error initializing OpenAI client: {e}")
            self.client = None
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        retries: int = 10,
        fallback_model: Optional[str] = None
    ) -> Union[str, Dict]:
        """
        Generate response from LLM with automatic retry for empty responses and fallback model.
        
        Args:
            messages: List of message dictionaries
            model: Primary model to use
            tools: Optional tool schemas
            retries: Number of retry attempts
            fallback_model: Fallback model to try if primary model fails
        
        Returns:
            str: Text response (normal)
            Dict: {'content': str, 'tool_calls': list} if tools were called
            None: If all retries failed on both models
        """
        if not self.client:
            raise Exception("LLM client not initialized")
        
        primary_model = model or self.model
        fallback_model = fallback_model or "gpt-4.1"
        
        # Try primary model first
        result = self._try_model(primary_model, messages, tools, retries)
        if result is not None:
            return result
        
        # If primary model failed, try fallback model
        if fallback_model != primary_model:
            print(f"Primary model {primary_model} failed, trying fallback model {fallback_model}")
            result = self._try_model(fallback_model, messages, tools, retries)
            if result is not None:
                return result
        
        print(f"Error: Both primary model {primary_model} and fallback model {fallback_model} failed")
        return None
    
    def _try_model(self, model: str, messages: List[Dict[str, str]], tools: Optional[List[Dict]], retries: int) -> Union[str, Dict, None]:
        """Try a specific model with retries."""
        for attempt in range(retries):
            try:
                # Get deployment name for Azure
                deployment = model
                if self.use_azure and model in self.deployment_map:
                    deployment = self.deployment_map[model]
                
                # Build API call
                api_params = {
                    "model": deployment,
                    "messages": messages,
                    # No max_tokens - use model default
                }
                
                # Add tools for native function calling
                if tools:
                    api_params["tools"] = tools
                    api_params["tool_choice"] = "auto"
                
                # Call API
                response = self.client.chat.completions.create(**api_params)
                
                # Track cost
                usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens
                )
                
                input_text = messages[-1]["content"] if messages else ""
                output_text = response.choices[0].message.content or ""
                
                self.cost_tracker.add_usage(model, usage, input_text, output_text)
                
                # Check for empty response
                message = response.choices[0].message
                content = message.content or ""
                
                # If we have tool calls, return them regardless of content
                if tools and hasattr(message, 'tool_calls') and message.tool_calls:
                    return {
                        'content': content,
                        'tool_calls': message.tool_calls
                    }
                
                # For text responses, check if content is not empty
                if content.strip():
                    return content
                else:
                    print(f"Warning: Empty response from {model} (attempt {attempt + 1}/{retries})")
                    print(f"  - Response object: {response}")
                    print(f"  - Message content: '{content}'")
                    print(f"  - Message length: {len(content)}")
                    if attempt < retries - 1:
                        time.sleep(1)  # Short delay before retry
                        continue
                    else:
                        print(f"Error: {model} returned empty response after {retries} attempts")
                        return None
                
            except openai.APIError as e:
                error_code = getattr(e, 'code', None)
                if error_code == 'model_not_found':
                    print(f"Model {model} not found or no access - skipping retries")
                    return None  # Don't retry for model not found errors
                print(f"API Error with {model}: {e} (attempt {attempt + 1}/{retries})")
            except openai.RateLimitError as e:
                print(f"Rate limit with {model}: {e} (attempt {attempt + 1}/{retries})")
            except Exception as e:
                print(f"Error with {model}: {e} (attempt {attempt + 1}/{retries})")
            
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        
        print(f"Error: {model} failed after {retries} attempts")
        return None
    
    def get_cost_summary(self) -> Dict:
        """Get cost tracking summary."""
        return self.cost_tracker.get_summary()
    
    def print_cost_summary(self):
        """Print cost summary."""
        self.cost_tracker.print_summary()

