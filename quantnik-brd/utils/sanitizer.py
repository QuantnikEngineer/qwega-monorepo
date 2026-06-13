"""
utils/sanitizer.py

Input sanitization for text that will be interpolated into LLM prompts.
Defends against prompt injection by stripping control sequences, neutralising
known injection patterns, and escaping characters that break ``str.format``.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns that attempt to override system instructions
_INJECTION_PATTERNS = [
    re.compile(r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*(?:system|assistant)\s*:", re.IGNORECASE),
    re.compile(r"<\|(?:im_start|im_end|system|endoftext)\|>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.IGNORECASE),
]

# Replacement marker for neutralised injection attempts.
_NEUTRALISED_MARKER = "[redacted: potential prompt-injection]"

# Hard cap on a single field's length when interpolated into a prompt.
# Prevents pathological inputs from blowing up token budgets.
MAX_FIELD_LENGTH = 200_000


def sanitize_for_prompt(
    text: str,
    field_name: str = "input",
    *,
    neutralise_injection: bool = True,
    max_length: int = MAX_FIELD_LENGTH,
) -> str:
    """Sanitize user-provided text before interpolating into LLM prompts.

    - Strips ASCII control characters (except newline/tab)
    - Detects known prompt injection patterns and replaces them with a
      neutral marker (when ``neutralise_injection`` is True)
    - Escapes ``{`` / ``}`` so the result is safe for ``str.format``
    - Truncates to ``max_length`` characters to bound token usage
    """
    if not text:
        return text

    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            logger.warning(
                "Potential prompt injection in '%s': pattern=%r preview=%.200s",
                field_name, pattern.pattern, cleaned,
            )
            if neutralise_injection:
                cleaned = pattern.sub(_NEUTRALISED_MARKER, cleaned)

    if len(cleaned) > max_length:
        logger.warning(
            "Field '%s' truncated from %d to %d chars for prompt safety.",
            field_name, len(cleaned), max_length,
        )
        cleaned = cleaned[:max_length] + "\n[...truncated...]"

    # Escape brace characters so str.format() cannot be hijacked by user input
    # containing tokens like {project_name} or {0}.
    cleaned = cleaned.replace("{", "{{").replace("}", "}}")

    return cleaned


def sanitize_filename(name: str | None, fallback: str = "project") -> str:
    """Return a filesystem-safe slug derived from ``name``.

    - Strips path separators, drive letters, and parent-directory traversal
    - Limits length to 80 chars
    - Falls back to ``fallback`` if the result would be empty
    """
    if not name:
        return fallback
    base = re.sub(r"[\\/]+", "_", name)
    base = base.replace("..", "_")
    base = re.sub(r"[^A-Za-z0-9 _\-\.]", "_", base).strip("._ ")
    base = base[:80].strip()
    return base or fallback
