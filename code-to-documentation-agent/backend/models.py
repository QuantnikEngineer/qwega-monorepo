from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, Union, List


# Confluence upload request/response models
class UploadToConfluenceRequest(BaseModel):
    page_title: str
    content: str
    parent_id: Optional[str] = None  # Optional parent page ID
    space_key: Optional[str] = None  # Optional space key (uses default if not provided)


class UploadToConfluenceResponse(BaseModel):
    success: bool
    page_id: Optional[str] = None
    page_title: Optional[str] = None
    space_key: Optional[str] = None
    space_name: Optional[str] = None
    web_url: Optional[str] = None
    created_date: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


# Confluence listing response models
class ConfluencePagesResponse(BaseModel):
    success: bool
    pages: List[dict] = []
    error: Optional[str] = None


class ConfluencePageContentResponse(BaseModel):
    success: bool
    page_id: Optional[str] = None
    page_title: Optional[str] = None
    content: Optional[str] = None
    space_key: Optional[str] = None
    space_name: Optional[str] = None
    last_modified_date: Optional[str] = None
    web_url: Optional[str] = None
    error: Optional[str] = None


class ExecuteRequest(BaseModel):
    # Backend fields (existing)
    user_id: str = "00000000-0000-0000-0000-0000000000a0"
    tenant_id: str = "00000000-0000-0000-0000-0000000000b0"
    session_id: str | None = None
    message: str | None = None
    api_key: str | None = None
    dataset_id: str | None = None  # optional
    files: list[str] | None = None  # optional
    
    # Frontend fields (new)
    content: Optional[str] = None
    source: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    test_case_option: Optional[str] = None  # New field for test case option
    userStoryText: Optional[str] = Field(default=None, alias="userStoryText")  # Accept both snake_case and camelCase
    conversationHistory: Optional[list[str]] = None  # Add conversation history field
    
    class Config:
        populate_by_name = True


class InitSecretsRequest(BaseModel):
    """Request model for initializing backend secrets context from JWT payload."""
    project_id: str = Field(..., description="Project ID from JWT payload")
    auth_provider: str = Field(..., description="Cloud provider from JWT payload (e.g., aws, azure, gcp)")

# For epic-based test case generation
class AgentResponse(BaseModel):
    source: str = "agent"
    content: str

# For SharePoint operations
class SharePointListRequest(BaseModel):
    site_name: str = Field(default="demo566", description="SharePoint site name")
    folder_path: str = Field(default="BuilderAI", description="Folder path in SharePoint")
    project_id: str = Field(default="", description="Project ID for fetching credentials")
    auth_provider: str = Field(default="", description="Authentication provider")

class SharePointDownloadRequest(BaseModel):
    project_id: str = Field(..., description="Project ID for fetching credentials")
    auth_provider: str = Field(..., description="Authentication provider")
    file_id: str = Field(..., description="SharePoint file ID to download")
    site_name: str = Field(default="", description="SharePoint site name")
    folder_path: str = Field(default="", description="Folder path in SharePoint")

class SharePointUploadRequest(BaseModel):
    file_content: str = Field(..., description="Content of the file to upload")
    file_name: str = Field(..., description="Name of the file")
    folder_path: str = Field(default="BuilderAI", description="Folder path in SharePoint")
    site_name: str = Field(default="demo566", description="SharePoint site name")
    project_id: str = Field(..., description="Project ID for fetching credentials")
    auth_provider: str = Field(..., description="Authentication provider")
# For user story request by epic key

# For SharePoint upload response
class SharePointUploadResponse(BaseModel):
    success: bool = Field(..., description="Whether the upload was successful")
    message: str = Field(..., description="Upload status message")
    file_id: str = Field(default="", description="SharePoint file ID")
    web_url: str = Field(default="", description="SharePoint web URL")
    file_url: str = Field(default="", description="Primary URL to open file in SharePoint viewer")
    folder_url: str = Field(default="", description="URL to open the folder containing the file")
    site_name: str = Field(default="", description="SharePoint site name used")
    folder_path: str = Field(default="", description="SharePoint folder path used")
    error: Optional[str] = Field(default=None, description="Error message if upload failed")

# For SharePoint file metadata (nested in download response)
class SharePointFileMetadata(BaseModel):
    id: Optional[str] = Field(default=None, description="SharePoint file ID")
    name: str = Field(default="download", description="File name")
    size: int = Field(default=0, description="File size in bytes")
    mime_type: str = Field(default="application/octet-stream", description="MIME type of the file")
    created_date: Optional[str] = Field(default=None, description="File creation date")
    modified_date: Optional[str] = Field(default=None, description="File last modified date")
    web_url: Optional[str] = Field(default=None, description="SharePoint web URL for the file")

# For SharePoint download response
class SharePointDownloadResponse(BaseModel):
    success: bool = Field(..., description="Whether the download was successful")
    file_metadata: Optional[SharePointFileMetadata] = Field(default=None, description="File metadata information")
    file_content_base64: Optional[str] = Field(default=None, description="Base64 encoded file content")
    content_length: int = Field(default=0, description="Content length in bytes")
    error: Optional[str] = Field(default=None, description="Error message if download failed")

# For SharePoint file item (used in listing)
class SharePointFileItem(BaseModel):
    id: str = Field(default="", description="SharePoint file/folder ID")
    name: str = Field(default="", description="File/folder name")
    isFolder: bool = Field(default=False, description="Whether this item is a folder")
    size: int = Field(default=0, description="File size in bytes (0 for folders)")
    createdDateTime: str = Field(default="", description="Creation date and time")
    lastModifiedDateTime: str = Field(default="", description="Last modification date and time")
    webUrl: str = Field(default="", description="SharePoint web URL")
    downloadUrl: str = Field(default="", description="Direct download URL")
    mimeType: str = Field(default="", description="MIME type of the file")
    createdBy: str = Field(default="Unknown", description="Display name of the creator")

# For SharePoint file listing response
class SharePointListResponse(BaseModel):
    success: bool = Field(..., description="Whether the listing was successful")
    files: List[SharePointFileItem] = Field(default=[], description="List of files and folders")
    folder_path: str = Field(default="", description="Current folder path")
    site_name: str = Field(default="", description="SharePoint site name")
    error: Optional[str] = Field(default=None, description="Error message if listing failed")

# Agent prompts (FastMCP-friendly)
class AgentPromptsRequest(BaseModel):
    agent_id: str

class AgentPromptsData(BaseModel):
    agent_id: str
    agent_name: Optional[str] = None
    prompts: List[str] = []
    total_prompts: int = 0

class AgentPromptsResponse(BaseModel):
    status: str  # "success" or "error"
    message: str
    data: AgentPromptsData

# For Code To Documentation Agent
class RepoListRequest(BaseModel):
    """Request model for listing repositories"""
    pass

class RepoListResponse(BaseModel):
    """Response model for repository listing"""
    success: bool = Field(..., description="Whether the request was successful")
    repos: List[Dict[str, Any]] = Field(default=[], description="List of repositories")
    error: Optional[str] = Field(default=None, description="Error message if request failed")

class RepoChunksRequest(BaseModel):
    """Request model for retrieving repository chunks"""
    repo_id: str = Field(..., description="Repository ID to retrieve chunks for")

class RepoChunksResponse(BaseModel):
    """Response model for repository chunks"""
    success: bool = Field(..., description="Whether the request was successful")
    repo_id: str = Field(..., description="Repository ID")
    chunks: List[Dict[str, Any]] = Field(default=[], description="Repository code chunks")
    error: Optional[str] = Field(default=None, description="Error message if request failed")

class GenerateDocumentationRequest(BaseModel):
    """Request model for generating documentation"""
    repo_id: str = Field(..., description="Repository ID to generate documentation for")
    repo_name: Optional[str] = Field(default=None, description="Repository name")
    llm_provider: str = Field(default="azure_openai", description="LLM provider to use")
    llm_model: str = Field(default="gpt-4o", description="LLM model to use")
    user_id: str = Field(default="00000000-0000-0000-0000-0000000000a0", description="User ID")
    tenant_id: str = Field(default="00000000-0000-0000-0000-0000000000b0", description="Tenant ID")
    session_id: Optional[str] = None

class GenerateDocumentationResponse(BaseModel):
    """Response model for documentation generation"""
    success: bool = Field(..., description="Whether documentation generation was successful")
    repo_id: str = Field(..., description="Repository ID")
    repo_name: Optional[str] = Field(default=None, description="Repository name")
    documentation: str = Field(..., description="Generated documentation in markdown format")
    error: Optional[str] = Field(default=None, description="Error message if generation failed")