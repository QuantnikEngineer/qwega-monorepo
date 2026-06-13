"""
Activation Service
==================
Activation token lifecycle: creation, validation, redemption.
Tokens are stored as SHA-256 hashes (T-04-09); raw tokens exist only in the
admin-shared activation URL.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.activation_token import ActivationToken

logger = get_logger(__name__)


class ActivationService:
    """Single-use activation token management."""

    TOKEN_EXPIRY_HOURS = 48

    @staticmethod
    async def create_token(db: AsyncSession, user_id: str, created_by: str | None = None) -> str:
        """
        Generate an activation token for *user_id*.

        Returns the RAW (unhashed) token — the caller puts this into the
        activation URL that the admin shares with the user.
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        activation = ActivationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ActivationService.TOKEN_EXPIRY_HOURS),
            created_by=created_by,
        )
        db.add(activation)
        await db.flush()
        logger.info("[activation] Token created", user_id=user_id, created_by=created_by)
        return raw_token

    @staticmethod
    async def validate_token(db: AsyncSession, raw_token: str) -> ActivationToken | None:
        """
        Validate token: exists, not used, not expired.

        Returns the token record or ``None``.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        result = await db.execute(
            select(ActivationToken).where(
                ActivationToken.token_hash == token_hash,
                ActivationToken.used_at.is_(None),
            )
        )
        token = result.scalar_one_or_none()
        if not token:
            return None
        expires = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return None
        return token

    @staticmethod
    async def redeem_token(db: AsyncSession, raw_token: str) -> ActivationToken | None:
        """
        Atomically mark token as used.

        Returns the token record if successful, ``None`` if already used or expired.
        The atomic ``UPDATE … WHERE used_at IS NULL`` prevents double-redemption (T-04-09).
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        now = datetime.now(timezone.utc)
        result = await db.execute(
            update(ActivationToken)
            .where(
                ActivationToken.token_hash == token_hash,
                ActivationToken.used_at.is_(None),
                ActivationToken.expires_at > now,
            )
            .values(used_at=now)
            .returning(ActivationToken.id, ActivationToken.user_id)
        )
        row = result.first()
        if not row:
            return None
        return await db.get(ActivationToken, row[0])
