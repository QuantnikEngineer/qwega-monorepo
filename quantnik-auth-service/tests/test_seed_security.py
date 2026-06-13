"""Regression tests for seeded credential hardening."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INITIAL_MIGRATION = ROOT / "alembic" / "versions" / "001_unified_schema.py"
KNOWN_SEEDED_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=1$Al4TmsvWORVcqXwgYM/RLA$RjvE6McnPw3vpSm2tSGjzO0ttBAZDuVpn4q2xL+lp04"
)


def test_initial_migration_has_no_known_admin_hash():
    content = INITIAL_MIGRATION.read_text(encoding="utf-8")
    assert KNOWN_SEEDED_HASH not in content
