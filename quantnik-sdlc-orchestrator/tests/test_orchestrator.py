"""
Tests for SDLC Orchestrator
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.requests import IntentType, OrchestratorType
from app.memory.conversation_memory import ConversationMemory, InMemoryStore


client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "child_orchestrators" in data
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "capabilities" in data


class TestCapabilitiesEndpoint:
    """Test capabilities endpoint."""
    
    def test_get_capabilities(self):
        """Test getting all capabilities."""
        response = client.get("/v1/capabilities")
        assert response.status_code == 200
        data = response.json()
        assert "orchestrators" in data
        assert len(data["orchestrators"]) == 2
        
        # Check planning orchestrator
        planning = next((o for o in data["orchestrators"] if o["name"] == "planning"), None)
        assert planning is not None
        assert "create_brd" in planning["intents"]
        
        # Check test orchestrator
        test = next((o for o in data["orchestrators"] if o["name"] == "test"), None)
        assert test is not None
        assert "generate_test_cases" in test["intents"]


class TestChatEndpoint:
    """Test chat endpoint."""
    
    def test_simple_chat(self):
        """Test simple chat."""
        response = client.post(
            "/v1/chat/simple",
            json={"message": "What can you do?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "message" in data
    
    def test_chat_with_session(self):
        """Test chat with explicit session."""
        response = client.post(
            "/v1/chat",
            json={
                "session_id": "test_session_123",
                "message": "Help me understand the workflow"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test_session_123"


class TestIntentClassification:
    """Test intent classification and routing."""
    
    def test_planning_intent_keywords(self):
        """Test planning intent keywords."""
        from app.agents.intent_classifier import IntentClassifier
        
        classifier = IntentClassifier()
        classifier._llm_type = "fallback"
        
        # BRD creation
        result = classifier._classify_with_keywords("Create a BRD from transcript", {})
        assert result.intent == IntentType.CREATE_BRD
        assert result.target_orchestrator == OrchestratorType.PLANNING
        
        # User story
        result = classifier._classify_with_keywords("Generate user stories from the BRD", {})
        assert result.intent == IntentType.CREATE_USER_STORY
        assert result.target_orchestrator == OrchestratorType.PLANNING
    
    def test_test_intent_keywords(self):
        """Test test intent keywords."""
        from app.agents.intent_classifier import IntentClassifier
        
        classifier = IntentClassifier()
        classifier._llm_type = "fallback"
        
        # Test cases
        result = classifier._classify_with_keywords("Generate test cases", {})
        assert result.intent == IntentType.GENERATE_TEST_CASES
        assert result.target_orchestrator == OrchestratorType.TEST
        
        # Test scripts
        result = classifier._classify_with_keywords("Create selenium test scripts", {})
        assert result.intent == IntentType.GENERATE_TEST_SCRIPT
        assert result.target_orchestrator == OrchestratorType.TEST
    
    def test_confirmation_intent(self):
        """Test confirmation intent."""
        from app.agents.intent_classifier import IntentClassifier
        
        classifier = IntentClassifier()
        classifier._llm_type = "fallback"
        
        for word in ["yes", "ok", "proceed", "continue"]:
            result = classifier._classify_with_keywords(word, {"last_orchestrator": "planning"})
            assert result.intent == IntentType.CONFIRMATION


class TestConversationMemory:
    """Test conversation memory."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_tracking(self):
        """Test orchestrator tracking in memory."""
        memory = ConversationMemory()
        
        await memory.set_last_orchestrator("test_sess", "planning")
        last_orch = await memory.get_last_orchestrator("test_sess")
        assert last_orch == "planning"
    
    @pytest.mark.asyncio
    async def test_suggested_actions(self):
        """Test suggested actions storage."""
        memory = ConversationMemory()
        
        actions = [
            {"action": "Create BRD", "intent": "create_brd", "orchestrator": "planning"},
            {"action": "Generate tests", "intent": "generate_test_cases", "orchestrator": "test"}
        ]
        
        await memory.set_suggested_actions("test_sess", actions)
        stored = await memory.get_suggested_actions("test_sess")
        
        assert len(stored) == 2
        assert stored[0]["orchestrator"] == "planning"


class TestLegacyEndpoint:
    """Test legacy endpoint."""
    
    def test_legacy_analyze(self):
        """Test legacy analyze endpoint."""
        response = client.post(
            "/api/v1/prompt/analyze",
            json={
                "query_text": "Create a BRD",
                "nextagentflow": "confirmedCreateBrd"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
