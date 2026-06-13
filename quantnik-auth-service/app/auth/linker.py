"""
User Linker (Layer 2)
=====================
Resolves a verified external identity (from AuthProvider) to an internal User.
Loads user roles, capabilities, and auth method metadata.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.base import UserIdentity
from app.models.auth_method import AuthMethodType
from app.models.role import UserRole
from app.models.user import User


class UserLinker:
    """Resolve external identity to internal User with roles and capabilities."""

    @staticmethod
    async def resolve(db: AsyncSession, identity: UserIdentity) -> dict:
        """
        Given a verified identity, load the full internal user profile.
        Returns dict with: user, roles, capabilities, must_change_password, auth_method_id.
        Raises ValueError if user not found.
        """
        stmt = (
            select(User)
            .where(User.normalized_email == identity.email)
            .options(
                selectinload(User.user_roles).selectinload(UserRole.role),
                selectinload(User.auth_methods),
            )
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError(f"No internal user for identity: {identity.email}")

        roles: list[str] = []
        capabilities: set[str] = set()
        for user_role in user.user_roles:
            role = user_role.role
            if role:
                roles.append(role.name)
                if role.capabilities:
                    capabilities.update(role.capabilities)

        must_change_password = False
        auth_method_id = None
        for auth_method in user.auth_methods:
            if auth_method.method_type == AuthMethodType.PASSWORD and auth_method.disabled_at is None:
                must_change_password = auth_method.must_change_password
                auth_method_id = auth_method.id
                break

        return {
            "user": user,
            "roles": roles,
            "capabilities": sorted(capabilities),
            "must_change_password": must_change_password,
            "auth_method_id": auth_method_id,
        }

