"""
Azure OpenAI Provider implementation.
"""

import time
import os
from typing import Any, Dict

from .base import BaseAIProvider, AIRequest, AIResponse


class AzureOpenAIProvider(BaseAIProvider):
    """Azure OpenAI API provider."""
    
    def __init__(
        self, 
        api_key: str, 
        model: str, 
        timeout: int = 30,
        endpoint: str = None,
        api_version: str = "2024-02-15-preview"
    ):
        super().__init__(api_key, model, timeout)
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version
    
    @property
    def provider_name(self) -> str:
        return "azure_openai"
    
    async def analyze(self, request: AIRequest) -> AIResponse:
        """Send analysis request to Azure OpenAI API."""
        from openai import AsyncAzureOpenAI
        
        start_time = time.time()
        
        client = AsyncAzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.endpoint
        )
        
        response = await client.chat.completions.create(
            model=self.model,  # This is the deployment name in Azure
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": request.prompt}
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            response_format={"type": "json_object"}
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        content = response.choices[0].message.content or ""
        tokens_used = response.usage.total_tokens if response.usage else 0
        
        return AIResponse(
            content=content,
            model=self.model,
            provider=self.provider_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            raw_response=response.model_dump()
        )
    
    async def health_check(self) -> bool:
        """Check Azure OpenAI API accessibility."""
        try:
            from openai import AsyncAzureOpenAI
            client = AsyncAzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
            await client.models.list()
            return True
        except Exception:
            return False
