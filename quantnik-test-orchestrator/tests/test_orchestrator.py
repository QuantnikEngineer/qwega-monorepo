"""
Basic tests for the Quantnik Test Orchestrator.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.requests import IntentType
from app.memory.conversation_memory import ConversationMemory, InMemoryStore
from app.tools.agent_tools import AgentToolRegistry


client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_check(self):
        """Test the health endpoint returns success."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "version" in data
    
    def test_root_endpoint(self):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "docs" in data


class TestChatEndpoint:
    """Test the chat endpoint."""
    
    def test_simple_chat(self):
        """Test simple chat with auto-generated session."""
        response = client.post(
            "/v1/chat/simple",
            json={"message": "Hello, what can you do?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "message" in data
    
    def test_chat_with_session(self):
        """Test chat with explicit session ID."""
        response = client.post(
            "/v1/chat",
            json={
                "session_id": "test_session_123",
                "message": "Generate test scenarios"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test_session_123"


class TestLegacyEndpoint:
    """Test the legacy analyze endpoint."""
    
    def test_legacy_analyze(self):
        """Test legacy endpoint for backward compatibility."""
        response = client.post(
            "/api/v1/prompt/analyze",
            json={
                "query_text": "Generate test scenarios",
                "nextagentflow": "confirmedUserStoryToTestScenario"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data


class TestMemoryEndpoints:
    """Test memory management endpoints."""
    
    def test_get_session_memory(self):
        """Test getting session memory."""
        client.post(
            "/v1/chat",
            json={
                "session_id": "memory_test_session",
                "message": "Test message"
            }
        )
        
        response = client.get("/v1/memory/memory_test_session")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "memory_test_session"
    
    def test_clear_session_memory(self):
        """Test clearing session memory."""
        response = client.delete("/v1/memory/test_session_to_clear")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cleared"


class TestConversationMemory:
    """Test the conversation memory module."""
    
    @pytest.mark.asyncio
    async def test_in_memory_store(self):
        """Test in-memory store operations."""
        store = InMemoryStore()
        
        await store.add_message("test_session", "user", "Hello")
        
        session = await store.get_session("test_session")
        assert session is not None
        assert len(session.messages) == 1
        assert session.messages[0].content == "Hello"
    
    @pytest.mark.asyncio
    async def test_conversation_memory(self):
        """Test conversation memory wrapper."""
        memory = ConversationMemory()
        
        await memory.add_user_message("conv_test", "User message")
        await memory.add_assistant_message("conv_test", "Assistant response")
        
        history = await memory.get_conversation_history("conv_test")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"
    
    @pytest.mark.asyncio
    async def test_entity_tracking(self):
        """Test entity tracking in memory."""
        memory = ConversationMemory()
        
        await memory.update_entities("entity_test", {
            "user_stories": ["US-001", "US-002"],
            "test_framework": "Selenium"
        })
        
        entities = await memory.get_entities("entity_test")
        assert entities["user_stories"] == ["US-001", "US-002"]
        assert entities["test_framework"] == "Selenium"


class TestIntentClassification:
    """Test intent classification (with fallback)."""
    
    def test_keyword_fallback(self):
        """Test keyword-based fallback classification."""
        from app.agents.intent_classifier import IntentClassifier
        
        classifier = IntentClassifier()
        classifier._llm_type = "fallback"
        
        # Test test cases intent
        result = classifier._classify_with_keywords("Generate test cases")
        assert result.intent == IntentType.GENERATE_TEST_CASES
        
        # Test test script intent
        result = classifier._classify_with_keywords("Create test scripts")
        assert result.intent == IntentType.GENERATE_TEST_SCRIPT
        
        # Test unknown intent
        result = classifier._classify_with_keywords("Random text")
        assert result.intent == IntentType.UNKNOWN
        assert result.requires_clarification


class FakeResponse:
    """Minimal HTTP response stub for agent tool tests."""

    def __init__(self, payload):
        self.status_code = 202
        self.headers = {}
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class FakeAsyncClient:
    """Capture outgoing POST URLs without making real HTTP requests."""

    last_post_url = None
    last_payload = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, json):
        FakeAsyncClient.last_post_url = url
        FakeAsyncClient.last_payload = json
        return FakeResponse({
            "job_id": "job-123",
            "poll_url": "/v1/jobs/job-123",
            "total": 1,
            "message": "submitted",
            "test_cases": []
        })


class TestTestCasesEndpointRouting:
    """Test scenario-agent endpoint selection for greenfield and brownfield."""

    @pytest.mark.asyncio
    async def test_call_test_cases_agent_uses_brownfield_endpoint_from_project_type(self, monkeypatch):
        monkeypatch.setattr("app.tools.agent_tools.httpx.AsyncClient", FakeAsyncClient)
        monkeypatch.setattr("app.tools.agent_tools.settings.get_test_scenario_agent_url", lambda: "https://scenario-agent")

        registry = AgentToolRegistry(timeout=5)

        await registry.call_test_cases_agent({
            "context": {
                "project_type": "brownfield",
                "user_stories": "As a user, I want to edit an existing order"
            },
            "entities": {}
        })

        assert FakeAsyncClient.last_post_url == "https://scenario-agent/v1/generate-test-cases/bulk/brownfield"

    @pytest.mark.asyncio
    async def test_call_test_cases_agent_uses_brownfield_endpoint_from_script_generation_type(self, monkeypatch):
        monkeypatch.setattr("app.tools.agent_tools.httpx.AsyncClient", FakeAsyncClient)
        monkeypatch.setattr("app.tools.agent_tools.settings.get_test_scenario_agent_url", lambda: "https://scenario-agent")

        registry = AgentToolRegistry(timeout=5)

        await registry.call_test_cases_agent({
            "context": {
                "script_generation_type": "Brownfield",
                "user_stories": "As a user, I want to update an existing customer profile"
            },
            "entities": {}
        })

        assert FakeAsyncClient.last_post_url == "https://scenario-agent/v1/generate-test-cases/bulk/brownfield"

    @pytest.mark.asyncio
    async def test_call_test_cases_agent_defaults_to_greenfield_endpoint(self, monkeypatch):
        monkeypatch.setattr("app.tools.agent_tools.httpx.AsyncClient", FakeAsyncClient)
        monkeypatch.setattr("app.tools.agent_tools.settings.get_test_scenario_agent_url", lambda: "https://scenario-agent")

        registry = AgentToolRegistry(timeout=5)

        await registry.call_test_cases_agent({
            "context": {
                "user_stories": "As a user, I want to register with email and password"
            },
            "entities": {}
        })

        assert FakeAsyncClient.last_post_url == "https://scenario-agent/v1/generate-test-cases/bulk"
