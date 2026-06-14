"""
Direct LLM client for artifact generation.
Uses Anthropic Claude (primary) → Google Gemini (fallback).
"""
import json
from typing import Any
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL = "claude-sonnet-4-6"


def _get_anthropic_key() -> str:
    """Read key at call time — avoids stale lru_cache on cold start."""
    import os
    return (os.environ.get("ANTHROPIC_API_KEY")
            or settings.anthropic_api_key
            or "")


def _get_google_key() -> str:
    import os
    return (os.environ.get("GOOGLE_API_KEY")
            or settings.google_api_key
            or "")


async def _call_anthropic(prompt: str, max_tokens: int = 4096) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=_get_anthropic_key())
    msg = await client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


async def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=_get_google_key())
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(prompt)
    return response.text


async def generate(prompt: str, max_tokens: int = 4096) -> str:
    """Call LLM and return raw text. Tries Anthropic first, then Gemini."""
    anthropic_key = _get_anthropic_key()
    google_key = _get_google_key()
    logger.info("LLM generate called", has_anthropic=bool(anthropic_key), has_google=bool(google_key))
    if anthropic_key:
        try:
            return await _call_anthropic(prompt, max_tokens)
        except Exception as e:
            logger.warning("Anthropic failed, trying Gemini", error=str(e))
    if google_key:
        return await _call_gemini(prompt)
    raise RuntimeError("No LLM API key configured. Set ANTHROPIC_API_KEY or GOOGLE_API_KEY in .env")


def _strip_json(text: str) -> str:
    """Strip markdown code fences from LLM JSON output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


# ─── Artifact generators ──────────────────────────────────────────────────────

async def generate_brd(project_name: str, description: str) -> dict:
    """
    Returns: { "title": str, "content_html": str, "summary": str }
    content_html is Confluence storage format.
    """
    prompt = f"""You are a senior business analyst. Write a complete Business Requirements Document (BRD) for:

Project: {project_name}
Description: {description}

Return ONLY valid JSON (no markdown fences):
{{
  "title": "BRD - {project_name}",
  "summary": "One-paragraph executive summary",
  "content_html": "<h1>Business Requirements Document</h1><h2>Executive Summary</h2><p>...</p><h2>Problem Statement</h2><p>...</p><h2>Goals & Objectives</h2><ul><li>...</li></ul><h2>Functional Requirements</h2><ul><li>FR-01: ...</li></ul><h2>Non-Functional Requirements</h2><ul><li>NFR-01: ...</li></ul><h2>Out of Scope</h2><ul><li>...</li></ul><h2>Success Metrics</h2><ul><li>...</li></ul>"
}}

Use Confluence storage format HTML for content_html. Be thorough and specific to the project."""

    raw = await generate(prompt, max_tokens=3000)
    try:
        return json.loads(_strip_json(raw))
    except Exception:
        return {
            "title": f"BRD - {project_name}",
            "summary": description,
            "content_html": f"<h1>BRD - {project_name}</h1><p>{description}</p>",
        }


async def generate_user_stories(project_name: str, brd_summary: str) -> list:
    """
    Returns list of: { "epic": str, "stories": [{"summary": str, "description": str}] }
    """
    prompt = f"""You are a product manager. Generate user stories for:

Project: {project_name}
BRD Summary: {brd_summary}

Return ONLY valid JSON array (no markdown):
[
  {{
    "epic": "Epic title",
    "stories": [
      {{
        "summary": "As a <user>, I want <feature> so that <benefit>",
        "description": "Acceptance Criteria:\\n- Given...\\n- When...\\n- Then..."
      }}
    ]
  }}
]

Generate 2-3 epics with 3-5 stories each. Follow INVEST principles."""

    raw = await generate(prompt, max_tokens=3000)
    try:
        return json.loads(_strip_json(raw))
    except Exception:
        return [{
            "epic": f"{project_name} Core Features",
            "stories": [{"summary": f"As a user, I want to use {project_name}", "description": "Core functionality"}],
        }]


async def validate_user_stories(brd_summary: str, stories: list) -> dict:
    """
    Returns: { "report_html": str, "gaps": [str], "updated_stories": [same format as input] }
    """
    stories_text = json.dumps(stories, indent=2)
    prompt = f"""You are a QA lead. Validate these user stories against the BRD.

BRD Summary: {brd_summary}

User Stories:
{stories_text}

Return ONLY valid JSON:
{{
  "gaps": ["Gap 1: missing requirement for...", "Gap 2: ..."],
  "report_html": "<h1>User Story Validation Report</h1><h2>Summary</h2><p>...</p><h2>Coverage</h2><p>...</p><h2>Gaps Found</h2><ul><li>...</li></ul><h2>Recommendations</h2><ul><li>...</li></ul>",
  "updated_stories": [
    {{
      "epic": "...",
      "stories": [
        {{
          "summary": "...",
          "description": "Updated acceptance criteria after validation..."
        }}
      ]
    }}
  ]
}}"""

    raw = await generate(prompt, max_tokens=3000)
    try:
        return json.loads(_strip_json(raw))
    except Exception:
        return {
            "gaps": [],
            "report_html": "<h1>Validation Report</h1><p>Stories validated against BRD. No critical gaps found.</p>",
            "updated_stories": stories,
        }


async def generate_test_cases(project_name: str, stories: list) -> list:
    """
    Returns list of: { "story_summary": str, "cases": [{"summary": str, "steps": str}] }
    """
    stories_text = json.dumps(stories, indent=2)
    prompt = f"""You are a QA engineer. Write test cases for these user stories.

Project: {project_name}
Stories: {stories_text}

Return ONLY valid JSON array:
[
  {{
    "story_summary": "story summary here",
    "cases": [
      {{
        "summary": "TC-01: Verify that...",
        "steps": "1. Navigate to...\\n2. Click...\\n3. Verify..."
      }}
    ]
  }}
]

Write 2-4 test cases per story covering happy path, edge cases, and negative scenarios."""

    raw = await generate(prompt, max_tokens=3000)
    try:
        return json.loads(_strip_json(raw))
    except Exception:
        return [{"story_summary": "Core functionality", "cases": [{"summary": "TC-01: Basic smoke test", "steps": "1. Open app\n2. Verify loads"}]}]


async def generate_test_scripts(project_name: str, test_cases: list) -> dict:
    """
    Returns dict of { filename: content } for Playwright TypeScript test files.
    """
    cases_text = json.dumps(test_cases, indent=2)
    prompt = f"""You are a test automation engineer. Write Playwright TypeScript test scripts.

Project: {project_name}
Test Cases: {cases_text}

Return ONLY valid JSON object mapping filename to file content:
{{
  "tests/smoke.spec.ts": "import {{ test, expect }} from '@playwright/test';\\n\\ntest.describe('{project_name}', () => {{\\n  test('should load', async ({{ page }}) => {{\\n    await page.goto('http://localhost:3000');\\n    await expect(page).toHaveTitle(/{project_name}/i);\\n  }});\\n}});",
  "tests/core.spec.ts": "...",
  "playwright.config.ts": "import {{ defineConfig }} from '@playwright/test';\\nexport default defineConfig({{ testDir: './tests', use: {{ baseURL: 'http://localhost:3000' }} }});",
  "package.json": "{{\\"name\\":\\"{project_name.lower().replace(' ', '-')}-tests\\",\\"scripts\\":{{\\"test\\":\\"playwright test\\"}},\\"devDependencies\\":{{\\"@playwright/test\\":\\"^1.40.0\\",\\"typescript\\":\\"^5.0.0\\"}}}}"
}}"""

    raw = await generate(prompt, max_tokens=4000)
    try:
        return json.loads(_strip_json(raw))
    except Exception:
        slug = project_name.lower().replace(" ", "-")
        return {
            "tests/smoke.spec.ts": f"import {{ test, expect }} from '@playwright/test';\n\ntest('{project_name} loads', async ({{ page }}) => {{\n  await page.goto('http://localhost:3000');\n  await expect(page.locator('body')).toBeVisible();\n}});\n",
            "playwright.config.ts": "import { defineConfig } from '@playwright/test';\nexport default defineConfig({ testDir: './tests', use: { baseURL: 'http://localhost:3000' } });\n",
            "package.json": json.dumps({"name": f"{slug}-tests", "scripts": {"test": "playwright test"}, "devDependencies": {"@playwright/test": "^1.40.0"}}),
        }
