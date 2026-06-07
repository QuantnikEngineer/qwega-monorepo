"""Tests for the conversation state machine and API endpoints."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.main import app, _sessions, _session_locks, MAX_MESSAGE_LENGTH
from models.brd_models import ConversationSession, ConversationStep


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    # Clean up sessions between tests
    _sessions.clear()
    _session_locks.clear()


# ── Health endpoint ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Session not found ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_session_not_found(client):
    resp = await client.post(
        "/sessions/nonexistent/chat",
        json={"message": "hello"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_session_not_found(client):
    resp = await client.get("/sessions/nonexistent/download")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_status_session_not_found(client):
    resp = await client.get("/sessions/nonexistent")
    assert resp.status_code == 404


# ── Chat message size limit ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_message_too_long(client):
    # Create a dummy session to avoid 404
    sid = "test-size-limit"
    _sessions[sid] = ConversationSession(session_id=sid)

    huge_message = "x" * (MAX_MESSAGE_LENGTH + 1)
    resp = await client.post(
        f"/sessions/{sid}/chat",
        json={"message": huge_message},
    )
    assert resp.status_code == 422  # Pydantic validation error


# ── Session step guards ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_docs_wrong_step(client):
    sid = "test-wrong-step"
    session = ConversationSession(session_id=sid, step=ConversationStep.GREETING)
    _sessions[sid] = session

    resp = await client.post(
        f"/sessions/{sid}/upload-docs",
        files=[],
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_confluence_link_wrong_mode(client):
    sid = "test-wrong-mode"
    session = ConversationSession(session_id=sid, mode="new")
    _sessions[sid] = session

    resp = await client.post(
        f"/sessions/{sid}/confluence-link",
        json={"link": "https://example.atlassian.net/wiki/spaces/X/pages/123/Title"},
    )
    assert resp.status_code == 400


# ── State machine: stuck GENERATING recovery ─────────────────────────────────

class TestStuckGeneratingRecovery:
    """Verify that a failed generation resets the step so the user isn't stuck."""

    @pytest.mark.asyncio
    async def test_generating_step_resets_on_error(self):
        """Directly test that _generate_brd resets step on failure.
        We mock the generation agent to raise an exception.
        """
        from unittest.mock import AsyncMock, patch
        from agents.conversation_agent import _generate_brd

        session = ConversationSession(
            session_id="test-stuck",
            step=ConversationStep.GENERATING,
            project_name="Test Project",
        )

        with patch(
            "agents.conversation_agent._call_generation_agent",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM timeout"),
        ):
            reply, updated = await _generate_brd(session)

        # Step should be reset to COLLECT_DOCS, not stuck at GENERATING
        assert updated.step == ConversationStep.COLLECT_DOCS
        assert updated.error == "LLM timeout"
        assert "failed" in reply.lower()


# ── Create session mode validation ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_session_invalid_mode(client):
    resp = await client.post(
        "/sessions",
        json={"mode": "invalid"},
    )
    assert resp.status_code == 400


# ── Publish without BRD ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_without_brd(client):
    sid = "test-no-brd"
    _sessions[sid] = ConversationSession(session_id=sid)

    resp = await client.post(f"/sessions/{sid}/publish")
    assert resp.status_code == 400


# ── Session status ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_status(client):
    sid = "test-status"
    _sessions[sid] = ConversationSession(
        session_id=sid,
        project_name="My Project",
        step=ConversationStep.COLLECT_DOCS,
    )

    resp = await client.get(f"/sessions/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_name"] == "My Project"
    assert data["step"] == "collect_docs"
    assert data["mode"] == "new"
