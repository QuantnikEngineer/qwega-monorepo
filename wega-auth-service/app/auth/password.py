"""
Password Authenticator (Layer 1)
================================
Validates email/password credentials using argon2-cffi (NOT passlib).
CRITICAL: argon2-cffi verify() arg order is verify(hash, password) — REVERSED from passlib.
"""

import asyncio

from argon2 import PasswordHasher, exceptions as argon2_exceptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.base import AuthProvider, UserIdentity
from app.core.config import settings
from app.core.logging import get_logger
from app.models.auth_method import AuthMethod, AuthMethodType
from app.models.user import User, UserStatus

logger = get_logger(__name__)

# Limit concurrent hash operations to prevent OOM (64MB × N concurrent)
_hash_semaphore = asyncio.Semaphore(4)

password_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
    hash_len=settings.argon2_hash_len,
    salt_len=settings.argon2_salt_len,
)

# Pre-computed dummy hash for constant-time comparison when user not found
DUMMY_HASH = password_hasher.hash("dummy-password-for-timing-safety")


class PasswordAuthenticator(AuthProvider):
    """Authenticate via email + password (argon2-cffi Argon2id)."""

    async def authenticate(self, *, db: AsyncSession, email: str, password: str) -> UserIdentity:
        """
        Validate email/password. Returns UserIdentity on success.
        Raises ValueError on invalid credentials.

        SECURITY: Always performs hash comparison (even for non-existent users)
        to prevent timing attacks.
        """
        email_normalized = email.strip().lower()

        stmt = (
            select(User, AuthMethod)
            .join(AuthMethod, AuthMethod.user_id == User.id)
            .where(
                User.normalized_email == email_normalized,
                AuthMethod.method_type == AuthMethodType.PASSWORD,
                AuthMethod.disabled_at.is_(None),
            )
        )
        result = await db.execute(stmt)
        row = result.first()

        if row is None:
            async with _hash_semaphore:
                try:
                    password_hasher.verify(DUMMY_HASH, password)
                except argon2_exceptions.VerifyMismatchError:
                    pass
            logger.warning("[auth] Login attempt for non-existent user", email=email_normalized)
            raise ValueError("Invalid email or password")

        user, auth_method = row

        is_first_login_pending = (
            user.status == UserStatus.PENDING and auth_method.must_change_password
        )
        if user.status != UserStatus.ACTIVE and not is_first_login_pending:
            logger.warning("[auth] Login attempt for non-active user", email=email_normalized, status=user.status.value)
            raise ValueError("Account locked. Contact your administrator.")

        async with _hash_semaphore:
            try:
                password_hasher.verify(auth_method.credential_hash, password)
            except argon2_exceptions.VerifyMismatchError:
                logger.warning("[auth] Invalid password", email=email_normalized)
                raise ValueError("Invalid email or password")
            except argon2_exceptions.InvalidHashError:
                logger.error("[auth] Corrupted hash", email=email_normalized)
                raise ValueError("Invalid email or password")

        if password_hasher.check_needs_rehash(auth_method.credential_hash):
            auth_method.credential_hash = password_hasher.hash(password)
            logger.info("[auth] Rehashed password with updated params", email=email_normalized)

        return UserIdentity(
            provider="local",
            subject_id=email_normalized,
            email=email_normalized,
            display_name=user.display_name,
        )

