"""
Role and UserRole Models
========================
Role definitions and user-role assignments.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(Base):
    """Role definition."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    agents = relationship("RoleAgent", back_populates="role", lazy="selectin")


class UserRole(Base):
    """User-to-role assignment."""

    __tablename__ = "user_roles"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(Text, ForeignKey("roles.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False, default="org")
    scope_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="admin_assigned")
    assigned_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("Role")


class RoleAgent(Base):
    """System-defined role-to-agent mapping."""

    __tablename__ = "role_agents"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    role_id: Mapped[str] = mapped_column(Text, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)

    role = relationship("Role", back_populates="agents")


class ProjectRoleAgentOverride(Base):
    """Sentinel: marks that a PM has customized agent access for a role in a project.

    Presence of a row means "use project_role_agents children, even if empty"
    (empty = deny all). Absence means "inherit global ceiling from role_agents".
    """

    __tablename__ = "project_role_agent_overrides"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(Text, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        {"extend_existing": True},
    )

    # Unique constraint added via migration: UNIQUE(project_id, role_id)


class ProjectRoleAgent(Base):
    """Per-project role-to-agent override (child of ProjectRoleAgentOverride).

    PM selects which agents from the global ceiling are available for a role
    within their project. Effective = intersection(global, project).
    """

    __tablename__ = "project_role_agents"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[str] = mapped_column(Text, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        {"extend_existing": True},
    )

    # Unique constraint added via migration: UNIQUE(project_id, role_id, agent_id)
