"""
Direct Atlassian REST API client — Confluence + Jira.
Uses Basic Auth (email:token). No child orchestrator needed.
"""
import httpx
import base64
import json
from typing import Optional, List, Dict, Any
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

TIMEOUT = httpx.Timeout(60.0)


def _auth_header() -> str:
    creds = f"{settings.atlassian_email}:{settings.atlassian_token}"
    return "Basic " + base64.b64encode(creds.encode()).decode()


def _headers() -> Dict[str, str]:
    return {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _base() -> str:
    url = settings.atlassian_url.rstrip("/")
    return url


# ─── Confluence ───────────────────────────────────────────────────────────────

async def get_confluence_space_id(space_key: str) -> Optional[str]:
    """Resolve a space key to its numeric ID."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(
            f"{_base()}/wiki/api/v2/spaces",
            headers=_headers(),
            params={"keys": space_key, "limit": 1},
        )
        r.raise_for_status()
        items = r.json().get("results", [])
        return str(items[0]["id"]) if items else None


async def create_confluence_page(
    space_key: str,
    title: str,
    body: str,
    parent_id: Optional[str] = None,
) -> str:
    """Create a Confluence page and return its URL."""
    space_id = await get_confluence_space_id(space_key)
    if not space_id:
        raise ValueError(f"Confluence space '{space_key}' not found")

    payload: Dict[str, Any] = {
        "spaceId": space_id,
        "status": "current",
        "title": title,
        "body": {
            "representation": "storage",
            "value": body,
        },
    }
    if parent_id:
        payload["parentId"] = parent_id

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            f"{_base()}/wiki/api/v2/pages",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        page_id = data["id"]
        base = _base()
        return f"{base}/wiki/spaces/{space_key}/pages/{page_id}"


# ─── Jira ─────────────────────────────────────────────────────────────────────

async def get_jira_project_id(project_key: str) -> Optional[str]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(
            f"{_base()}/rest/api/3/project/{project_key}",
            headers=_headers(),
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get("id")


async def create_jira_epic(project_key: str, summary: str, description: str) -> Dict[str, str]:
    """Create a Jira Epic. Returns {key, url}."""
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            },
            "issuetype": {"name": "Epic"},
        }
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            f"{_base()}/rest/api/3/issue",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
        key = r.json()["key"]
        return {"key": key, "url": f"{_base()}/browse/{key}"}


async def create_jira_story(
    project_key: str,
    summary: str,
    description: str,
    epic_key: Optional[str] = None,
) -> Dict[str, str]:
    """Create a Jira Story under an epic. Returns {key, url}."""
    fields: Dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "description": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
        },
        "issuetype": {"name": "Story"},
    }
    if epic_key:
        fields["parent"] = {"key": epic_key}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            f"{_base()}/rest/api/3/issue",
            headers=_headers(),
            json={"fields": fields},
        )
        r.raise_for_status()
        key = r.json()["key"]
        return {"key": key, "url": f"{_base()}/browse/{key}"}


async def create_jira_test_case(
    project_key: str,
    summary: str,
    description: str,
    story_key: Optional[str] = None,
) -> Dict[str, str]:
    """Create a Jira Task representing a test case. Returns {key, url}."""
    fields: Dict[str, Any] = {
        "project": {"key": project_key},
        "summary": summary,
        "description": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
        },
        "issuetype": {"name": "Task"},
        "labels": ["test-case"],
    }
    if story_key:
        fields["parent"] = {"key": story_key}

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            f"{_base()}/rest/api/3/issue",
            headers=_headers(),
            json={"fields": fields},
        )
        r.raise_for_status()
        key = r.json()["key"]
        return {"key": key, "url": f"{_base()}/browse/{key}"}


async def update_jira_story(issue_key: str, description: str) -> None:
    """Update a story's description."""
    payload = {
        "fields": {
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
            }
        }
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.put(
            f"{_base()}/rest/api/3/issue/{issue_key}",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
