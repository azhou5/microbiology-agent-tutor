import logging
from openai import OpenAI
from ..config.config import config

logger = logging.getLogger(__name__)

client = OpenAI(api_key=config.OPENAI_API_KEY)

def chat_complete(
    messages: list[dict],
    model: str = config.MODEL_NAME,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    response_format: dict = None
) -> str:
    """
    Simple wrapper for OpenAI chat completion.
    """
    try:
        kwargs = {
            "model": model,
            "messages": messages,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise

