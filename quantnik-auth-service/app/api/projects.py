"""
Projects API
============
Project CRUD, membership management, agent access delegation,
and project-scoped operations.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.agent import AgentCatalog
from app.models.audit import AuditLog
from app.models.role import (
    Role,
    RoleAgent,
    ProjectRoleAgent,
    ProjectRoleAgentOverride,
)
from app.services.project_service import ProjectService
from app.services.role_service import RoleService

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Roles that cannot be configured at project level
_BLOCKED_ROLES = {"superadmin"}


# ── Schemas ──────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Project name")
    description: str | None = Field(default=None)
    slug: str | None = Field(default=None, description="URL slug (auto-generated from name if omitted)")
    open_for_registration: bool = Field(default=False, description="Allow self-service registration into this project")


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None)
    open_for_registration: bool | None = Field(default=None, description="Allow self-service registration into this project")


class MemberAdd(BaseModel):
    user_id: str = Field(..., description="User UUID")
    role_name: str = Field(..., description="Role to assign in project context")


# ── Authorization helpers ────────────────────────────────────────

def _require_capability(current_user: dict, *capabilities: str) -> None:
    """Raise 403 if caller lacks ALL of the specified capabilities."""
    user_caps = set(current_user.get("capabilities", []))
    if not user_caps.intersection(capabilities):
        raise HTTPException(
            status_code=403,
            detail=f"Requires one of: {', '.join(capabilities)}",
        )


def _is_platform_admin(current_user: dict) -> bool:
    """Check if user has platform:manage capability."""
    return "platform:manage" in current_user.get("capabilities", [])


async def _require_project_access(
    db: AsyncSession,
    project_id: str,
    current_user: dict,
    require_member: bool = True,
) -> None:
    """Verify project exists, belongs to user's org, and user is a member (or admin)."""
    project = await ProjectService.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.org_id != current_user.get("org_id"):
        raise HTTPException(status_code=404, detail="Project not found")
    if require_member and not _is_platform_admin(current_user):
        is_member = await ProjectService.is_project_member(db, project_id, current_user["user_id"])
        is_creator = project.created_by == current_user["user_id"]
        if not is_member and not is_creator:
            raise HTTPException(status_code=403, detail="Not a member of this project")
    return project


# ── GET /api/projects ────────────────────────────────────────────

@router.get("")
async def list_projects(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List active projects visible to the current user.

    SuperAdmin sees all org projects; other users see only projects
    they created or are a member of.
    """
    org_id = current_user.get("org_id")
    if _is_platform_admin(current_user):
        projects = await ProjectService.list_projects(db, org_id=org_id)
    else:
        projects = await ProjectService.get_user_projects(
            db, user_id=current_user["user_id"], org_id=org_id,
        )
    return {
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "orgId": p.org_id,
                "description": p.description,
                "createdBy": p.created_by,
                "isActive": p.is_active,
                "openForRegistration": p.open_for_registration,
                "createdAt": p.created_at.isoformat() if p.created_at else None,
            }
            for p in projects
        ],
    }


# ── POST /api/projects ──────────────────────────────────────────

@router.post("", status_code=201)
async def create_project(
    payload: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new project. Requires project:create capability."""
    _require_capability(current_user, "project:create", "platform:manage")

    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="User has no organization")

    try:
        project = await ProjectService.create_project(
            db,
            name=payload.name,
            org_id=org_id,
            created_by=current_user["user_id"],
            description=payload.description,
            slug=payload.slug,
            open_for_registration=payload.open_for_registration,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A project with this slug already exists in the organization.",
        )

    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "orgId": project.org_id,
        "description": project.description,
        "createdBy": project.created_by,
        "isActive": project.is_active,
        "openForRegistration": project.open_for_registration,
        "createdAt": project.created_at.isoformat() if project.created_at else None,
    }


# ── GET /api/projects/{project_id} ──────────────────────────────

@router.get("/{project_id}")
async def get_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get project details. Any org member can view."""
    project = await _require_project_access(db, project_id, current_user, require_member=False)
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "orgId": project.org_id,
        "description": project.description,
        "createdBy": project.created_by,
        "isActive": project.is_active,
        "openForRegistration": project.open_for_registration,
        "createdAt": project.created_at.isoformat() if project.created_at else None,
    }


# ── PUT /api/projects/{project_id} ──────────────────────────────

@router.put("/{project_id}")
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update project. Creator or SuperAdmin only."""
    project = await _require_project_access(db, project_id, current_user, require_member=False)

    # Only creator or platform admin can update
    if not _is_platform_admin(current_user) and project.created_by != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Only project creator or SuperAdmin can update")

    try:
        project = await ProjectService.update_project(
            db, project_id=project_id,
            name=payload.name, description=payload.description,
            open_for_registration=payload.open_for_registration,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "orgId": project.org_id,
        "description": project.description,
        "isActive": project.is_active,
        "openForRegistration": project.open_for_registration,
    }


# ── DELETE /api/projects/{project_id} ────────────────────────────

@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Soft-delete project. SuperAdmin only."""
    _require_capability(current_user, "platform:manage")
    await _require_project_access(db, project_id, current_user, require_member=False)

    try:
        await ProjectService.deactivate_project(db, project_id)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "deactivated", "projectId": project_id}


# ── GET /api/projects/{project_id}/members ───────────────────────

@router.get("/{project_id}/members")
async def list_members(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List project members. Any project member or admin can view."""
    await _require_project_access(db, project_id, current_user)
    members = await ProjectService.list_members(db, project_id)
    return {"members": members, "total": len(members)}


# ── POST /api/projects/{project_id}/members ──────────────────────

@router.post("/{project_id}/members", status_code=201)
async def add_member(
    project_id: str,
    payload: MemberAdd,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a member to a project with a role. Requires project:manage_members."""
    _require_capability(current_user, "project:manage_members", "platform:manage")
    await _require_project_access(db, project_id, current_user, require_member=False)

    try:
        user_role = await ProjectService.add_member(
            db,
            project_id=project_id,
            user_id=payload.user_id,
            role_name=payload.role_name,
            added_by=current_user["user_id"],
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "added", "userId": payload.user_id, "roleName": payload.role_name}


# ── DELETE /api/projects/{project_id}/members/{user_id} ──────────

@router.delete("/{project_id}/members/{user_id}")
async def remove_member(
    project_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a member from a project. Requires project:manage_members."""
    _require_capability(current_user, "project:manage_members", "platform:manage")
    await _require_project_access(db, project_id, current_user, require_member=False)

    count = await ProjectService.remove_member(db, project_id, user_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="User is not a member of this project")
    await db.commit()
    return {"status": "removed", "userId": user_id, "rolesRemoved": count}


# ── Project Agent Access Delegation ──────────────────────────────
# PM (project creator) or users with project:manage_agents can customize
# which agents each role has access to within their project.


class UpdateProjectAgentsRequest(BaseModel):
    agent_ids: list[str] = Field(..., description="Agent IDs to assign (subset of global ceiling)")


async def _require_project_agent_management(
    db: AsyncSession, project_id: str, current_user: dict,
) -> None:
    """Verify caller can manage project agent access.

    Allowed: platform admin, project creator, or user with project:manage_agents.
    Uses DB-level checks, not flat JWT capabilities.
    """
    project = await ProjectService.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.org_id != current_user.get("org_id"):
        raise HTTPException(status_code=404, detail="Project not found")

    if _is_platform_admin(current_user):
        return
    if project.created_by == current_user["user_id"]:
        return

    # Check project-scoped capability via DB
    has_cap = await ProjectService.has_project_capability(
        db, project_id, current_user["user_id"], "project:manage_agents",
    )
    if has_cap:
        return

    raise HTTPException(status_code=403, detail="Not authorized to manage project agent access")


@router.get("/{project_id}/agents")
async def list_project_agent_overrides(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all roles with their project-level agent config.

    Returns global ceiling, project overrides, and effective agents per role.
    """
    await _require_project_agent_management(db, project_id, current_user)

    # Get all configurable roles (exclude superadmin)
    all_roles = await RoleService.get_all_roles(db)
    configurable_roles = [r for r in all_roles if r.name not in _BLOCKED_ROLES]

    roles_config = []
    for role in configurable_roles:
        global_agents = await RoleService.get_role_agents(db, role.id)
        global_ids = sorted(ra.agent_id for ra in global_agents)

        # Check override
        override_result = await db.execute(
            select(ProjectRoleAgentOverride).where(
                ProjectRoleAgentOverride.project_id == project_id,
                ProjectRoleAgentOverride.role_id == role.id,
            )
        )
        override = override_result.scalar_one_or_none()

        if override:
            proj_result = await db.execute(
                select(ProjectRoleAgent.agent_id).where(
                    ProjectRoleAgent.project_id == project_id,
                    ProjectRoleAgent.role_id == role.id,
                )
            )
            project_ids = sorted(row[0] for row in proj_result.all())
            effective = sorted(set(project_ids) & set(global_ids))
            mode = "override"
        else:
            project_ids = None
            effective = global_ids
            mode = "inherit"

        roles_config.append({
            "role_id": role.id,
            "role_name": role.name,
            "mode": mode,
            "global_agent_ids": global_ids,
            "project_agent_ids": project_ids,
            "effective_agent_ids": effective,
        })

    return {"project_id": project_id, "roles": roles_config}


@router.get("/{project_id}/agents/{role_id}")
async def get_project_role_agents(
    project_id: str,
    role_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get agent config for a specific role in a project."""
    await _require_project_agent_management(db, project_id, current_user)

    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.name in _BLOCKED_ROLES:
        raise HTTPException(status_code=403, detail=f"Cannot configure agents for {role.name} role")

    global_agents = await RoleService.get_role_agents(db, role.id)
    global_ids = sorted(ra.agent_id for ra in global_agents)

    override_result = await db.execute(
        select(ProjectRoleAgentOverride).where(
            ProjectRoleAgentOverride.project_id == project_id,
            ProjectRoleAgentOverride.role_id == role_id,
        )
    )
    override = override_result.scalar_one_or_none()

    if override:
        proj_result = await db.execute(
            select(ProjectRoleAgent.agent_id).where(
                ProjectRoleAgent.project_id == project_id,
                ProjectRoleAgent.role_id == role_id,
            )
        )
        project_ids = sorted(row[0] for row in proj_result.all())
        effective = sorted(set(project_ids) & set(global_ids))
        mode = "override"
    else:
        project_ids = None
        effective = global_ids
        mode = "inherit"

    return {
        "project_id": project_id,
        "role_id": role_id,
        "role_name": role.name,
        "mode": mode,
        "global_agent_ids": global_ids,
        "project_agent_ids": project_ids,
        "effective_agent_ids": effective,
    }


@router.put("/{project_id}/agents/{role_id}")
async def update_project_role_agents(
    project_id: str,
    role_id: str,
    body: UpdateProjectAgentsRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set project-level agent overrides for a role.

    Submitted agent_ids must be a subset of the global ceiling for this role.
    """
    await _require_project_agent_management(db, project_id, current_user)

    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.name in _BLOCKED_ROLES:
        raise HTTPException(status_code=403, detail=f"Cannot configure agents for {role.name} role")

    # Validate all agent_ids exist in catalog
    if body.agent_ids:
        cat_result = await db.execute(
            select(AgentCatalog.id).where(AgentCatalog.id.in_(body.agent_ids))
        )
        valid_ids = {row[0] for row in cat_result.all()}
        invalid = set(body.agent_ids) - valid_ids
        if invalid:
            raise HTTPException(status_code=422, detail=f"Unknown agent IDs: {sorted(invalid)}")

    # Validate submitted agents are subset of global ceiling
    global_result = await db.execute(
        select(RoleAgent.agent_id).where(RoleAgent.role_id == role_id)
    )
    global_ceiling = {row[0] for row in global_result.all()}
    outside_ceiling = set(body.agent_ids) - global_ceiling
    if outside_ceiling:
        raise HTTPException(
            status_code=422,
            detail=f"Agents not in global ceiling for this role: {sorted(outside_ceiling)}",
        )

    # Capture old state for audit
    old_proj_result = await db.execute(
        select(ProjectRoleAgent.agent_id).where(
            ProjectRoleAgent.project_id == project_id,
            ProjectRoleAgent.role_id == role_id,
        )
    )
    old_agents = sorted(row[0] for row in old_proj_result.all())

    # Upsert override sentinel
    override_result = await db.execute(
        select(ProjectRoleAgentOverride).where(
            ProjectRoleAgentOverride.project_id == project_id,
            ProjectRoleAgentOverride.role_id == role_id,
        )
    )
    override = override_result.scalar_one_or_none()
    if override:
        override.updated_by = current_user["user_id"]
        override.updated_at = datetime.now(timezone.utc)
    else:
        db.add(ProjectRoleAgentOverride(
            id=str(uuid.uuid4()),
            project_id=project_id,
            role_id=role_id,
            updated_by=current_user["user_id"],
        ))

    # Replace child rows
    await db.execute(
        delete(ProjectRoleAgent).where(
            ProjectRoleAgent.project_id == project_id,
            ProjectRoleAgent.role_id == role_id,
        )
    )
    for agent_id in body.agent_ids:
        db.add(ProjectRoleAgent(
            id=str(uuid.uuid4()),
            project_id=project_id,
            role_id=role_id,
            agent_id=agent_id,
        ))

    # Audit
    db.add(AuditLog(
        user_id=current_user["user_id"],
        action="project_agent_access_updated",
        resource_type="project",
        resource_id=project_id,
        details={
            "role_id": role_id,
            "role_name": role.name,
            "old_agents": old_agents,
            "new_agents": sorted(body.agent_ids),
        },
        ip_address=request.client.host if request.client else None,
    ))

    await db.commit()

    effective = sorted(set(body.agent_ids) & global_ceiling)
    return {
        "project_id": project_id,
        "role_id": role_id,
        "role_name": role.name,
        "mode": "override",
        "global_agent_ids": sorted(global_ceiling),
        "project_agent_ids": sorted(body.agent_ids),
        "effective_agent_ids": effective,
    }


@router.delete("/{project_id}/agents/{role_id}")
async def reset_project_role_agents(
    project_id: str,
    role_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove project override — revert to inheriting global ceiling."""
    await _require_project_agent_management(db, project_id, current_user)

    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Delete children first, then sentinel
    await db.execute(
        delete(ProjectRoleAgent).where(
            ProjectRoleAgent.project_id == project_id,
            ProjectRoleAgent.role_id == role_id,
        )
    )
    await db.execute(
        delete(ProjectRoleAgentOverride).where(
            ProjectRoleAgentOverride.project_id == project_id,
            ProjectRoleAgentOverride.role_id == role_id,
        )
    )

    # Audit
    db.add(AuditLog(
        user_id=current_user["user_id"],
        action="project_agent_access_reset",
        resource_type="project",
        resource_id=project_id,
        details={"role_id": role_id, "role_name": role.name, "action": "reset_to_global"},
        ip_address=request.client.host if request.client else None,
    ))

    await db.commit()

    global_agents = await RoleService.get_role_agents(db, role.id)
    global_ids = sorted(ra.agent_id for ra in global_agents)

    return {
        "project_id": project_id,
        "role_id": role_id,
        "role_name": role.name,
        "mode": "inherit",
        "global_agent_ids": global_ids,
        "project_agent_ids": None,
        "effective_agent_ids": global_ids,
    }
