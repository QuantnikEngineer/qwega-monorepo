"""
Request Models
==============
Pydantic models for API request validation - Test Orchestrator specific.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class IntentType(str, Enum):
    """Supported intent types for the test orchestrator."""
    GENERATE_TEST_CASES = "generate_test_cases"
    GENERATE_TEST_SCRIPT = "generate_test_script"
    GENERATE_TEST_DATA = "generate_test_data"
    GENERAL_QUESTION = "general_question"
    CONFIRMATION = "confirmation"
    UNKNOWN = "unknown"


class ChatMessage(BaseModel):
    """A single chat message in the conversation."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class UserStoryItem(BaseModel):
    """Individual user story for test generation."""
    id: str = Field(..., description="User story ID")
    key: str = Field(..., description="Jira key (e.g., WEGA-123)")
    summary: str = Field(..., description="Story summary/title")
    description: str = Field(..., description="Full story description")


class EpicGroup(BaseModel):
    """Group of user stories under an epic."""
    epic_key: str = Field(..., description="Epic Jira key")
    epic_summary: str = Field(..., description="Epic title")
    user_stories: List[UserStoryItem] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """
    Main chat request model for test orchestrator.
    
    Example for test scenario generation:
        {
            "session_id": "sess_123",
            "message": "Generate test scenarios for user stories",
            "context": {
                "user_stories": [...]
            },
            "explicit_intent": "generate_test_cases"
        }
    """
    session_id: str = Field(..., description="Unique session identifier")
    message: str = Field(..., description="User's natural language message")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Previous messages")
    explicit_intent: Optional[str] = Field(default=None, description="Explicit intent override")


class TestScenarioRequest(BaseModel):
    """Request model for test scenario generation."""
    session_id: str = Field(..., description="Session identifier")
    user_stories: Union[List[EpicGroup], str] = Field(..., description="User stories to generate scenarios for")
    scenario_types: Optional[List[str]] = Field(default=None, description="Types of scenarios to generate")


class TestScriptRequest(BaseModel):
    """Request model for test script generation."""
    session_id: str = Field(..., description="Session identifier")
    test_cases: Union[List[Dict[str, Any]], str] = Field(..., description="Test cases to convert to scripts")
    framework_type: str = Field(..., description="Test framework (e.g., Selenium BDD)")
    language: str = Field(..., description="Programming language")
    script_generation_type: str = Field(default="Greenfield", description="Greenfield or Brownfield")


class TestDataRequest(BaseModel):
    """Request model for test data generation."""
    session_id: str = Field(..., description="Session identifier")
    test_cases: List[Dict[str, Any]] = Field(..., description="Test cases to generate data for")
    output_format: str = Field(default="json", description="Output format: json or excel")


class LegacyAnalyzeRequest(BaseModel):
    """Legacy request model for backward compatibility."""
    query_text: str = Field(..., description="User query text")
    nextagentflow: Optional[str] = Field(default=None, description="Agent flow identifier")
    create_user_story_text: Optional[Union[str, List[Any]]] = Field(default=None)
    scenario_types: Optional[List[str]] = Field(default=None)
    test_scenarios: Optional[str] = Field(default=None)
    test_case_format: Optional[str] = Field(default=None)
    test_cases: Optional[str] = Field(default=None)
    framework_type: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default=None)
    script_generation_type: Optional[str] = Field(default=None)
    input_test_text: Optional[str] = Field(default=None)
    user_story_name: Optional[str] = Field(default=None)
    instructions: Optional[str] = Field(default=None)
