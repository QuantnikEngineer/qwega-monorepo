"""
Request Models
==============
Pydantic models for SDLC Orchestrator API requests.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class OrchestratorType(str, Enum):
    """Types of child orchestrators."""
    PLANNING = "planning"
    TEST = "test"
    COMMON_INTEGRATION = "common_integration"
    UNKNOWN = "unknown"


class IntentType(str, Enum):
    """All supported intent types across all orchestrators."""
    # Planning orchestrator intents
    CREATE_BRD = "create_brd"
    CREATE_USER_STORY = "create_user_story"
    VALIDATE_USER_STORY = "validate_user_story"
    SAVE_VALIDATED_USER_STORIES = "save_validated_user_stories"
    CREATE_USER_MANUAL = "create_user_manual"
    BRD_SUMMARY = "brd_summary"
    
    # Test orchestrator intents
    GENERATE_TEST_CASES = "generate_test_cases"
    GENERATE_TEST_SCRIPT = "generate_test_script"
    GENERATE_TEST_DATA = "generate_test_data"
    
    # Common Integration orchestrator intents
    CONTEXT_ENRICH_UPLOAD = "context_enrich_upload"
    CONTEXT_ENRICH_INGEST = "context_enrich_ingest"
    CONTEXT_ENRICH_FEEDBACK = "context_enrich_feedback"
    CONTEXT_ENRICH_QUERY = "context_enrich_query"
    CONTEXT_ENRICH_LIST_DOCUMENTS = "context_enrich_list_documents"
    
    # Common intents
    GENERAL_QUESTION = "general_question"
    CONFIRMATION = "confirmation"
    UNKNOWN = "unknown"


# Map intents to orchestrator types
INTENT_TO_ORCHESTRATOR: Dict[IntentType, OrchestratorType] = {
    IntentType.CREATE_BRD: OrchestratorType.PLANNING,
    IntentType.CREATE_USER_STORY: OrchestratorType.PLANNING,
    IntentType.VALIDATE_USER_STORY: OrchestratorType.PLANNING,
    IntentType.SAVE_VALIDATED_USER_STORIES: OrchestratorType.PLANNING,
    IntentType.CREATE_USER_MANUAL: OrchestratorType.PLANNING,
    IntentType.BRD_SUMMARY: OrchestratorType.PLANNING,
    IntentType.GENERATE_TEST_CASES: OrchestratorType.TEST,
    IntentType.GENERATE_TEST_SCRIPT: OrchestratorType.TEST,
    IntentType.GENERATE_TEST_DATA: OrchestratorType.TEST,
    IntentType.CONTEXT_ENRICH_UPLOAD: OrchestratorType.COMMON_INTEGRATION,
    IntentType.CONTEXT_ENRICH_INGEST: OrchestratorType.COMMON_INTEGRATION,
    IntentType.CONTEXT_ENRICH_FEEDBACK: OrchestratorType.COMMON_INTEGRATION,
    IntentType.CONTEXT_ENRICH_QUERY: OrchestratorType.COMMON_INTEGRATION,
    IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS: OrchestratorType.COMMON_INTEGRATION,
    IntentType.GENERAL_QUESTION: OrchestratorType.UNKNOWN,
    IntentType.CONFIRMATION: OrchestratorType.UNKNOWN,
    IntentType.UNKNOWN: OrchestratorType.UNKNOWN,
}


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class ChatRequest(BaseModel):
    """
    Main chat request model for SDLC Orchestrator.
    
    Frontend React/TSX applications should send requests to this endpoint.
    The orchestrator will intelligently route to the appropriate child orchestrator.
    """
    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., description="User's natural language message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Previous messages")
    explicit_intent: Optional[str] = Field(default=None, description="Explicit intent override")
    target_orchestrator: Optional[str] = Field(default=None, description="Force specific orchestrator")


class LegacyAnalyzeRequest(BaseModel):
    """Legacy request model for backward compatibility."""
    query_text: str = Field(..., description="User query text")
    nextagentflow: Optional[str] = Field(default=None)
    brd_document_uri: Optional[str] = Field(default=None)
    create_user_story_text: Optional[Union[str, List[Any]]] = Field(default=None)
    scenario_types: Optional[str] = Field(default=None)
    test_scenarios: Optional[str] = Field(default=None)
    test_cases: Optional[str] = Field(default=None)
    framework_type: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default=None)
    script_generation_type: Optional[str] = Field(default=None)


class CapabilitiesRequest(BaseModel):
    """Request to get orchestrator capabilities."""
    orchestrator: Optional[str] = Field(default=None, description="Specific orchestrator or 'all'")
