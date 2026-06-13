"""Add ADO service to service registry

Stub migration — this was applied by a parallel branch. We include the
revision file so that Alembic can locate the current production DB head
and chain subsequent migrations from it.

Revision ID: 003_add_ado_service
Revises: 002_agent_catalog
"""

from alembic import op

revision = "003_add_ado_service"
down_revision = "002_agent_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Already applied in production — no-op stub.
    pass


def downgrade() -> None:
    pass
