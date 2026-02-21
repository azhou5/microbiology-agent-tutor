import logging
from typing import List, Dict, Any
from ..utils.llm import chat_complete

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.conversation_history: List[Dict[str, str]] = []

    def chat(self, user_input: str, system_prompt: str, **kwargs) -> str:
        """
        Process a user message and return the agent's response.
        """
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_input})

        # Prepare messages for LLM
        messages = [{"role": "system", "content": system_prompt}] + self.conversation_history

        # Get response
        try:
            response = chat_complete(messages, **kwargs)
            
            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": response})
            
            return response
        except Exception as e:
            logger.error(f"Error in {self.name} agent: {e}")
            return "I apologize, but I encountered an error. Please try again."

    def get_history(self) -> List[Dict[str, str]]:
        return self.conversation_history

