"""
Google Gemini AI Provider implementation.
"""

import time
import httpx
from typing import Any, Dict

from .base import BaseAIProvider, AIRequest, AIResponse


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI provider."""
    
    API_BASE = "https://generativelanguage.googleapis.com/v1beta"
    
    @property
    def provider_name(self) -> str:
        return "gemini"
    
    async def analyze(self, request: AIRequest) -> AIResponse:
        """Send analysis request to Gemini API."""
        start_time = time.time()
        
        url = f"{self.API_BASE}/models/{self.model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": self._build_system_prompt()},
                        {"text": request.prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
                "responseMimeType": "application/json"
            }
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        
        latency_ms = (time.time() - start_time) * 1000
        
        content = ""
        if "candidates" in data and data["candidates"]:
            parts = data["candidates"][0].get("content", {}).get("parts", [])
            if parts:
                content = parts[0].get("text", "")
        
        tokens_used = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        
        return AIResponse(
            content=content,
            model=self.model,
            provider=self.provider_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            raw_response=data
        )
    
    async def health_check(self) -> bool:
        """Check Gemini API accessibility."""
        try:
            url = f"{self.API_BASE}/models?key={self.api_key}"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                return response.status_code == 200
        except Exception:
            return False
