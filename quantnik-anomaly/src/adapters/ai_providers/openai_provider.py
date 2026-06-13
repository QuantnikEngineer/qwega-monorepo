"""
OpenAI Provider implementation.
"""

import time
from typing import Any, Dict

from .base import BaseAIProvider, AIRequest, AIResponse


class OpenAIProvider(BaseAIProvider):
    """OpenAI API provider."""
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    async def analyze(self, request: AIRequest) -> AIResponse:
        """Send analysis request to OpenAI API."""
        from openai import AsyncOpenAI
        
        start_time = time.time()
        
        client = AsyncOpenAI(api_key=self.api_key)
        
        response = await client.chat.completions.create(
            model=self.model,
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
        """Check OpenAI API accessibility."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            await client.models.list()
            return True
        except Exception:
            return False
