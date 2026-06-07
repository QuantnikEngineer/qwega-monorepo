"""
Google Vertex AI Provider implementation.
"""

import time
from typing import Any, Dict

from .base import BaseAIProvider, AIRequest, AIResponse


class VertexProvider(BaseAIProvider):
    """Google Vertex AI provider."""
    
    def __init__(self, api_key: str, model: str, timeout: int = 30, project_id: str = None, location: str = "us-central1"):
        super().__init__(api_key, model, timeout)
        self.project_id = project_id
        self.location = location
        self._client = None
    
    @property
    def provider_name(self) -> str:
        return "vertex"
    
    def _get_client(self):
        """Get or create Vertex AI client."""
        if self._client is None:
            import vertexai
            from vertexai.generative_models import GenerativeModel
            
            vertexai.init(project=self.project_id, location=self.location)
            self._client = GenerativeModel(self.model)
        return self._client
    
    async def analyze(self, request: AIRequest) -> AIResponse:
        """Send analysis request to Vertex AI."""
        import asyncio
        start_time = time.time()
        
        client = self._get_client()
        
        full_prompt = f"{self._build_system_prompt()}\n\n{request.prompt}"
        
        generation_config = {
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
            "response_mime_type": "application/json"
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.generate_content(
                full_prompt,
                generation_config=generation_config
            )
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        content = response.text if response.text else ""
        tokens_used = (
            response.usage_metadata.total_token_count 
            if hasattr(response, 'usage_metadata') else 0
        )
        
        return AIResponse(
            content=content,
            model=self.model,
            provider=self.provider_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            raw_response={"text": content}
        )
    
    async def health_check(self) -> bool:
        """Check Vertex AI accessibility."""
        try:
            self._get_client()
            return True
        except Exception:
            return False
