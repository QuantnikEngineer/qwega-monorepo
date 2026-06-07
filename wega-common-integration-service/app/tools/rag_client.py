"""
RAG Agent Client
================
HTTP client for communicating with the RAG Agent for context enrichment operations.
"""

from typing import Dict, Any, Optional, List, AsyncGenerator
import httpx
import certifi
import json
import asyncio
import ssl

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import (
    IntentType, SDLCPhase, FeedbackType, IngestSource
)
from app.models.responses import (
    UploadResponse, IngestResponse, FeedbackResponse, QueryResponse,
    DocumentUploadItem, IngestDocumentItem, SourceItem,
    DocumentListResponse, DocumentStatusItem
)

logger = get_logger(__name__)

FILE_NAME = "rag_client.py"


class RAGClient:
    """
    Client for calling the RAG Agent endpoints.
    
    Handles:
    - File upload (/api/v1/upload)
    - Content ingestion (/api/v1/ingest)
    - Feedback submission (/api/v1/feedback)
    - Knowledge base query (/api/v1/query)
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 2
    
    def __init__(self, timeout: int = None):
        timeout = timeout or settings.agent_call_timeout
        logger.info(f"[{FILE_NAME}] RAGClient.__init__: ENTRY", timeout=timeout)
        self._timeout = timeout
        self._base_url = settings.get_rag_agent_url()
        
        if settings.ssl_verify:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            ssl_context = False
            logger.warning(f"[{FILE_NAME}] RAGClient.__init__: SSL verification disabled")
        
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        )
        
        timeouts = httpx.Timeout(
            timeout=float(timeout),
            connect=60.0,
            read=float(timeout),
            write=60.0,
            pool=60.0
        )
        
        self._client = httpx.AsyncClient(
            timeout=timeouts,
            verify=ssl_context,
            limits=limits,
            http1=True,
            http2=False,
            follow_redirects=True
        )
        
        logger.info(f"[{FILE_NAME}] RAGClient.__init__: EXIT - Client configured", base_url=self._base_url)
    
    def _create_fresh_client(self) -> httpx.AsyncClient:
        """Create a fresh HTTP client for each request."""
        logger.debug(f"[{FILE_NAME}] _create_fresh_client: ENTRY")
        
        if settings.ssl_verify:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            ssl_context = False
        
        timeouts = httpx.Timeout(
            timeout=float(self._timeout),
            connect=60.0,
            read=float(self._timeout),
            write=60.0,
            pool=60.0
        )
        
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        )
        
        client = httpx.AsyncClient(
            timeout=timeouts,
            verify=ssl_context,
            limits=limits,
            http1=True,
            http2=False,
            follow_redirects=True
        )
        
        logger.debug(f"[{FILE_NAME}] _create_fresh_client: EXIT")
        return client
    
    async def close(self):
        """Close the HTTP client."""
        logger.info(f"[{FILE_NAME}] close: ENTRY")
        await self._client.aclose()
        logger.info(f"[{FILE_NAME}] close: EXIT")
    
    async def upload_files(
        self,
        files: List[Dict[str, Any]],
        selected_model: Optional[str] = None,
        project_name: Optional[str] = None
    ) -> UploadResponse:
        """
        Upload files to the RAG knowledge base.
        
        Args:
            files: List of file dicts with 'filename', 'content', 'content_type'
            selected_model: Optional model selection for downstream processing
            project_name: Project name — required gatekeeper for RAG API
            
        Returns:
            UploadResponse with document upload results
        """
        if not project_name:
            raise ValueError("project_name is required for /api/v1/upload")
        
        logger.info(
            f"[{FILE_NAME}] upload_files: ENTRY",
            file_count=len(files),
            file_names=[f.get("filename") for f in files],
            selected_model=selected_model,
            project_name=project_name
        )
        
        url = f"{self._base_url}/api/v1/upload"
        
        httpx_files = []
        for f in files:
            httpx_files.append(
                ("files", (f["filename"], f["content"], f.get("content_type", "application/octet-stream")))
            )
        
        form_data = {"project_name": project_name}
        
        fresh_client = self._create_fresh_client()
        try:
            headers = {"Accept": "application/json"}
            if selected_model:
                headers["X-Selected-Model"] = selected_model
            
            logger.debug(f"[{FILE_NAME}] upload_files: Sending request to {url}", project_name=project_name)
            
            response = await fresh_client.post(
                url,
                data=form_data,
                files=httpx_files,
                headers=headers,
                timeout=self._timeout
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                f"[{FILE_NAME}] upload_files: EXIT - Success",
                document_count=len(result.get("documents", [])),
                skipped_count=len(result.get("skipped", []))
            )
            
            return UploadResponse(
                documents=[
                    DocumentUploadItem(**doc) for doc in result.get("documents", [])
                ],
                skipped=result.get("skipped", []),
                message=result.get("message", "Upload completed")
            )
            
        except httpx.HTTPError as e:
            logger.error(
                f"[{FILE_NAME}] upload_files: EXIT - HTTP error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"RAG Agent upload error: {str(e)}")
        finally:
            await fresh_client.aclose()
    
    async def ingest(
        self,
        source: IngestSource,
        payload: Dict[str, Any],
        selected_model: Optional[str] = None,
        project_name: Optional[str] = None
    ) -> IngestResponse:
        """
        Ingest content from various sources into the knowledge base.
        
        Args:
            source: Ingest source type (website, sharepoint, repo, agent_output)
            payload: Source-specific payload
            selected_model: Optional model selection
            project_name: Project name — required gatekeeper for RAG API
            
        Returns:
            IngestResponse with ingestion results
        """
        if not project_name:
            raise ValueError("project_name is required for /api/v1/ingest")
        
        logger.info(
            f"[{FILE_NAME}] ingest: ENTRY",
            source=source.value,
            payload_keys=list(payload.keys()),
            selected_model=selected_model,
            project_name=project_name
        )
        
        url = f"{self._base_url}/api/v1/ingest"
        
        request_body = {"source": source.value, "project_name": project_name, **payload}
        
        # DEBUG: Log the full request details
        logger.info(
            f"[{FILE_NAME}] ingest: Request details",
            url=url,
            request_body=request_body
        )
        print(f"\n[RAG_CLIENT_DEBUG] URL: {url}", flush=True)
        print(f"[RAG_CLIENT_DEBUG] Request body: {request_body}\n", flush=True)
        
        fresh_client = self._create_fresh_client()
        try:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if selected_model:
                headers["X-Selected-Model"] = selected_model
            
            logger.info(f"[{FILE_NAME}] ingest: Sending POST to {url}", request_body=request_body)
            
            response = await fresh_client.post(
                url,
                json=request_body,
                headers=headers,
                timeout=self._timeout
            )
            
            logger.info(
                f"[{FILE_NAME}] ingest: Response received",
                status_code=response.status_code,
                response_text=response.text[:500] if response.text else None
            )
            print(f"[RAG_CLIENT_DEBUG] Response status: {response.status_code}", flush=True)
            print(f"[RAG_CLIENT_DEBUG] Response body: {response.text[:500] if response.text else 'empty'}", flush=True)
            
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                f"[{FILE_NAME}] ingest: EXIT - Success",
                source=result.get("source"),
                document_count=len(result.get("documents", []))
            )
            
            return IngestResponse(
                source=result.get("source", source.value),
                documents=[
                    IngestDocumentItem(**doc) for doc in result.get("documents", [])
                ],
                skipped=result.get("skipped", []),
                message=result.get("message", "Ingestion completed")
            )
            
        except httpx.HTTPError as e:
            logger.error(
                f"[{FILE_NAME}] ingest: EXIT - HTTP error",
                source=source.value,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"RAG Agent ingest error: {str(e)}")
        finally:
            await fresh_client.aclose()
    
    async def submit_feedback(
        self,
        feedback_type: FeedbackType,
        rating: Optional[str] = None,
        content: Optional[str] = None,
        artifact_type: Optional[str] = None,
        sdlc_phase: Optional[str] = None,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        ref_doc_id: Optional[str] = None,
        selected_model: Optional[str] = None,
        project_name: Optional[str] = None,
        query_log_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> FeedbackResponse:
        """
        Submit feedback to the RAG knowledge base.
        
        Args:
            feedback_type: Type of feedback (rating, correction, domain_preference)
            rating: Rating value for 'rating' type
            content: Feedback content
            artifact_type: Type of artifact
            sdlc_phase: SDLC phase
            agent_name: Name of agent
            session_id: Session identifier
            ref_doc_id: Reference document ID
            selected_model: Optional model selection
            
        Returns:
            FeedbackResponse with submission result
        """
        logger.info(
            f"[{FILE_NAME}] submit_feedback: ENTRY",
            feedback_type=feedback_type.value,
            has_content=content is not None,
            selected_model=selected_model
        )
        
        if not project_name:
            raise ValueError("project_name is required for /api/v1/feedback")
        
        url = f"{self._base_url}/api/v1/feedback"
        
        request_body = {"feedback_type": feedback_type.value, "project_name": project_name}
        if rating:
            request_body["rating"] = rating
        if content:
            request_body["content"] = content
        if artifact_type:
            request_body["artifact_type"] = artifact_type
        if sdlc_phase:
            request_body["sdlc_phase"] = sdlc_phase
        if agent_name:
            request_body["agent_name"] = agent_name
        if session_id:
            request_body["session_id"] = session_id
        if ref_doc_id:
            request_body["ref_doc_id"] = ref_doc_id
        if query_log_id:
            request_body["query_log_id"] = query_log_id
        if conversation_id:
            request_body["conversation_id"] = conversation_id
        
        fresh_client = self._create_fresh_client()
        try:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if selected_model:
                headers["X-Selected-Model"] = selected_model
            
            logger.debug(f"[{FILE_NAME}] submit_feedback: Sending request to {url}", request_body=request_body)
            
            response = await fresh_client.post(
                url,
                json=request_body,
                headers=headers,
                timeout=self._timeout
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                f"[{FILE_NAME}] submit_feedback: EXIT - Success",
                feedback_id=result.get("id"),
                indexed=result.get("indexed")
            )
            
            return FeedbackResponse(
                id=result.get("id", ""),
                feedback_type=result.get("feedback_type", feedback_type.value),
                indexed=result.get("indexed", False),
                message=result.get("message", "Feedback submitted"),
                status=result.get("status"),
                query_log_id=result.get("query_log_id"),
            )
            
        except httpx.HTTPError as e:
            logger.error(
                f"[{FILE_NAME}] submit_feedback: EXIT - HTTP error",
                feedback_type=feedback_type.value,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"RAG Agent feedback error: {str(e)}")
        finally:
            await fresh_client.aclose()
    
    async def query(
        self,
        query: str,
        sdlc_phase: Optional[SDLCPhase] = None,
        top_k: int = 5,
        include_sources: bool = True,
        criticality: Optional[str] = None,
        include_non_critical: bool = False,
        selected_model: Optional[str] = None,
        project_name: Optional[str] = None
    ) -> QueryResponse:
        """
        Query the RAG knowledge base.
        
        Args:
            query: Query string
            sdlc_phase: Filter by SDLC phase
            top_k: Number of results to return
            include_sources: Whether to include source references
            criticality: Filter by criticality level
            selected_model: Optional model selection
            
        Returns:
            QueryResponse with query results
        """
        logger.info(
            f"[{FILE_NAME}] query: ENTRY",
            query_length=len(query),
            query_preview=query[:50],
            sdlc_phase=sdlc_phase.value if sdlc_phase else None,
            top_k=top_k,
            selected_model=selected_model
        )
        
        # project_name is now OPTIONAL — when omitted the RAG service searches
        # the whole knowledge base and conversationally asks the user whether
        # they want to scope the next query to a specific project.
        url = f"{self._base_url}/api/v1/query"

        request_body = {
            "query": query,
            "top_k": top_k,
            "include_sources": include_sources,
            # Critical / Non-Critical scope toggle from the Wega Brain UI.
            # False (default) = critical KB only; True = also search non-critical.
            "include_non_critical": bool(include_non_critical),
        }
        if project_name:
            request_body["project_name"] = project_name
        if sdlc_phase:
            request_body["sdlc_phase"] = sdlc_phase.value
        if criticality:
            request_body["criticality"] = criticality
        
        fresh_client = self._create_fresh_client()
        try:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if selected_model:
                headers["X-Selected-Model"] = selected_model
            
            logger.debug(f"[{FILE_NAME}] query: Sending request to {url}", request_body=request_body)
            
            response = await fresh_client.post(
                url,
                json=request_body,
                headers=headers,
                timeout=self._timeout
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(
                f"[{FILE_NAME}] query: EXIT - Success",
                retrieval_count=result.get("retrieval_count", 0),
                guardrail_passed=result.get("guardrail_passed", True)
            )
            
            return QueryResponse(
                query=result.get("query", query),
                answer=result.get("answer", ""),
                sources=[
                    SourceItem(**src) for src in result.get("sources", [])
                ],
                guardrail_passed=result.get("guardrail_passed", True),
                retrieval_count=result.get("retrieval_count", 0),
                sdlc_phase=result.get("sdlc_phase"),
                query_log_id=result.get("query_log_id"),
                conversation_id=result.get("conversation_id"),
            )
            
        except httpx.HTTPError as e:
            logger.error(
                f"[{FILE_NAME}] query: EXIT - HTTP error",
                query_preview=query[:50],
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"RAG Agent query error: {str(e)}")
        finally:
            await fresh_client.aclose()
    
    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 20,
        filename: Optional[str] = None,
        project_name: Optional[str] = None
    ) -> DocumentListResponse:
        """
        List documents from the RAG knowledge base.
        
        Args:
            skip: Number of documents to skip (pagination)
            limit: Maximum number of documents to return
            filename: Optional filename filter
            
        Returns:
            DocumentListResponse with list of documents
        """
        logger.info(
            f"[{FILE_NAME}] list_documents: ENTRY",
            skip=skip,
            limit=limit,
            filename=filename
        )
        
        if not project_name:
            raise ValueError("project_name is required for /api/v1/documents")
        
        url = f"{self._base_url}/api/v1/documents"
        params = {"project_name": project_name, "skip": skip, "limit": limit}
        
        fresh_client = self._create_fresh_client()
        try:
            logger.debug(f"[{FILE_NAME}] list_documents: Sending GET to {url}", params=params)
            
            response = await fresh_client.get(
                url,
                params=params,
                timeout=self._timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            documents = [DocumentStatusItem(**doc) for doc in result.get("documents", [])]
            
            # Filter by filename if provided
            if filename:
                filename_lower = filename.lower()
                documents = [
                    doc for doc in documents
                    if filename_lower in doc.filename.lower() or filename_lower in doc.original_name.lower()
                ]
            
            logger.info(
                f"[{FILE_NAME}] list_documents: EXIT - Success",
                total=result.get("total", 0),
                returned_count=len(documents)
            )
            
            return DocumentListResponse(
                total=len(documents) if filename else result.get("total", 0),
                documents=documents
            )
            
        except httpx.HTTPError as e:
            logger.error(
                f"[{FILE_NAME}] list_documents: EXIT - HTTP error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"RAG Agent list documents error: {str(e)}")
        finally:
            await fresh_client.aclose()
    
    async def get_document(self, doc_id: str) -> DocumentStatusItem:
        """
        Get a specific document by ID.
        
        Args:
            doc_id: Document UUID
            
        Returns:
            DocumentStatusItem with document details
        """
        logger.info(f"[{FILE_NAME}] get_document: ENTRY", doc_id=doc_id)
        
        url = f"{self._base_url}/api/v1/documents/{doc_id}"
        
        fresh_client = self._create_fresh_client()
        try:
            logger.debug(f"[{FILE_NAME}] get_document: Sending GET to {url}")
            
            response = await fresh_client.get(url, timeout=self._timeout)
            response.raise_for_status()
            
            result = response.json()
            
            logger.info(
                f"[{FILE_NAME}] get_document: EXIT - Success",
                filename=result.get("filename"),
                status=result.get("status")
            )
            
            return DocumentStatusItem(**result)
            
        except httpx.HTTPError as e:
            logger.error(
                f"[{FILE_NAME}] get_document: EXIT - HTTP error",
                doc_id=doc_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"RAG Agent get document error: {str(e)}")
        finally:
            await fresh_client.aclose()
    
    async def check_health(self) -> Dict[str, Any]:
        """Check health of RAG Agent."""
        logger.debug(f"[{FILE_NAME}] check_health: ENTRY")
        
        url = f"{self._base_url}/health"
        
        fresh_client = self._create_fresh_client()
        try:
            response = await fresh_client.get(url, timeout=30)
            response.raise_for_status()
            result = response.json()
            logger.info(f"[{FILE_NAME}] check_health: EXIT - Success", status=result.get("status"))
            return result
        except Exception as e:
            logger.error(
                f"[{FILE_NAME}] check_health: EXIT - Error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {"status": "unhealthy", "error": str(e)}
        finally:
            await fresh_client.aclose()


_client_instance: Optional[RAGClient] = None


def get_rag_client() -> RAGClient:
    """Get the global RAG client instance."""
    global _client_instance
    if _client_instance is None:
        logger.info(f"[{FILE_NAME}] get_rag_client: Creating new RAGClient instance")
        _client_instance = RAGClient()
    return _client_instance
