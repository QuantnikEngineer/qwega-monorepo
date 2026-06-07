"""
ServiceRegistry Model
=====================
Platform-level service catalog. SuperAdmin controls which tools are available.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ServiceRegistry(Base):
    """Platform service definition."""

    __tablename__ = "service_registry"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    tool_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
