"""
Project Service
===============
Project CRUD, membership management, and project-scoped authorization.
"""

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.org import Org
from app.models.project import Project
from app.models.role import Role, UserRole
from app.models.user import User

logger = get_logger(__name__)


def _slugify(name: str) -> str:
    """Convert project name to URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


class ProjectService:
    """Project lifecycle and membership operations."""

    @staticmethod
    async def get_user_projects(
        db: AsyncSession, user_id: str, org_id: str,
    ) -> list[Project]:
        """Return active projects the user belongs to (creator OR project-scoped member).

        Used by login, refresh, and /me to resolve multi-project context.
        Results are ordered: created-by projects first, then by name.
        """
        # Projects where user is creator
        created_stmt = (
            select(Project)
            .where(
                Project.org_id == org_id,
                Project.is_active == True,
                Project.created_by == user_id,
            )
        )
        # Projects where user has a project-scoped role
        member_stmt = (
            select(Project)
            .where(
                Project.org_id == org_id,
                Project.is_active == True,
                Project.id.in_(
                    select(UserRole.scope_id).where(
                        UserRole.user_id == user_id,
                        UserRole.scope_type == "project",
                        UserRole.scope_id.isnot(None),
                    )
                ),
            )
        )
        created_result = await db.execute(created_stmt)
        member_result = await db.execute(member_stmt)

        # Deduplicate (creator who is also a member) preserving creator-first order
        seen: set[str] = set()
        projects: list[Project] = []
        for p in created_result.scalars().all():
            if p.id not in seen:
                seen.add(p.id)
                projects.append(p)
        for p in sorted(member_result.scalars().all(), key=lambda x: x.name):
            if p.id not in seen:
                seen.add(p.id)
                projects.append(p)
        return projects

    @staticmethod
    async def get_user_project_roles(
        db: AsyncSession, user_id: str, projects: list[Project],
    ) -> dict[str, list[str]]:
        """Build project_id → [role_name, ...] mapping for a user's projects."""
        if not projects:
            return {}
        project_ids = [p.id for p in projects]
        result = await db.execute(
            select(UserRole)
            .where(
                UserRole.user_id == user_id,
                UserRole.scope_type == "project",
                UserRole.scope_id.in_(project_ids),
            )
            .options(selectinload(UserRole.role))
        )
        mapping: dict[str, list[str]] = {}
        for ur in result.scalars().all():
            pid = ur.scope_id
            role_name = ur.role.name if ur.role else str(ur.role_id)
            mapping.setdefault(pid, []).append(role_name)
        return mapping

    @staticmethod
    async def create_project(
        db: AsyncSession,
        name: str,
        org_id: str,
        created_by: str,
        description: str | None = None,
        slug: str | None = None,
        open_for_registration: bool = False,
    ) -> Project:
        """Create a new project within an organization (multi-project model)."""
        slug = slug or _slugify(name)
        if not slug:
            raise ValueError("Project name must produce a valid slug")

        # Check slug uniqueness within org
        existing = await db.execute(
            select(Project).where(
                Project.org_id == org_id,
                Project.slug == slug,
                Project.is_active == True,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"A project with slug '{slug}' already exists in this organization")

        project = Project(
            name=name,
            slug=slug,
            org_id=org_id,
            description=description,
            created_by=created_by,
            is_active=True,
            open_for_registration=open_for_registration,
        )
        db.add(project)
        await db.flush()
        logger.info("[project] Created", project_id=project.id, name=name, slug=slug, by=created_by)
        return project

    @staticmethod
    async def get_project(db: AsyncSession, project_id: str) -> Project | None:
        """Get a project by ID (active only)."""
        result = await db.execute(
            select(Project).where(Project.id == project_id, Project.is_active == True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_projects(db: AsyncSession, org_id: str) -> list[Project]:
        """List all active projects in an organization."""
        result = await db.execute(
            select(Project)
            .where(Project.org_id == org_id, Project.is_active == True)
            .order_by(Project.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_open_registration_project(
        db: AsyncSession, slug: str, org_id: str,
    ) -> Project | None:
        """Fetch an active project by slug that accepts self-registration."""
        result = await db.execute(
            select(Project).where(
                Project.org_id == org_id,
                Project.slug == slug,
                Project.is_active == True,
                Project.open_for_registration == True,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_project(
        db: AsyncSession,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        open_for_registration: bool | None = None,
    ) -> Project:
        """Update project details."""
        project = await ProjectService.get_project(db, project_id)
        if not project:
            raise ValueError("Project not found")

        if name is not None:
            project.name = name
            project.slug = _slugify(name)
            # Check slug uniqueness within org
            existing = await db.execute(
                select(Project).where(
                    Project.org_id == project.org_id,
                    Project.slug == project.slug,
                    Project.is_active == True,
                    Project.id != project_id,
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"A project with slug '{project.slug}' already exists")

        if description is not None:
            project.description = description

        if open_for_registration is not None:
            project.open_for_registration = open_for_registration

        project.updated_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info("[project] Updated", project_id=project_id)
        return project

    @staticmethod
    async def deactivate_project(db: AsyncSession, project_id: str) -> Project:
        """Soft-delete a project."""
        project = await ProjectService.get_project(db, project_id)
        if not project:
            raise ValueError("Project not found")

        project.is_active = False
        project.updated_at = datetime.now(timezone.utc)
        await db.flush()
        logger.info("[project] Deactivated", project_id=project_id)
        return project

    # ── Membership (via user_roles with scope_type="project") ────

    @staticmethod
    async def add_member(
        db: AsyncSession,
        project_id: str,
        user_id: str,
        role_name: str,
        added_by: str,
    ) -> UserRole:
        """Add a user to a project with a specific role."""
        # Validate project exists
        project = await ProjectService.get_project(db, project_id)
        if not project:
            raise ValueError("Project not found")

        # Validate user exists and is in same org
        user = await db.execute(select(User).where(User.id == user_id))
        user_obj = user.scalar_one_or_none()
        if not user_obj:
            raise ValueError("User not found")
        if user_obj.org_id != project.org_id:
            raise ValueError("User must belong to the same organization as the project")

        # Validate role exists
        role_result = await db.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if not role:
            raise ValueError(f"Role '{role_name}' not found")

        # Check if user already has this role in this project
        existing = await db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
                UserRole.scope_type == "project",
                UserRole.scope_id == project_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"User already has role '{role_name}' in this project")

        user_role = UserRole(
            user_id=user_id,
            role_id=role.id,
            scope_type="project",
            scope_id=project_id,
            source="project_assigned",
            assigned_by=added_by,
        )
        db.add(user_role)
        await db.flush()
        logger.info(
            "[project] Member added",
            project_id=project_id, user_id=user_id, role=role_name, by=added_by,
        )
        return user_role

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        project_id: str,
        user_id: str,
    ) -> int:
        """Remove all project-scoped roles for a user in a project. Returns count removed."""
        result = await db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.scope_type == "project",
                UserRole.scope_id == project_id,
            )
        )
        roles = list(result.scalars().all())
        for r in roles:
            await db.delete(r)
        await db.flush()
        logger.info("[project] Member removed", project_id=project_id, user_id=user_id, count=len(roles))
        return len(roles)

    @staticmethod
    async def list_members(db: AsyncSession, project_id: str) -> list[dict]:
        """List project members with their project-scoped roles."""
        result = await db.execute(
            select(UserRole)
            .where(
                UserRole.scope_type == "project",
                UserRole.scope_id == project_id,
            )
            .options(selectinload(UserRole.role))
        )
        user_roles = list(result.scalars().all())

        # Group by user
        members: dict[str, dict] = {}
        user_ids = list({ur.user_id for ur in user_roles})

        if user_ids:
            users_result = await db.execute(
                select(User).where(User.id.in_(user_ids))
            )
            users_map = {u.id: u for u in users_result.scalars().all()}
        else:
            users_map = {}

        for ur in user_roles:
            uid = ur.user_id
            if uid not in members:
                user = users_map.get(uid)
                members[uid] = {
                    "userId": uid,
                    "email": user.normalized_email if user else "",
                    "displayName": user.display_name if user else "",
                    "roles": [],
                }
            members[uid]["roles"].append({
                "roleName": ur.role.name if ur.role else ur.role_id,
                "assignedAt": ur.assigned_at.isoformat() if ur.assigned_at else None,
            })

        return list(members.values())

    # ── Authorization helpers ────────────────────────────────────

    @staticmethod
    async def is_project_member(db: AsyncSession, project_id: str, user_id: str) -> bool:
        """Check if user has any project-scoped role in this project."""
        result = await db.execute(
            select(func.count(UserRole.id)).where(
                UserRole.user_id == user_id,
                UserRole.scope_type == "project",
                UserRole.scope_id == project_id,
            )
        )
        return (result.scalar() or 0) > 0

    @staticmethod
    async def has_project_capability(
        db: AsyncSession,
        project_id: str,
        user_id: str,
        capability: str,
    ) -> bool:
        """Check if user has a specific capability in a project context."""
        result = await db.execute(
            select(UserRole)
            .where(
                UserRole.user_id == user_id,
                UserRole.scope_type == "project",
                UserRole.scope_id == project_id,
            )
            .options(selectinload(UserRole.role))
        )
        for ur in result.scalars().all():
            if ur.role and capability in (ur.role.capabilities or []):
                return True
        return False
