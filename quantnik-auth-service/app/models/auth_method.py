"""
AuthMethod Model
================
Supports multiple auth methods per user (password now, SSO future).
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuthMethodType(str, enum.Enum):
    """Auth method variants."""

    PASSWORD = "password"
    SSO_OIDC = "sso_oidc"
    SSO_SAML = "sso_saml"


class AuthMethod(Base):
    """Linked authentication method for a user."""

    __tablename__ = "auth_methods"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    method_type: Mapped[AuthMethodType] = mapped_column(SAEnum(AuthMethodType), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="local")
    provider_subject_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    credential_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failed_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lockout_backoff_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="auth_methods")
