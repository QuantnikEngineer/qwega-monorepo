"""
Auth Schemas
============
Pydantic request/response models for authentication endpoints.
"""

from typing import List

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """Login payload."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    @field_validator("email")
    @classmethod
    def validate_wipro_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.endswith("@wipro.com"):
            raise ValueError("Must be a @wipro.com email address")
        return value


class UserProfile(BaseModel):
    """Authenticated user profile."""

    id: str
    email: str
    display_name: str = Field(alias="displayName")
    roles: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    org_id: str = Field(alias="orgId")

    model_config = {"populate_by_name": True}


class TokenResponse(BaseModel):
    """Token response payload."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    user: UserProfile = Field(..., description="Authenticated user profile")
    must_change_password: bool = Field(default=False)


class PasswordChangeRequest(BaseModel):
    """Password change request payload."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=12, description="New password (min 12 chars)")


class RefreshResponse(BaseModel):
    """Refresh response payload."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    """Self-service registration payload."""

    email: str = Field(..., min_length=5, description="User email address")
    display_name: str = Field(..., min_length=2, max_length=100, description="Display name")
    password: str = Field(..., min_length=12, description="Password (min 12 chars)")
    project_slug: str | None = Field(default=None, description="Optional project slug for direct-to-project registration")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email format")
        if not value.endswith("@wipro.com"):
            raise ValueError("Registration is restricted to @wipro.com email addresses")
        return value

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        return value.strip()
