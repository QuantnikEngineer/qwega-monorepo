"""
Refresh Token Manager
=====================
Handles refresh token rotation with family-based reuse detection.
If a previously-rotated token is reused, the entire family is revoked
(potential token theft).
"""

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.session import Session

logger = get_logger(__name__)


class RefreshManager:
    """Family-based refresh token rotation with reuse detection."""

    @staticmethod
    async def validate_and_rotate(
        db: AsyncSession,
        refresh_token: str,
    ) -> dict | None:
        """
        Validate a refresh token and prepare for rotation.
        Returns { session, user_id, token_family_id } if valid.
        Returns None if token is invalid/expired/revoked.
        If token reuse detected, revokes entire family and returns None.
        """
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        stmt = select(Session).where(Session.refresh_token_hash == token_hash)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            logger.warning("[refresh] Token not found")
            return None

        if session.revoked_at is not None:
            logger.error(
                "[refresh] TOKEN REUSE DETECTED — revoking family",
                family_id=session.token_family_id,
                session_id=session.id,
            )
            await RefreshManager._revoke_family(db, session.token_family_id, "token_reuse")
            return None

        if session.rotated_at is not None:
            logger.error(
                "[refresh] Rotated token reused — revoking family",
                family_id=session.token_family_id,
            )
            await RefreshManager._revoke_family(db, session.token_family_id, "token_reuse")
            return None

        now_utc = datetime.now(timezone.utc)
        expires = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
        if expires < now_utc:
            logger.info("[refresh] Token expired", session_id=session.id)
            session.revoked_at = datetime.now(timezone.utc)
            session.revoked_reason = "expired"
            return None

        session.rotated_at = datetime.now(timezone.utc)

        return {
            "session": session,
            "user_id": session.user_id,
            "token_family_id": session.token_family_id,
        }

    @staticmethod
    async def _revoke_family(db: AsyncSession, family_id: str, reason: str) -> None:
        """Revoke all sessions in a token family."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Session)
            .where(
                Session.token_family_id == family_id,
                Session.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_reason=reason)
        )
        await db.execute(stmt)
        logger.info("[refresh] Family revoked", family_id=family_id, reason=reason)

    @staticmethod
    async def revoke_user_sessions(db: AsyncSession, user_id: str, reason: str = "logout") -> None:
        """Revoke all active sessions for a user (e.g., on logout or password change)."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(Session)
            .where(
                Session.user_id == user_id,
                Session.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_reason=reason)
        )
        await db.execute(stmt)
        logger.info("[refresh] All user sessions revoked", user_id=user_id, reason=reason)

