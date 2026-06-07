from __future__ import annotations

from collections import defaultdict
from typing import Any


class ConversationMemory:
    def __init__(self) -> None:
        self._messages: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._context: dict[str, dict[str, Any]] = defaultdict(dict)

    async def add_user_message(self, session_id: str, content: str) -> None:
        self._messages[session_id].append({"role": "user", "content": content})

    async def add_assistant_message(self, session_id: str, content: str) -> None:
        self._messages[session_id].append({"role": "assistant", "content": content})

    async def get_conversation_history(self, session_id: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._messages.get(session_id, [])[-limit:]

    async def set_last_agent(self, session_id: str, agent: str) -> None:
        self._context[session_id]["last_agent"] = agent

    async def get_last_agent(self, session_id: str) -> str | None:
        return self._context.get(session_id, {}).get("last_agent")

    async def set_suggested_actions(self, session_id: str, actions: list[dict[str, Any]]) -> None:
        self._context[session_id]["suggested_actions"] = actions

    async def get_suggested_actions(self, session_id: str) -> list[dict[str, Any]]:
        return self._context.get(session_id, {}).get("suggested_actions", [])


_memory: ConversationMemory | None = None


def get_memory() -> ConversationMemory:
    global _memory
    if _memory is None:
        _memory = ConversationMemory()
    return _memory