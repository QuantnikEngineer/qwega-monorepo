"""
Bootstrap Admin — Generate initial activation link for seeded SuperAdmin.

Usage (from wega-auth-service/):
    python scripts/bootstrap_admin.py

This solves the chicken-and-egg problem: the seeded admin@wipro.com user has
no password (by design — migration 002 removed it). This script generates a
one-time activation URL so the SuperAdmin can set their initial password via
the browser.

The script is idempotent — running it again creates a new token (previous
unused tokens remain valid until they expire or are used).

NOTE — SQLAlchemy enum storage:
    SQLAlchemy ``SAEnum(PythonEnum)`` stores the **name** (e.g. ``ACTIVE``,
    ``PASSWORD``), NOT the value (``active``, ``password``).  Any raw SQL
    that inserts or updates ``users.status`` or ``auth_methods.method_type``
    MUST use the uppercase enum name, or SQLAlchemy will raise a LookupError
    at read time.  Prefer using the ORM or PasswordService/ActivationService
    instead of raw SQL whenever possible.
"""

import asyncio
import hashlib
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

ADMIN_EMAIL = "admin@wipro.com"
ADMIN_USER_ID = "00000000-0000-4000-8000-000000000002"
TOKEN_EXPIRY_HOURS = 48


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Verify admin user exists
        result = await db.execute(
            text("SELECT id, normalized_email, status FROM users WHERE id = :uid"),
            {"uid": ADMIN_USER_ID},
        )
        row = result.first()
        if not row:
            print(f"ERROR: Seeded admin user ({ADMIN_USER_ID}) not found in database.")
            print("       Have you run alembic migrations?  alembic upgrade head")
            await engine.dispose()
            sys.exit(1)

        print(f"Found admin user: {row[1]} (status={row[2]})")

        # Ensure user is active (seed sets status=active, but just in case)
        if row[2] != "active":
            await db.execute(
                text("UPDATE users SET status = 'ACTIVE' WHERE id = :uid"),
                {"uid": ADMIN_USER_ID},
            )

        # Generate activation token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token_id = str(__import__("uuid").uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=TOKEN_EXPIRY_HOURS)

        await db.execute(
            text(
                "INSERT INTO activation_tokens (id, user_id, token_hash, expires_at, created_by, created_at) "
                "VALUES (:id, :user_id, :token_hash, :expires_at, :created_by, :created_at)"
            ),
            {
                "id": token_id,
                "user_id": ADMIN_USER_ID,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "created_by": None,
                "created_at": now,
            },
        )
        await db.commit()

    await engine.dispose()

    activation_url = f"{settings.frontend_url}/login?token={raw_token}"

    print()
    print("=" * 70)
    print("  WEGA SuperAdmin Bootstrap")
    print("=" * 70)
    print()
    print(f"  Email:    {ADMIN_EMAIL}")
    print(f"  Expires:  {TOKEN_EXPIRY_HOURS} hours from now")
    print()
    print("  Activation URL (open in browser):")
    print()
    print(f"  {activation_url}")
    print()
    print("=" * 70)
    print()
    print("  Steps:")
    print("  1. Open the URL above in your browser")
    print("  2. Set a password (min 12 chars, upper+lower+digit+special)")
    print("  3. Log in with admin@wipro.com and your new password")
    print("  4. You now have full SuperAdmin access to manage users/roles")
    print()


if __name__ == "__main__":
    asyncio.run(main())
