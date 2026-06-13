"""
ProjectSecret Model
===================
Encrypted secret storage for project tool integrations.
Secrets (PAT tokens, API keys) are Fernet-encrypted at rest.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProjectSecret(Base):
    """Encrypted project secret (PAT tokens, API keys)."""

    __tablename__ = "project_secrets"
    __table_args__ = (
        UniqueConstraint("project_id", "service_id", "secret_key", name="uq_project_service_secret"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(Text, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    service_id: Mapped[str] = mapped_column(Text, ForeignKey("service_registry.id"), nullable=False)
    secret_key: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
