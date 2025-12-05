"""
Configuration API endpoints for MicroTutor V4.

Provides endpoints to get current configuration and available models.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from microtutor.core.config.config_helper import config

router = APIRouter()


class ModelInfo(BaseModel):
    """Information about an available model."""
    name: str
    display_name: str
    provider: str
    is_available: bool = True
    description: str = None


class ConfigResponse(BaseModel):
    """Response containing current configuration."""
    use_azure: bool
    current_model: str
    current_provider: str
    available_models: List[ModelInfo]
    azure_endpoint: str = None
    personal_model: str = None


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Get current configuration",
    description="Get the current model configuration and available models"
)
async def get_config() -> ConfigResponse:
    """Get the current configuration and available models."""
    try:
        # Validate that required configuration is available
        if not hasattr(config, 'USE_AZURE_OPENAI'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Configuration not properly loaded"
            )
        # Get current configuration
        use_azure = getattr(config, 'USE_AZURE_OPENAI', True)
        current_model = getattr(config, 'API_MODEL_NAME', 'gpt-4.1')
        current_provider = 'azure' if use_azure else 'personal'
        
        # Log current configuration
        print(f"🔧 [CONFIG] Current System: {current_provider.upper()}")
        print(f"🤖 [CONFIG] Current Model: {current_model}")
        print(f"🌐 [CONFIG] Azure Endpoint: {getattr(config, 'AZURE_OPENAI_ENDPOINT', 'Not set')}")
        print(f"🔑 [CONFIG] API Key Available: {'Yes' if getattr(config, 'AZURE_OPENAI_API_KEY' if use_azure else 'OPENAI_API_KEY', '') else 'No'}")
        
        # Get available models
        available_models = []
        
        # Azure models
        azure_models = [
            ModelInfo(
                name="gpt-4.1",
                display_name="GPT-4.1 (2025-04-14)",
                provider="azure",
                description="Latest GPT-4.1 model via Azure OpenAI"
            ),
            ModelInfo(
                name="gpt-4o-1120",
                display_name="GPT-4o (2024-11-20)",
                provider="azure",
                description="GPT-4o model via Azure OpenAI"
            ),
            ModelInfo(
                name="o4-mini-0416",
                display_name="o4-mini (2025-04-16)",
                provider="azure",
                description="o4-mini model via Azure OpenAI"
            ),
            ModelInfo(
                name="o3-mini-0131",
                display_name="o3-mini (2025-01-31)",
                provider="azure",
                description="o3-mini model via Azure OpenAI"
            )
        ]
        
        # Personal OpenAI models
        personal_models = [
            ModelInfo(
                name="o4",
                display_name="o4",
                provider="personal",
                description="Latest o4 model via Personal OpenAI"
            ),
            ModelInfo(
                name="gpt-5-mini-2025-08-07",
                display_name="GPT-5 Mini (2025-08-07)",
                provider="personal",
                description="GPT-5 Mini model via Personal OpenAI"
            ),
            ModelInfo(
                name="gpt-5-2025-08-07",
                display_name="GPT-5 (2025-08-07)",
                provider="personal",
                description="GPT-5 model via Personal OpenAI"
            ),
            ModelInfo(
                name="gpt-4.1-2025-04-14",
                display_name="GPT-4.1 (2025-04-14)",
                provider="personal",
                description="GPT-4.1 model via Personal OpenAI"
            )
        ]
        
        available_models = azure_models + personal_models
        
        return ConfigResponse(
            use_azure=use_azure,
            current_model=current_model,
            current_provider=current_provider,
            available_models=available_models,
            azure_endpoint=getattr(config, 'AZURE_OPENAI_ENDPOINT', ''),
            personal_model=getattr(config, 'PERSONAL_OPENAI_MODEL', 'o4-mini-2025-04-16')
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get configuration: {str(e)}"
        )


@router.get(
    "/models",
    response_model=List[ModelInfo],
    summary="Get available models",
    description="Get list of all available models for both providers"
)
async def get_available_models() -> List[ModelInfo]:
    """Get all available models."""
    try:
        # Azure models
        azure_models = [
            ModelInfo(
                name="gpt-4.1",
                display_name="GPT-4.1 (2025-04-14)",
                provider="azure",
                description="Latest GPT-4.1 model via Azure OpenAI"
            ),
            ModelInfo(
                name="gpt-4o-1120",
                display_name="GPT-4o (2024-11-20)",
                provider="azure",
                description="GPT-4o model via Azure OpenAI"
            ),
            ModelInfo(
                name="o4-mini-0416",
                display_name="o4-mini (2025-04-16)",
                provider="azure",
                description="o4-mini model via Azure OpenAI"
            ),
            ModelInfo(
                name="o3-mini-0131",
                display_name="o3-mini (2025-01-31)",
                provider="azure",
                description="o3-mini model via Azure OpenAI"
            )
        ]
        
        # Personal OpenAI models
        personal_models = [
            ModelInfo(
                name="o4",
                display_name="o4",
                provider="personal",
                description="Latest o4 model via Personal OpenAI"
            ),
            ModelInfo(
                name="gpt-5-mini-2025-08-07",
                display_name="GPT-5 Mini (2025-08-07)",
                provider="personal",
                description="GPT-5 Mini model via Personal OpenAI"
            ),
            ModelInfo(
                name="gpt-5-2025-08-07",
                display_name="GPT-5 (2025-08-07)",
                provider="personal",
                description="GPT-5 model via Personal OpenAI"
            ),
            ModelInfo(
                name="gpt-4.1-2025-04-14",
                display_name="GPT-4.1 (2025-04-14)",
                provider="personal",
                description="GPT-4.1 model via Personal OpenAI"
            )
        ]
        
        return azure_models + personal_models
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available models: {str(e)}"
        )
