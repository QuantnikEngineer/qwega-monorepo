"""Account lockout and backoff tests for ENFC-06."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

from app.models.auth_method import AuthMethod

TEST_DB_FILE = Path("./test_wega_auth.db")
TEST_DB_URL = "sqlite+aiosqlite:///./test_wega_auth.db"


def _alembic_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    return config


@pytest.mark.migration
@pytest.mark.skipif(
    True,  # SQLite lacks ON CONFLICT DO NOTHING support used in migrations
    reason="Migration test requires PostgreSQL (ON CONFLICT syntax)",
)
def test_migration_adds_lockout_columns() -> None:
    """Migration creates persistent lockout columns."""
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()

    command.upgrade(_alembic_config(), "head")

    engine = create_engine("sqlite:///./test_wega_auth.db")
    inspector = inspect(engine)
    auth_method_columns = {column["name"] for column in inspector.get_columns("auth_methods")}
    assert "failed_login_attempts" in auth_method_columns
    assert "last_failed_login_at" in auth_method_columns
    assert "locked_until" in auth_method_columns
    assert "lockout_backoff_level" in auth_method_columns
    model_columns = set(AuthMethod.__table__.columns.keys())
    assert {"failed_login_attempts", "last_failed_login_at", "locked_until", "lockout_backoff_level"} <= model_columns
    engine.dispose()

    command.downgrade(_alembic_config(), "base")
    if TEST_DB_FILE.exists():
        TEST_DB_FILE.unlink()


@pytest.mark.integration
class TestAuthLockout:
    async def test_failed_logins_lock_account_after_threshold(self, test_client, async_session, seed_user):
        _, password = seed_user
        from app.core.config import settings

        threshold = settings.lockout_threshold
        lockout_seconds = settings.lockout_window_minutes * 60

        for attempt in range(1, threshold):
            response = await test_client.post(
                "/api/auth/login",
                json={"email": "test.user@wipro.com", "password": f"wrong-{attempt}"},
            )
            assert response.status_code == 401
            detail = response.json()["detail"]
            assert detail["error"] == "invalid_credentials"

        # The threshold-th attempt triggers lockout
        final = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": "wrong-final"},
        )
        assert final.status_code == 401
        final_detail = final.json()["detail"]
        assert final_detail["error"] == "invalid_credentials"
        assert final_detail["retry_after_seconds"] == lockout_seconds

        auth_method = (
            await async_session.execute(
                select(AuthMethod).where(AuthMethod.user.has(normalized_email="test.user@wipro.com"))
            )
        ).scalar_one()
        assert auth_method.failed_login_attempts == threshold
        assert auth_method.locked_until is not None
        assert auth_method.locked_until > datetime.now(timezone.utc)

        locked_valid = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        assert locked_valid.status_code == 401
        assert locked_valid.json()["detail"]["error"] == "invalid_credentials"

    async def test_lockout_expires_and_success_resets_counters(self, test_client, async_session, seed_user):
        _, password = seed_user
        from app.core.config import settings

        threshold = settings.lockout_threshold

        for attempt in range(threshold):
            await test_client.post(
                "/api/auth/login",
                json={"email": "test.user@wipro.com", "password": f"wrong-{attempt}"},
            )

        auth_method = (
            await async_session.execute(
                select(AuthMethod).where(AuthMethod.user.has(normalized_email="test.user@wipro.com"))
            )
        ).scalar_one()
        auth_method.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await async_session.commit()

        response = await test_client.post(
            "/api/auth/login",
            json={"email": "test.user@wipro.com", "password": password},
        )
        assert response.status_code == 200

        refreshed = (
            await async_session.execute(
                select(AuthMethod).where(AuthMethod.user.has(normalized_email="test.user@wipro.com"))
            )
        ).scalar_one()
        assert refreshed.failed_login_attempts == 0
        assert refreshed.last_failed_login_at is None
        assert refreshed.locked_until is None
        assert refreshed.lockout_backoff_level == 0
