"""
utils/validators.py

Input validation and normalisation:
  - Email format check
  - Name normalisation (title-case, strip extra whitespace)
  - Role alias resolution → StakeholderRole enum
  - Parse free-text stakeholder entries from the user's chat message
"""
from __future__ import annotations
import logging
import re
from models.brd_models import Stakeholder, StakeholderRole, ROLE_ALIASES

logger = logging.getLogger(__name__)


# ── Email ─────────────────────────────────────────────────────────────────────

# Pragmatic email regex: covers the vast majority of real addresses without
# attempting full RFC 5322 compliance.
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,24}$"
)
_MAX_EMAIL_LEN = 254  # RFC 5321


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    e = email.strip()
    if len(e) > _MAX_EMAIL_LEN or ".." in e:
        return False
    return bool(_EMAIL_RE.match(e))


def normalise_email(email: str) -> str:
    """Lowercase and strip whitespace."""
    return email.strip().lower()


# ── Name ──────────────────────────────────────────────────────────────────────

def normalise_name(name: str) -> str:
    """Title-case, collapse internal spaces, strip leading/trailing whitespace."""
    return " ".join(part.strip().capitalize() for part in name.strip().split())


# ── Role ──────────────────────────────────────────────────────────────────────

def resolve_role(raw: str) -> StakeholderRole | None:
    """
    Map a user-supplied role string to a StakeholderRole enum value.
    Tries:
      1. Exact enum value match
      2. Alias lookup (case-insensitive)
      3. Conservative whole-word substring match against alias keys
    Returns None if no match is found.

    Note: partial matching only fires when the user input matches an alias
    on a word boundary.  This avoids spurious matches like the input "compliance
    questions about pm" resolving to PROJECT_MANAGER via the "pm" alias.
    """
    logger.info("Resolving role: %s", raw)
    cleaned = raw.strip().lower()
    if not cleaned:
        return None

    # 1. Direct enum value
    for role in StakeholderRole:
        if role.value.lower() == cleaned:
            logger.info("Role resolved via direct match: %s -> %s", raw, role.value)
            return role

    # 2. Alias lookup (exact)
    if cleaned in ROLE_ALIASES:
        logger.info("Role resolved via alias: %s -> %s", raw, ROLE_ALIASES[cleaned].value)
        return ROLE_ALIASES[cleaned]

    # 3. Whole-word boundary match.  Only consider aliases at least 4 chars
    # long to avoid false positives from short tokens like "po" / "sa".
    cleaned_tokens = set(re.findall(r"[a-z]+", cleaned))
    best: tuple[int, StakeholderRole] | None = None
    for alias, role in ROLE_ALIASES.items():
        if len(alias) < 4:
            continue
        alias_tokens = set(re.findall(r"[a-z]+", alias))
        if not alias_tokens:
            continue
        # Require all alias tokens to be present in the input as whole words.
        if alias_tokens.issubset(cleaned_tokens):
            score = sum(len(t) for t in alias_tokens)
            if best is None or score > best[0]:
                best = (score, role)

    if best is not None:
        logger.info("Role resolved via word-boundary match: %s -> %s", raw, best[1].value)
        return best[1]

    logger.warning("Role not resolved: %s", raw)
    return None


# ── Stakeholder list parser ───────────────────────────────────────────────────

class ParsedStakeholder(Stakeholder):
    """Stakeholder with optional parse errors attached."""
    errors: list[str] = []


def parse_stakeholder_block(text: str) -> list[ParsedStakeholder]:
    """
    Parse a free-text block where each line (or comma-separated entry) describes
    one stakeholder.  Accepts formats like:

        Alice Smith, alice@acme.com, Product Owner
        Bob Jones | bob@co.com | Solution Architect
        Carol White - carol@co.com - Business SME

    Returns a list of ParsedStakeholder objects.  Items with validation errors
    still appear in the list so callers can surface them to the user.
    """
    logger.info("Parsing stakeholder block: length=%d", len(text))
    results: list[ParsedStakeholder] = []
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]

    for line in lines:
        # Skip obvious header/instruction lines
        if line.lower().startswith(("name", "stakeholder", "#", "-"*3)):
            continue

        # Try splitting on common separators: | , ;  (tabs already split by splitlines)
        for sep in ["|", ",", ";"]:
            if sep in line:
                parts = [p.strip() for p in line.split(sep)]
                break
        else:
            # Fallback: split on 2+ spaces
            parts = re.split(r"\s{2,}", line)

        if len(parts) < 3:
            # Try to be lenient: maybe user wrote "Name <email> Role"
            m = re.match(
                r"^(.+?)\s+([^\s]+@[^\s]+)\s+(.+)$", line
            )
            if m:
                parts = [m.group(1), m.group(2), m.group(3)]
            else:
                continue  # Can't parse this line

        name_raw, email_raw, role_raw = parts[0], parts[1], parts[2]
        errors: list[str] = []

        # Normalise
        name  = normalise_name(name_raw)
        email = normalise_email(email_raw)
        role  = resolve_role(role_raw)

        if not name:
            errors.append("Name is empty.")
        if not is_valid_email(email):
            errors.append(f"'{email}' is not a valid email address.")
        if role is None:
            errors.append(
                f"Role '{role_raw}' was not recognised. "
                f"Valid roles: {', '.join(r.value for r in StakeholderRole)}."
            )
            role = StakeholderRole.PRODUCT_OWNER  # placeholder so model is valid

        results.append(ParsedStakeholder(
            name=name, email=email, role=role, errors=errors
        ))

    logger.info("Parsed %d stakeholders, %d with errors", len(results), sum(1 for r in results if r.errors))
    return results


def format_validation_errors(parsed: list[ParsedStakeholder]) -> str:
    """
    Return a human-readable error summary, or empty string if all clean.
    """
    logger.info("Formatting validation errors for %d stakeholders", len(parsed))
    lines = []
    for p in parsed:
        if p.errors:
            lines.append(f"• **{p.name}** ({p.email}): {' '.join(p.errors)}")
    return "\n".join(lines)


def all_valid(parsed: list[ParsedStakeholder]) -> bool:
    return all(not p.errors for p in parsed)


# ── Stakeholder dedupe ────────────────────────────────────────────────────────

def dedupe_stakeholders(stakeholders: list) -> tuple[list, list[str]]:
    """Remove duplicates while preserving the first occurrence.

    Two stakeholders are considered duplicates when their normalised email
    matches OR when their (name, role) pair matches.

    Returns ``(unique_stakeholders, removed_descriptions)``.
    """
    seen_emails: set[str] = set()
    seen_name_roles: set[tuple[str, str]] = set()
    unique = []
    removed: list[str] = []
    for s in stakeholders:
        email = (getattr(s, "email", "") or "").strip().lower()
        name = (getattr(s, "name", "") or "").strip().lower()
        role_val = getattr(getattr(s, "role", None), "value", str(getattr(s, "role", "")))
        key = (name, role_val)
        if (email and email in seen_emails) or key in seen_name_roles:
            removed.append(f"{getattr(s, 'name', '?')} <{email}>")
            continue
        if email:
            seen_emails.add(email)
        seen_name_roles.add(key)
        unique.append(s)
    if removed:
        logger.info("Deduped %d stakeholder(s): %s", len(removed), removed)
    return unique, removed


# ── Project name ──────────────────────────────────────────────────────────────

MAX_PROJECT_NAME_LEN = 120


def validate_project_name(raw: str | None) -> tuple[str | None, str | None]:
    """Return ``(cleaned_name, error)``.

    - Strips whitespace and surrounding quotes
    - Rejects empty strings, control characters, and path separators
    - Caps length at ``MAX_PROJECT_NAME_LEN``
    """
    if raw is None:
        return None, "Project name is required."
    name = raw.strip().strip('"\'')
    if not name:
        return None, "Project name cannot be empty."
    if re.search(r"[\x00-\x1F\x7F]", name):
        return None, "Project name contains control characters."
    if any(sep in name for sep in ("/", "\\", "..")):
        return None, "Project name cannot contain path separators."
    if len(name) > MAX_PROJECT_NAME_LEN:
        return None, f"Project name is too long (max {MAX_PROJECT_NAME_LEN} characters)."
    return name, None