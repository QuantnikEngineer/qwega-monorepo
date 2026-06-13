"""Authentication API routes."""

import hashlib
from datetime import datetime, timedelta, timezone

from argon2 import exceptions as argon2_exceptions
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.linker import UserLinker
from app.auth.password import PasswordAuthenticator
from app.auth.refresh import RefreshManager


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC). Handles naive datetimes from SQLite."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
from app.auth.session_issuer import SessionIssuer
from app.core.config import settings
from app.core.logging import get_logger
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.auth_method import AuthMethod, AuthMethodType
from app.models.project import Project
from app.models.role import UserRole
from app.models.session import Session
from app.models.user import User, UserStatus
from app.schemas.activation import ActivateAccountRequest, ActivateAccountResponse, ValidateTokenResponse
from app.schemas.auth import LoginRequest, PasswordChangeRequest, RegisterRequest
from app.services.activation_service import ActivationService
from app.services.password_service import PasswordService, password_hasher
from app.services.project_service import ProjectService
from app.services.role_service import RoleService
from app.services.user_service import UserService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _login_error_detail(*, retry_after_seconds: int | None = None) -> dict[str, object]:
    detail: dict[str, object] = {
        "error": "invalid_credentials",
        "message": "Invalid email or password",
    }
    if retry_after_seconds is not None:
        detail["retry_after_seconds"] = retry_after_seconds
    return detail


def _calculate_retry_delay_seconds(failed_attempts: int) -> int:
    exponent = max(failed_attempts - 1, 0)
    delay = settings.lockout_backoff_base_seconds * (2**exponent)
    return max(
        settings.lockout_backoff_base_seconds,
        min(delay, settings.lockout_backoff_max_seconds),
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    is_production = settings.app_env == "production"
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite=settings.cookie_samesite,
        path=settings.cookie_path,
        max_age=settings.jwt_refresh_token_expire_days * 86400,
    )


async def _get_user_with_context(db: AsyncSession, user_id: str) -> tuple[User | None, list[str], list[str], bool]:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.user_roles).selectinload(UserRole.role),
            selectinload(User.auth_methods),
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        return None, [], [], False

    roles: list[str] = []
    capabilities: set[str] = set()
    for user_role in user.user_roles:
        role = user_role.role
        if role:
            roles.append(role.name)
            capabilities.update(role.capabilities or [])

    must_change_password = False
    for auth_method in user.auth_methods:
        if auth_method.method_type == AuthMethodType.PASSWORD and auth_method.disabled_at is None:
            must_change_password = auth_method.must_change_password
            break

    return user, roles, sorted(capabilities), must_change_password


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Authenticate user and issue token pair."""
    email_normalized = payload.email.strip().lower()
    now = datetime.now(timezone.utc)
    auth_method_stmt = select(AuthMethod).where(
        AuthMethod.method_type == AuthMethodType.PASSWORD,
        AuthMethod.disabled_at.is_(None),
        AuthMethod.user.has(User.normalized_email == email_normalized),
    )
    auth_method_result = await db.execute(auth_method_stmt)
    auth_method = auth_method_result.scalar_one_or_none()

    if auth_method and auth_method.locked_until and _ensure_utc(auth_method.locked_until) <= now:
        auth_method.locked_until = None
        auth_method.failed_login_attempts = 0
        auth_method.lockout_backoff_level = 0

    if auth_method and auth_method.locked_until and _ensure_utc(auth_method.locked_until) > now:
        retry_after_seconds = max(
            1,
            int((_ensure_utc(auth_method.locked_until) - now).total_seconds()),
        )
        raise HTTPException(status_code=401, detail=_login_error_detail(retry_after_seconds=retry_after_seconds))

    try:
        authenticator = PasswordAuthenticator()
        identity = await authenticator.authenticate(
            db=db, email=payload.email, password=payload.password
        )
        linked = await UserLinker.resolve(db, identity)
        user: User = linked["user"]
        roles: list[str] = linked["roles"]
        capabilities: list[str] = linked["capabilities"]
        must_change_password: bool = linked["must_change_password"]
    except ValueError:
        retry_after_seconds = settings.lockout_backoff_base_seconds
        if auth_method:
            failed_attempts = auth_method.failed_login_attempts + 1
            auth_method.failed_login_attempts = failed_attempts
            auth_method.last_failed_login_at = now
            if failed_attempts >= settings.lockout_threshold:
                auth_method.locked_until = now + timedelta(minutes=settings.lockout_window_minutes)
                auth_method.lockout_backoff_level = max(auth_method.lockout_backoff_level, 0) + 1
                retry_after_seconds = settings.lockout_window_minutes * 60
            else:
                retry_after_seconds = _calculate_retry_delay_seconds(failed_attempts)
            await db.commit()

        logger.warning("[auth] Login failed", email=email_normalized)
        raise HTTPException(
            status_code=401,
            detail=_login_error_detail(retry_after_seconds=retry_after_seconds),
        ) from None

    if auth_method and (
        auth_method.failed_login_attempts
        or auth_method.last_failed_login_at is not None
        or auth_method.locked_until is not None
        or auth_method.lockout_backoff_level
    ):
        auth_method.failed_login_attempts = 0
        auth_method.last_failed_login_at = None
        auth_method.locked_until = None
        auth_method.lockout_backoff_level = 0

    issuer = SessionIssuer(request.app.state.jwt_manager)

    # Phase 5: resolve flat capabilities + allowed agents for JWT
    resolved = await RoleService.resolve_flat_capabilities(db, user.id)

    # Multi-project: resolve all projects this user belongs to
    user_projects = await ProjectService.get_user_projects(db, user.id, user.org_id)
    project_id = user_projects[0].id if user_projects else None
    project_ids = [p.id for p in user_projects]

    # Per-project agent access (Phase 2 delegation)
    project_allowed_agents = await RoleService.resolve_all_project_agents(
        db, user.id, project_ids,
    ) if project_ids else {}

    tokens = await issuer.issue(
        db=db,
        user=user,
        roles=resolved["roles"],
        capabilities=resolved["capabilities"],
        device_info=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        allowed_agents=resolved["allowed_agents"],
        project_allowed_agents=project_allowed_agents,
        project_id=project_id,
        project_ids=project_ids,
        # Keep scoped claims for backward compat during rolling deploy
        platform_capabilities=resolved["capabilities"],
        org_capabilities=resolved["capabilities"],
        project_roles={},
        self_capabilities=resolved["capabilities"],
    )
    await UserService.update_last_login(db, user)

    user_payload = {
        "id": user.id,
        "email": user.normalized_email,
        "display_name": user.display_name,
        "roles": resolved["roles"],
        "capabilities": resolved["capabilities"],
        "org_id": user.org_id,
        "project_id": project_id,
        "must_change_password": must_change_password,
        "allowed_agents": resolved["allowed_agents"],
        # Keep scoped for backward compat during rolling deploy
        "platform_capabilities": resolved["capabilities"],
        "org_capabilities": resolved["capabilities"],
        "project_roles": {},
        "self_capabilities": resolved["capabilities"],
    }
    response = JSONResponse(
        content={
            "access_token": tokens["access_token"],
            "token_type": "bearer",
            "expires_in": tokens["expires_in"],
            "user": user_payload,
        }
    )
    _set_refresh_cookie(response, tokens["refresh_token"])
    logger.info("[auth] Login success", user_id=user.id, email=user.normalized_email)
    return response


@router.post("/refresh")
async def refresh(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Rotate refresh token and return new access token."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    validated = await RefreshManager.validate_and_rotate(db, refresh_token)
    if validated is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user, roles, capabilities, _ = await _get_user_with_context(db, validated["user_id"])
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    # QUANTNIK-1921: reject refresh attempts for non-ACTIVE users (e.g. DEACTIVATED
    # / SUSPENDED / PENDING).  This guards against a deactivated user holding
    # an unexpired refresh token surviving long enough to mint a fresh access
    # token before session revocation propagates.
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "user_not_active",
                "message": "User account is not active",
            },
        )

    # Phase 5: resolve flat capabilities + allowed agents for JWT
    resolved = await RoleService.resolve_flat_capabilities(db, user.id)

    # Multi-project: resolve all projects this user belongs to
    user_projects = await ProjectService.get_user_projects(db, user.id, user.org_id)
    project_id = user_projects[0].id if user_projects else None
    project_ids = [p.id for p in user_projects]

    # Per-project agent access (Phase 2 delegation)
    project_allowed_agents = await RoleService.resolve_all_project_agents(
        db, user.id, project_ids,
    ) if project_ids else {}

    issuer = SessionIssuer(request.app.state.jwt_manager)
    tokens = await issuer.issue(
        db=db,
        user=user,
        roles=resolved["roles"],
        capabilities=resolved["capabilities"],
        device_info=request.headers.get("User-Agent"),
        ip_address=request.client.host if request.client else None,
        token_family_id=validated["token_family_id"],
        allowed_agents=resolved["allowed_agents"],
        project_allowed_agents=project_allowed_agents,
        project_id=project_id,
        project_ids=project_ids,
        # Keep scoped claims for backward compat during rolling deploy
        platform_capabilities=resolved["capabilities"],
        org_capabilities=resolved["capabilities"],
        project_roles={},
        self_capabilities=resolved["capabilities"],
    )

    # Build user projects list for response
    user_project_list = [
        {"id": p.id, "name": p.name, "slug": p.slug}
        for p in user_projects
    ]

    response = JSONResponse(
        content={
            "access_token": tokens["access_token"],
            "token_type": "bearer",
            "expires_in": tokens["expires_in"],
            "user": {
                "id": user.id,
                "email": user.normalized_email,
                "display_name": user.display_name,
                "roles": resolved["roles"],
                "capabilities": resolved["capabilities"],
                "allowed_agents": resolved["allowed_agents"],
                "org_id": user.org_id,
                "project_id": project_id,
                "projects": user_project_list,
            },
        }
    )
    _set_refresh_cookie(response, tokens["refresh_token"])
    return response


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Revoke refresh-token family and clear cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        session_result = await db.execute(select(Session).where(Session.refresh_token_hash == token_hash))
        session = session_result.scalar_one_or_none()
        if session:
            await RefreshManager._revoke_family(db, session.token_family_id, "logout")

    response.delete_cookie(
        key="refresh_token",
        path=settings.cookie_path,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.app_env == "production",
    )
    response.status_code = 204
    return response


@router.post("/change-password")
async def change_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change current user's password."""
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await UserService.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    stmt = select(AuthMethod).where(
        AuthMethod.user_id == user_id,
        AuthMethod.method_type == AuthMethodType.PASSWORD,
        AuthMethod.disabled_at.is_(None),
    )
    result = await db.execute(stmt)
    auth_method = result.scalar_one_or_none()
    if auth_method is None or not auth_method.credential_hash:
        raise HTTPException(status_code=400, detail="No password auth method found")

    old_password = getattr(payload, "old_password", None) or getattr(payload, "current_password", None)
    try:
        password_hasher.verify(auth_method.credential_hash, old_password or "")
    except argon2_exceptions.VerifyMismatchError:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_credentials", "message": "Current password is incorrect"},
        ) from None
    except argon2_exceptions.InvalidHashError:
        raise HTTPException(status_code=400, detail="Password credentials unavailable") from None

    violations = PasswordService.validate_policy(payload.new_password)
    if violations:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "password_policy",
                "message": "Password does not meet requirements",
                "violations": violations,
            },
        )

    new_hash = PasswordService.hash_password(payload.new_password)
    await UserService.change_password(db, user_id, new_hash)
    await RefreshManager.revoke_user_sessions(db, user_id, reason="password_changed")

    return {"message": "Password changed successfully"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Return current authenticated user profile."""
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    user, roles, capabilities, must_change_password = await _get_user_with_context(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Phase 5: resolve flat capabilities + allowed agents
    resolved = await RoleService.resolve_flat_capabilities(db, user_id)

    # Multi-project: use shared resolver (includes creator + member projects)
    user_projects = await ProjectService.get_user_projects(db, user.id, user.org_id)
    project_id = user_projects[0].id if user_projects else None
    projects = [{"id": p.id, "name": p.name, "slug": p.slug} for p in user_projects]
    project_roles_map = await ProjectService.get_user_project_roles(db, user.id, user_projects)

    return {
        "id": user.id,
        "email": user.normalized_email,
        "display_name": user.display_name,
        "roles": resolved["roles"],
        "capabilities": resolved["capabilities"],
        "org_id": user.org_id,
        "project_id": project_id,
        "projects": projects,
        "project_ids": [p["id"] for p in projects],
        "project_roles": project_roles_map,
        "must_change_password": must_change_password,
        "auth_method": "password",
        "allowed_agents": resolved["allowed_agents"],
        # Keep scoped for backward compat during rolling deploy
        "platform_capabilities": resolved["capabilities"],
        "org_capabilities": resolved["capabilities"],
        "self_capabilities": resolved["capabilities"],
    }


# ── Activation endpoints (public — token authenticates) ──────────


@router.get("/activate")
async def validate_activation_token(
    token: str = Query(..., description="Activation token from URL"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate an activation token without consuming it."""
    import hashlib as _hashlib

    from app.models.activation_token import ActivationToken

    token_hash = _hashlib.sha256(token.encode()).hexdigest()
    result = await db.execute(
        select(ActivationToken).where(ActivationToken.token_hash == token_hash)
    )
    activation = result.scalar_one_or_none()

    if activation is None:
        return ValidateTokenResponse(valid=False).model_dump()

    # Check if already used
    if activation.used_at is not None:
        user = await UserService.get_by_id(db, activation.user_id)
        return ValidateTokenResponse(
            valid=False,
            email=user.normalized_email if user else None,
            display_name=user.display_name if user else None,
            expired=False,
            used=True,
        ).model_dump()

    # Check if expired
    now = datetime.now(timezone.utc)
    if activation.expires_at:
        expires = activation.expires_at if activation.expires_at.tzinfo else activation.expires_at.replace(tzinfo=timezone.utc)
        if expires < now:
            user = await UserService.get_by_id(db, activation.user_id)
            return ValidateTokenResponse(
                valid=False,
                email=user.normalized_email if user else None,
                display_name=user.display_name if user else None,
                expired=True,
                used=False,
            ).model_dump()

    # Valid token
    user = await UserService.get_by_id(db, activation.user_id)
    return ValidateTokenResponse(
        valid=True,
        email=user.normalized_email if user else None,
        display_name=user.display_name if user else None,
        expired=False,
        used=False,
    ).model_dump()


@router.post("/activate")
async def activate_account(
    payload: ActivateAccountRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Redeem activation token and set password."""
    # 1. Redeem token atomically
    activation = await ActivationService.redeem_token(db, payload.token)
    if activation is None:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Activation link has expired or already been used",
                "code": "invalid_token",
            },
        )

    # 2. Validate password policy
    violations = PasswordService.validate_policy(payload.password)
    if violations:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "password_policy",
                "message": "Password does not meet requirements",
                "violations": violations,
            },
        )

    # 3. Create password auth method
    hashed = PasswordService.hash_password(payload.password)
    auth_method = AuthMethod(
        user_id=activation.user_id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=hashed,
        is_primary=True,
        must_change_password=False,
    )
    db.add(auth_method)

    # 4. Update user status to ACTIVE
    user = await UserService.get_by_id(db, activation.user_id)
    if user:
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info("[auth] Account activated", user_id=activation.user_id)
    return ActivateAccountResponse(
        message="Account activated successfully",
        user_id=activation.user_id,
    ).model_dump()


# ── GET /api/auth/registration-defaults ──────────────────────────
# Public endpoint — returns default project/role for direct-to-project registration.
# Reads from settings (REGISTRATION_DEFAULT_PROJECT_SLUG, REGISTRATION_DEFAULT_ROLE).

@router.get("/registration-defaults")
async def registration_defaults(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return registration defaults for the frontend registration form.

    Public endpoint — no authentication required.
    Configured via environment variables:
      REGISTRATION_DEFAULT_PROJECT_SLUG — slug of the default project
      REGISTRATION_DEFAULT_ROLE — role name (default: po_sm_ba)
    """
    from app.core.config import settings as app_settings

    default_slug = app_settings.registration_default_project_slug.strip()
    default_role = app_settings.registration_default_role.strip()

    if not default_slug:
        return {"mode": "pm"}

    # Resolve the project
    from app.models.org import Org
    org_result = await db.execute(select(Org).limit(1))
    org = org_result.scalar_one_or_none()
    if not org:
        return {"mode": "pm"}

    project = await ProjectService.get_open_registration_project(db, default_slug, org.id)
    if not project:
        return {"mode": "pm"}

    return {
        "mode": "project",
        "project_slug": project.slug,
        "project_name": project.name,
        "role": default_role,
    }


# ── POST /api/auth/register ──────────────────────────────────────
# Self-service registration: creates user with PM role (org-scope) by default,
# or with a project-scoped role when project_slug is provided.
# Public endpoint — no authentication required.
# Rate limiting enforced at gateway level.

# Simple in-memory rate limiter (per-IP, resets on service restart)
from collections import defaultdict
import time

_register_attempts: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    """Return True if request is within rate limit."""
    now = time.time()
    window = settings.registration_rate_limit_window
    max_attempts = settings.registration_rate_limit_max
    attempts = _register_attempts[ip]
    # Prune old entries
    _register_attempts[ip] = [t for t in attempts if now - t < window]
    return len(_register_attempts[ip]) < max_attempts


@router.post("/register", status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Self-service user registration.

    Two modes:
    - **PM mode** (default): No project_slug → assigns PM role (org-scope).
    - **Project mode**: project_slug provided → assigns role (default po_sm_ba)
      scoped to the specified project, which must be active and open for registration.

    Returns a consistent response regardless of whether the email already exists
    (account enumeration prevention).
    """
    client_ip = request.client.host if request.client else "unknown"

    # Rate limiting
    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts. Please try again later.",
        )

    # Record this attempt
    _register_attempts[client_ip].append(time.time())

    email_normalized = payload.email.strip().lower()

    # Check if user already exists
    existing = await UserService.get_by_email(db, email_normalized)
    if existing:
        logger.info("[auth] Registration attempt for existing email", email_domain=email_normalized.split("@")[-1], ip=client_ip)
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Please sign in instead.",
        )

    # Validate password policy
    violations = PasswordService.validate_policy(payload.password)
    if violations:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "password_policy",
                "message": "Password does not meet requirements",
                "violations": violations,
            },
        )

    # Get default org
    from app.models.org import Org
    org_result = await db.execute(select(Org).limit(1))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=500, detail="Platform not initialized")

    # Resolve registration mode: project vs PM
    from app.core.config import settings as app_settings
    target_project = None
    project_role_name = app_settings.registration_default_role.strip()

    if payload.project_slug:
        target_project = await ProjectService.get_open_registration_project(
            db, payload.project_slug, org.id,
        )
        if not target_project:
            raise HTTPException(
                status_code=400,
                detail="This project is not available for registration. Please check the link or contact an administrator.",
            )

    # Create user (active immediately — no activation flow needed)
    user = User(
        normalized_email=email_normalized,
        display_name=payload.display_name,
        org_id=org.id,
        status=UserStatus.ACTIVE,
        created_by=None,  # self-registered
    )
    db.add(user)
    await db.flush()

    # Create password auth method
    hashed = PasswordService.hash_password(payload.password)
    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=hashed,
        is_primary=True,
        must_change_password=False,
    )
    db.add(auth_method)

    # Assign role based on registration mode
    from app.services.role_service import RoleService

    if target_project:
        # Project mode — assign project-scoped role (e.g. po_sm_ba)
        role = await RoleService.get_role_by_name(db, project_role_name)
        if role:
            user_role = UserRole(
                user_id=user.id,
                role_id=role.id,
                scope_type="project",
                scope_id=target_project.id,
                source="self_registered_project",
                assigned_by=None,
            )
            db.add(user_role)
        reg_details = {
            "email_domain": email_normalized.split("@")[-1],
            "role": project_role_name,
            "project_slug": target_project.slug,
            "project_id": target_project.id,
            "source": "self_registration_project",
        }
    else:
        # PM mode — assign org-scoped PM role (existing behavior)
        pm_role = await RoleService.get_role_by_name(db, "pm")
        if pm_role:
            user_role = UserRole(
                user_id=user.id,
                role_id=pm_role.id,
                scope_type="org",
                scope_id=org.id,
                source="self_registered",
                assigned_by=None,
            )
            db.add(user_role)
        reg_details = {
            "email_domain": email_normalized.split("@")[-1],
            "role": "pm",
            "source": "self_registration",
        }

    # Audit log
    from app.models.audit import AuditLog
    db.add(AuditLog(
        user_id=user.id,
        action="user_self_registered",
        resource_type="user",
        resource_id=user.id,
        details=reg_details,
        ip_address=client_ip,
    ))

    await db.commit()

    logger.info(
        "[auth] User self-registered",
        user_id=user.id,
        email_domain=email_normalized.split("@")[-1],
        mode="project" if target_project else "pm",
        ip=client_ip,
    )

    return JSONResponse(
        status_code=201,
        content={"status": "registered", "message": "If this email is valid, your account has been created. You can now log in."},
    )
