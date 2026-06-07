"""
Conversation Memory
===================
Simple in-memory conversation state management.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

FILE_NAME = "conversation_memory.py"


class ConversationMemory:
    """
    In-memory conversation state management.
    
    For production, this should be replaced with Redis or similar.
    """
    
    def __init__(self):
        logger.info(f"[{FILE_NAME}] ConversationMemory.__init__: ENTRY")
        self._sessions: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "history": [],
            "entities": {},
            "last_intent": None,
            "suggested_actions": [],
            "context": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        self._memory_limit = settings.conversation_memory_limit
        self._ttl_hours = settings.session_ttl_hours
        logger.info(f"[{FILE_NAME}] ConversationMemory.__init__: EXIT")
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a message to conversation history."""
        logger.debug(
            f"[{FILE_NAME}] add_message: ENTRY",
            session_id=session_id,
            role=role,
            content_length=len(content)
        )
        
        session = self._sessions[session_id]
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        session["history"].append(message)
        session["updated_at"] = datetime.utcnow()
        
        if len(session["history"]) > self._memory_limit:
            session["history"] = session["history"][-self._memory_limit:]
        
        logger.debug(
            f"[{FILE_NAME}] add_message: EXIT",
            session_id=session_id,
            history_length=len(session["history"])
        )
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get conversation history."""
        logger.debug(f"[{FILE_NAME}] get_conversation_history: ENTRY", session_id=session_id, limit=limit)
        
        session = self._sessions[session_id]
        history = session["history"]
        
        if limit:
            history = history[-limit:]
        
        logger.debug(
            f"[{FILE_NAME}] get_conversation_history: EXIT",
            session_id=session_id,
            history_length=len(history)
        )
        return history
    
    async def set_entities(self, session_id: str, entities: Dict[str, Any]) -> None:
        """Update session entities."""
        logger.debug(f"[{FILE_NAME}] set_entities: ENTRY", session_id=session_id, entity_keys=list(entities.keys()))
        
        session = self._sessions[session_id]
        session["entities"].update(entities)
        session["updated_at"] = datetime.utcnow()
        
        logger.debug(f"[{FILE_NAME}] set_entities: EXIT", session_id=session_id)
    
    async def get_entities(self, session_id: str) -> Dict[str, Any]:
        """Get session entities."""
        logger.debug(f"[{FILE_NAME}] get_entities: ENTRY", session_id=session_id)
        
        entities = self._sessions[session_id]["entities"]
        
        logger.debug(f"[{FILE_NAME}] get_entities: EXIT", session_id=session_id, entity_keys=list(entities.keys()))
        return entities
    
    async def set_last_intent(self, session_id: str, intent: str) -> None:
        """Set the last classified intent."""
        logger.debug(f"[{FILE_NAME}] set_last_intent: ENTRY", session_id=session_id, intent=intent)
        
        session = self._sessions[session_id]
        session["last_intent"] = intent
        session["updated_at"] = datetime.utcnow()
        
        logger.debug(f"[{FILE_NAME}] set_last_intent: EXIT", session_id=session_id)
    
    async def get_last_intent(self, session_id: str) -> Optional[str]:
        """Get the last classified intent."""
        logger.debug(f"[{FILE_NAME}] get_last_intent: ENTRY", session_id=session_id)
        
        intent = self._sessions[session_id]["last_intent"]
        
        logger.debug(f"[{FILE_NAME}] get_last_intent: EXIT", session_id=session_id, intent=intent)
        return intent
    
    async def set_suggested_actions(self, session_id: str, actions: List[Dict[str, Any]]) -> None:
        """Set suggested actions."""
        logger.debug(
            f"[{FILE_NAME}] set_suggested_actions: ENTRY",
            session_id=session_id,
            action_count=len(actions)
        )
        
        session = self._sessions[session_id]
        session["suggested_actions"] = actions
        session["updated_at"] = datetime.utcnow()
        
        logger.debug(f"[{FILE_NAME}] set_suggested_actions: EXIT", session_id=session_id)
    
    async def get_suggested_actions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get suggested actions."""
        logger.debug(f"[{FILE_NAME}] get_suggested_actions: ENTRY", session_id=session_id)
        
        actions = self._sessions[session_id]["suggested_actions"]
        
        logger.debug(f"[{FILE_NAME}] get_suggested_actions: EXIT", session_id=session_id, action_count=len(actions))
        return actions
    
    async def set_context(self, session_id: str, context: Dict[str, Any]) -> None:
        """Set session context."""
        logger.debug(f"[{FILE_NAME}] set_context: ENTRY", session_id=session_id, context_keys=list(context.keys()))
        
        session = self._sessions[session_id]
        session["context"].update(context)
        session["updated_at"] = datetime.utcnow()
        
        logger.debug(f"[{FILE_NAME}] set_context: EXIT", session_id=session_id)
    
    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get session context."""
        logger.debug(f"[{FILE_NAME}] get_context: ENTRY", session_id=session_id)
        
        context = self._sessions[session_id]["context"]
        
        logger.debug(f"[{FILE_NAME}] get_context: EXIT", session_id=session_id, context_keys=list(context.keys()))
        return context
    
    async def get_full_context(self, session_id: str) -> Dict[str, Any]:
        """Get full session state."""
        logger.debug(f"[{FILE_NAME}] get_full_context: ENTRY", session_id=session_id)
        
        session = self._sessions[session_id]
        
        result = {
            "history": session["history"],
            "entities": session["entities"],
            "last_intent": session["last_intent"],
            "suggested_actions": session["suggested_actions"],
            "context": session["context"]
        }
        
        logger.debug(f"[{FILE_NAME}] get_full_context: EXIT", session_id=session_id)
        return result
    
    async def clear_session(self, session_id: str) -> None:
        """Clear session data."""
        logger.info(f"[{FILE_NAME}] clear_session: ENTRY", session_id=session_id)
        
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        logger.info(f"[{FILE_NAME}] clear_session: EXIT", session_id=session_id)
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        logger.info(f"[{FILE_NAME}] cleanup_expired_sessions: ENTRY")
        
        cutoff = datetime.utcnow() - timedelta(hours=self._ttl_hours)
        expired = []
        
        for session_id, session in self._sessions.items():
            if session["updated_at"] < cutoff:
                expired.append(session_id)
        
        for session_id in expired:
            del self._sessions[session_id]
        
        logger.info(f"[{FILE_NAME}] cleanup_expired_sessions: EXIT", expired_count=len(expired))
        return len(expired)


_memory_instance: Optional[ConversationMemory] = None


def get_memory() -> ConversationMemory:
    """Get the global memory instance."""
    global _memory_instance
    if _memory_instance is None:
        logger.info(f"[{FILE_NAME}] get_memory: Creating new ConversationMemory instance")
        _memory_instance = ConversationMemory()
    return _memory_instance
