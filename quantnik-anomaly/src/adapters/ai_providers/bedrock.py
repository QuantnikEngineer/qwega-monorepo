"""
AWS Bedrock AI Provider implementation.
"""

import time
import json
from typing import Any, Dict

from .base import BaseAIProvider, AIRequest, AIResponse


class BedrockProvider(BaseAIProvider):
    """AWS Bedrock AI provider."""
    
    def __init__(self, api_key: str, model: str, timeout: int = 30, region: str = "us-east-1"):
        super().__init__(api_key, model, timeout)
        self.region = region
        self._client = None
    
    @property
    def provider_name(self) -> str:
        return "bedrock"
    
    def _get_client(self):
        """Get or create Bedrock client."""
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region
            )
        return self._client
    
    async def analyze(self, request: AIRequest) -> AIResponse:
        """Send analysis request to AWS Bedrock."""
        import asyncio
        start_time = time.time()
        
        client = self._get_client()
        
        # Build payload based on model family
        if "claude" in self.model.lower():
            payload = self._build_claude_payload(request)
        elif "titan" in self.model.lower():
            payload = self._build_titan_payload(request)
        else:
            payload = self._build_claude_payload(request)
        
        # Run synchronous boto3 call in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.invoke_model(
                modelId=self.model,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json"
            )
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        response_body = json.loads(response["body"].read())
        content = self._extract_content(response_body)
        
        return AIResponse(
            content=content,
            model=self.model,
            provider=self.provider_name,
            tokens_used=response_body.get("usage", {}).get("total_tokens", 0),
            latency_ms=latency_ms,
            raw_response=response_body
        )
    
    def _build_claude_payload(self, request: AIRequest) -> Dict[str, Any]:
        """Build payload for Claude models."""
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "system": self._build_system_prompt(),
            "messages": [
                {"role": "user", "content": request.prompt}
            ]
        }
    
    def _build_titan_payload(self, request: AIRequest) -> Dict[str, Any]:
        """Build payload for Titan models."""
        return {
            "inputText": f"{self._build_system_prompt()}\n\n{request.prompt}",
            "textGenerationConfig": {
                "maxTokenCount": request.max_tokens,
                "temperature": request.temperature
            }
        }
    
    def _extract_content(self, response: Dict[str, Any]) -> str:
        """Extract content from response based on model."""
        if "content" in response:
            # Claude format
            return response["content"][0]["text"]
        elif "results" in response:
            # Titan format
            return response["results"][0]["outputText"]
        return str(response)
    
    async def health_check(self) -> bool:
        """Check Bedrock accessibility."""
        try:
            client = self._get_client()
            client.list_foundation_models()
            return True
        except Exception:
            return False
