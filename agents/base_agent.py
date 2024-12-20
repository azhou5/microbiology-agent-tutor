from typing import List, Dict, Any
from pydantic import BaseModel
from langchain.chat_models import AzureChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
import os
import json

class BaseAgent:
    def __init__(self, model_name: str = "gpt-4-turbo", temperature: float = 0.7):
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version="2024-05-01-preview",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            deployment_name=model_name,
            temperature=0.3,
            streaming=True,
        )
        self.conversation_history: List[Dict[str, Any]] = []
    
    def add_to_history(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_chat_messages(self, system_prompt: str) -> List[Any]:
        """Convert conversation history to LangChain message format."""
        messages = [SystemMessage(content=system_prompt)]
        
        for msg in self.conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        return messages
    
    def generate_response(self, system_prompt: str, user_input: str) -> str:
        """Generate a response using the LLM."""
        self.add_to_history("user", user_input)
        messages = self.get_chat_messages(system_prompt)
        
        response = self.llm.predict_messages(messages)
        response_text = response.content
        
        self.add_to_history("assistant", response_text)
        return response_text
    
    def generate_structured_response(self, system_prompt: str, user_input: str, output_format: str) -> Dict:
        """Generate a structured response using the LLM with a specific output format."""
        format_prompt = f"{system_prompt}\n\nYou must respond ONLY with valid JSON in the following format:\n{output_format}"
        
        response = self.generate_response(format_prompt, user_input)
        
        try:
            # Clean the response to handle potential text before or after JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                # Remove any whitespace or newlines within the JSON string
                json_str = ' '.join(json_str.split())
                return json.loads(json_str)
            else:
                return {"error": "Invalid response format"}
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Attempted to parse: {response}")
            return {"error": "Failed to parse response"}