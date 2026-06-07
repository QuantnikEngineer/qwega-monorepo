"""
User Management API
===================
Admin CRUD endpoints for user provisioning, activation-link generation,
role assignment, and safety rules (self-lock, last-SuperAdmin protection).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.refresh import RefreshManager
from app.core.config import settings
from app.core.logging import get_logger
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.audit import AuditLog
from app.models.role import Role, UserRole
from app.models.user import User, UserStatus
from app.schemas.user import (
    AdminUserCreate,
    AdminUserUpdate,
    ActivationLinkResponse,
    UserListResponse,
    UserResponse,
)
from app.services.activation_service import ActivationService
from app.services.role_service import RoleService
from app.services.user_service import UserService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


def _build_user_response(user: User) -> dict:
    """Serialize a User model into a UserResponse-compatible dict."""
    roles: list[dict] = []
    seen_roles: set[str] = set()
    for ur in (user.user_roles or []):
        role = ur.role
        role_name = role.name if role else ur.role_id
        if role_name in seen_roles:
            continue
        seen_roles.add(role_name)
        roles.append({
            "roleName": role_name,
            "scopeType": ur.scope_type,
            "scopeId": ur.scope_id,
        })
    # Collect project names from project-scoped role assignments
    projects: list[str] = []
    seen_projects: set[str] = set()
    for ur in (user.user_roles or []):
        if ur.scope_type == "project" and ur.scope_id and ur.scope_id not in seen_projects:
            seen_projects.add(ur.scope_id)
            # scope_id is the project ID — we'll resolve names in the list endpoint
            projects.append(ur.scope_id)

    return {
        "id": user.id,
        "email": user.normalized_email,
        "displayName": user.display_name,
        "status": user.status.value if isinstance(user.status, UserStatus) else str(user.status),
        "orgId": user.org_id,
        "createdAt": user.created_at.isoformat() if user.created_at else "",
        "lastLoginAt": user.last_login_at.isoformat() if user.last_login_at else None,
        "roles": roles,
        "projectIds": projects,
    }


async def _load_user_with_roles(db: AsyncSession, user_id: str) -> User | None:
    """Load a user with eagerly-loaded role assignments."""
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _role_assignment_signature(db: AsyncSession, user_id: str) -> frozenset:
    """Return a stable signature of a user's role assignments.

    The signature is a frozenset of ``(role_name, scope_type, scope_id)`` tuples,
    suitable for set-equality comparison to detect role/capability changes.
    """
    user_roles = await RoleService.get_user_roles(db, user_id)
    sig: list[tuple[str, str, str]] = []
    for ur in user_roles:
        role = await db.get(Role, ur.role_id)
        role_name = role.name if role else ur.role_id
        sig.append((role_name, ur.scope_type or "", ur.scope_id or ""))
    return frozenset(sig)


# ── Shared constants for PM role restriction ────────────────────
ALLOWED_PM_ROLES = {"po_sm_ba", "developer", "tester", "mlops"}


def _require_user_management(current_user: dict) -> list[str]:
    """Verify caller has user-management capability; return capabilities list or raise 403."""
    capabilities = current_user.get("capabilities", [])
    if "org:manage_users" not in capabilities and "team:manage_users" not in capabilities:
        raise HTTPException(
            status_code=403,
            detail="User management requires org:manage_users or team:manage_users capability",
        )
    return capabilities


# ── GET /api/users ──────────────────────────────────────────────

@router.get("")
async def list_users(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List users visible to the current user.

    SuperAdmin (org:manage_users) sees all org users.
    PM (team:manage_users only) sees users who are members of PM's projects,
    plus users the PM created directly.
    """
    capabilities = _require_user_management(current_user)

    org_id = current_user.get("org_id")

    if "org:manage_users" in capabilities:
        # SA: see all org users
        users = await UserService.list_users(db, org_id=org_id or None)
    else:
        # PM: see users who are members of PM's projects + users PM created
        from app.services.project_service import ProjectService
        pm_projects = await ProjectService.get_user_projects(
            db, user_id=current_user["user_id"], org_id=org_id,
        )
        project_ids = [p.id for p in pm_projects]

        # Users who are members of PM's projects (via project-scoped roles)
        member_user_ids: set[str] = set()
        if project_ids:
            member_stmt = (
                select(UserRole.user_id)
                .where(
                    UserRole.scope_type == "project",
                    UserRole.scope_id.in_(project_ids),
                )
                .distinct()
            )
            result = await db.execute(member_stmt)
            member_user_ids = {row[0] for row in result.all()}

        # Also include users the PM created (backward compat)
        created_users = await UserService.list_users(
            db, org_id=org_id or None, created_by=current_user["user_id"],
        )
        all_user_ids = member_user_ids | {u.id for u in created_users}

        if all_user_ids:
            stmt = (
                select(User)
                .where(User.id.in_(all_user_ids))
                .order_by(User.display_name)
            )
            result = await db.execute(stmt)
            users = list(result.scalars().all())
        else:
            users = []

    # Eagerly load role assignments for each user
    user_ids = [u.id for u in users]
    if user_ids:
        stmt = (
            select(User)
            .where(User.id.in_(user_ids))
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .order_by(User.display_name)
        )
        result = await db.execute(stmt)
        users = list(result.scalars().unique().all())

    # Resolve project IDs to names for display
    user_dicts = [_build_user_response(u) for u in users]
    all_project_ids: set[str] = set()
    for ud in user_dicts:
        all_project_ids.update(ud.get("projectIds", []))
    project_name_map: dict[str, str] = {}
    if all_project_ids:
        from app.models.project import Project
        proj_stmt = select(Project.id, Project.name).where(Project.id.in_(all_project_ids))
        proj_result = await db.execute(proj_stmt)
        project_name_map = {row[0]: row[1] for row in proj_result.all()}
    for ud in user_dicts:
        ud["projects"] = [
            {"id": pid, "name": project_name_map.get(pid, pid)}
            for pid in ud.pop("projectIds", [])
        ]

    return {
        "users": user_dicts,
        "total": len(user_dicts),
    }


# ── POST /api/users ────────────────────────────────────────────

@router.post("", status_code=201)
async def create_user(
    payload: AdminUserCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Create a user with activation link (D-09)."""
    capabilities = _require_user_management(current_user)

    # PM role restriction: can only assign PO/SM/BA, Developer, Tester, MLOps — not SuperAdmin or PM
    if "org:manage_users" not in capabilities:
        requested_roles = {ra.role_name for ra in payload.role_assignments}
        if not requested_roles.issubset(ALLOWED_PM_ROLES):
            raise HTTPException(
                status_code=403,
                detail="PM can only assign PO/SM/BA, Developer, Tester, or MLOps roles",
            )

    role_assignments = [ra.model_dump() for ra in payload.role_assignments]
    try:
        user, raw_token = await UserService.create_user_with_activation(
            db,
            email=payload.email,
            display_name=payload.display_name,
            role_assignments=role_assignments,
            created_by=current_user["user_id"],
        )
        await db.commit()
    except ValueError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise HTTPException(
                status_code=409,
                detail="A user with this email already exists",
            ) from exc
        raise HTTPException(status_code=400, detail=msg) from exc

    # Reload user with role relationships
    loaded = await _load_user_with_roles(db, user.id)
    user_data = _build_user_response(loaded or user)

    activation_url = f"{settings.frontend_url}/login?token={raw_token}"
    return JSONResponse(
        status_code=201,
        content={
            "user": user_data,
            "activation_url": activation_url,
            "expires_in_hours": ActivationService.TOKEN_EXPIRY_HOURS,
        },
    )


# ── GET /api/users/{user_id} ───────────────────────────────────

@router.get("/{user_id}")
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get single user details with role assignments."""
    user = await _load_user_with_roles(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _build_user_response(user)


# ── PUT /api/users/{user_id} ───────────────────────────────────

@router.put("/{user_id}")
async def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update user details and role assignments with safety rules."""
    capabilities = _require_user_management(current_user)
    requesting_user_id = current_user["user_id"]

    # PM enforcement: can update users in PM's projects or users PM created
    if "org:manage_users" not in capabilities:
        target_user = await UserService.get_by_id(db, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if target user is a member of any project the PM manages
        from app.services.project_service import ProjectService
        pm_projects = await ProjectService.get_user_projects(
            db, user_id=current_user["user_id"], org_id=current_user.get("org_id"),
        )
        project_ids = [p.id for p in pm_projects]
        is_project_member = False
        if project_ids:
            member_stmt = (
                select(UserRole.user_id)
                .where(
                    UserRole.scope_type == "project",
                    UserRole.scope_id.in_(project_ids),
                    UserRole.user_id == user_id,
                )
                .limit(1)
            )
            result = await db.execute(member_stmt)
            is_project_member = result.first() is not None

        is_created_by_pm = target_user.created_by == current_user["user_id"]
        if not is_project_member and not is_created_by_pm:
            raise HTTPException(status_code=403, detail="Not authorized to manage this user")
        if payload.role_assignments:
            requested_roles = {ra.role_name for ra in payload.role_assignments}
            if not requested_roles.issubset(ALLOWED_PM_ROLES):
                raise HTTPException(status_code=403, detail="PM can only assign PO/SM/BA, Developer, Tester, or MLOps roles")

    # ── Safety rule D-27 / RBAC-09: self-lock prevention ──
    if payload.role_assignments is not None and requesting_user_id == user_id:
        new_role_names = {ra.role_name for ra in payload.role_assignments}
        current_roles = await RoleService.get_user_roles(db, user_id)
        had_superadmin = False
        for ur in current_roles:
            role = await db.get(Role, ur.role_id)
            if role and role.name == "superadmin":
                had_superadmin = True
                break
        if had_superadmin and "superadmin" not in new_role_names:
            raise HTTPException(
                status_code=403,
                detail={
                    "detail": "You cannot remove your own SuperAdmin role",
                    "code": "self_lock_violation",
                },
            )

    # ── Safety rule D-28: last-SuperAdmin protection on role removal ──
    if payload.role_assignments is not None:
        new_role_names_set = {ra.role_name for ra in payload.role_assignments}
        if "superadmin" not in new_role_names_set:
            # Check if the target user currently has superadmin
            target_roles = await RoleService.get_user_roles(db, user_id)
            superadmin_role = await RoleService.get_role_by_name(db, "superadmin")
            target_had_superadmin = superadmin_role and any(
                ur.role_id == superadmin_role.id for ur in target_roles
            )
            if target_had_superadmin and superadmin_role:
                count_result = await db.execute(
                    select(func.count(UserRole.id)).where(
                        UserRole.role_id == superadmin_role.id,
                        UserRole.user_id != user_id,
                    )
                )
                other_superadmins = count_result.scalar() or 0
                if other_superadmins == 0:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "detail": "Cannot remove the last SuperAdmin role",
                            "code": "last_admin_violation",
                        },
                    )

    role_assignments_dicts = (
        [ra.model_dump() for ra in payload.role_assignments]
        if payload.role_assignments is not None
        else None
    )
    try:
        # WEGA-1920: capture old role-assignment signature so we can detect
        # an actual role/capability change after the update is applied.
        old_role_sig: frozenset | None = None
        if role_assignments_dicts is not None:
            old_role_sig = await _role_assignment_signature(db, user_id)

        user = await UserService.update_user(
            db,
            user_id=user_id,
            display_name=payload.display_name,
            role_assignments=role_assignments_dicts,
            status=payload.status,
            requesting_user_id=requesting_user_id,
        )

        # WEGA-1920: when role assignments actually change, revoke all of the
        # user's active refresh sessions so stale capabilities cannot be used
        # to refresh into a new access token.  No-op updates (same set of
        # roles + scopes) do NOT revoke sessions.
        if old_role_sig is not None:
            new_role_sig = await _role_assignment_signature(db, user_id)
            if old_role_sig != new_role_sig:
                await RefreshManager.revoke_user_sessions(
                    db, user_id, reason="role_changed"
                )
                db.add(AuditLog(
                    user_id=requesting_user_id,
                    action="user_roles_updated",
                    resource_type="user",
                    resource_id=user_id,
                    details={
                        "old_roles": sorted(
                            f"{name}:{stype}:{sid}"
                            for name, stype, sid in old_role_sig
                        ),
                        "new_roles": sorted(
                            f"{name}:{stype}:{sid}"
                            for name, stype, sid in new_role_sig
                        ),
                        "sessions_revoked": True,
                        "reason": "role_changed",
                    },
                    ip_address=request.client.host if request.client else None,
                ))
                logger.info(
                    "[user] Roles changed — sessions revoked",
                    user_id=user_id,
                    by=requesting_user_id,
                )

        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    loaded = await _load_user_with_roles(db, user.id)
    return _build_user_response(loaded or user)


# ── DELETE /api/users/{user_id} ─────────────────────────────────

@router.delete("/{user_id}")
async def deactivate_user(
    user_id: str,
    permanent: bool = Query(False, description="Hard-delete (only for users with no attribution)"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate user (soft delete). Hard-delete with ?permanent=true only if
    the user has no attribution references (projects created, settings configured, etc.)."""
    _require_user_management(current_user)

    try:
        if permanent:
            # Eligibility gate: reject if user has attribution references
            from app.models.project import Project
            from app.models.project_secret import ProjectSecret
            from app.models.project_settings import ProjectSettings
            refs = []
            for model, col, label in [
                (Project, Project.created_by, "project creator"),
                (ProjectSecret, ProjectSecret.updated_by, "secret updater"),
                (ProjectSettings, ProjectSettings.configured_by, "settings configurator"),
            ]:
                count = (await db.execute(
                    select(func.count()).select_from(model).where(col == user_id)
                )).scalar() or 0
                if count:
                    refs.append(f"{label} ({count})")
            if refs:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot permanently delete: user is referenced as {', '.join(refs)}. Deactivate instead.",
                )
            summary = await UserService.delete_user(
                db,
                user_id=user_id,
                requesting_user_id=current_user["user_id"],
            )
            await db.commit()
            return {"status": "deleted", **summary}

        user = await UserService.deactivate_user(
            db,
            user_id=user_id,
            requesting_user_id=current_user["user_id"],
        )
        await db.commit()
    except HTTPException:
        raise
    except ValueError as exc:
        msg = str(exc)
        if "your own account" in msg or "last superadmin" in msg.lower():
            raise HTTPException(status_code=403, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc
    except Exception as exc:
        logger.error("[user] Delete failed", error=str(exc), user_id=user_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    loaded = await _load_user_with_roles(db, user.id)
    return _build_user_response(loaded or user)


# ── POST /api/users/{user_id}/reset-password ────────────────────

@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin-initiated password reset — generates new activation token."""
    try:
        raw_token = await UserService.admin_reset_password(
            db, user_id=user_id, created_by=current_user["user_id"],
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    activation_url = f"{settings.frontend_url}/login?token={raw_token}"
    return {
        "activation_url": activation_url,
        "expires_in_hours": ActivationService.TOKEN_EXPIRY_HOURS,
    }


# ── POST /api/users/{user_id}/resend-activation ─────────────────

@router.post("/{user_id}/resend-activation")
async def resend_activation(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resend activation link — only valid for PENDING users (D-35)."""
    user = await UserService.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.status != UserStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Can only resend activation for users in PENDING status",
        )

    raw_token = await ActivationService.create_token(
        db, user_id=user_id, created_by=current_user["user_id"],
    )
    await db.commit()

    activation_url = f"{settings.frontend_url}/login?token={raw_token}"
    return {
        "activation_url": activation_url,
        "expires_in_hours": ActivationService.TOKEN_EXPIRY_HOURS,
    }
