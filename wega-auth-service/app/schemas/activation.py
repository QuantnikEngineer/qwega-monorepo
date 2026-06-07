"""
Activation Schemas
==================
Request/response models for account activation flow.
"""

from pydantic import BaseModel, Field, field_validator


class ActivateAccountRequest(BaseModel):
    """User activates their account with the token and a new password."""

    token: str = Field(..., description="Activation token from URL")
    password: str = Field(..., min_length=12, description="New password")
    confirm_password: str = Field(..., description="Password confirmation")

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class ActivateAccountResponse(BaseModel):
    """Successful activation response."""

    message: str = "Account activated successfully"
    user_id: str


class ValidateTokenResponse(BaseModel):
    """Token validation probe — used by frontend before showing activation form."""

    valid: bool
    email: str | None = None
    display_name: str | None = None
    expired: bool = False
    used: bool = False
