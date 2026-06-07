"""
Server-side conversation memory manager.

Stores conversation turns in Postgres keyed by conversation_id.
Auto-generates conversation_id when not provided.
Summarises older turns via LLM after a configurable threshold to
compress token usage while retaining context.
"""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.conversation import Conversation


MAX_FULL_TURNS = 10        # keep last N turns verbatim
SUMMARY_TRIGGER = 10       # summarise after this many turns


class ConversationManager:

    async def get_or_create(
        self,
        db: AsyncSession,
        conversation_id: str | None,
        project_name: str,
    ) -> tuple[str, Conversation]:
        """
        Returns (conversation_id, Conversation).
        Creates a new row if conversation_id is None or not found.
        """
        if conversation_id:
            result = await db.execute(
                select(Conversation).where(Conversation.conversation_id == conversation_id)
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conversation_id, conv

        # New conversation
        conv_id = conversation_id or str(uuid.uuid4())
        conv = Conversation(
            conversation_id=conv_id,
            project_name=project_name,
            turns=[],
            turn_count=0,
        )
        db.add(conv)
        await db.flush()
        logger.info("conversation_created", conversation_id=conv_id)
        return conv_id, conv

    async def load_history(
        self,
        db: AsyncSession,
        conversation_id: str,
    ) -> list[dict]:
        """
        Returns the conversation context for the LLM prompt:
        summary (if exists) + last N full turns.
        """
        result = await db.execute(
            select(Conversation).where(Conversation.conversation_id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return []

        turns = conv.turns or []
        recent = turns[-MAX_FULL_TURNS:]

        context = []
        if conv.summary:
            context.append({"role": "system", "content": f"Previous conversation summary: {conv.summary}"})
        context.extend(recent)
        return context

    async def add_turn(
        self,
        db: AsyncSession,
        conversation_id: str,
        role: str,
        content: str,
    ) -> None:
        """Appends a turn and triggers summarisation if needed."""
        result = await db.execute(
            select(Conversation).where(Conversation.conversation_id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return

        turns = list(conv.turns or [])
        turns.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        conv.turns = turns
        conv.turn_count = len(turns)
        await db.commit()

    async def maybe_summarise(
        self,
        db: AsyncSession,
        conversation_id: str,
        summarise_fn,
    ) -> None:
        """
        If turn count exceeds threshold, summarise older turns and
        keep only the recent window.
        ``summarise_fn`` is an async callable(text) -> str.
        """
        result = await db.execute(
            select(Conversation).where(Conversation.conversation_id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return

        turns = conv.turns or []
        if len(turns) <= SUMMARY_TRIGGER:
            return

        # Summarise everything except the last MAX_FULL_TURNS
        older = turns[:-MAX_FULL_TURNS]
        older_text = "\n".join(
            f"{t.get('role', 'unknown')}: {t.get('content', '')}" for t in older
        )

        existing_summary = conv.summary or ""
        text_to_summarise = (
            f"Previous summary: {existing_summary}\n\nNew turns:\n{older_text}"
            if existing_summary
            else older_text
        )

        try:
            summary = await summarise_fn(text_to_summarise)
            conv.summary = summary
            conv.turns = turns[-MAX_FULL_TURNS:]
            conv.turn_count = len(conv.turns)
            await db.commit()
            logger.info("conversation_summarised", conversation_id=conversation_id)
        except Exception as e:
            logger.warning("conversation_summary_failed", error=str(e))
