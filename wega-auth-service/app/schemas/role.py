"""
Role Schemas
============
Role and capability response schemas for admin panel.
"""

from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    """Single role with its capability list."""

    id: str
    name: str
    description: str | None = None
    capabilities: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CapabilityResponse(BaseModel):
    """Single capability descriptor."""

    name: str
    description: str = ""
    category: str = ""


class RoleListResponse(BaseModel):
    """All roles."""

    roles: list[RoleResponse]


class CapabilityMatrixResponse(BaseModel):
    """Capability matrix grouped by category."""

    categories: dict[str, list[dict]]  # category -> [{name, roles: [role_names]}]

    model_config = {"from_attributes": True}


class RoleAgentResponse(BaseModel):
    """Single role-to-agent mapping."""

    role_id: str
    agent_id: str
    agent_name: str

    model_config = {"from_attributes": True}


class MyAgentsResponse(BaseModel):
    """Agent list for the requesting user's role."""

    agents: list[str] = Field(default_factory=list, description="List of allowed agent IDs")


class AgentCatalogResponse(BaseModel):
    """Agent catalog entry."""

    id: str
    name: str
    description: str | None = None
    category: str | None = None
    is_active: bool = True

    model_config = {"from_attributes": True}
