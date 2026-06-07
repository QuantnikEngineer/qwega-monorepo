"""Stub for SharePoint client-secret migration (already applied in QA/stage).

This migration originally added SharePoint-related columns to the service
registry.  The schema changes are already present in deployed environments,
so upgrade/downgrade are no-ops — the file exists solely to satisfy Alembic's
revision graph when the DB reports this as its current head.

Revision ID: 005_sharepoint_clientsecret
Revises: 004_project_agent_overrides
"""

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "005_sharepoint_clientsecret"
down_revision = "004_project_agent_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Already applied in QA/stage — no-op stub.
    pass


def downgrade() -> None:
    pass
