"""
Orchestrator Client
===================
HTTP client for communicating with child orchestrators.
"""

from typing import Dict, Any, Optional, List, AsyncGenerator
import httpx
import certifi
import json
import asyncio
import ssl
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from app.core.logging import get_logger
from app.core.config import settings, OrchestratorCapabilities
from app.models.requests import OrchestratorType

logger = get_logger(__name__)


class OrchestratorClient:
    """
    Client for calling child orchestrators (Planning and Test).
    
    Handles:
    - HTTP communication with child orchestrators
    - Health checks
    - Request/response transformation
    - Retry logic for Cloud Run cold starts
    """
    
    # Retry configuration for Cloud Run cold starts
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2
    
    def __init__(self, timeout: int = 900):
        logger.info("[OrchestratorClient.__init__] Initializing orchestrator client", timeout=timeout)
        self._timeout = timeout
        
        # Configure SSL context properly
        if settings.ssl_verify:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            ssl_context = False
            logger.warning("[OrchestratorClient.__init__] SSL verification disabled")
        
        # Configure connection limits and timeouts for Cloud Run compatibility
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        )
        
        # Configure timeouts: longer connect timeout for cold starts
        timeouts = httpx.Timeout(
            timeout=float(timeout),
            connect=60.0,  # 60s connect timeout for Cloud Run cold starts
            read=float(timeout),
            write=60.0,
            pool=60.0  # Pool timeout for getting connection from pool
        )
        
        # Create transport with specific settings for Cloud Run
        # Using default transport but with HTTP/1.1 forced
        self._client = httpx.AsyncClient(
            timeout=timeouts,
            verify=ssl_context,
            limits=limits,
            http1=True,  # Explicitly enable HTTP/1.1
            http2=False,  # Disable HTTP/2 to avoid connection issues
            follow_redirects=True
        )
        
        logger.info(
            "[OrchestratorClient.__init__] HTTP client configured",
            http1=True,
            http2=False,
            connect_timeout=60.0,
            ssl_verify=settings.ssl_verify
        )
        
        self._orchestrator_urls = {
            OrchestratorType.PLANNING: settings.get_planning_orchestrator_url(),
            OrchestratorType.TEST: settings.get_test_orchestrator_url(),
            OrchestratorType.COMMON_INTEGRATION: settings.get_common_integration_orchestrator_url(),
        }
        logger.info(
            "[OrchestratorClient.__init__] Orchestrator URLs configured",
            planning_url=settings.get_planning_orchestrator_url(),
            test_url=settings.get_test_orchestrator_url(),
            common_integration_url=settings.get_common_integration_orchestrator_url()
        )
    
    def _get_id_token(self, audience: str) -> Optional[str]:
        """Get Google Cloud ID token for service-to-service authentication."""
        try:
            # Extract base URL (without path) for audience
            from urllib.parse import urlparse
            parsed = urlparse(audience)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            token = id_token.fetch_id_token(Request(), base_url)
            logger.info(
                "[OrchestratorClient._get_id_token] ID token fetched successfully",
                audience=base_url
            )
            return token
        except Exception as e:
            logger.warning(
                "[OrchestratorClient._get_id_token] Failed to fetch ID token (may not be needed for public services)",
                audience=audience,
                error=str(e),
                error_type=type(e).__name__
            )
            return None
    
    def _get_auth_headers(self, url: str) -> Dict[str, str]:
        """Get authentication headers for Cloud Run service calls."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"  # For SSE
        }
        token = self._get_id_token(url)
        if token:
            headers["Authorization"] = f"Bearer {token}"
            logger.info("[OrchestratorClient._get_auth_headers] Auth header added")
        else:
            logger.info("[OrchestratorClient._get_auth_headers] No auth token, proceeding without auth")
        return headers
    
    async def close(self):
        """Close the HTTP client."""
        logger.info("[OrchestratorClient.close] Closing HTTP client")
        await self._client.aclose()
        logger.debug("[OrchestratorClient.close] HTTP client closed successfully")
    
    def get_url(self, orchestrator: OrchestratorType) -> str:
        """Get URL for an orchestrator."""
        url = self._orchestrator_urls.get(orchestrator, "")
        logger.debug("[OrchestratorClient.get_url] Retrieved URL", orchestrator=orchestrator.value, url=url)
        return url
    
    async def check_health(self, orchestrator: OrchestratorType) -> Dict[str, Any]:
        """Check health of a child orchestrator."""
        logger.debug("[OrchestratorClient.check_health] Starting health check", orchestrator=orchestrator.value)
        url = self.get_url(orchestrator)
        if not url:
            logger.warning("[OrchestratorClient.check_health] URL not configured", orchestrator=orchestrator.value)
            return {"status": "unknown", "error": "URL not configured"}
        
        # Use fresh client for health check
        fresh_client = self._create_fresh_client()
        try:
            logger.info("[OrchestratorClient.check_health] Sending health check request", url=f"{url}/health")
            headers = self._get_auth_headers(url)
            response = await fresh_client.get(f"{url}/health", timeout=30, headers=headers)
            response.raise_for_status()
            result = response.json()
            logger.info(
                "[OrchestratorClient.check_health] Health check successful",
                orchestrator=orchestrator.value,
                status=result.get("status"),
                response=result
            )
            return result
        except Exception as e:
            logger.error(
                "[OrchestratorClient.check_health] Health check failed",
                orchestrator=orchestrator.value,
                url=f"{url}/health",
                error=str(e),
                error_type=type(e).__name__
            )
            return {"status": "unhealthy", "error": str(e)}
        finally:
            await fresh_client.aclose()
    
    async def verify_connectivity(self, orchestrator: OrchestratorType) -> Dict[str, Any]:
        """
        Verify connectivity to a child orchestrator before making stream calls.
        This helps diagnose connection issues.
        """
        url = self.get_url(orchestrator)
        if not url:
            return {"success": False, "error": "URL not configured"}
        
        result = {
            "url": url,
            "dns_resolved": False,
            "tcp_connected": False,
            "http_ok": False,
            "error": None
        }
        
        try:
            import socket
            from urllib.parse import urlparse
            
            # Parse URL
            parsed = urlparse(url)
            host = parsed.netloc
            port = 443 if parsed.scheme == "https" else 80
            
            # Check DNS resolution
            logger.info(f"[verify_connectivity] Resolving DNS for {host}")
            ip_addresses = socket.gethostbyname_ex(host)
            result["dns_resolved"] = True
            result["ip_addresses"] = ip_addresses[2]
            logger.info(f"[verify_connectivity] DNS resolved: {ip_addresses[2]}")
            
            # Check TCP connectivity
            logger.info(f"[verify_connectivity] Testing TCP connection to {host}:{port}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((ip_addresses[2][0], port))
            sock.close()
            result["tcp_connected"] = True
            logger.info("[verify_connectivity] TCP connection successful")
            
            # Check HTTP connectivity
            health_result = await self.check_health(orchestrator)
            result["http_ok"] = health_result.get("status") != "unhealthy"
            result["health_response"] = health_result
            
            result["success"] = all([result["dns_resolved"], result["tcp_connected"], result["http_ok"]])
            
        except socket.gaierror as e:
            result["error"] = f"DNS resolution failed: {str(e)}"
            logger.error("[verify_connectivity] DNS resolution failed", error=str(e))
        except socket.timeout as e:
            result["error"] = f"TCP connection timeout: {str(e)}"
            logger.error("[verify_connectivity] TCP connection timeout", error=str(e))
        except socket.error as e:
            result["error"] = f"Socket error: {str(e)}"
            logger.error("[verify_connectivity] Socket error", error=str(e))
        except Exception as e:
            result["error"] = f"Connectivity check failed: {str(e)}"
            logger.error("[verify_connectivity] Connectivity check failed", error=str(e), error_type=type(e).__name__)
        
        return result
    
    async def call_chat(
        self,
        orchestrator: OrchestratorType,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        explicit_intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call the /v1/chat endpoint of a child orchestrator.
        Includes retry logic for Cloud Run cold starts.
        
        Args:
            orchestrator: Target orchestrator (planning or test)
            session_id: Session identifier
            message: User message
            context: Additional context
            history: Conversation history
            explicit_intent: Explicit intent override
            
        Returns:
            Response from the child orchestrator
        """
        logger.info(
            "[OrchestratorClient.call_chat] Starting chat call",
            orchestrator=orchestrator.value,
            session_id=session_id,
            message_length=len(message),
            has_context=context is not None,
            history_count=len(history) if history else 0,
            explicit_intent=explicit_intent
        )
        
        url = self.get_url(orchestrator)
        if not url:
            error_msg = f"URL not configured for {orchestrator.value} orchestrator"
            logger.error("[OrchestratorClient.call_chat] URL not configured", orchestrator=orchestrator.value)
            raise ValueError(error_msg)
        
        # Build request payload
        payload = {
            "session_id": session_id,
            "message": message
        }
        
        if context:
            payload["context"] = context
        
        if history:
            payload["history"] = [
                {"role": h["role"], "content": h["content"]}
                for h in history
            ]
        
        if explicit_intent:
            payload["explicit_intent"] = explicit_intent
        
        logger.info(
            "[OrchestratorClient.call_chat] Sending request to child orchestrator",
            orchestrator=orchestrator.value,
            url=f"{url}/v1/chat",
            session_id=session_id,
            request_payload=payload
        )
        
        last_exception = None
        fresh_client = None
        
        for attempt in range(self.MAX_RETRIES):
            # Use fresh client for each attempt to avoid stale connections
            fresh_client = self._create_fresh_client()
            try:
                logger.info(
                    "[OrchestratorClient.call_chat] Attempting connection with fresh client",
                    orchestrator=orchestrator.value,
                    session_id=session_id,
                    attempt=attempt + 1,
                    max_retries=self.MAX_RETRIES,
                    url=f"{url}/v1/chat"
                )
                
                headers = self._get_auth_headers(url)
                response = await fresh_client.post(
                    f"{url}/v1/chat",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                
                result = response.json()
                logger.info(
                    "[OrchestratorClient.call_chat] Response received from child orchestrator",
                    orchestrator=orchestrator.value,
                    session_id=session_id,
                    status=result.get("status", "unknown"),
                    response_payload=result
                )
                await fresh_client.aclose()
                return result
                
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                last_exception = e
                if fresh_client:
                    try:
                        await fresh_client.aclose()
                    except Exception:
                        pass
                
                logger.warning(
                    "[OrchestratorClient.call_chat] Connection failed, will retry",
                    orchestrator=orchestrator.value,
                    session_id=session_id,
                    attempt=attempt + 1,
                    max_retries=self.MAX_RETRIES,
                    error=str(e),
                    error_type=type(e).__name__,
                    url=f"{url}/v1/chat"
                )
                
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY_SECONDS * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "[OrchestratorClient.call_chat] Connection error after all retries",
                        orchestrator=orchestrator.value,
                        session_id=session_id,
                        url=f"{url}/v1/chat",
                        error=str(e),
                        error_type=type(e).__name__,
                        request_payload=payload
                    )
                    raise RuntimeError(f"{orchestrator.value} orchestrator connection error: {str(e)}")
                    
            except httpx.HTTPError as e:
                if fresh_client:
                    try:
                        await fresh_client.aclose()
                    except Exception:
                        pass
                logger.error(
                    "[OrchestratorClient.call_chat] HTTP error calling child orchestrator",
                    orchestrator=orchestrator.value,
                    session_id=session_id,
                    url=f"{url}/v1/chat",
                    error=str(e),
                    error_type=type(e).__name__,
                    request_payload=payload
                )
                raise RuntimeError(f"{orchestrator.value} orchestrator error: {str(e)}")
        
        # Should not reach here
        if last_exception:
            raise RuntimeError(f"{orchestrator.value} orchestrator connection error: {str(last_exception)}")
    
    def _create_fresh_client(self) -> httpx.AsyncClient:
        """
        Create a fresh HTTP client for each request.
        This avoids stale connection issues in Cloud Run.
        """
        # Configure SSL context properly
        if settings.ssl_verify:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            ssl_context = False
        
        # Configure timeouts
        timeouts = httpx.Timeout(
            timeout=float(self._timeout),
            connect=60.0,
            read=float(self._timeout),
            write=60.0,
            pool=60.0
        )
        
        # Configure connection limits
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        )
        
        return httpx.AsyncClient(
            timeout=timeouts,
            verify=ssl_context,
            limits=limits,
            http1=True,
            http2=False,
            follow_redirects=True
        )

    async def _stream_with_retry(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        orchestrator_name: str,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream SSE with retry logic for Cloud Run cold starts.
        Uses a fresh client for each attempt to avoid stale connections.
        
        Yields raw text chunks from the stream.
        """
        last_exception = None
        fresh_client = None
        
        for attempt in range(self.MAX_RETRIES):
            # Create a fresh client for each attempt to avoid stale connections
            fresh_client = self._create_fresh_client()
            connection_successful = False
            
            try:
                logger.info(
                    "[OrchestratorClient._stream_with_retry] Attempting connection with fresh client",
                    orchestrator=orchestrator_name,
                    session_id=session_id,
                    attempt=attempt + 1,
                    max_retries=self.MAX_RETRIES,
                    url=url
                )
                
                async with fresh_client.stream(
                    "POST",
                    url,
                    json=payload,
                    timeout=self._timeout,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    connection_successful = True
                    logger.info(
                        "[OrchestratorClient._stream_with_retry] Connection established",
                        orchestrator=orchestrator_name,
                        session_id=session_id,
                        status_code=response.status_code,
                        attempt=attempt + 1
                    )
                    
                    # Collect all chunks first, then yield them
                    # This ensures the client stays open during streaming
                    async for chunk in response.aiter_text():
                        yield chunk
                    
                    # Successfully completed, close client and exit
                    await fresh_client.aclose()
                    return
                    
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                last_exception = e
                # Close the client before retry
                if fresh_client:
                    try:
                        await fresh_client.aclose()
                    except Exception:
                        pass
                
                logger.warning(
                    "[OrchestratorClient._stream_with_retry] Connection failed, will retry",
                    orchestrator=orchestrator_name,
                    session_id=session_id,
                    attempt=attempt + 1,
                    max_retries=self.MAX_RETRIES,
                    error=str(e),
                    error_type=type(e).__name__,
                    url=url
                )
                
                if attempt < self.MAX_RETRIES - 1:
                    # Wait before retry (exponential backoff)
                    delay = self.RETRY_DELAY_SECONDS * (2 ** attempt)
                    logger.info(
                        "[OrchestratorClient._stream_with_retry] Waiting before retry",
                        delay_seconds=delay
                    )
                    await asyncio.sleep(delay)
                else:
                    # Last attempt failed
                    logger.error(
                        "[OrchestratorClient._stream_with_retry] All connection attempts failed",
                        orchestrator=orchestrator_name,
                        session_id=session_id,
                        error=str(e),
                        error_type=type(e).__name__,
                        url=url
                    )
                    raise
            except httpx.HTTPError as e:
                # Close client and don't retry for other HTTP errors
                if fresh_client:
                    try:
                        await fresh_client.aclose()
                    except Exception:
                        pass
                logger.error(
                    "[OrchestratorClient._stream_with_retry] HTTP error (not retrying)",
                    orchestrator=orchestrator_name,
                    session_id=session_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    url=url
                )
                raise
            except Exception as e:
                # Close client on any other error
                if fresh_client:
                    try:
                        await fresh_client.aclose()
                    except Exception:
                        pass
                raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    async def call_chat_stream(
        self,
        orchestrator: OrchestratorType,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        explicit_intent: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Call the /v1/chat/stream endpoint of a child orchestrator.
        
        Yields SSE events from the child orchestrator for passthrough to frontend.
        Includes retry logic for Cloud Run cold starts and connection failures.
        
        Args:
            orchestrator: Target orchestrator (planning or test)
            session_id: Session identifier
            message: User message
            context: Additional context
            history: Conversation history
            explicit_intent: Explicit intent override
            
        Yields:
            Parsed SSE event data from the child orchestrator
        """
        logger.info(
            "[OrchestratorClient.call_chat_stream] Starting SSE stream call",
            orchestrator=orchestrator.value,
            session_id=session_id,
            message_length=len(message),
            has_context=context is not None,
            history_count=len(history) if history else 0,
            explicit_intent=explicit_intent
        )
        
        url = self.get_url(orchestrator)
        if not url:
            error_msg = f"URL not configured for {orchestrator.value} orchestrator"
            logger.error("[OrchestratorClient.call_chat_stream] URL not configured", orchestrator=orchestrator.value)
            raise ValueError(error_msg)
        
        payload = {
            "session_id": session_id,
            "message": message,
        }
        
        if context:
            payload["context"] = context
        
        if history:
            payload["history"] = [
                {"role": h["role"], "content": h["content"]}
                for h in history
            ]
        
        if explicit_intent:
            payload["explicit_intent"] = explicit_intent
        
        logger.info(
            "[OrchestratorClient.call_chat_stream] Sending SSE stream request",
            orchestrator=orchestrator.value,
            url=f"{url}/v1/chat/stream",
            session_id=session_id,
            request_payload=payload
        )
        
        event_count = 0
        try:
            headers = self._get_auth_headers(url)
            
            buffer = ""
            async for chunk in self._stream_with_retry(
                url=f"{url}/v1/chat/stream",
                payload=payload,
                headers=headers,
                orchestrator_name=orchestrator.value,
                session_id=session_id
            ):
                buffer += chunk
                
                while "\n\n" in buffer:
                    event_str, buffer = buffer.split("\n\n", 1)
                    
                    if event_str.startswith("data: "):
                        data_str = event_str[6:].strip()
                        if data_str:
                            try:
                                event_data = json.loads(data_str)
                                event_data["_source_orchestrator"] = orchestrator.value
                                event_count += 1
                                logger.debug(
                                    "[OrchestratorClient.call_chat_stream] SSE event received",
                                    orchestrator=orchestrator.value,
                                    session_id=session_id,
                                    event_count=event_count,
                                    event_type=event_data.get("type"),
                                    event_stage=event_data.get("stage"),
                                    event_data=event_data
                                )
                                yield event_data
                            except json.JSONDecodeError as je:
                                logger.warning(
                                    "[OrchestratorClient.call_chat_stream] Failed to parse SSE event JSON",
                                    orchestrator=orchestrator.value,
                                    session_id=session_id,
                                    error=str(je),
                                    error_type=type(je).__name__,
                                    raw_data=data_str[:200]
                                )
            
            # Handle remaining buffer
            if buffer.strip().startswith("data: "):
                data_str = buffer.strip()[6:]
                if data_str:
                    try:
                        event_data = json.loads(data_str)
                        event_data["_source_orchestrator"] = orchestrator.value
                        event_count += 1
                        logger.debug(
                            "[OrchestratorClient.call_chat_stream] Final SSE event from buffer",
                            orchestrator=orchestrator.value,
                            session_id=session_id,
                            event_count=event_count,
                            event_type=event_data.get("type"),
                            event_data=event_data
                        )
                        yield event_data
                    except json.JSONDecodeError as je:
                        logger.warning(
                            "[OrchestratorClient.call_chat_stream] Failed to parse final buffer JSON",
                            error=str(je),
                            raw_data=data_str[:200]
                        )
            
            logger.info(
                "[OrchestratorClient.call_chat_stream] SSE stream completed",
                orchestrator=orchestrator.value,
                session_id=session_id,
                total_events=event_count
            )
                            
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            logger.error(
                "[OrchestratorClient.call_chat_stream] SSE stream connection error after retries",
                orchestrator=orchestrator.value,
                session_id=session_id,
                url=f"{url}/v1/chat/stream",
                error=str(e),
                error_type=type(e).__name__,
                events_before_error=event_count,
                request_payload=payload
            )
            raise RuntimeError(f"{orchestrator.value} orchestrator connection error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(
                "[OrchestratorClient.call_chat_stream] SSE stream HTTP error",
                orchestrator=orchestrator.value,
                session_id=session_id,
                url=f"{url}/v1/chat/stream",
                error=str(e),
                error_type=type(e).__name__,
                events_before_error=event_count,
                request_payload=payload
            )
            raise RuntimeError(f"{orchestrator.value} orchestrator stream error: {str(e)}")
        except Exception as e:
            logger.error(
                "[OrchestratorClient.call_chat_stream] Unexpected error in SSE stream",
                orchestrator=orchestrator.value,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
                events_before_error=event_count
            )
            raise
    
    async def call_legacy_analyze(
        self,
        orchestrator: OrchestratorType,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call the legacy /api/v1/prompt/analyze endpoint."""
        logger.info(
            "[OrchestratorClient.call_legacy_analyze] Starting legacy analyze call",
            orchestrator=orchestrator.value,
            request_payload=payload
        )
        
        url = self.get_url(orchestrator)
        if not url:
            error_msg = f"URL not configured for {orchestrator.value} orchestrator"
            logger.error("[OrchestratorClient.call_legacy_analyze] URL not configured", orchestrator=orchestrator.value)
            raise ValueError(error_msg)
        
        try:
            logger.debug(
                "[OrchestratorClient.call_legacy_analyze] Sending legacy request",
                url=f"{url}/api/v1/prompt/analyze",
                orchestrator=orchestrator.value
            )
            response = await self._client.post(
                f"{url}/api/v1/prompt/analyze",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            logger.info(
                "[OrchestratorClient.call_legacy_analyze] Legacy response received",
                orchestrator=orchestrator.value,
                response_payload=result
            )
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "[OrchestratorClient.call_legacy_analyze] Legacy endpoint HTTP error",
                orchestrator=orchestrator.value,
                url=f"{url}/api/v1/prompt/analyze",
                error=str(e),
                error_type=type(e).__name__,
                request_payload=payload
            )
            raise RuntimeError(f"{orchestrator.value} orchestrator error: {str(e)}")
    
    async def call_chat_multipart(
        self,
        orchestrator: OrchestratorType,
        session_id: str,
        message: str,
        files: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        explicit_intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call the /v1/chat endpoint with multipart/form-data for file uploads.
        
        Args:
            orchestrator: Target orchestrator (typically planning for BRD creation)
            session_id: Session identifier
            message: User message
            files: List of file dicts with 'filename', 'content_type', 'content', 'field_name'
            context: Additional context
            history: Conversation history
            explicit_intent: Explicit intent override
            
        Returns:
            Response from the child orchestrator
        """
        logger.info(
            "[OrchestratorClient.call_chat_multipart] Starting multipart chat call",
            orchestrator=orchestrator.value,
            session_id=session_id,
            message_length=len(message) if message else 0,
            file_count=len(files),
            file_names=[f["filename"] for f in files],
            explicit_intent=explicit_intent
        )
        
        url = self.get_url(orchestrator)
        if not url:
            error_msg = f"URL not configured for {orchestrator.value} orchestrator"
            logger.error("[OrchestratorClient.call_chat_multipart] URL not configured", orchestrator=orchestrator.value)
            raise ValueError(error_msg)
        
        # Build multipart form data
        form_data = {
            "session_id": session_id,
            "message": message or "",
        }
        
        if context:
            form_data["context"] = json.dumps(context)
        
        if history:
            form_data["history"] = json.dumps([
                {"role": h["role"], "content": h["content"]}
                for h in history
            ])
        
        if explicit_intent:
            form_data["explicit_intent"] = explicit_intent
        
        # Prepare files for httpx
        httpx_files = []
        for f in files:
            field_name = f.get("field_name", "file")
            httpx_files.append(
                (field_name, (f["filename"], f["content"], f.get("content_type", "application/octet-stream")))
            )
        
        logger.info(
            "[OrchestratorClient.call_chat_multipart] Sending multipart request",
            orchestrator=orchestrator.value,
            url=f"{url}/v1/chat",
            session_id=session_id,
            form_fields=list(form_data.keys()),
            file_count=len(httpx_files)
        )
        
        # Use fresh client for multipart requests
        fresh_client = self._create_fresh_client()
        try:
            headers = self._get_auth_headers(url)
            # Remove Content-Type from headers as httpx sets it for multipart
            headers.pop("Content-Type", None)
            headers.pop("Accept", None)
            
            response = await fresh_client.post(
                f"{url}/v1/chat",
                data=form_data,
                files=httpx_files,
                headers=headers,
                timeout=self._timeout
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                "[OrchestratorClient.call_chat_multipart] Response received",
                orchestrator=orchestrator.value,
                session_id=session_id,
                status=result.get("status", "unknown")
            )
            return result
            
        except httpx.HTTPError as e:
            logger.error(
                "[OrchestratorClient.call_chat_multipart] HTTP error",
                orchestrator=orchestrator.value,
                session_id=session_id,
                url=f"{url}/v1/chat",
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"{orchestrator.value} orchestrator multipart error: {str(e)}")
        finally:
            await fresh_client.aclose()
    
    async def call_chat_stream_multipart(
        self,
        orchestrator: OrchestratorType,
        session_id: str,
        message: str,
        files: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        explicit_intent: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Call the /v1/chat/stream endpoint with multipart/form-data for file uploads.
        
        Yields SSE events from the child orchestrator.
        """
        logger.info(
            "[OrchestratorClient.call_chat_stream_multipart] Starting multipart stream call",
            orchestrator=orchestrator.value,
            session_id=session_id,
            file_count=len(files),
            file_names=[f["filename"] for f in files]
        )
        
        url = self.get_url(orchestrator)
        if not url:
            error_msg = f"URL not configured for {orchestrator.value} orchestrator"
            logger.error("[OrchestratorClient.call_chat_stream_multipart] URL not configured", orchestrator=orchestrator.value)
            raise ValueError(error_msg)
        
        form_data = {
            "session_id": session_id,
            "message": message or "",
        }
        
        if context:
            form_data["context"] = json.dumps(context)
        
        if history:
            form_data["history"] = json.dumps([
                {"role": h["role"], "content": h["content"]}
                for h in history
            ])
        
        if explicit_intent:
            form_data["explicit_intent"] = explicit_intent
        
        httpx_files = []
        for f in files:
            field_name = f.get("field_name", "file")
            httpx_files.append(
                (field_name, (f["filename"], f["content"], f.get("content_type", "application/octet-stream")))
            )
        
        event_count = 0
        fresh_client = self._create_fresh_client()
        try:
            headers = self._get_auth_headers(url)
            # Remove Content-Type from headers as httpx sets it for multipart
            headers.pop("Content-Type", None)
            headers.pop("Accept", None)
            
            async with fresh_client.stream(
                "POST",
                f"{url}/v1/chat/stream",
                data=form_data,
                files=httpx_files,
                headers=headers,
                timeout=self._timeout
            ) as response:
                response.raise_for_status()
                logger.debug(
                    "[OrchestratorClient.call_chat_stream_multipart] Stream connection established",
                    orchestrator=orchestrator.value,
                    session_id=session_id
                )
                
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        
                        if event_str.startswith("data: "):
                            data_str = event_str[6:].strip()
                            if data_str:
                                try:
                                    event_data = json.loads(data_str)
                                    event_data["_source_orchestrator"] = orchestrator.value
                                    event_count += 1
                                    yield event_data
                                except json.JSONDecodeError as je:
                                    logger.warning(
                                        "[OrchestratorClient.call_chat_stream_multipart] Failed to parse SSE JSON",
                                        error=str(je),
                                        raw_data=data_str[:200]
                                    )
                
                # Handle remaining buffer
                if buffer.strip().startswith("data: "):
                    data_str = buffer.strip()[6:]
                    if data_str:
                        try:
                            event_data = json.loads(data_str)
                            event_data["_source_orchestrator"] = orchestrator.value
                            event_count += 1
                            yield event_data
                        except json.JSONDecodeError:
                            pass
                
                logger.info(
                    "[OrchestratorClient.call_chat_stream_multipart] Stream completed",
                    orchestrator=orchestrator.value,
                    session_id=session_id,
                    total_events=event_count
                )
            
            # Close client after successful completion
            await fresh_client.aclose()
                            
        except httpx.HTTPError as e:
            await fresh_client.aclose()
            logger.error(
                "[OrchestratorClient.call_chat_stream_multipart] Stream HTTP error",
                orchestrator=orchestrator.value,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"{orchestrator.value} orchestrator stream error: {str(e)}")

    def get_capabilities(self, orchestrator: OrchestratorType) -> Dict[str, Any]:
        """Get capabilities of a child orchestrator."""
        logger.debug("[OrchestratorClient.get_capabilities] Getting capabilities", orchestrator=orchestrator.value)
        if orchestrator == OrchestratorType.PLANNING:
            caps = {
                **OrchestratorCapabilities.PLANNING_ORCHESTRATOR,
                "url": settings.get_planning_orchestrator_url()
            }
            logger.debug("[OrchestratorClient.get_capabilities] Planning capabilities retrieved", capabilities=caps)
            return caps
        elif orchestrator == OrchestratorType.TEST:
            caps = {
                **OrchestratorCapabilities.TEST_ORCHESTRATOR,
                "url": settings.get_test_orchestrator_url()
            }
            logger.debug("[OrchestratorClient.get_capabilities] Test capabilities retrieved", capabilities=caps)
            return caps
        elif orchestrator == OrchestratorType.COMMON_INTEGRATION:
            caps = {
                **OrchestratorCapabilities.COMMON_INTEGRATION_ORCHESTRATOR,
                "url": settings.get_common_integration_orchestrator_url()
            }
            logger.debug("[OrchestratorClient.get_capabilities] Common Integration capabilities retrieved", capabilities=caps)
            return caps
        logger.debug("[OrchestratorClient.get_capabilities] Unknown orchestrator, returning empty", orchestrator=orchestrator.value)
        return {}
    
    def get_all_capabilities(self) -> List[Dict[str, Any]]:
        """Get capabilities of all child orchestrators."""
        logger.debug("[OrchestratorClient.get_all_capabilities] Retrieving all capabilities")
        caps = [
            self.get_capabilities(OrchestratorType.PLANNING),
            self.get_capabilities(OrchestratorType.TEST),
            self.get_capabilities(OrchestratorType.COMMON_INTEGRATION),
        ]
        logger.debug("[OrchestratorClient.get_all_capabilities] All capabilities retrieved", count=len(caps))
        return caps


# Global client instance
_client_instance: Optional[OrchestratorClient] = None


def get_orchestrator_client() -> OrchestratorClient:
    """Get the global orchestrator client instance."""
    global _client_instance
    if _client_instance is None:
        logger.info("[get_orchestrator_client] Creating new OrchestratorClient instance")
        _client_instance = OrchestratorClient()
    return _client_instance
