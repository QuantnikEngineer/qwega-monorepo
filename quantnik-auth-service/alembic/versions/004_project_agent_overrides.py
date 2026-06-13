"""Add project_role_agent_overrides and project_role_agents tables

Per-project agent access delegation: PMs can customize which agents
each role has access to within their project context.

Revision ID: 004_project_agent_overrides
Revises: 003_add_ado_service
"""

from alembic import op
import sqlalchemy as sa

revision = "004_project_agent_overrides"
down_revision = "003_add_ado_service"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sentinel table: marks that a PM has customized a role's agents in a project
    op.create_table(
        "project_role_agent_overrides",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Text(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("updated_by", sa.Text(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "role_id", name="uq_project_role_override"),
    )

    # Child table: the actual agent selections per project-role
    op.create_table(
        "project_role_agents",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Text(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.UniqueConstraint("project_id", "role_id", "agent_id", name="uq_project_role_agent"),
    )

    # Index for fast lookup during JWT resolution
    op.create_index(
        "ix_project_role_agents_lookup",
        "project_role_agents",
        ["project_id", "role_id"],
    )
    op.create_index(
        "ix_project_role_agent_overrides_lookup",
        "project_role_agent_overrides",
        ["project_id", "role_id"],
    )

    # Grant project:manage_agents capability to PM role
    op.execute(
        """
        UPDATE roles
        SET capabilities = capabilities::jsonb || '"project:manage_agents"'::jsonb
        WHERE name = 'pm'
          AND NOT capabilities::jsonb ? 'project:manage_agents'
        """
    )


def downgrade() -> None:
    op.drop_index("ix_project_role_agent_overrides_lookup")
    op.drop_index("ix_project_role_agents_lookup")
    op.drop_table("project_role_agents")
    op.drop_table("project_role_agent_overrides")
