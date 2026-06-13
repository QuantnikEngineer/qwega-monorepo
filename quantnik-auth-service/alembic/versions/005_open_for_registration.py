"""Add open_for_registration flag to projects table

Allows projects to accept self-service user registration.
When True, users can register directly into the project with a
designated role (e.g. PO/SM/BA) via the registration page.

Revision ID: 005_open_for_registration
Revises: 004_project_agent_overrides
"""

from alembic import op
import sqlalchemy as sa

revision = "005_open_for_registration"
down_revision = "005_sharepoint_clientsecret"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("open_for_registration", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("projects", "open_for_registration")
