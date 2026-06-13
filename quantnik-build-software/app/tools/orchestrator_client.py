"""
HTTP client for calling Planning & Test child orchestrators.
"""
import httpx
import certifi
import ssl
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TIMEOUT = httpx.Timeout(timeout=900.0, connect=60.0, read=900.0, write=60.0, pool=60.0)


def _ssl_ctx():
    if settings.ssl_verify:
        return ssl.create_default_context(cafile=certifi.where())
    return False


class ChildOrchestratorClient:
    """Calls planning / test child orchestrators."""

    async def call(
        self,
        base_url: str,
        session_id: str,
        message: str,
        explicit_intent: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[list] = None,
    ) -> Dict[str, Any]:
        payload = {
            "session_id": session_id,
            "message": message,
            "explicit_intent": explicit_intent,
            "context": context or {},
            "history": history or [],
        }
        async with httpx.AsyncClient(verify=_ssl_ctx(), timeout=TIMEOUT) as client:
            resp = await client.post(f"{base_url}/v1/chat", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def call_planning(self, session_id: str, message: str, intent: str,
                            context: Dict[str, Any] = None) -> Dict[str, Any]:
        return await self.call(settings.get_planning_url(), session_id, message, intent, context)

    async def call_test(self, session_id: str, message: str, intent: str,
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
        return await self.call(settings.get_test_url(), session_id, message, intent, context)


_client: Optional[ChildOrchestratorClient] = None


def get_client() -> ChildOrchestratorClient:
    global _client
    if _client is None:
        _client = ChildOrchestratorClient()
    return _client
