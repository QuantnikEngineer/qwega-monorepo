"""
Abstract base class for AI providers.
Allows swapping between Gemini, Bedrock, Vertex, OpenAI, Azure OpenAI.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel


class AIRequest(BaseModel):
    """Standard request format for AI analysis."""
    prompt: str
    context: Dict[str, Any]
    max_tokens: int = 8192
    temperature: float = 0.3


class AIResponse(BaseModel):
    """Standard response format from AI providers."""
    content: str
    model: str
    provider: str
    tokens_used: int
    latency_ms: float
    raw_response: Optional[Dict[str, Any]] = None


class BaseAIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, api_key: str, model: str, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass
    
    @abstractmethod
    async def analyze(self, request: AIRequest) -> AIResponse:
        """
        Send analysis request to AI provider.
        
        Args:
            request: Standardized AI request
            
        Returns:
            AIResponse with analysis results
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the AI provider is accessible."""
        pass
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for anomaly analysis. (IP - kept in core)"""
        from src.core.prompts import get_analysis_system_prompt
        return get_analysis_system_prompt()


def get_ai_provider(
    provider: str,
    api_key: str,
    model: str,
    timeout: int = 30
) -> BaseAIProvider:
    """
    Factory function to get the appropriate AI provider.
    
    Args:
        provider: Provider name (gemini, bedrock, vertex, openai, azure_openai)
        api_key: API key for the provider
        model: Model name to use
        timeout: Request timeout in seconds
        
    Returns:
        Configured AI provider instance
    """
    providers = {
        "gemini": "src.adapters.ai_providers.gemini.GeminiProvider",
        "bedrock": "src.adapters.ai_providers.bedrock.BedrockProvider",
        "vertex": "src.adapters.ai_providers.vertex.VertexProvider",
        "openai": "src.adapters.ai_providers.openai_provider.OpenAIProvider",
        "azure_openai": "src.adapters.ai_providers.azure_openai.AzureOpenAIProvider",
    }
    
    if provider not in providers:
        raise ValueError(f"Unknown AI provider: {provider}. Available: {list(providers.keys())}")
    
    module_path, class_name = providers[provider].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    provider_class = getattr(module, class_name)
    
    return provider_class(api_key=api_key, model=model, timeout=timeout)
