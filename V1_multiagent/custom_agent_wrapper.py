from agentlite.agents.BaseAgent import BaseAgent
from langchain.schema import HumanMessage
from typing import Union, List, Any

class CustomAgentWrapper(BaseAgent):
    """
    A wrapper for the BaseAgent class that overrides the llm_layer method
    to handle the LangChain API correctly.
    """
    
    def llm_layer(self, prompt: Union[str, List[Any]]) -> str:
        """
        Override the llm_layer method to use the correct LangChain API.
        
        Args:
            prompt: Either a string or a list of message objects
            
        Returns:
            The content of the response
        """
        # If the prompt is a string, convert it to a message
        if isinstance(prompt, str):
            messages = [HumanMessage(content=prompt)]
        else:
            # If it's already a list of messages, use it as is
            messages = prompt
            
        # Use predict_messages instead of run
        response = self.llm.predict_messages(messages)
        return response.content 