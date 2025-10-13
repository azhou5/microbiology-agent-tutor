"""
Base Agent for Medical Microbiology Tutor (V4)

Base class for all agents, providing common LLM interaction functionality.
Adapted from V3 to work standalone in V4 structure.
"""

from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import json
from openai import AzureOpenAI, OpenAI
from microtutor.core.config_helper import config

# Load environment variables
load_dotenv()

class BaseAgent:
    def __init__(self, model_name: str = None):
        # Determine which client to use based on the toggle
        use_azure_env = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if use_azure_env and azure_endpoint and azure_api_key:
            # Use Azure OpenAI
            self.client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
            )
            self.use_azure = True
        elif openai_api_key:
            # Use personal OpenAI
            self.client = OpenAI(api_key=openai_api_key)
            self.use_azure = False
        else:
            raise ValueError("Missing required OpenAI environment variables. Check USE_AZURE_OPENAI setting and credentials.")
        
        # Use provided model name or default from config
        self.model_name = model_name if model_name else config.API_MODEL_NAME
        self.conversation_history = []
    
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response using the LLM."""
        self.add_to_history("user", user_prompt)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add conversation history
        for msg in self.conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # For Azure, use deployment name if available, otherwise use model name
        model_to_use = self.model_name
        if self.use_azure:
            # Check if there's a deployment mapping for this model
            o4_mini_deployment = os.getenv("AZURE_OPENAI_O4_MINI_DEPLOYMENT")
            if self.model_name == config.API_MODEL_NAME and o4_mini_deployment:
                model_to_use = o4_mini_deployment
        
        # Use the model's default max_tokens (no explicit limit)
        response = self.client.chat.completions.create(
            model=model_to_use,
            messages=messages,
        )
        
        response_text = response.choices[0].message.content
        self.add_to_history("assistant", response_text)
        return response_text

    def add_to_history(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
    
    def reset_history(self):
        """Reset the conversation history."""
        self.conversation_history = [] 