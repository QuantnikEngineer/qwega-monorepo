"""
Reset Password — Reset any user's password by email.

Usage (from quantnik-auth-service/):
    python scripts/reset_password.py --email priya.sharma@wipro.com --password "NewPass1!@#$"
    python scripts/reset_password.py --email priya.sharma@wipro.com   # prompts for password
    python scripts/reset_password.py --env remote --email priya.sharma@wipro.com --password "NewPass1!@#$"

Idempotent: replaces existing password auth method. Also sets status to ACTIVE.
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

MIN_LENGTH = 12
POLICY_RULES = [
    ("At least 12 characters", lambda p: len(p) >= MIN_LENGTH),
    ("One uppercase letter", lambda p: bool(re.search(r"[A-Z]", p))),
    ("One lowercase letter", lambda p: bool(re.search(r"[a-z]", p))),
    ("One digit", lambda p: bool(re.search(r"\d", p))),
    ("One special character", lambda p: bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", p))),
]


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


def validate_password(password: str) -> list[str]:
    return [desc for desc, test in POLICY_RULES if not test(password)]


async def main(db_url: str, email: str, password: str) -> None:
    email_normalized = email.strip().lower()
    now = datetime.now(timezone.utc)
    ph = get_hasher(db_url)

    engine = create_async_engine(db_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        row = (await db.execute(
            text("SELECT id, display_name, status FROM users WHERE normalized_email = :e"),
            {"e": email_normalized},
        )).first()

        if not row:
            print(f"ERROR: User '{email_normalized}' not found in database.")
            await engine.dispose()
            sys.exit(1)

        user_id, display_name, status = row
        print(f"  Found: {display_name} ({email_normalized}) — status={status}")

        # Set status to ACTIVE
        await db.execute(
            text("UPDATE users SET status = 'ACTIVE', updated_at = :now WHERE id = :uid"),
            {"now": now, "uid": user_id},
        )

        # Replace password auth method
        await db.execute(text("DELETE FROM auth_methods WHERE user_id = :uid"), {"uid": user_id})

        hashed = ph.hash(password)
        await db.execute(
            text(
                "INSERT INTO auth_methods (id, user_id, method_type, provider, credential_hash, is_primary, "
                "must_change_password, failed_login_attempts, lockout_backoff_level, linked_at) "
                "VALUES (:id, :uid, 'PASSWORD', 'local', :hash, true, false, 0, 0, :now)"
            ),
            {"id": str(uuid.uuid4()), "uid": user_id, "hash": hashed, "now": now},
        )

        await db.commit()

    await engine.dispose()

    print()
    print("=" * 50)
    print("  PASSWORD RESET COMPLETE")
    print(f"  User:     {display_name}")
    print(f"  Email:    {email_normalized}")
    print(f"  Status:   ACTIVE")
    print(f"  Password: {'*' * len(password)}")
    print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset a user's password")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", default=None, help="New password (prompted if omitted)")
    add_db_args(parser)
    args = parser.parse_args()

    pwd = args.password
    if not pwd:
        pwd = getpass.getpass("New password (min 12 chars, upper+lower+digit+special): ")

    violations = validate_password(pwd)
    if violations:
        print("ERROR: Password policy violations:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    db_url = resolve_db_url(args)
    print(f"  DB: {db_url.split('@')[-1] if '@' in db_url else 'local'}")
    asyncio.run(main(db_url, args.email, pwd))
