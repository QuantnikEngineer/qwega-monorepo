"""
Role Service
============
Role listing and capability resolution service.
Resolves a user's role assignments into flat capability sets (Phase 5).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.role import Role, RoleAgent, UserRole, ProjectRoleAgent, ProjectRoleAgentOverride

logger = get_logger(__name__)


class RoleService:
    """Role listing and flat capability resolution."""

    @staticmethod
    async def get_all_roles(db: AsyncSession) -> list[Role]:
        """Return every role ordered alphabetically."""
        result = await db.execute(select(Role).order_by(Role.name))
        return list(result.scalars().all())

    @staticmethod
    async def get_role_by_name(db: AsyncSession, name: str) -> Role | None:
        """Find a single role by its unique name."""
        result = await db.execute(select(Role).where(Role.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_roles(db: AsyncSession, user_id: str) -> list[UserRole]:
        """Return all UserRole assignments for a user."""
        result = await db.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_role_agents(db: AsyncSession, role_id: str) -> list[RoleAgent]:
        """Return all agent mappings for a role."""
        result = await db.execute(
            select(RoleAgent).where(RoleAgent.role_id == role_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def resolve_flat_capabilities(db: AsyncSession, user_id: str) -> dict:
        """Resolve user's roles into flat capabilities + allowed agents for JWT.

        Phase 5 simplified model — flat org-level capabilities for JWT.
        NOTE: With multi-project support, project-scoped capabilities are
        still flattened here for the JWT. Per-project capability checks
        should use ProjectService.has_project_capability() directly.
        """
        user_roles = await RoleService.get_user_roles(db, user_id)
        roles: list[str] = []
        capabilities: set[str] = set()
        agents: set[str] = set()
        active_agent_ids = await RoleService._get_active_agent_ids(db)

        for ur in user_roles:
            role = await db.get(Role, ur.role_id)
            if not role:
                continue
            roles.append(role.name)
            capabilities.update(role.capabilities or [])
            role_agents = await RoleService.get_role_agents(db, ur.role_id)
            agents.update(
                ra.agent_id for ra in role_agents
                if ra.agent_id in active_agent_ids
            )

        capabilities.add("settings:manage_own")  # Universal for all authenticated users

        return {
            "roles": roles,
            "capabilities": sorted(capabilities),
            "allowed_agents": sorted(agents),
        }

    @staticmethod
    async def _get_active_agent_ids(db: AsyncSession) -> set[str]:
        """Return IDs of all active agents from the catalog."""
        from app.models.agent import AgentCatalog
        result = await db.execute(
            select(AgentCatalog.id).where(AgentCatalog.is_active == True)  # noqa: E712
        )
        return {row[0] for row in result.all()}

    @staticmethod
    async def resolve_project_allowed_agents(
        db: AsyncSession, user_id: str, project_id: str,
    ) -> list[str]:
        """Resolve effective agents for a user in a specific project context.

        For each of the user's project-scoped roles in this project:
          - If a ProjectRoleAgentOverride exists → use ProjectRoleAgent rows (intersection with global)
          - Otherwise → use global RoleAgent rows
        Returns the union across all applicable roles, filtered to active agents.
        """
        active_ids = await RoleService._get_active_agent_ids(db)

        # Get user's project-scoped roles for this project
        user_roles = await db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.scope_type == "project",
                UserRole.scope_id == project_id,
            )
        )
        project_user_roles = list(user_roles.scalars().all())

        agents: set[str] = set()

        for ur in project_user_roles:
            # Global ceiling for this role
            global_result = await db.execute(
                select(RoleAgent.agent_id).where(RoleAgent.role_id == ur.role_id)
            )
            global_agents = {row[0] for row in global_result.all()}

            # Check if project override exists
            override_result = await db.execute(
                select(ProjectRoleAgentOverride).where(
                    ProjectRoleAgentOverride.project_id == project_id,
                    ProjectRoleAgentOverride.role_id == ur.role_id,
                )
            )
            override = override_result.scalar_one_or_none()

            if override:
                # PM has customized: use project selection ∩ global ceiling
                proj_result = await db.execute(
                    select(ProjectRoleAgent.agent_id).where(
                        ProjectRoleAgent.project_id == project_id,
                        ProjectRoleAgent.role_id == ur.role_id,
                    )
                )
                proj_agents = {row[0] for row in proj_result.all()}
                effective = proj_agents & global_agents
            else:
                # No override: inherit global ceiling
                effective = global_agents

            agents.update(effective & active_ids)

        # Also include agents from org-scoped roles (not subject to project overrides)
        org_roles = await db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.scope_type.in_(["org", "platform"]),
            )
        )
        for ur in org_roles.scalars().all():
            role_agents = await RoleService.get_role_agents(db, ur.role_id)
            agents.update(
                ra.agent_id for ra in role_agents if ra.agent_id in active_ids
            )

        return sorted(agents)

    @staticmethod
    async def resolve_all_project_agents(
        db: AsyncSession, user_id: str, project_ids: list[str],
    ) -> dict[str, list[str]]:
        """Resolve allowed agents for each project. Used for JWT enrichment."""
        result = {}
        for pid in project_ids:
            result[pid] = await RoleService.resolve_project_allowed_agents(db, user_id, pid)
        return result

    # DEPRECATED — Phase 5 uses resolve_flat_capabilities
    @staticmethod
    async def resolve_scoped_capabilities(db: AsyncSession, user_id: str) -> dict:
        """
        Resolve user's role assignments into scoped capability structure for JWT (D-17).

        Scope hierarchy: Platform > Org > Project > Self
        Returns dict with keys:
            platform_capabilities, org_capabilities, project_roles,
            self_capabilities, flat_roles, flat_capabilities
        """
        user_roles = await RoleService.get_user_roles(db, user_id)
        platform_capabilities: set[str] = set()
        org_capabilities: set[str] = set()
        project_roles: dict[str, list[str]] = {}
        self_capabilities: set[str] = set()
        flat_roles: list[str] = []
        flat_capabilities: set[str] = set()

        for ur in user_roles:
            role = await db.get(Role, ur.role_id)
            if not role:
                continue
            flat_roles.append(role.name)
            caps = role.capabilities or []
            flat_capabilities.update(caps)

            if ur.scope_type == "platform":
                platform_capabilities.update(caps)
            elif ur.scope_type == "org":
                org_capabilities.update(caps)
            elif ur.scope_type == "project" and ur.scope_id:
                project_roles.setdefault(ur.scope_id, []).append(role.name)
            else:
                self_capabilities.update(caps)

        # Self capabilities are always present for any authenticated user
        self_capabilities.add("settings:manage_own")

        return {
            "platform_capabilities": sorted(platform_capabilities),
            "org_capabilities": sorted(org_capabilities),
            "project_roles": project_roles,
            "self_capabilities": sorted(self_capabilities),
            "flat_roles": flat_roles,
            "flat_capabilities": sorted(flat_capabilities),
        }
