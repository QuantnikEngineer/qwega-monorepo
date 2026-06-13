"""
Roles API
=========
Role listing and capability matrix endpoints for admin panel.
"""

from collections import defaultdict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.role import MyAgentsResponse, RoleResponse
from app.services.role_service import RoleService

router = APIRouter(prefix="/api/roles", tags=["roles"])

# Capability name prefix → human-readable category
_CAPABILITY_CATEGORIES: dict[str, str] = {
    "platform": "Platform",
    "org": "Organization",
    "project": "Project",
    "team": "Team",
    "sdlc": "SDLC",
    "integration": "Integrations",
    "settings": "Settings",
    "admin": "Admin",
}


def _capability_category(cap_name: str) -> str:
    """Derive category from capability name prefix."""
    prefix = cap_name.split(":")[0] if ":" in cap_name else cap_name
    return _CAPABILITY_CATEGORIES.get(prefix, "Other")


@router.get("")
async def list_roles(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all roles with capabilities."""
    roles = await RoleService.get_all_roles(db)
    return {
        "roles": [
            RoleResponse.model_validate(r).model_dump()
            for r in roles
        ],
    }


@router.get("/agents")
async def get_my_agents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return allowed agent IDs for the requesting user's role(s).

    System-defined mapping — agents are role-inherent (D-10/D-13).
    """
    user_roles = await RoleService.get_user_roles(db, current_user["user_id"])
    agents: set[str] = set()
    for ur in user_roles:
        role_agents = await RoleService.get_role_agents(db, ur.role_id)
        agents.update(ra.agent_id for ra in role_agents)
    return {"agents": sorted(agents)}


@router.get("/capabilities")
async def get_capabilities(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return capability matrix organized by category."""
    roles = await RoleService.get_all_roles(db)

    # Build: capability -> set of role names that have it
    cap_roles: dict[str, set[str]] = defaultdict(set)
    for role in roles:
        for cap in (role.capabilities or []):
            cap_roles[cap].add(role.name)

    # Group by category
    categories: dict[str, list[dict]] = defaultdict(list)
    for cap_name in sorted(cap_roles.keys()):
        category = _capability_category(cap_name)
        categories[category].append({
            "name": cap_name,
            "roles": sorted(cap_roles[cap_name]),
        })

    return JSONResponse(
        content={"categories": dict(categories)},
        headers={"Cache-Control": "public, max-age=300"},
    )
