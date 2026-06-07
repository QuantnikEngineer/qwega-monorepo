# utils/json_parser.py
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def _escape_control_chars_in_json_strings(s: str) -> str:
    """
    Escape literal control characters that appear *inside* JSON string values.
    JSON disallows raw tab/newline/carriage-return inside strings; they must be escaped.
    """
    out: list[str] = []
    in_str = False
    esc = False

    for ch in s:
        if not in_str:
            if ch == '"':
                in_str = True
            out.append(ch)
            continue

        # inside a string
        if esc:
            out.append(ch)
            esc = False
            continue

        if ch == "\\":
            out.append(ch)
            esc = True
            continue

        if ch == '"':
            out.append(ch)
            in_str = False
            continue

        # Escape common invalid literal controls inside strings
        if ch == "\n":
            out.append("\\n")
            continue
        if ch == "\r":
            out.append("\\r")
            continue
        if ch == "\t":
            out.append("\\t")
            continue

        # Drop any other ASCII control chars inside strings
        if ord(ch) < 0x20:
            continue

        out.append(ch)

    return "".join(out)


def parse_llm_json(raw: str) -> dict:
    """Extract and parse a JSON object from an LLM agent's text response."""
    logger.info("Parsing JSON from LLM response: length=%d", len(raw))

    # Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)

    # Find the outermost JSON object (best-effort)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        logger.error("No JSON found in LLM response: preview=%s", raw[:400])
        raise ValueError(f"No JSON found in LLM response: {raw[:300]}")

    json_str = match.group(0)

    # 1) Strip ASCII control characters EXCEPT \n \r \t (we will escape these inside strings)
    json_str = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", json_str)

    # 2) Fix invalid escape sequences like \existing
    def _fix_invalid_escape(m: re.Match) -> str:
        seq = m.group(0)
        if len(seq) == 2 and seq[1] in '"\\/bfnrt':
            return seq
        if len(seq) == 6 and seq[1] == "u":
            return seq
        return seq[1:]  # strip leading backslash for invalid escapes

    json_str = re.sub(r"\\(?:u[0-9a-fA-F]{4}|.)", _fix_invalid_escape, json_str)

    # 3) Strip JS-style comments
    json_str = re.sub(r"//.*", "", json_str)
    json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)

    # 4) Remove trailing commas
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

    # 5) Escape literal \n/\r/\t INSIDE strings (fixes your current crash)
    json_str = _escape_control_chars_in_json_strings(json_str)

    # Try strict JSON first
    try:
        result = json.loads(json_str)
        logger.info("JSON successfully parsed")
        return result
    except json.JSONDecodeError as e:
        logger.warning("Strict JSON parse failed: %s", e)

    # Fallback: allow control characters if any still remain
    try:
        result = json.loads(json_str, strict=False)
        logger.info("JSON parsed with strict=False fallback")
        return result
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: preview=%s", json_str[:600])
        raise ValueError(
            f"JSON parse failed: {e}\n"
            f"Preview of cleaned JSON:\n{json_str[:600]}"
        ) from e
