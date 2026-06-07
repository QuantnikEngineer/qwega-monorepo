"""
Conversation Memory Module
==========================
Extended memory management for SDLC orchestrator with cross-orchestrator context.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)
FILE_NAME = "conversation_memory.py"


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    routed_to: Optional[str] = None  # Which orchestrator handled this
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "routed_to": self.routed_to
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            routed_to=data.get("routed_to")
        )


@dataclass
class SessionMemory:
    """Complete memory state for a session with orchestrator routing info."""
    session_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    last_intent: Optional[str] = None
    last_orchestrator: Optional[str] = None  # Last orchestrator that handled a request
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)
    pending_confirmation: Optional[Dict[str, Any]] = None  # Intent awaiting user confirmation
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "entities": self.entities,
            "context": self.context,
            "last_intent": self.last_intent,
            "last_orchestrator": self.last_orchestrator,
            "suggested_actions": self.suggested_actions,
            "pending_confirmation": self.pending_confirmation,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMemory":
        return cls(
            session_id=data["session_id"],
            messages=[ConversationMessage.from_dict(m) for m in data.get("messages", [])],
            entities=data.get("entities", {}),
            context=data.get("context", {}),
            last_intent=data.get("last_intent"),
            last_orchestrator=data.get("last_orchestrator"),
            suggested_actions=data.get("suggested_actions", []),
            pending_confirmation=data.get("pending_confirmation"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"])
        )


class MemoryStore(ABC):
    """Abstract base class for memory storage."""
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionMemory]:
        pass
    
    @abstractmethod
    async def save_session(self, memory: SessionMemory) -> None:
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        pass


class InMemoryStore(MemoryStore):
    """In-memory storage for development."""
    
    def __init__(self):
        self._sessions: Dict[str, SessionMemory] = {}
        logger.info("Initialized in-memory store")
    
    async def get_session(self, session_id: str) -> Optional[SessionMemory]:
        return self._sessions.get(session_id)
    
    async def save_session(self, memory: SessionMemory) -> None:
        memory.last_activity = datetime.utcnow()
        self._sessions[memory.session_id] = memory
    
    async def delete_session(self, session_id: str) -> None:
        if session_id in self._sessions:
            del self._sessions[session_id]


class ConversationMemory:
    """High-level conversation memory manager with orchestrator awareness."""
    
    def __init__(self, store: Optional[MemoryStore] = None):
        self._store = store or InMemoryStore()
    
    async def get_or_create_session(self, session_id: str) -> SessionMemory:
        session = await self._store.get_session(session_id)
        if not session:
            session = SessionMemory(session_id=session_id)
            await self._store.save_session(session)
            logger.info("Created new session", session_id=session_id)
        return session
    
    async def add_user_message(
        self, 
        session_id: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        session = await self.get_or_create_session(session_id)
        message = ConversationMessage(role="user", content=content, metadata=metadata or {})
        session.messages.append(message)
        
        if len(session.messages) > settings.conversation_memory_limit:
            session.messages = session.messages[-settings.conversation_memory_limit:]
        
        await self._store.save_session(session)
    
    async def add_assistant_message(
        self, 
        session_id: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        routed_to: Optional[str] = None
    ) -> None:
        session = await self.get_or_create_session(session_id)
        message = ConversationMessage(
            role="assistant", 
            content=content, 
            metadata=metadata or {},
            routed_to=routed_to
        )
        session.messages.append(message)
        
        if len(session.messages) > settings.conversation_memory_limit:
            session.messages = session.messages[-settings.conversation_memory_limit:]
        
        await self._store.save_session(session)
    
    async def get_conversation_history(
        self, 
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        session = await self._store.get_session(session_id)
        if not session:
            return []
        
        messages = session.messages
        if limit:
            messages = messages[-limit:]
        
        return [{"role": m.role, "content": m.content, "routed_to": m.routed_to} for m in messages]
    
    async def update_entities(self, session_id: str, entities: Dict[str, Any]) -> None:
        session = await self.get_or_create_session(session_id)
        session.entities.update(entities)
        await self._store.save_session(session)
    
    async def get_entities(self, session_id: str) -> Dict[str, Any]:
        session = await self._store.get_session(session_id)
        return session.entities if session else {}
    
    async def update_context(self, session_id: str, context: Dict[str, Any]) -> None:
        session = await self.get_or_create_session(session_id)
        session.context.update(context)
        await self._store.save_session(session)
    
    async def set_last_intent(self, session_id: str, intent: str) -> None:
        session = await self.get_or_create_session(session_id)
        session.last_intent = intent
        await self._store.save_session(session)
    
    async def set_last_orchestrator(self, session_id: str, orchestrator: str) -> None:
        """Track which orchestrator last handled a request."""
        session = await self.get_or_create_session(session_id)
        session.last_orchestrator = orchestrator
        await self._store.save_session(session)
    
    async def get_last_orchestrator(self, session_id: str) -> Optional[str]:
        """Get the last orchestrator that handled a request."""
        session = await self._store.get_session(session_id)
        return session.last_orchestrator if session else None
    
    async def set_suggested_actions(
        self, 
        session_id: str, 
        actions: List[Dict[str, Any]]
    ) -> None:
        """Store suggested actions for confirmation handling."""
        session = await self.get_or_create_session(session_id)
        session.suggested_actions = actions
        await self._store.save_session(session)
    
    async def get_suggested_actions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get stored suggested actions."""
        session = await self._store.get_session(session_id)
        return session.suggested_actions if session else []
    
    async def set_pending_confirmation(
        self, 
        session_id: str, 
        confirmation_data: Optional[Dict[str, Any]]
    ) -> None:
        """Store pending confirmation for an intent that requires user confirmation."""
        logger.info(
            f"[{FILE_NAME}] set_pending_confirmation: ENTRY",
            session_id=session_id,
            has_confirmation_data=confirmation_data is not None,
            pending_intent=confirmation_data.get("intent") if confirmation_data else None
        )
        try:
            session = await self.get_or_create_session(session_id)
            session.pending_confirmation = confirmation_data
            await self._store.save_session(session)
            logger.info(
                f"[{FILE_NAME}] set_pending_confirmation: EXIT - Success",
                session_id=session_id
            )
        except Exception as e:
            logger.error(
                f"[{FILE_NAME}] set_pending_confirmation: EXIT - Error",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def get_pending_confirmation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get pending confirmation data."""
        logger.debug(
            f"[{FILE_NAME}] get_pending_confirmation: ENTRY",
            session_id=session_id
        )
        try:
            session = await self._store.get_session(session_id)
            result = session.pending_confirmation if session else None
            logger.debug(
                f"[{FILE_NAME}] get_pending_confirmation: EXIT",
                session_id=session_id,
                has_pending=result is not None
            )
            return result
        except Exception as e:
            logger.error(
                f"[{FILE_NAME}] get_pending_confirmation: EXIT - Error",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def clear_pending_confirmation(self, session_id: str) -> None:
        """Clear pending confirmation after user responds."""
        logger.info(
            f"[{FILE_NAME}] clear_pending_confirmation: ENTRY",
            session_id=session_id
        )
        try:
            session = await self._store.get_session(session_id)
            if session:
                session.pending_confirmation = None
                await self._store.save_session(session)
            logger.info(
                f"[{FILE_NAME}] clear_pending_confirmation: EXIT - Success",
                session_id=session_id
            )
        except Exception as e:
            logger.error(
                f"[{FILE_NAME}] clear_pending_confirmation: EXIT - Error",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def get_full_context(self, session_id: str) -> Dict[str, Any]:
        session = await self._store.get_session(session_id)
        if not session:
            return {
                "history": [],
                "entities": {},
                "context": {},
                "last_intent": None,
                "last_orchestrator": None,
                "suggested_actions": []
            }
        
        return {
            "history": [m.to_dict() for m in session.messages],
            "entities": session.entities,
            "context": session.context,
            "last_intent": session.last_intent,
            "last_orchestrator": session.last_orchestrator,
            "suggested_actions": session.suggested_actions,
            "pending_confirmation": session.pending_confirmation
        }
    
    async def clear_session(self, session_id: str) -> None:
        await self._store.delete_session(session_id)
        logger.info("Cleared session", session_id=session_id)


_memory_instance: Optional[ConversationMemory] = None


def get_memory() -> ConversationMemory:
    """Get the global memory instance."""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ConversationMemory()
    return _memory_instance
