from typing import List, Dict, Any
from pydantic import BaseModel
from langchain.chat_models import AzureChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
import os
from dotenv import load_dotenv
import json
from custom_agent_wrapper import CustomAgentWrapper
from agentlite.actions import BaseAction
from agentlite.actions.InnerActions import ThinkAction, FinishAction
from agentlite.commons import TaskPackage

# Load environment variables
load_dotenv()

# Verify Azure OpenAI configuration
if not os.getenv("AZURE_OPENAI_API_KEY") or not os.getenv("AZURE_OPENAI_ENDPOINT"):
    raise ValueError("Missing required Azure OpenAI environment variables")

class BaseAgent(CustomAgentWrapper):
    def __init__(self, model_name: str = "gpt-4", temperature: float = 0.3):
        # Initialize Azure OpenAI through LangChain
        self.llm = AzureChatOpenAI(
            openai_api_type="azure",
            openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", model_name),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            temperature=temperature,
            streaming=True,
        )
        
        super().__init__(
            name="base_agent",
            role="I am a base agent for medical microbiology tutoring.",
            llm=self.llm,
            actions=[ThinkAction(), FinishAction()],
            reasoning_type="react"
        )
        
        self.conversation_history = []
    
    def llm_layer(self, prompt: str) -> str:
        """Input a prompt, llm generates a text."""
        # If the prompt is a string, convert it to a message
        if isinstance(prompt, str):
            messages = [HumanMessage(content=prompt)]
        else:
            # If it's already a list of messages, use it as is
            messages = prompt
            
        response = self.llm.predict_messages(messages)
        return response.content
    
    def generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a response using the LLM."""
        self.add_to_history("user", user_prompt)
        messages = self.get_chat_messages(system_prompt)
        
        response = self.llm.predict_messages(messages)
        response_text = response.content
        
        self.add_to_history("assistant", response_text)
        return response_text

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