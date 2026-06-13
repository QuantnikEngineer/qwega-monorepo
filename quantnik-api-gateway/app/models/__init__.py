"""Gateway API response models."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Canonical error payload for gateway responses."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    request_id: str = Field(..., description="Request correlation id")


class HealthResponse(BaseModel):
    """Gateway health response payload."""

    status: str
    service: str
    version: str


class JWKSResponse(BaseModel):
    """JWKS contract response."""

    keys: list[dict]
