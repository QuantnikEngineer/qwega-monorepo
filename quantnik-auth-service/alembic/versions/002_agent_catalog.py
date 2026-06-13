"""agent_catalog

Create agent_catalog table, seed platform agents, add FK + unique
constraints on role_agents, and grant admin:manage_agents capability
to the superadmin role.

Phase A of Agent Access Management.

Revision ID: 002_agent_catalog
Revises: 6f360649fc0f
Create Date: 2025-07-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_agent_catalog"
down_revision: Union[str, Sequence[str], None] = "6f360649fc0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# All platform agents to seed
AGENTS = {
    "brd-generator": ("BRD Generator", "Generates Business Requirements Documents from transcripts", "planning"),
    "brd-summary": ("BRD Summary", "Summarizes BRD documents", "planning"),
    "user-story-generator": ("User Stories Creator", "Creates user stories from BRD", "analysis"),
    "user-story-validator": ("User Stories Validator", "Validates user stories against BRD", "analysis"),
    "test-case": ("Test Case", "Generates test cases from user stories", "testing"),
    "test-script": ("Test Script", "Generates test scripts from test cases", "testing"),
    "test-data": ("Test Data", "Generates test data for test cases", "testing"),
    "test-data-generator": ("Test Data Generator", "Advanced test data generation", "testing"),
    "end-to-end-test": ("End-to-End Test", "Generates E2E test scenarios", "testing"),
    "user-manual": ("User Manual", "Generates user documentation", "build"),
    "code-assistant": ("Code Analysis", "AI-powered code assistant", "build"),
}

SUPERADMIN_ROLE_ID = "00000000-0000-4000-8000-000000000010"


def upgrade() -> None:
    # 1. Create agent_catalog table (IF NOT EXISTS — init_db may have created it)
    conn = op.get_bind()
    table_exists = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'agent_catalog')"
    )).scalar()
    if not table_exists:
        op.create_table(
            "agent_catalog",
            sa.Column("id", sa.String(100), primary_key=True),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(50), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )

    # 2. Seed agents (MUST happen before FK is added)
    #    Use raw SQL with NOW() to handle both init_db and migration-created tables
    for aid, (name, desc, cat) in AGENTS.items():
        conn.execute(sa.text(
            "INSERT INTO agent_catalog (id, name, description, category, is_active, created_at) "
            "VALUES (:id, :name, :desc, :cat, true, NOW()) ON CONFLICT (id) DO NOTHING"
        ), {"id": aid, "name": name, "desc": desc, "cat": cat})

    # 3. Unique constraint on role_agents(role_id, agent_id) — idempotent
    uq_exists = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_role_agents_role_agent')"
    )).scalar()
    if not uq_exists:
        op.create_unique_constraint(
            "uq_role_agents_role_agent", "role_agents", ["role_id", "agent_id"]
        )

    # 4. FK role_agents.agent_id → agent_catalog.id — idempotent
    fk_exists = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_role_agents_agent_catalog')"
    )).scalar()
    if not fk_exists:
        op.create_foreign_key(
            "fk_role_agents_agent_catalog",
            "role_agents", "agent_catalog",
            ["agent_id"], ["id"],
        )

    # 5. Grant admin:manage_agents to superadmin
    op.execute(sa.text("""
        UPDATE roles
        SET capabilities = capabilities::jsonb || '"admin:manage_agents"'::jsonb
        WHERE id = '00000000-0000-4000-8000-000000000010'
        AND NOT capabilities::jsonb @> '"admin:manage_agents"'::jsonb
    """))


def downgrade() -> None:
    # Remove FK and unique constraint
    op.drop_constraint("fk_role_agents_agent_catalog", "role_agents", type_="foreignkey")
    op.drop_constraint("uq_role_agents_role_agent", "role_agents", type_="unique")

    # Drop agent_catalog table
    op.drop_table("agent_catalog")

    # Remove admin:manage_agents from superadmin
    op.execute(sa.text("""
        UPDATE roles
        SET capabilities = (
            SELECT jsonb_agg(elem)
            FROM jsonb_array_elements(capabilities::jsonb) AS elem
            WHERE elem != '"admin:manage_agents"'::jsonb
        )
        WHERE id = '00000000-0000-4000-8000-000000000010'
        AND capabilities::jsonb @> '"admin:manage_agents"'::jsonb
    """))
