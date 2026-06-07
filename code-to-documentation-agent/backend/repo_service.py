"""
Repository Service - Handles interaction with external repository APIs
"""
import httpx
import logging
import os
from typing import List, Dict, Any, Optional
from models import RepoListResponse, RepoChunksResponse

logger = logging.getLogger(__name__)

class RepositoryService:
    """Service to interact with external repository APIs"""
    
    def __init__(self, base_url: str | None = None):
        """
        Initialize the repository service.
        
        URL Resolution Priority:
        1. Explicit base_url parameter (highest priority)
        2. RAG_SERVICE_URL environment variable
        3. BUILDAI_BACKEND_API_URL + '/rag'
        4. Hardcoded default: https://demobuildai-agents.waip.wiprocms.com/rag
        
        Args:
            base_url: Optional explicit base URL override
        """
        if base_url:
            self.base_url = base_url.rstrip("/")
            logger.info(f"Using explicit RAG service URL: {self.base_url}")
        else:
            # Production: Use CODE_CONTEXT_URL env var
            code_context_url = os.getenv("CODE_CONTEXT_URL")
            if code_context_url:
                self.base_url = code_context_url.rstrip("/")
                logger.info(f"Using production RAG service URL: {self.base_url}")
            else:
                self.base_url = None
                logger.warning("CODE_CONTEXT_URL environment variable is not configured")
        
        self.timeout = 30.0
        # SSL verification configuration - can be overridden via environment variable
        # Set VERIFY_SSL=true in environment to enable SSL verification
        verify_ssl_env = os.getenv("VERIFY_SSL", "false").lower()
        self.verify_ssl = verify_ssl_env in ["true", "1", "yes", "on"]
        
        if not self.verify_ssl:
            logger.warning("SSL verification is disabled for repository service. Set VERIFY_SSL=true to enable.")
    
    async def list_repositories(self) -> RepoListResponse:
        """
        Fetch list of all repositories from the external API
        
        Returns:
            RepoListResponse with list of repositories or error
        """
        # Check if Code Context is configured
        if not self.base_url:
            logger.warning("Code Context is not configured for this project")
            return RepoListResponse(
                success=False,
                repos=[],
                error="Code Context is not configured for this project."
            )
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl) as client:
                response = await client.get(f"{self.base_url}/list_repo_contexts")
                response.raise_for_status()
                
                data = response.json()
                
                # Handle different response formats
                repos = []
                if isinstance(data, list):
                    repos = data
                elif isinstance(data, dict):
                    # Check for 'repositories' key (your API format)
                    repos = data.get("repositories", data.get("repos", []))
                

                # Filter out repositories with empty or missing repository_url
                filtered_repositories = []
                for repo in repos:
                    repo_url = repo.get("repository_url", "").strip()
                    if repo_url:  # Only include repositories with non-empty URLs
                        filtered_repositories.append(repo)
                    else:
                        logger.info(f"Skipping repository '{repo.get('title', 'Unknown')}' (repo_id: {repo.get('repo_id', 'Unknown')}) - empty repository URL")
                

                # Transform to frontend-friendly format
                formatted_repos = []
                for repo in filtered_repositories:
                    formatted_repos.append({
                        "id": repo.get("repo_id"),
                        "name": repo.get("repository_url", "").split("/")[-1] or repo.get("repo_id"),
                        "description": repo.get("description") or f"{repo.get('total_files', 0)} files, {repo.get('total_chunks', 0)} chunks",
                        "language": ", ".join(repo.get("file_types", [])[:3]) if repo.get("file_types") else None,
                        "updated_at": f"{repo.get('upload_date', '')} {repo.get('upload_time', '')}",
                        "size": repo.get("total_chunks", 0),
                        "repository_url": repo.get("repository_url"),
                        "branch": repo.get("branch"),
                        "total_files": repo.get("total_files", 0),
                        "total_chunks": repo.get("total_chunks", 0),
                        "file_types": repo.get("file_types", []),
                        "project_id": repo.get("project_id")  # Include project_id for filtering
                    })
                
                logger.info(f"Successfully fetched {len(formatted_repos)} repositories")
                
                return RepoListResponse(
                    success=True,
                    repos=formatted_repos,
                    error=None
                )
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching repositories: {e}")
            return RepoListResponse(
                success=False,
                repos=[],
                error=f"HTTP {e.response.status_code}: {str(e)}"
            )
        except httpx.RequestError as e:
            logger.error(f"Request error fetching repositories: {e}")
            return RepoListResponse(
                success=False,
                repos=[],
                error=f"Connection error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching repositories: {e}")
            return RepoListResponse(
                success=False,
                repos=[],
                error=f"Unexpected error: {str(e)}"
            )
    
    async def retrieve_repo_chunks(self, repo_id: str) -> RepoChunksResponse:
        """
        Retrieve code chunks for a specific repository
        
        Args:
            repo_id: Repository ID to retrieve chunks for
            
        Returns:
            RepoChunksResponse with chunks or error
        """
        # Check if Code Context is configured
        if not self.base_url:
            logger.warning("Code Context is not configured for this project")
            return RepoChunksResponse(
                success=False,
                chunks=[],
                error="Code Context is not configured for this project."
            )
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=self.verify_ssl) as client:
                response = await client.get(
                    f"{self.base_url}/retrieve_repo_chunks",
                    params={"repo_id": repo_id}
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Handle your API's response format
                chunks = []
                
                if isinstance(data, list):
                    chunks = data
                elif isinstance(data, dict):
                    # Check if response has 'files' key (your API format)
                    if "files" in data:
                        files_dict = data["files"]
                        # Extract all chunks from all files
                        for filename, file_data in files_dict.items():
                            if isinstance(file_data, dict) and "chunks" in file_data:
                                for chunk in file_data["chunks"]:
                                    # Add file context to each chunk
                                    chunk_with_context = {
                                        "file_path": chunk.get("file_path", filename),
                                        "filename": chunk.get("filename", filename),
                                        "content": chunk.get("content", chunk.get("text", "")),
                                        "chunk_id": chunk.get("chunk_id"),
                                        "chunk_index": chunk.get("chunk_index"),
                                        "file_extension": chunk.get("file_extension"),
                                        "chunk_method": chunk.get("chunk_method"),
                                        "size": chunk.get("size"),
                                        "type": "code"
                                    }
                                    chunks.append(chunk_with_context)
                    else:
                        # Try other common keys
                        chunks = data.get("chunks", data.get("data", []))
                
                logger.info(f"Successfully fetched {len(chunks)} chunks for repo {repo_id}")
                
                return RepoChunksResponse(
                    success=True,
                    repo_id=repo_id,
                    chunks=chunks,
                    error=None
                )
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching chunks for repo {repo_id}: {e}")
            return RepoChunksResponse(
                success=False,
                repo_id=repo_id,
                chunks=[],
                error=f"HTTP {e.response.status_code}: {str(e)}"
            )
        except httpx.RequestError as e:
            logger.error(f"Request error fetching chunks for repo {repo_id}: {e}")
            return RepoChunksResponse(
                success=False,
                repo_id=repo_id,
                chunks=[],
                error=f"Connection error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching chunks for repo {repo_id}: {e}")
            return RepoChunksResponse(
                success=False,
                repo_id=repo_id,
                chunks=[],
                error=f"Unexpected error: {str(e)}"
            )

# Create singleton instance
repo_service = RepositoryService()

