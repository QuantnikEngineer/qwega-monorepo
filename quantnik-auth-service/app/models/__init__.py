"""
ORM Models
==========
SQLAlchemy ORM models for the auth database.
Import all models here so Alembic can discover them.
"""

from app.models.activation_token import ActivationToken
from app.models.agent import AgentCatalog
from app.models.audit import AuditLog
from app.models.auth_method import AuthMethod, AuthMethodType
from app.models.org import Org
from app.models.project import Project
from app.models.project_secret import ProjectSecret
from app.models.project_settings import ProjectSettings
from app.models.role import Role, RoleAgent, UserRole, ProjectRoleAgent, ProjectRoleAgentOverride
from app.models.service_registry import ServiceRegistry
from app.models.session import Session
from app.models.user import User, UserStatus

__all__ = [
    "ActivationToken",
    "AgentCatalog",
    "Org",
    "Project",
    "ProjectSecret",
    "ProjectSettings",
    "User",
    "UserStatus",
    "AuthMethod",
    "AuthMethodType",
    "Session",
    "Role",
    "RoleAgent",
    "UserRole",
    "ProjectRoleAgent",
    "ProjectRoleAgentOverride",
    "AuditLog",
    "ServiceRegistry",
]
