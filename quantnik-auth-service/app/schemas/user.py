"""
User Schemas
============
Pydantic models for user management endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class UserCreate(BaseModel):
    """Create-user request payload (legacy — uses temporary password)."""

    email: str = Field(..., description="User email (@wipro.com)")
    display_name: str = Field(..., min_length=1, description="User display name")
    role: str = Field(default="developer", description="Initial role name")
    temporary_password: str = Field(..., min_length=12, description="Temporary password for first login")

    @field_validator("email")
    @classmethod
    def validate_wipro_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.endswith("@wipro.com"):
            raise ValueError("Must be a @wipro.com email address")
        return value


# ---------------------------------------------------------------------------
# Admin user management schemas (Phase 4 — activation-based provisioning)
# ---------------------------------------------------------------------------


class RoleAssignmentInput(BaseModel):
    """Single role assignment (org-scoped only, Phase 5 D-03)."""

    role_name: str = Field(..., description="Role code: superadmin, pm, po_sm_ba, developer, tester, mlops")
    scope_type: str = Field(default="org", description="Always 'org' — flat scoping (D-03)")
    scope_id: str | None = Field(default=None, description="Deprecated — org-level only")


class AdminUserCreate(BaseModel):
    """Admin creates a new user with activation link."""

    email: str = Field(..., description="User email (@wipro.com required)")
    display_name: str = Field(..., min_length=1, description="Full name")
    role_assignments: list[RoleAssignmentInput] = Field(
        default_factory=lambda: [RoleAssignmentInput(role_name="developer", scope_type="org")],
    )

    @field_validator("email")
    @classmethod
    def validate_wipro_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.endswith("@wipro.com"):
            raise ValueError("Must be a @wipro.com email address")
        return value


class AdminUserUpdate(BaseModel):
    """Admin updates user details and role assignments."""

    display_name: str | None = Field(default=None, min_length=1)
    role_assignments: list[RoleAssignmentInput] | None = Field(default=None)
    status: str | None = Field(default=None, description="pending, active, suspended, deactivated")


class UserResponse(BaseModel):
    """User details response."""

    id: str
    email: str
    display_name: str = Field(alias="displayName")
    status: str
    org_id: str = Field(alias="orgId")
    created_at: str = Field(alias="createdAt")
    last_login_at: str | None = Field(default=None, alias="lastLoginAt")
    roles: list[dict] = Field(default_factory=list, description="[{role_name, scope_type, scope_id}]")

    model_config = {"populate_by_name": True, "from_attributes": True}


class UserListResponse(BaseModel):
    """Paginated user list."""

    users: list[UserResponse]
    total: int


class ActivationLinkResponse(BaseModel):
    """Response after creating user with activation link."""

    user: UserResponse
    activation_url: str
    expires_in_hours: int = 48
