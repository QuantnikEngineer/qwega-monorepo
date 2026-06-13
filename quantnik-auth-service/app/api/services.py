"""
Services API
============
Platform service registry management (SuperAdmin) and
per-project tool configuration (MLOps).
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.url_validation import UnsafeURLError, validate_tool_url
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.audit import AuditLog
from app.models.project_settings import ProjectSettings
from app.models.project_secret import ProjectSecret
from app.models.service_registry import ServiceRegistry
from app.services.project_service import ProjectService
from app.services.secret_service import encrypt_secret, decrypt_secret

logger = logging.getLogger(__name__)

router = APIRouter(tags=["services"])


# ── Schemas ──────────────────────────────────────────────────────

class ServiceCreate(BaseModel):
    tool_id: str = Field(..., min_length=1, description="Unique tool identifier")
    name: str = Field(..., min_length=1)
    icon: str | None = None
    description: str | None = None
    category: str | None = None
    color: str | None = None
    default_config: dict = Field(default_factory=dict)
    enabled: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    description: str | None = None
    category: str | None = None
    enabled: bool | None = None


class ProjectToolConfig(BaseModel):
    config: dict = Field(default_factory=dict, description="Tool-specific metadata (URLs, keys, flags)")
    is_enabled: bool = Field(default=True)
    secrets: dict[str, str] = Field(
        default_factory=dict,
        description="Secret key-value pairs (PAT tokens, API keys). Stored encrypted.",
    )


# ── Helpers ──────────────────────────────────────────────────────

def _require_platform_manage(current_user: dict) -> None:
    if "platform:manage" not in current_user.get("capabilities", []):
        raise HTTPException(status_code=403, detail="Requires platform:manage capability")


async def _require_project_integration_access(
    db: AsyncSession,
    project_id: str,
    current_user: dict,
) -> None:
    """Verify caller can configure integrations for this project."""
    project = await ProjectService.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.org_id != current_user.get("org_id"):
        raise HTTPException(status_code=404, detail="Project not found")

    caps = set(current_user.get("capabilities", []))
    if "platform:manage" in caps:
        return  # SuperAdmin bypasses

    # Must have project:configure_integrations or integration:configure_tools
    has_cap = caps.intersection({"project:configure_integrations", "integration:configure_tools"})
    if not has_cap:
        raise HTTPException(status_code=403, detail="Requires integration configuration capability")

    # Must be a project member with the capability
    has_project_cap = await ProjectService.has_project_capability(
        db, project_id, current_user["user_id"], "project:configure_integrations",
    )
    # Also check org-level integration:configure_tools
    if not has_project_cap and "integration:configure_tools" not in caps:
        raise HTTPException(status_code=403, detail="Not authorized to configure this project's integrations")


# ── Tool Readiness ───────────────────────────────────────────────

# Minimum non-secret config fields required per tool for sidebar readiness.
# Tools not listed here default to requiring "url".
REQUIRED_CONFIG_FIELDS: dict[str, list[str]] = {
    "jira": ["url", "projectKey", "email"],
    "confluence": ["url", "spaceKey", "spaceId", "email"],
    "github": ["url"],
    "qtest": ["url", "qtestProjectId"],
    "harness-pipelines": ["url", "accountId", "orgIdentifier", "projectIdentifier"],
    "harness-repo": ["url", "accountId", "orgIdentifier", "repoIdentifier"],
    "snyk": ["orgId"],
    "trivy": ["serverUrl"],
}

# Secret keys that must be present for a tool to be considered ready.
REQUIRED_SECRET_KEYS: dict[str, list[str]] = {
    # All tools currently require patToken except Trivy (optional)
    "trivy": [],
}
_DEFAULT_REQUIRED_SECRETS = ["patToken"]


def _compute_tool_ready(
    *,
    tool_id: str,
    platform_enabled: bool,
    project_enabled: bool,
    configured: bool,
    config: dict,
    secret_keys: list[str],
) -> bool:
    """Compute backend-authoritative readiness flag for a tool.

    ready = platformEnabled ∧ projectEnabled ∧ configured
            ∧ hasRequiredConfig ∧ hasRequiredSecrets
    """
    if not (platform_enabled and project_enabled and configured):
        return False

    # Check required config fields are present and non-empty strings
    required_fields = REQUIRED_CONFIG_FIELDS.get(tool_id, ["url"])
    for field in required_fields:
        val = config.get(field)
        if not isinstance(val, str) or not val.strip():
            return False

    # Check required secrets exist
    required_secrets = REQUIRED_SECRET_KEYS.get(tool_id, _DEFAULT_REQUIRED_SECRETS)
    for secret in required_secrets:
        if secret not in secret_keys:
            return False

    return True


# ── Platform Service Registry ────────────────────────────────────

@router.get("/api/services")
async def list_services(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all platform services. Any authenticated user can read."""
    result = await db.execute(
        select(ServiceRegistry).order_by(ServiceRegistry.name)
    )
    services = result.scalars().all()
    return {
        "services": [
            {
                "id": s.id,
                "toolId": s.tool_id,
                "name": s.name,
                "icon": s.icon,
                "description": s.description,
                "category": s.category,
                "color": s.color,
                "defaultConfig": s.default_config,
                "enabled": s.enabled,
            }
            for s in services
        ],
    }


@router.post("/api/services", status_code=201)
async def create_service(
    payload: ServiceCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a new platform service. SuperAdmin only."""
    _require_platform_manage(current_user)

    # Check tool_id uniqueness
    existing = await db.execute(
        select(ServiceRegistry).where(ServiceRegistry.tool_id == payload.tool_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Service '{payload.tool_id}' already exists")

    service = ServiceRegistry(
        tool_id=payload.tool_id,
        name=payload.name,
        icon=payload.icon,
        description=payload.description,
        category=payload.category,
        color=payload.color,
        default_config=payload.default_config,
        enabled=payload.enabled,
    )
    db.add(service)
    await db.commit()

    return {
        "id": service.id,
        "toolId": service.tool_id,
        "name": service.name,
        "enabled": service.enabled,
    }


@router.put("/api/services/{service_id}")
async def update_service(
    service_id: str,
    payload: ServiceUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update a platform service. SuperAdmin only."""
    _require_platform_manage(current_user)

    result = await db.execute(
        select(ServiceRegistry).where(ServiceRegistry.id == service_id)
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if payload.name is not None:
        service.name = payload.name
    if payload.icon is not None:
        service.icon = payload.icon
    if payload.description is not None:
        service.description = payload.description
    if payload.category is not None:
        service.category = payload.category
    if payload.enabled is not None:
        service.enabled = payload.enabled

    await db.commit()
    return {
        "id": service.id,
        "toolId": service.tool_id,
        "name": service.name,
        "enabled": service.enabled,
    }


# ── Project Tool Settings ────────────────────────────────────────

@router.get("/api/projects/{project_id}/settings")
async def get_project_settings(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get resolved tool settings for a project.

    Returns all platform-enabled services with their project-specific config.
    Resolution: platform disabled → unavailable; platform enabled + project config → merged.
    Secrets are returned as masked indicators only.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.org_id != current_user.get("org_id"):
        raise HTTPException(status_code=404, detail="Project not found")

    # Auth: platform admin OR org member with integration:use_tools
    caps = set(current_user.get("capabilities", []))
    if "platform:manage" not in caps:
        if "integration:use_tools" not in caps:
            raise HTTPException(status_code=403, detail="Requires integration:use_tools capability")

    # Get all platform services
    svc_result = await db.execute(select(ServiceRegistry).order_by(ServiceRegistry.name))
    services = list(svc_result.scalars().all())

    # Get project settings
    ps_result = await db.execute(
        select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    )
    proj_settings = {ps.service_id: ps for ps in ps_result.scalars().all()}

    # Get project secrets (masked)
    sec_result = await db.execute(
        select(ProjectSecret).where(ProjectSecret.project_id == project_id)
    )
    proj_secrets: dict[str, list[str]] = {}
    for sec in sec_result.scalars().all():
        proj_secrets.setdefault(sec.service_id, []).append(sec.secret_key)

    tools = []
    for svc in services:
        ps = proj_settings.get(svc.id)
        # Resolve config: project override → default_config.defaults → empty
        if ps:
            config = ps.config
        else:
            dc = svc.default_config or {}
            config = dc.get("defaults", dc) if isinstance(dc, dict) else {}
        is_enabled = ps.is_enabled if ps else False

        tools.append({
            "serviceId": svc.id,
            "toolId": svc.tool_id,
            "name": svc.name,
            "icon": svc.icon,
            "description": svc.description,
            "category": svc.category,
            "color": svc.color,
            "platformEnabled": svc.enabled,
            "projectEnabled": is_enabled,
            "available": svc.enabled,  # platform must be enabled
            "configured": ps is not None,
            "config": config if svc.enabled else {},
            "defaultConfig": svc.default_config,
            "secretKeys": proj_secrets.get(svc.id, []),
            "hasSecrets": len(proj_secrets.get(svc.id, [])) > 0,
            "ready": _compute_tool_ready(
                tool_id=svc.tool_id,
                platform_enabled=svc.enabled,
                project_enabled=is_enabled,
                configured=ps is not None,
                config=config,
                secret_keys=proj_secrets.get(svc.id, []),
            ),
        })

    return {"projectId": project_id, "tools": tools}


@router.put("/api/projects/{project_id}/settings/{service_id}")
async def update_project_tool_settings(
    project_id: str,
    service_id: str,
    payload: ProjectToolConfig,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Configure a tool for a project. MLOps or SuperAdmin only.

    Config metadata and secrets are handled separately:
    - config: stored as JSON in project_settings
    - secrets: Fernet-encrypted in project_secrets
    """
    await _require_project_integration_access(db, project_id, current_user)

    # Validate service exists and is platform-enabled
    svc_result = await db.execute(
        select(ServiceRegistry).where(ServiceRegistry.id == service_id)
    )
    service = svc_result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if not service.enabled:
        raise HTTPException(status_code=400, detail="Service is disabled at platform level")

    # SSRF protection: validate any URL fields in the config
    _URL_CONFIG_KEYS = ("url", "serverUrl")
    for key in _URL_CONFIG_KEYS:
        url_val = payload.config.get(key)
        if url_val:
            try:
                validate_tool_url(url_val)
            except UnsafeURLError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tool URL in '{key}': {exc}",
                )

    # Upsert project_settings
    ps_result = await db.execute(
        select(ProjectSettings).where(
            ProjectSettings.project_id == project_id,
            ProjectSettings.service_id == service_id,
        )
    )
    ps = ps_result.scalar_one_or_none()
    if ps:
        ps.config = payload.config
        ps.is_enabled = payload.is_enabled
        ps.configured_by = current_user["user_id"]
    else:
        ps = ProjectSettings(
            project_id=project_id,
            service_id=service_id,
            config=payload.config,
            is_enabled=payload.is_enabled,
            configured_by=current_user["user_id"],
        )
        db.add(ps)

    # Handle secrets
    for key, value in payload.secrets.items():
        if not value:
            continue
        encrypted = encrypt_secret(value)
        sec_result = await db.execute(
            select(ProjectSecret).where(
                ProjectSecret.project_id == project_id,
                ProjectSecret.service_id == service_id,
                ProjectSecret.secret_key == key,
            )
        )
        existing_sec = sec_result.scalar_one_or_none()
        if existing_sec:
            existing_sec.encrypted_value = encrypted
            existing_sec.updated_by = current_user["user_id"]
        else:
            db.add(ProjectSecret(
                project_id=project_id,
                service_id=service_id,
                secret_key=key,
                encrypted_value=encrypted,
                updated_by=current_user["user_id"],
            ))

    await db.commit()
    return {
        "status": "saved",
        "serviceId": service_id,
        "toolId": service.tool_id,
        "isEnabled": payload.is_enabled,
    }


# ── Internal Endpoints (gateway-to-auth service calls) ──────────


async def _require_internal_key(x_internal_key: str = Header(None)) -> None:
    """Validate internal API key for service-to-service calls."""
    from app.core.config import get_settings
    expected = get_settings().internal_api_key
    if not x_internal_key or x_internal_key != expected:
        raise HTTPException(status_code=403, detail="Invalid internal API key")


@router.get("/api/internal/project-settings/{project_id}")
async def get_internal_project_settings(
    project_id: str,
    _auth: None = Depends(_require_internal_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Internal endpoint: return non-secret tool config for a project.

    Called by the gateway to inject tool config as headers for downstream
    orchestrators and agents. Returns only **ready** tools with their config
    (URLs, project keys, etc.). Secrets are NEVER included.

    A tool is ready when: platform enabled ∧ project enabled ∧ configured
    ∧ has required config fields ∧ has required secrets stored.
    """
    # Get project settings for enabled tools only
    ps_result = await db.execute(
        select(ProjectSettings).where(
            ProjectSettings.project_id == project_id,
            ProjectSettings.is_enabled == True,  # noqa: E712
        )
    )
    proj_settings = list(ps_result.scalars().all())

    # Map service_id → tool_id for response keying
    svc_ids = [ps.service_id for ps in proj_settings]
    if svc_ids:
        svc_result = await db.execute(
            select(ServiceRegistry).where(ServiceRegistry.id.in_(svc_ids))
        )
        svc_map = {s.id: s for s in svc_result.scalars().all()}
    else:
        svc_map = {}

    # Get secret keys per service (existence check, not decryption)
    sec_result = await db.execute(
        select(ProjectSecret).where(ProjectSecret.project_id == project_id)
    )
    secret_keys_by_svc: dict[str, list[str]] = {}
    for sec in sec_result.scalars().all():
        secret_keys_by_svc.setdefault(sec.service_id, []).append(sec.secret_key)

    tools: dict[str, dict] = {}
    for ps in proj_settings:
        svc = svc_map.get(ps.service_id)
        if not svc or not svc.enabled:
            continue
        config = ps.config or {}
        # Only include tools that are fully ready
        if _compute_tool_ready(
            tool_id=svc.tool_id,
            platform_enabled=svc.enabled,
            project_enabled=ps.is_enabled,
            configured=True,
            config=config,
            secret_keys=secret_keys_by_svc.get(ps.service_id, []),
        ):
            tools[svc.tool_id] = config

    return {"projectId": project_id, "tools": tools}


@router.get("/api/internal/project-secrets/{project_id}/{tool_id}")
async def get_internal_project_secrets(
    project_id: str,
    tool_id: str,
    _auth: None = Depends(_require_internal_key),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Internal endpoint: return decrypted secrets for a single ready tool.

    Called by the gateway to construct upstream authentication headers
    (e.g. Atlassian Basic auth). Returns only the minimum required secrets
    plus the ``email`` from config (needed for Basic auth construction).

    Security guardrails:
    - X-Internal-Key validation
    - Only returns secrets for tools that are fully ready
    - Audit log entry for every access (success or failure)
    - Response includes Cache-Control: no-store
    - Fails closed: any error → empty response, no partial data
    """
    # Resolve service registry entry
    svc_result = await db.execute(
        select(ServiceRegistry).where(ServiceRegistry.tool_id == tool_id)
    )
    svc = svc_result.scalar_one_or_none()
    if not svc or not svc.enabled:
        await _audit_secret_access(db, project_id, tool_id, success=False, reason="service_not_found")
        return JSONResponse(
            status_code=404,
            content={"error": "Tool not found or disabled"},
            headers={"Cache-Control": "no-store"},
        )

    # Check project settings
    ps_result = await db.execute(
        select(ProjectSettings).where(
            ProjectSettings.project_id == project_id,
            ProjectSettings.service_id == svc.id,
            ProjectSettings.is_enabled == True,  # noqa: E712
        )
    )
    ps = ps_result.scalar_one_or_none()
    if not ps:
        await _audit_secret_access(db, project_id, tool_id, success=False, reason="not_configured")
        return JSONResponse(
            status_code=404,
            content={"error": "Tool not configured for this project"},
            headers={"Cache-Control": "no-store"},
        )

    config = ps.config or {}

    # SSRF belt-and-suspenders: validate URLs even on read path
    for key in ("url", "serverUrl"):
        url_val = config.get(key)
        if url_val:
            try:
                validate_tool_url(url_val)
            except UnsafeURLError:
                logger.warning(
                    "SSRF: blocked unsafe URL in config.%s for project=%s tool=%s",
                    key, project_id, tool_id,
                )
                await _audit_secret_access(db, project_id, tool_id, success=False, reason="ssrf_blocked")
                return JSONResponse(
                    status_code=422,
                    content={"error": f"Tool URL in '{key}' failed security validation"},
                    headers={"Cache-Control": "no-store"},
                )

    # Fetch secrets for this specific tool
    sec_result = await db.execute(
        select(ProjectSecret).where(
            ProjectSecret.project_id == project_id,
            ProjectSecret.service_id == svc.id,
        )
    )
    secrets_rows = list(sec_result.scalars().all())
    secret_keys = [s.secret_key for s in secrets_rows]

    # Check readiness — fail closed
    if not _compute_tool_ready(
        tool_id=tool_id,
        platform_enabled=svc.enabled,
        project_enabled=ps.is_enabled,
        configured=True,
        config=config,
        secret_keys=secret_keys,
    ):
        await _audit_secret_access(db, project_id, tool_id, success=False, reason="not_ready")
        return JSONResponse(
            status_code=424,
            content={"error": "Tool is not fully configured (missing required fields or secrets)"},
            headers={"Cache-Control": "no-store"},
        )

    # Decrypt only the required secrets (allowlist)
    required_secrets = REQUIRED_SECRET_KEYS.get(tool_id, _DEFAULT_REQUIRED_SECRETS)
    decrypted: dict[str, str] = {}
    try:
        for row in secrets_rows:
            if row.secret_key in required_secrets:
                decrypted[row.secret_key] = decrypt_secret(row.encrypted_value)
    except Exception:
        logger.exception("Failed to decrypt secrets for project=%s tool=%s", project_id, tool_id)
        await _audit_secret_access(db, project_id, tool_id, success=False, reason="decrypt_error")
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to decrypt secrets"},
            headers={"Cache-Control": "no-store"},
        )

    await _audit_secret_access(db, project_id, tool_id, success=True)

    return JSONResponse(
        content={
            "tool_id": tool_id,
            "auth_type": svc.default_config.get("_auth_type", "basic"),
            "config": config,
            "secrets": decrypted,
        },
        headers={"Cache-Control": "no-store"},
    )


async def _audit_secret_access(
    db: AsyncSession,
    project_id: str,
    tool_id: str,
    *,
    success: bool,
    reason: str | None = None,
) -> None:
    """Write an audit log entry for internal secret retrieval attempts."""
    try:
        db.add(AuditLog(
            action="internal_secret_retrieval",
            resource_type="project_tool",
            resource_id=f"{project_id}/{tool_id}",
            details={"success": success, "reason": reason} if reason else {"success": success},
        ))
        await db.commit()
    except Exception:
        logger.warning("Failed to write audit log for secret access: project=%s tool=%s", project_id, tool_id)