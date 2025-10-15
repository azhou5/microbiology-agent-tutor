"""
Embedding utilities for text vectorization using OpenAI/Azure OpenAI.

This module provides centralized functions for generating embeddings from text
using either OpenAI or Azure OpenAI services, with automatic client selection
based on environment configuration.
"""

import os
from typing import List, Union
from openai import AzureOpenAI, OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_embedding(text: str) -> List[float]:
    """
    Get embedding for a single text using OpenAI or Azure OpenAI.
    
    Args:
        text: The text to embed
        
    Returns:
        List of float values representing the embedding vector
        
    Raises:
        ValueError: If required API credentials are missing
        Exception: If the embedding request fails
    """
    # Determine which client to use based on the toggle
    use_azure_env = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if use_azure_env and azure_endpoint and azure_api_key:
        # Use Azure OpenAI
        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
        )
    elif openai_api_key:
        # Use personal OpenAI
        client = OpenAI(api_key=openai_api_key)
    else:
        raise ValueError(
            "Missing required OpenAI environment variables. "
            "Check USE_AZURE_OPENAI setting and credentials."
        )
    
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        input=text
    )
    return response.data[0].embedding


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Get embeddings for a batch of texts using OpenAI or Azure OpenAI.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embedding vectors, one for each input text
        
    Raises:
        ValueError: If required API credentials are missing
        Exception: If the embedding request fails
    """
    # Determine which client to use based on the toggle
    use_azure_env = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if use_azure_env and azure_endpoint and azure_api_key:
        # Use Azure OpenAI
        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
        )
    elif openai_api_key:
        # Use personal OpenAI
        client = OpenAI(api_key=openai_api_key)
    else:
        raise ValueError(
            "Missing required OpenAI environment variables. "
            "Check USE_AZURE_OPENAI setting and credentials."
        )
    
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        input=texts
    )
    return [data.embedding for data in response.data]


def get_embedding_model_name() -> str:
    """
    Get the currently configured embedding model name.
    
    Returns:
        The embedding model name from environment variables
    """
    return os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


def get_embedding_dimension() -> int:
    """
    Get the dimension of the current embedding model.
    
    Returns:
        The embedding dimension (1536 for text-embedding-3-small, 3072 for text-embedding-3-large)
    """
    model_name = get_embedding_model_name()
    
    if "text-embedding-3-large" in model_name:
        return 3072
    elif "text-embedding-3-small" in model_name or "text-embedding-ada-002" in model_name:
        return 1536
    else:
        # Default to 1536 for unknown models
        return 1536
