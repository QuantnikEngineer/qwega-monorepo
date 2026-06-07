"""
Password Service
================
Password hashing and policy validation.
Server-side validation mirrors frontend validators.ts rules.
"""

import re

from argon2 import PasswordHasher

from app.core.config import settings

password_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
    hash_len=settings.argon2_hash_len,
    salt_len=settings.argon2_salt_len,
)

MIN_LENGTH = 12
POLICY_RULES = [
    ("At least 12 characters", lambda p: len(p) >= MIN_LENGTH),
    ("One uppercase letter", lambda p: bool(re.search(r"[A-Z]", p))),
    ("One lowercase letter", lambda p: bool(re.search(r"[a-z]", p))),
    ("One digit", lambda p: bool(re.search(r"\d", p))),
    ("One special character", lambda p: bool(re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", p))),
]


class PasswordService:
    """Password hashing and policy enforcement."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with Argon2id (OWASP 2025 params)."""
        return password_hasher.hash(password)

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its Argon2id hash. Returns True if valid."""
        try:
            return password_hasher.verify(password_hash, password)
        except Exception:
            return False

    @staticmethod
    def validate_policy(password: str) -> list[str]:
        """
        Validate password against policy rules.
        Returns list of failed rule descriptions (empty = all pass).
        """
        failures: list[str] = []
        for description, test_fn in POLICY_RULES:
            if not test_fn(password):
                failures.append(description)
        return failures

    @staticmethod
    def check_policy_or_raise(password: str) -> None:
        """Validate password and raise ValueError if policy not met."""
        failures = PasswordService.validate_policy(password)
        if failures:
            raise ValueError(f"Password does not meet policy: {', '.join(failures)}")

