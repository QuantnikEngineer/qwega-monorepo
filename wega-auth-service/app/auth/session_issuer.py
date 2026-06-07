"""
Session Issuer (Layer 3)
========================
Creates JWT access + refresh token pairs and persists session records
for family-based token rotation.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_manager import JWTManager
from app.core.config import settings
from app.core.logging import get_logger
from app.models.session import Session
from app.models.user import User

logger = get_logger(__name__)


class SessionIssuer:
    """Create access + refresh token pairs with session tracking."""

    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager

    async def issue(
        self,
        db: AsyncSession,
        user: User,
        roles: list[str],
        capabilities: list[str],
        device_info: str | None = None,
        ip_address: str | None = None,
        token_family_id: str | None = None,
        # Scoped claims (D-17) — optional for backward compat during rolling deploy
        platform_capabilities: list[str] | None = None,
        org_capabilities: list[str] | None = None,
        project_roles: dict[str, list[str]] | None = None,
        self_capabilities: list[str] | None = None,
        # Phase 5: allowed agent IDs per role
        allowed_agents: list[str] | None = None,
        # Per-project agent access (Phase 2 delegation)
        project_allowed_agents: dict[str, list[str]] | None = None,
        # Project context
        project_id: str | None = None,
        project_ids: list[str] | None = None,
    ) -> dict:
        """
        Issue a new access + refresh token pair.
        If token_family_id is provided, this is a rotation (not a new login).
        Scoped capability params are forwarded to JWTManager for D-17 claims.
        """
        access_token = self.jwt_manager.create_access_token(
            sub=user.id,
            email=user.normalized_email,
            display_name=user.display_name,
            roles=roles,
            capabilities=capabilities,
            org_id=user.org_id,
            project_id=project_id,
            project_ids=project_ids,
            platform_capabilities=platform_capabilities,
            org_capabilities=org_capabilities,
            project_roles=project_roles,
            self_capabilities=self_capabilities,
            allowed_agents=allowed_agents,
            project_allowed_agents=project_allowed_agents,
        )

        refresh_token = self.jwt_manager.create_refresh_token()
        refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        family_id = token_family_id or str(uuid.uuid4())

        session = Session(
            user_id=user.id,
            token_family_id=family_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days),
            device_info=device_info,
            ip_address=ip_address,
        )
        db.add(session)
        await db.flush()

        expires_in = settings.jwt_access_token_expire_minutes * 60
        logger.info(
            "[session] Token pair issued",
            user_id=user.id,
            family_id=family_id,
            is_rotation=token_family_id is not None,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "token_family_id": family_id,
            "session_id": session.id,
        }

