from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import json
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Verify Azure OpenAI configuration
if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
    raise ValueError("Missing required Azure OpenAI environment variables")

class BaseAgent:
    def __init__(self, model_name: str = "o3-mini"):
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        )
        
        self.model_name = model_name
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
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=800
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