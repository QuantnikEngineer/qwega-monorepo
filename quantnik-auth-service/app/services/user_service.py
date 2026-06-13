"""
User Service
============
User CRUD operations and admin user provisioning.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.refresh import RefreshManager
from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.models.auth_method import AuthMethod, AuthMethodType
from app.models.org import Org
from app.models.role import Role, UserRole
from app.models.user import User, UserStatus
from app.services.activation_service import ActivationService
from app.services.password_service import PasswordService
from app.services.role_service import RoleService

logger = get_logger(__name__)


class UserService:
    """User management operations."""

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """Find user by normalized email."""
        stmt = select(User).where(User.normalized_email == email.strip().lower())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> User | None:
        """Find user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(
        db: AsyncSession,
        email: str,
        display_name: str,
        temporary_password: str,
        role_name: str = "developer",
        created_by: str | None = None,
    ) -> User:
        """
        Admin-provisioned user creation.
        Creates user + password auth method + role assignment.
        """
        email_normalized = email.strip().lower()

        if not email_normalized.endswith("@wipro.com"):
            raise ValueError("Must be a @wipro.com email address")

        existing_user = await UserService.get_by_email(db, email_normalized)
        if existing_user:
            raise ValueError("A user with this email already exists")

        PasswordService.check_policy_or_raise(temporary_password)

        org_result = await db.execute(select(Org).limit(1))
        org = org_result.scalar_one_or_none()
        if not org:
            raise ValueError("No organization found — seed data may be missing")

        user = User(
            normalized_email=email_normalized,
            display_name=display_name,
            org_id=org.id,
            status=UserStatus.ACTIVE,
            created_by=created_by,
        )
        db.add(user)
        await db.flush()

        auth_method = AuthMethod(
            user_id=user.id,
            method_type=AuthMethodType.PASSWORD,
            provider="local",
            credential_hash=PasswordService.hash_password(temporary_password),
            is_primary=True,
            must_change_password=True,
        )
        db.add(auth_method)

        role_result = await db.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if role:
            user_role = UserRole(
                user_id=user.id,
                role_id=role.id,
                scope_type="org",
                scope_id=org.id,
                source="admin_assigned",
                assigned_by=created_by,
            )
            db.add(user_role)

        await db.flush()
        logger.info("[user] Created", email=email_normalized, role=role_name, created_by=created_by)
        return user

    @staticmethod
    async def update_last_login(db: AsyncSession, user: User) -> None:
        """Update user's last_login_at timestamp."""
        now = datetime.now(timezone.utc)
        user.last_login_at = now
        user.updated_at = now

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user_id: str,
        new_password_hash: str,
    ) -> None:
        """Update password hash and clear must_change_password flag."""
        stmt = select(AuthMethod).where(
            AuthMethod.user_id == user_id,
            AuthMethod.method_type == AuthMethodType.PASSWORD,
            AuthMethod.disabled_at.is_(None),
        )
        result = await db.execute(stmt)
        auth_method = result.scalar_one_or_none()
        if not auth_method:
            raise ValueError("No password auth method found")

        auth_method.credential_hash = new_password_hash
        auth_method.must_change_password = False
        auth_method.last_used_at = datetime.now(timezone.utc)
        logger.info("[user] Password changed", user_id=user_id)

    # ------------------------------------------------------------------
    # Phase 4 — Activation-based provisioning and admin CRUD
    # ------------------------------------------------------------------

    @staticmethod
    async def create_user_with_activation(
        db: AsyncSession,
        email: str,
        display_name: str,
        role_assignments: list[dict],
        created_by: str,
    ) -> tuple[User, str]:
        """
        Create user with activation token (D-09).

        Unlike ``create_user`` (which sets a temp password), this creates a
        *pending* user with **no** password auth method.  The user sets their
        password during activation.

        Returns ``(user, raw_activation_token)``.
        """
        email_normalized = email.strip().lower()

        if not email_normalized.endswith("@wipro.com"):
            raise ValueError("Must be a @wipro.com email address")

        existing = await UserService.get_by_email(db, email_normalized)
        if existing:
            raise ValueError("A user with this email already exists")

        # Single default org (RBAC-10)
        org_result = await db.execute(select(Org).limit(1))
        org = org_result.scalar_one_or_none()
        if not org:
            raise ValueError("No organization found — seed data may be missing")

        user = User(
            normalized_email=email_normalized,
            display_name=display_name,
            org_id=org.id,
            status=UserStatus.PENDING,
            created_by=created_by,
        )
        db.add(user)
        await db.flush()

        # Assign roles
        for ra in role_assignments:
            role = await RoleService.get_role_by_name(db, ra["role_name"])
            if not role:
                logger.warning("[user] Role not found, skipping", role_name=ra["role_name"])
                continue

            scope_type = ra.get("scope_type", "org")
            scope_id = ra.get("scope_id") or org.id

            # Phase 3: below-PM roles require project scope
            if role.name in ("po_sm_ba", "developer", "tester", "mlops"):
                if scope_type != "project" or not scope_id or scope_id == org.id:
                    raise ValueError(
                        f"Role '{role.name}' requires project-level scoping "
                        f"(scope_type='project' with a valid project scope_id)"
                    )

            user_role = UserRole(
                user_id=user.id,
                role_id=role.id,
                scope_type=scope_type,
                scope_id=scope_id,
                source="admin_assigned",
                assigned_by=created_by,
            )
            db.add(user_role)

        await db.flush()

        # Generate activation token
        raw_token = await ActivationService.create_token(db, user.id, created_by=created_by)

        logger.info(
            "[user] Created with activation",
            email=email_normalized,
            roles=[r["role_name"] for r in role_assignments],
            created_by=created_by,
        )
        return user, raw_token

    @staticmethod
    async def list_users(db: AsyncSession, org_id: str | None = None, created_by: str | None = None) -> list[User]:
        """List all users, optionally filtered by org and/or creator."""
        stmt = select(User).order_by(User.display_name)
        if org_id:
            stmt = stmt.where(User.org_id == org_id)
        if created_by:
            stmt = stmt.where(User.created_by == created_by)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: str,
        display_name: str | None = None,
        role_assignments: list[dict] | None = None,
        status: str | None = None,
        requesting_user_id: str | None = None,
    ) -> User:
        """Update user details and/or role assignments."""
        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")

        if display_name is not None:
            user.display_name = display_name

        # QUANTNIK-1921: track previous status so we can detect a deactivation →
        # active transition (a "reactivation") and force the user through a
        # password reset on next login.
        previous_status = user.status
        reactivated = False

        if status is not None:
            try:
                new_status = UserStatus(status)
            except ValueError:
                raise ValueError(f"Invalid status: {status}")
            if (
                previous_status == UserStatus.DEACTIVATED
                and new_status == UserStatus.ACTIVE
            ):
                reactivated = True
            user.status = new_status

        user.updated_at = datetime.now(timezone.utc)

        if reactivated:
            # Flip must_change_password on the active password auth method so
            # the next login forces the user through the password change flow,
            # mirroring the first-login mechanism (auth_method.must_change_password).
            am_stmt = select(AuthMethod).where(
                AuthMethod.user_id == user_id,
                AuthMethod.method_type == AuthMethodType.PASSWORD,
                AuthMethod.disabled_at.is_(None),
            )
            am_result = await db.execute(am_stmt)
            auth_method = am_result.scalar_one_or_none()
            if auth_method is not None:
                auth_method.must_change_password = True

            db.add(AuditLog(
                user_id=requesting_user_id,
                action="user_reactivated",
                resource_type="user",
                resource_id=user_id,
                details={
                    "email": user.normalized_email,
                    "must_change_password": True,
                    "reason": "reactivated",
                },
            ))
            logger.info(
                "[user] Reactivated — password reset required",
                user_id=user_id,
                by=requesting_user_id,
            )

        if role_assignments is not None:
            # Replace all existing role assignments
            existing = await RoleService.get_user_roles(db, user_id)
            for er in existing:
                await db.delete(er)
            await db.flush()

            org_result = await db.execute(select(Org).limit(1))
            org = org_result.scalar_one_or_none()

            for ra in role_assignments:
                role = await RoleService.get_role_by_name(db, ra["role_name"])
                if not role:
                    logger.warning("[user] Role not found, skipping", role_name=ra["role_name"])
                    continue

                scope_type = ra.get("scope_type", "org")
                scope_id = ra.get("scope_id") or (org.id if org else None)

                # Phase 3: below-PM roles require project scope
                if role.name in ("po_sm_ba", "developer", "tester", "mlops"):
                    if scope_type != "project" or not scope_id or scope_id == (org.id if org else None):
                        raise ValueError(
                            f"Role '{role.name}' requires project-level scoping "
                            f"(scope_type='project' with a valid project scope_id)"
                        )

                user_role = UserRole(
                    user_id=user.id,
                    role_id=role.id,
                    scope_type=scope_type,
                    scope_id=scope_id,
                    source="admin_assigned",
                    assigned_by=requesting_user_id,
                )
                db.add(user_role)

        await db.flush()
        logger.info("[user] Updated", user_id=user_id, by=requesting_user_id)
        return user

    @staticmethod
    async def deactivate_user(
        db: AsyncSession,
        user_id: str,
        requesting_user_id: str,
    ) -> User:
        """
        Deactivate a user (D-27 / D-28 safety checks).

        - Cannot deactivate yourself.
        - Cannot deactivate the last superadmin.
        """
        if user_id == requesting_user_id:
            raise ValueError("Cannot deactivate your own account")

        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")

        # D-28: prevent deactivating the last superadmin
        user_roles = await RoleService.get_user_roles(db, user_id)
        superadmin_role = await RoleService.get_role_by_name(db, "superadmin")
        is_superadmin = superadmin_role and any(
            ur for ur in user_roles
            if ur.role_id == superadmin_role.id and ur.scope_type == "platform"
        )
        if is_superadmin:
            # Check if there are other platform-scoped superadmins
            from sqlalchemy import func

            count_result = await db.execute(
                select(func.count(UserRole.id)).where(
                    UserRole.role_id == superadmin_role.id,
                    UserRole.scope_type == "platform",
                    UserRole.user_id != user_id,
                )
            )
            other_superadmins = count_result.scalar() or 0
            if other_superadmins == 0:
                raise ValueError("Cannot deactivate the last superadmin")

        user.status = UserStatus.DEACTIVATED
        user.updated_at = datetime.now(timezone.utc)

        # QUANTNIK-1921: revoke all active refresh sessions immediately so the
        # deactivated user cannot rotate into a fresh access token.
        await RefreshManager.revoke_user_sessions(db, user_id, reason="deactivated")

        db.add(AuditLog(
            user_id=requesting_user_id,
            action="user_deactivated",
            resource_type="user",
            resource_id=user_id,
            details={
                "email": user.normalized_email,
                "sessions_revoked": True,
                "reason": "deactivated",
            },
        ))

        await db.flush()
        logger.info("[user] Deactivated", user_id=user_id, by=requesting_user_id)
        return user

    @staticmethod
    async def delete_user(
        db: AsyncSession,
        user_id: str,
        requesting_user_id: str,
    ) -> dict:
        """
        Permanently delete a user with same safety checks as deactivate.

        - Cannot delete yourself.
        - Cannot delete the last superadmin.
        - Cascades to auth_methods, sessions, user_roles, activation_tokens.
        - Audit log entries are preserved (nullable FK).
        """
        if user_id == requesting_user_id:
            raise ValueError("Cannot delete your own account")

        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")

        # Same D-28 safety check as deactivate
        user_roles = await RoleService.get_user_roles(db, user_id)
        superadmin_role = await RoleService.get_role_by_name(db, "superadmin")
        is_superadmin = superadmin_role and any(
            ur for ur in user_roles
            if ur.role_id == superadmin_role.id and ur.scope_type == "platform"
        )
        if is_superadmin:
            from sqlalchemy import func

            count_result = await db.execute(
                select(func.count(UserRole.id)).where(
                    UserRole.role_id == superadmin_role.id,
                    UserRole.scope_type == "platform",
                    UserRole.user_id != user_id,
                )
            )
            other_superadmins = count_result.scalar() or 0
            if other_superadmins == 0:
                raise ValueError("Cannot delete the last superadmin")

        summary = {"id": user.id, "email": user.normalized_email, "name": user.display_name}

        # Explicitly delete dependent records (ORM cascade may SET NULL instead of DELETE)
        from app.models.auth_method import AuthMethod
        from app.models.session import Session as AuthSession
        from app.models.activation_token import ActivationToken

        await db.execute(select(UserRole).where(UserRole.user_id == user_id))
        for ur in list(user.user_roles):
            await db.delete(ur)
        await db.execute(
            select(AuthMethod).where(AuthMethod.user_id == user_id)
        )
        for am in list(user.auth_methods):
            await db.delete(am)
        for sess in list(user.sessions):
            await db.delete(sess)
        # Activation tokens
        token_result = await db.execute(
            select(ActivationToken).where(ActivationToken.user_id == user_id)
        )
        for token in token_result.scalars().all():
            await db.delete(token)
        # Nullify audit_log references (preserve audit trail)
        from app.models.audit import AuditLog
        await db.execute(
            select(AuditLog).where(AuditLog.user_id == user_id)
        )
        from sqlalchemy import update
        await db.execute(
            update(AuditLog).where(AuditLog.user_id == user_id).values(user_id=None)
        )
        # Nullify created_by self-references
        await db.execute(
            update(User).where(User.created_by == user_id).values(created_by=None)
        )

        await db.delete(user)
        await db.flush()
        logger.info("[user] Permanently deleted", user_id=user_id, by=requesting_user_id)
        return summary

    @staticmethod
    async def admin_reset_password(
        db: AsyncSession,
        user_id: str,
        created_by: str,
    ) -> str:
        """
        Admin-initiated password reset.

        Disables the current password auth method, sets the user status back
        to PENDING, and returns a new activation token.
        """
        user = await UserService.get_by_id(db, user_id)
        if not user:
            raise ValueError("User not found")

        # Disable current password auth method
        stmt = select(AuthMethod).where(
            AuthMethod.user_id == user_id,
            AuthMethod.method_type == AuthMethodType.PASSWORD,
            AuthMethod.disabled_at.is_(None),
        )
        result = await db.execute(stmt)
        auth_method = result.scalar_one_or_none()
        if auth_method:
            auth_method.disabled_at = datetime.now(timezone.utc)

        # Set user back to pending
        user.status = UserStatus.PENDING
        user.updated_at = datetime.now(timezone.utc)

        # Generate new activation token
        raw_token = await ActivationService.create_token(db, user_id, created_by=created_by)
        logger.info("[user] Admin password reset", user_id=user_id, by=created_by)
        return raw_token

