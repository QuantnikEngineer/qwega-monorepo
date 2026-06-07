"""grant_pm_po_all_agents

Grant PM and PO/SM/BA roles access to the full agent catalog (same as
SuperAdmin).  Previously PM had 3 agents and PO/SM/BA had 4; both now
get all 11.

Revision ID: 6f360649fc0f
Revises: 001_unified_schema
Create Date: 2026-04-22 14:13:44.106956

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f360649fc0f"
down_revision: Union[str, Sequence[str], None] = "001_unified_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Constants (must match 001_unified_schema seed IDs)
# ---------------------------------------------------------------------------
PM_ROLE_ID = "00000000-0000-4000-8000-000000000012"
POSMBA_ROLE_ID = "00000000-0000-4000-8000-000000000013"

ALL_AGENTS = {
    "brd-generator": "BRD Generator",
    "brd-summary": "BRD Summary",
    "user-story-generator": "User Stories Creator",
    "user-story-validator": "User Stories Validator",
    "test-case": "Test Case",
    "test-script": "Test Script",
    "test-data": "Test Data",
    "test-data-generator": "Test Data Generator",
    "end-to-end-test": "End-to-End Test",
    "user-manual": "User Manual",
    "code-assistant": "Code Analysis",
}

# Agents already seeded in 001 — only insert the missing ones.
PM_EXISTING = {"brd-generator", "brd-summary", "user-story-generator"}
POSMBA_EXISTING = {"brd-generator", "brd-summary", "user-story-generator", "user-manual"}

role_agents_t = sa.table(
    "role_agents",
    sa.column("id", sa.Text),
    sa.column("role_id", sa.Text),
    sa.column("agent_id", sa.String),
    sa.column("agent_name", sa.Text),
)


def _rows(role_id: str, existing: set[str], id_start: int) -> list[dict]:
    missing = sorted(set(ALL_AGENTS) - existing)
    return [
        {
            "id": f"00000000-0000-4000-8000-20000000{id_start + i:04d}",
            "role_id": role_id,
            "agent_id": aid,
            "agent_name": ALL_AGENTS[aid],
        }
        for i, aid in enumerate(missing)
    ]


def upgrade() -> None:
    pm_rows = _rows(PM_ROLE_ID, PM_EXISTING, 1)
    po_rows = _rows(POSMBA_ROLE_ID, POSMBA_EXISTING, 21)
    conn = op.get_bind()
    for row in pm_rows + po_rows:
        conn.execute(sa.text(
            "INSERT INTO role_agents (id, role_id, agent_id, agent_name) "
            "VALUES (:id, :role_id, :agent_id, :agent_name) "
            "ON CONFLICT (id) DO NOTHING"
        ), row)


def downgrade() -> None:
    # Remove the rows we added (identified by the 2000xxxx ID series).
    op.execute(
        sa.text(
            "DELETE FROM role_agents WHERE id LIKE '00000000-0000-4000-8000-2000000000%'"
        )
    )
