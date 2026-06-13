"""
Agent Access API
================
Agent catalog and role-agent mapping management endpoints.
SuperAdmin only (admin:manage_agents capability).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.agent import AgentCatalog
from app.models.audit import AuditLog
from app.models.role import Role, RoleAgent

router = APIRouter(prefix="/api/agents", tags=["agents"])

SUPERADMIN_ROLE_NAME = "superadmin"


def _require_any_capability(user: dict, *capabilities: str):
    """Raise 403 unless the user has at least one of the given capabilities."""
    user_caps = user.get("capabilities", [])
    if any(cap in user_caps for cap in capabilities):
        return
    raise HTTPException(status_code=403, detail=f"Missing capability: {capabilities[0]}")


def _require_capability(user: dict, capability: str):
    if capability not in user.get("capabilities", []):
        raise HTTPException(status_code=403, detail=f"Missing capability: {capability}")


class UpdateRoleAgentsRequest(BaseModel):
    agent_ids: list[str] = Field(..., min_length=0, description="Agent IDs to assign")


@router.get("")
async def list_agent_catalog(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all agents from the catalog.

    Accessible to platform admins (admin:manage_agents) and project managers
    (project:manage_agents) who need the catalog to configure project-level access.
    """
    _require_any_capability(current_user, "admin:manage_agents", "project:manage_agents")
    result = await db.execute(
        select(AgentCatalog).order_by(AgentCatalog.category, AgentCatalog.name)
    )
    agents = result.scalars().all()
    return {
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "category": a.category,
                "is_active": a.is_active,
            }
            for a in agents
        ]
    }


@router.get("/roles/{role_id}")
async def get_role_agents(
    role_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List agent mappings for a specific role. Requires admin:manage_agents."""
    _require_capability(current_user, "admin:manage_agents")

    # Verify role exists
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    result = await db.execute(
        select(RoleAgent).where(RoleAgent.role_id == role_id)
    )
    role_agents = result.scalars().all()

    return {
        "role_id": role_id,
        "role_name": role.name,
        "agent_ids": sorted(ra.agent_id for ra in role_agents),
    }


@router.put("/roles/{role_id}")
async def update_role_agents(
    role_id: str,
    body: UpdateRoleAgentsRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Replace agent list for a role. Requires admin:manage_agents."""
    _require_capability(current_user, "admin:manage_agents")

    # Verify role exists
    role = await db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Block edits to superadmin role
    if role.name == SUPERADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=403,
            detail="SuperAdmin agent access cannot be modified",
        )

    # Validate all agent_ids exist in catalog
    if body.agent_ids:
        result = await db.execute(
            select(AgentCatalog.id).where(AgentCatalog.id.in_(body.agent_ids))
        )
        valid_ids = {row[0] for row in result.all()}
        invalid = set(body.agent_ids) - valid_ids
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown agent IDs: {sorted(invalid)}",
            )

    # Get current agents for audit log
    result = await db.execute(
        select(RoleAgent.agent_id).where(RoleAgent.role_id == role_id)
    )
    old_agents = sorted(row[0] for row in result.all())

    # Delete existing and insert new
    await db.execute(
        delete(RoleAgent).where(RoleAgent.role_id == role_id)
    )

    # Build agent name lookup from catalog
    if body.agent_ids:
        cat_result = await db.execute(
            select(AgentCatalog).where(AgentCatalog.id.in_(body.agent_ids))
        )
        catalog = {a.id: a.name for a in cat_result.scalars().all()}
    else:
        catalog = {}

    for agent_id in body.agent_ids:
        db.add(RoleAgent(
            id=str(uuid.uuid4()),
            role_id=role_id,
            agent_id=agent_id,
            agent_name=catalog.get(agent_id, agent_id),
        ))

    # Audit log
    db.add(AuditLog(
        user_id=current_user["user_id"],
        action="agent_access_updated",
        resource_type="role",
        resource_id=role_id,
        details={
            "role_name": role.name,
            "old_agents": old_agents,
            "new_agents": sorted(body.agent_ids),
        },
        ip_address=request.client.host if request.client else None,
    ))

    return {
        "role_id": role_id,
        "role_name": role.name,
        "agent_ids": sorted(body.agent_ids),
    }
