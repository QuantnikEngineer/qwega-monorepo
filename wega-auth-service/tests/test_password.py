"""Password hashing and password policy test stubs."""

import pytest


@pytest.mark.unit
class TestArgon2Hashing:
    async def test_argon2_params(self, password_service):
        password = "TestP@ssw0rd123"
        password_hash = password_service.hash_password(password)

        assert "$argon2id$" in password_hash
        assert "m=65536" in password_hash
        assert "t=3" in password_hash
        assert "p=1" in password_hash

    async def test_hash_verify_roundtrip(self, password_service):
        password = "TestP@ssw0rd123"
        password_hash = password_service.hash_password(password)

        assert password_service.verify_password(password, password_hash) is True

    async def test_wrong_password_rejected(self, password_service):
        password_hash = password_service.hash_password("TestP@ssw0rd123")

        assert password_service.verify_password("WrongP@ssw0rd123", password_hash) is False


@pytest.mark.unit
class TestPasswordPolicy:
    async def test_policy_enforcement(self, password_service):
        validator = (
            getattr(password_service, "validate_policy", None)
            or getattr(password_service, "validate_password", None)
            or getattr(password_service, "validate_password_policy", None)
        )
        if validator is None:
            pytest.skip("Password policy validator not implemented yet")

        weak_cases = [
            ("Sh0rt!", "character"),
            ("alllowercase1!", "uppercase"),
            ("ALLUPPERCASE1!", "lowercase"),
            ("NoDigitsHere!", "digit"),
            ("NoSpecial123", "special"),
        ]

        for candidate, keyword in weak_cases:
            violations = validator(candidate)
            assert violations, f"Expected violations for password: {candidate}"
            assert any(keyword in str(v).lower() for v in violations), (
                f"Expected '{keyword}' violation for password: {candidate}. "
                f"Violations: {violations}"
            )

    async def test_strong_password_passes(self, password_service):
        validator = (
            getattr(password_service, "validate_policy", None)
            or getattr(password_service, "validate_password", None)
            or getattr(password_service, "validate_password_policy", None)
        )
        if validator is None:
            pytest.skip("Password policy validator not implemented yet")

        violations = validator("StrongP@ssw0rd123!")
        assert violations == []
