import os


class LLMConfig:
    """constructing the llm configuration for running multi-agent system"""

    def __init__(self, config_dict: dict) -> None:
        self.config_dict = config_dict
        self.context_len = None
        self.llm_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        if not self.llm_name:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME environment variable must be set")
        self.temperature = 0.9
        self.stop = ["\n"]
        self.max_tokens = 256
        self.end_of_prompt = ""
        self.api_key: str = os.environ.get("OPENAI_API_KEY", "EMPTY")
        self.base_url = None
        self.provider = None
        self.api_type = os.environ.get("OPENAI_API_TYPE", "azure")
        self.__dict__.update(config_dict)
