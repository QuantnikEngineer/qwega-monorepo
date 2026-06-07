"""
Create SuperAdmin — Register a superadmin user with a password, ready to login.

Usage (from wega-auth-service/):
    python scripts/create_superadmin.py --email aniket@wipro.com --name "Aniket A" --password "MyPass123!@#"
    python scripts/create_superadmin.py --env remote --email aniket@wipro.com --name "Aniket A" --password "MyPass123!@#"

Idempotent: if the email already exists, resets their password and ensures superadmin role.
"""

import argparse
import asyncio
import getpass
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argon2 import PasswordHasher
from db_config import add_db_args, resolve_db_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def get_hasher(db_url: str) -> PasswordHasher:
    """Use app settings for argon2 params if available, else defaults."""
    try:
        from app.core.config import settings
        return PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost,
            parallelism=settings.argon2_parallelism,
            hash_len=settings.argon2_hash_len,
            salt_len=settings.argon2_salt_len,
        )
    except Exception:
        return PasswordHasher()

ORG_ID = "00000000-0000-4000-8000-000000000001"
SUPERADMIN_ROLE_ID = "00000000-0000-4000-8000-000000000010"

MIN_LENGTH = 12
POLICY_RULES = [
    ("At least 12 characters", lambda p: len(p) >= MIN_LENGTH),
    ("One uppercase letter", lambda p: bool(re.search(r"[A-Z]", p))),
    ("One lowercase letter", lambda p: bool(re.search(r"[a-z]", p))),
    ("One digit", lambda p: bool(re.search(r"\d", p))),
    ("One special character", lambda p: bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", p))),
]


def validate_password(password: str) -> list[str]:
    return [desc for desc, test in POLICY_RULES if not test(password)]


async def main(db_url: str, email: str, display_name: str, password: str) -> None:
    email_normalized = email.strip().lower()
    now = datetime.now(timezone.utc)
    ph = get_hasher(db_url)

    engine = create_async_engine(db_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        # Check if user exists
        row = (await db.execute(
            text("SELECT id, status FROM users WHERE normalized_email = :e"),
            {"e": email_normalized},
        )).first()

        if row:
            user_id = row[0]
            print(f"  User exists (id={user_id}), resetting password & ensuring superadmin role...")

            # Fix status to ACTIVE
            await db.execute(
                text("UPDATE users SET status = 'ACTIVE', display_name = :name, updated_at = :now WHERE id = :uid"),
                {"name": display_name, "now": now, "uid": user_id},
            )

            # Replace auth method
            await db.execute(text("DELETE FROM auth_methods WHERE user_id = :uid"), {"uid": user_id})
        else:
            user_id = str(uuid.uuid4())
            print(f"  Creating user {email_normalized} (id={user_id})...")

            await db.execute(
                text(
                    "INSERT INTO users (id, normalized_email, display_name, org_id, status, created_at, updated_at) "
                    "VALUES (:id, :email, :name, :org, 'ACTIVE', :now, :now)"
                ),
                {"id": user_id, "email": email_normalized, "name": display_name, "org": ORG_ID, "now": now},
            )

        # Create password auth method
        hashed = ph.hash(password)
        await db.execute(
            text(
                "INSERT INTO auth_methods (id, user_id, method_type, provider, credential_hash, is_primary, "
                "must_change_password, failed_login_attempts, lockout_backoff_level, linked_at) "
                "VALUES (:id, :uid, 'PASSWORD', 'local', :hash, true, false, 0, 0, :now)"
            ),
            {"id": str(uuid.uuid4()), "uid": user_id, "hash": hashed, "now": now},
        )

        # Ensure superadmin role (platform scope)
        existing_role = (await db.execute(
            text("SELECT id FROM user_roles WHERE user_id = :uid AND role_id = :rid AND scope_type = 'platform'"),
            {"uid": user_id, "rid": SUPERADMIN_ROLE_ID},
        )).first()

        if not existing_role:
            await db.execute(
                text(
                    "INSERT INTO user_roles (id, user_id, role_id, scope_type, source, assigned_at) "
                    "VALUES (:id, :uid, :rid, 'platform', 'script', :now)"
                ),
                {"id": str(uuid.uuid4()), "uid": user_id, "rid": SUPERADMIN_ROLE_ID, "now": now},
            )
            print("  Assigned superadmin role")

        await db.commit()

    await engine.dispose()

    print()
    print("=" * 50)
    print("  SUPERADMIN READY")
    print(f"  Email:    {email_normalized}")
    print(f"  Password: {'*' * len(password)}")
    print(f"  Role:     superadmin (platform)")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or reset a SuperAdmin user")
    parser.add_argument("--email", required=True, help="User email (must be @wipro.com)")
    parser.add_argument("--name", required=True, help="Display name")
    parser.add_argument("--password", default=None, help="Password (prompted if omitted)")
    add_db_args(parser)
    args = parser.parse_args()

    if not args.email.strip().lower().endswith("@wipro.com"):
        print("ERROR: Email must be @wipro.com")
        sys.exit(1)

    pwd = args.password
    if not pwd:
        pwd = getpass.getpass("Password (min 12 chars, upper+lower+digit+special): ")

    violations = validate_password(pwd)
    if violations:
        print("ERROR: Password policy violations:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    db_url = resolve_db_url(args)
    print(f"  DB: {db_url.split('@')[-1] if '@' in db_url else 'local'}")
    asyncio.run(main(db_url, args.email, args.name, pwd))
