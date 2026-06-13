"""Tests for utils/validators.py — stakeholder parsing, email, role resolution."""
import pytest
from utils.validators import (
    is_valid_email,
    normalise_email,
    normalise_name,
    resolve_role,
    parse_stakeholder_block,
    format_validation_errors,
    all_valid,
)
from models.brd_models import StakeholderRole


# ── Email validation ──────────────────────────────────────────────────────────

class TestEmailValidation:
    def test_valid_emails(self):
        assert is_valid_email("alice@acme.com")
        assert is_valid_email("bob.jones+tag@sub.domain.co.uk")
        assert is_valid_email("user@example.io")

    def test_invalid_emails(self):
        assert not is_valid_email("")
        assert not is_valid_email("not-an-email")
        assert not is_valid_email("@domain.com")
        assert not is_valid_email("user@")
        assert not is_valid_email("user@.com")
        assert not is_valid_email("user@domain")

    def test_normalise_email(self):
        assert normalise_email("  Alice@ACME.COM  ") == "alice@acme.com"


# ── Name normalisation ────────────────────────────────────────────────────────

class TestNameNormalisation:
    def test_basic(self):
        assert normalise_name("alice smith") == "Alice Smith"

    def test_extra_whitespace(self):
        assert normalise_name("  bob   jones  ") == "Bob Jones"

    def test_already_normalised(self):
        assert normalise_name("Carol White") == "Carol White"


# ── Role resolution ──────────────────────────────────────────────────────────

class TestRoleResolution:
    def test_exact_enum_value(self):
        assert resolve_role("Product Owner / Product Manager") == StakeholderRole.PRODUCT_OWNER

    def test_alias_shorthand(self):
        assert resolve_role("PO") == StakeholderRole.PRODUCT_OWNER
        assert resolve_role("sme") == StakeholderRole.BUSINESS_SME
        assert resolve_role("SA") == StakeholderRole.SOLUTION_ARCHITECT

    def test_alias_case_insensitive(self):
        assert resolve_role("product owner") == StakeholderRole.PRODUCT_OWNER
        assert resolve_role("BUSINESS SPONSOR") == StakeholderRole.BUSINESS_SPONSOR

    def test_partial_match(self):
        assert resolve_role("compliance") == StakeholderRole.COMPLIANCE_OFFICER

    def test_unknown_role(self):
        assert resolve_role("CEO") is None


# ── Stakeholder block parsing ─────────────────────────────────────────────────

class TestParseStakeholderBlock:
    def test_comma_separated(self):
        block = "Alice Smith, alice@acme.com, Product Owner"
        result = parse_stakeholder_block(block)
        assert len(result) == 1
        assert result[0].name == "Alice Smith"
        assert result[0].email == "alice@acme.com"
        assert result[0].role == StakeholderRole.PRODUCT_OWNER
        assert result[0].errors == []

    def test_pipe_separated(self):
        block = "Bob Jones | bob@co.com | Solution Architect"
        result = parse_stakeholder_block(block)
        assert len(result) == 1
        assert result[0].name == "Bob Jones"
        assert result[0].role == StakeholderRole.SOLUTION_ARCHITECT

    def test_multiple_lines(self):
        block = (
            "Alice Smith, alice@acme.com, PO\n"
            "Bob Jones, bob@co.com, SA\n"
            "Carol White, carol@co.com, SME\n"
        )
        result = parse_stakeholder_block(block)
        assert len(result) == 3
        assert all_valid(result)

    def test_invalid_email_produces_error(self):
        block = "Alice Smith, not-email, Product Owner"
        result = parse_stakeholder_block(block)
        assert len(result) == 1
        assert not all_valid(result)
        assert any("not a valid email" in e for e in result[0].errors)

    def test_unknown_role_produces_error(self):
        block = "Alice Smith, alice@acme.com, CEO"
        result = parse_stakeholder_block(block)
        assert len(result) == 1
        assert not all_valid(result)
        assert any("not recognised" in e for e in result[0].errors)

    def test_empty_input(self):
        assert parse_stakeholder_block("") == []
        assert parse_stakeholder_block("   \n   \n") == []

    def test_skips_header_lines(self):
        block = "Name, Email, Role\nAlice Smith, alice@acme.com, PO"
        result = parse_stakeholder_block(block)
        assert len(result) == 1


class TestFormatValidationErrors:
    def test_no_errors(self):
        block = "Alice Smith, alice@acme.com, PO"
        parsed = parse_stakeholder_block(block)
        assert format_validation_errors(parsed) == ""

    def test_with_errors(self):
        block = "Alice Smith, bademail, PO"
        parsed = parse_stakeholder_block(block)
        msg = format_validation_errors(parsed)
        assert "Alice Smith" in msg
        assert "bademail" in msg
