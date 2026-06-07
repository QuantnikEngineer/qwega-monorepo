"""
Conversation Memory Module
==========================
Manages conversation history and context for each session.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class SessionMemory:
    """Complete memory state for a session."""
    session_id: str
    messages: List[ConversationMessage] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    last_intent: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "entities": self.entities,
            "context": self.context,
            "last_intent": self.last_intent,
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
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"])
        )


class MemoryStore(ABC):
    """Abstract base class for memory storage backends."""
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionMemory]:
        pass
    
    @abstractmethod
    async def save_session(self, memory: SessionMemory) -> None:
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        pass
    
    @abstractmethod
    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        pass


class InMemoryStore(MemoryStore):
    """In-memory storage for development and testing."""
    
    def __init__(self):
        logger.info("[conversation_memory.py] InMemoryStore.__init__: ENTRY")
        self._sessions: Dict[str, SessionMemory] = {}
        logger.info("[conversation_memory.py] InMemoryStore.__init__: EXIT")
    
    async def get_session(self, session_id: str) -> Optional[SessionMemory]:
        logger.info("[conversation_memory.py] InMemoryStore.get_session: ENTRY", session_id=session_id)
        session = self._sessions.get(session_id)
        logger.info("[conversation_memory.py] InMemoryStore.get_session: EXIT", session_id=session_id, found=session is not None)
        return session
    
    async def save_session(self, memory: SessionMemory) -> None:
        logger.info("[conversation_memory.py] InMemoryStore.save_session: ENTRY", session_id=memory.session_id)
        memory.last_activity = datetime.utcnow()
        self._sessions[memory.session_id] = memory
        logger.info(
            "[conversation_memory.py] InMemoryStore.save_session: EXIT",
            session_id=memory.session_id,
            messages_count=len(memory.messages),
            entities_count=len(memory.entities)
        )
    
    async def delete_session(self, session_id: str) -> None:
        logger.info("[conversation_memory.py] InMemoryStore.delete_session: ENTRY", session_id=session_id)
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("[conversation_memory.py] InMemoryStore.delete_session: EXIT - deleted", session_id=session_id)
        else:
            logger.info("[conversation_memory.py] InMemoryStore.delete_session: EXIT - not found", session_id=session_id)
    
    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        logger.info("[conversation_memory.py] InMemoryStore.add_message: ENTRY", session_id=session_id, role=role)
        session = await self.get_session(session_id)
        if not session:
            session = SessionMemory(session_id=session_id)
            logger.debug("Created new session for message", session_id=session_id)
        
        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        session.messages.append(message)
        
        if len(session.messages) > settings.conversation_memory_limit:
            session.messages = session.messages[-settings.conversation_memory_limit:]
            logger.debug("Trimmed session messages to limit", session_id=session_id, limit=settings.conversation_memory_limit)
        
        await self.save_session(session)
        logger.info("[conversation_memory.py] InMemoryStore.add_message: EXIT", session_id=session_id)
    
    async def cleanup_expired(self) -> int:
        """Remove expired sessions."""
        logger.info("[conversation_memory.py] InMemoryStore.cleanup_expired: ENTRY")
        expiry_time = datetime.utcnow() - timedelta(hours=settings.session_ttl_hours)
        expired = [
            sid for sid, mem in self._sessions.items()
            if mem.last_activity < expiry_time
        ]
        for sid in expired:
            del self._sessions[sid]
        logger.info("[conversation_memory.py] InMemoryStore.cleanup_expired: EXIT", count=len(expired))
        return len(expired)


class RedisStore(MemoryStore):
    """Redis-backed storage for production."""
    
    def __init__(self, redis_client):
        self._redis = redis_client
        self._prefix = "test_orch:session:"
        logger.info("Initialized Redis store")
    
    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"
    
    async def get_session(self, session_id: str) -> Optional[SessionMemory]:
        key = self._key(session_id)
        logger.debug("Getting session from Redis", session_id=session_id, key=key)
        data = await self._redis.get(key)
        if data:
            logger.debug("Session found in Redis", session_id=session_id)
            return SessionMemory.from_dict(json.loads(data))
        logger.debug("Session not found in Redis", session_id=session_id)
        return None
    
    async def save_session(self, memory: SessionMemory) -> None:
        memory.last_activity = datetime.utcnow()
        key = self._key(memory.session_id)
        await self._redis.setex(
            key,
            timedelta(hours=settings.session_ttl_hours),
            json.dumps(memory.to_dict())
        )
        logger.debug(
            "Saved session to Redis",
            session_id=memory.session_id,
            key=key,
            messages_count=len(memory.messages),
            ttl_hours=settings.session_ttl_hours
        )
    
    async def delete_session(self, session_id: str) -> None:
        key = self._key(session_id)
        await self._redis.delete(key)
        logger.debug("Deleted session from Redis", session_id=session_id, key=key)
    
    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        logger.debug(
            "Adding message to Redis session",
            session_id=session_id,
            role=role,
            content_preview=content[:100] if content else None,
            metadata=metadata
        )
        session = await self.get_session(session_id)
        if not session:
            session = SessionMemory(session_id=session_id)
            logger.debug("Created new session for message", session_id=session_id)
        
        message = ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        session.messages.append(message)
        
        if len(session.messages) > settings.conversation_memory_limit:
            session.messages = session.messages[-settings.conversation_memory_limit:]
            logger.debug("Trimmed session messages to limit", session_id=session_id, limit=settings.conversation_memory_limit)
        
        await self.save_session(session)


class ConversationMemory:
    """High-level conversation memory manager."""
    
    def __init__(self, store: Optional[MemoryStore] = None):
        logger.info("[conversation_memory.py] ConversationMemory.__init__: ENTRY")
        self._store = store or InMemoryStore()
        logger.info("[conversation_memory.py] ConversationMemory.__init__: EXIT")
    
    async def get_or_create_session(self, session_id: str) -> SessionMemory:
        logger.info("[conversation_memory.py] ConversationMemory.get_or_create_session: ENTRY", session_id=session_id)
        session = await self._store.get_session(session_id)
        if not session:
            session = SessionMemory(session_id=session_id)
            await self._store.save_session(session)
            logger.info("Created new session", session_id=session_id)
        logger.info("[conversation_memory.py] ConversationMemory.get_or_create_session: EXIT", session_id=session_id)
        return session
    
    async def add_user_message(
        self, 
        session_id: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        logger.info("[conversation_memory.py] ConversationMemory.add_user_message: ENTRY", session_id=session_id)
        await self._store.add_message(session_id, "user", content, metadata)
        logger.info("[conversation_memory.py] ConversationMemory.add_user_message: EXIT", session_id=session_id)
    
    async def add_assistant_message(
        self, 
        session_id: str, 
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        logger.info("[conversation_memory.py] ConversationMemory.add_assistant_message: ENTRY", session_id=session_id)
        await self._store.add_message(session_id, "assistant", content, metadata)
        logger.info("[conversation_memory.py] ConversationMemory.add_assistant_message: EXIT", session_id=session_id)
    
    async def get_conversation_history(
        self, 
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        logger.info("[conversation_memory.py] ConversationMemory.get_conversation_history: ENTRY", session_id=session_id)
        session = await self._store.get_session(session_id)
        if not session:
            logger.info("[conversation_memory.py] ConversationMemory.get_conversation_history: EXIT - no session", session_id=session_id)
            return []
        
        messages = session.messages
        if limit:
            messages = messages[-limit:]
        
        logger.info("[conversation_memory.py] ConversationMemory.get_conversation_history: EXIT", session_id=session_id, message_count=len(messages))
        return [{"role": m.role, "content": m.content} for m in messages]
    
    async def update_entities(
        self, 
        session_id: str, 
        entities: Dict[str, Any]
    ) -> None:
        logger.info("[conversation_memory.py] ConversationMemory.update_entities: ENTRY", session_id=session_id)
        session = await self.get_or_create_session(session_id)
        session.entities.update(entities)
        await self._store.save_session(session)
        logger.info("[conversation_memory.py] ConversationMemory.update_entities: EXIT", session_id=session_id, entities=list(entities.keys()))
    
    async def get_entities(self, session_id: str) -> Dict[str, Any]:
        logger.info("[conversation_memory.py] ConversationMemory.get_entities: ENTRY", session_id=session_id)
        session = await self._store.get_session(session_id)
        result = session.entities if session else {}
        logger.info("[conversation_memory.py] ConversationMemory.get_entities: EXIT", session_id=session_id, entity_count=len(result))
        return result
    
    async def update_context(
        self, 
        session_id: str, 
        context: Dict[str, Any]
    ) -> None:
        session = await self.get_or_create_session(session_id)
        session.context.update(context)
        await self._store.save_session(session)
    
    async def set_last_intent(self, session_id: str, intent: str) -> None:
        session = await self.get_or_create_session(session_id)
        session.last_intent = intent
        await self._store.save_session(session)
    
    async def get_full_context(self, session_id: str) -> Dict[str, Any]:
        session = await self._store.get_session(session_id)
        if not session:
            return {
                "history": [],
                "entities": {},
                "context": {},
                "last_intent": None
            }
        
        return {
            "history": [m.to_dict() for m in session.messages],
            "entities": session.entities,
            "context": session.context,
            "last_intent": session.last_intent
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
