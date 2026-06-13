import os
import logging
import re
from typing import Optional

from .http_utils import classify_http_error, http_request_with_retry
from .jira_common import JiraConfigError, get_jira_config, jira_config_error_result

logger = logging.getLogger(__name__)


def _get_jira_search_context(project_key: Optional[str] = None) -> dict:
    """Return common Jira search configuration shared by fetch helpers."""
    base_url, auth, configured_project = get_jira_config(require_project=False)
    return {
        "base_url": base_url,
        "auth": auth,
        "resolved_project": project_key or configured_project,
        "epic_issue_type": os.getenv("JIRA_EPIC_ISSUE_TYPE", "Epic"),
        "headers": {"Accept": "application/json"},
        # Atlassian deprecated /rest/api/3/search and removed it for cloud
        # tenants on 2025-04-30. The new "Enhanced JQL" endpoint is
        # /rest/api/3/search/jql with nextPageToken-based pagination.
        # Ref: https://developer.atlassian.com/changelog/#CHANGE-2046
        "search_url": base_url.rstrip("/") + "/rest/api/3/search/jql",
    }


def _extract_confluence_page_id(url: str) -> Optional[str]:
    """Extract the numeric Confluence page ID from a page URL.

    Matches URLs like:
    - https://domain.atlassian.net/wiki/spaces/SPACE/pages/12345/Title
    - https://domain.atlassian.net/wiki/spaces/SPACE/pages/12345
    """
    match = re.search(r"/pages/(\d+)", url)
    return match.group(1) if match else None


def search_epics_by_brd_url(brd_url: str) -> dict:
    """Find Jira epics that were generated from the given Confluence BRD URL.

    During greenfield export, the BRD URL is embedded in every epic description
    as ``Source BRD: <url>``.  This function searches Jira for epics whose
    description contains the Confluence page ID (unique numeric identifier) and
    then confirms the full URL match locally to avoid false positives.

    Returns:
        {"status": "success", "epic_keys": ["PROJ-1", "PROJ-3", ...]}
        or {"status": "error", "error_message": "..."}
        or {"status": "not_found", "error_message": "..."} when no epics match.
    """
    try:
        search_context = _get_jira_search_context()
    except JiraConfigError as exc:
        return jira_config_error_result(exc)

    page_id = _extract_confluence_page_id(brd_url)
    if not page_id:
        return {
            "status": "error",
            "error_message": (
                "Could not extract a Confluence page ID from the provided URL. "
                "Expected format: .../wiki/spaces/SPACE/pages/<numeric-id>/..."
            ),
        }

    auth = search_context["auth"]
    headers = search_context["headers"]
    search_url = search_context["search_url"]
    project_key = search_context["resolved_project"]
    epic_issue_type = search_context["epic_issue_type"]

    # Use the page ID as a precise search token. It is a long number that
    # is extremely unlikely to appear in unrelated epic descriptions.
    jql_parts = [f'issuetype = "{epic_issue_type}"', f'description ~ "{page_id}"']
    if project_key:
        jql_parts.insert(0, f"project = {project_key}")

    jql = " AND ".join(jql_parts)

    try:
        resp = http_request_with_retry(
            "GET",
            search_url,
            auth=auth,
            headers=headers,
            params={
                "jql": jql,
                "fields": "summary,description",
                "maxResults": 50,
            },
        )

        if resp.status_code >= 300:
            logger.error(
                "Jira BRD-URL epic search failed: %s - %s",
                resp.status_code,
                resp.text,
            )
            return {
                "status": "error",
                "error_category": classify_http_error(resp.status_code),
                "error_message": (
                    f"Jira search failed: HTTP {resp.status_code}. {resp.text}"
                ),
            }

        issues = resp.json().get("issues", [])
        logger.info(
            "Jira BRD-URL search for page_id=%s returned %d candidate epics",
            page_id,
            len(issues),
        )

        # Local confirmation: the epic description must contain the full BRD URL
        # (or at minimum the page ID) to rule out numeric coincidences.
        matched_keys: list[str] = []
        for issue in issues:
            desc_text = _extract_description_text(issue["fields"].get("description"))
            if brd_url in desc_text or page_id in desc_text:
                matched_keys.append(issue["key"])
                logger.info(
                    "Epic %s matched BRD URL (page_id=%s)", issue["key"], page_id
                )

        if not matched_keys:
            return {
                "status": "not_found",
                "error_message": (
                    f"No Jira epics found that reference BRD page ID {page_id}. "
                    "This can happen if the epics were created before the BRD URL "
                    "embedding feature was added. Please provide jira_epic_keys manually."
                ),
            }

        return {"status": "success", "epic_keys": matched_keys}

    except Exception as exc:
        logger.exception("Error searching epics by BRD URL: %s", exc)
        return {"status": "error", "error_message": str(exc)}


def _paginated_jira_search(
    search_url: str,
    auth: tuple,
    headers: dict,
    jql: str,
    fields: str,
    page_size: int = 100,
) -> list:
    """Fetch every matching issue from Jira using nextPageToken pagination.

    Targets the new /rest/api/3/search/jql endpoint (Atlassian removed the
    legacy /rest/api/3/search endpoint for cloud tenants on 2025-04-30).
    The new endpoint uses nextPageToken-based pagination and no longer
    returns ``total`` — pagination ends when ``isLast`` is true or the
    response omits ``nextPageToken``.

    Raises RuntimeError on a non-2xx HTTP response.
    """
    issues: list = []
    next_page_token: Optional[str] = None

    while True:
        params = {
            "jql": jql,
            "fields": fields,
            "maxResults": page_size,
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        resp = http_request_with_retry(
            "GET",
            search_url,
            auth=auth,
            headers=headers,
            params=params,
        )

        if resp.status_code >= 300:
            raise RuntimeError(
                f"Jira search failed: HTTP {resp.status_code}. {resp.text}"
            )

        data = resp.json()
        batch = data.get("issues", [])
        issues.extend(batch)

        next_page_token = data.get("nextPageToken")
        is_last = data.get("isLast")

        if is_last is True or not next_page_token or not batch:
            break

    return issues


def fetch_jira_epics_and_stories(epic_keys: list[str] | None = None) -> dict:
    """Fetch epics and their child stories from Jira.

    If ``epic_keys`` is provided, fetches only those specific epics and their
    stories.  Otherwise fetches all epics in the configured project.

    Returns:
        {"status": "success", "epics": [...]}
        or {"status": "error", "error_message": "..."}

    Each epic in the list has the shape::

        {
            "issue_key": "PROJ-1",
            "epic_title": "...",
            "epic_description": "...",
            "user_stories": [
                {
                    "issue_key": "PROJ-5",
                    "title": "...",
                    "description": "...",
                }
            ]
        }
    """
    try:
        search_context = _get_jira_search_context()
    except JiraConfigError as exc:
        return jira_config_error_result(exc)

    base_url = search_context["base_url"]
    auth = search_context["auth"]
    headers = search_context["headers"]
    search_url = search_context["search_url"]
    project_key = search_context["resolved_project"]
    epic_issue_type = search_context["epic_issue_type"]
    epic_link_field = os.getenv("JIRA_EPIC_LINK_FIELD")

    try:
        # Build JQL to locate the target epics
        if epic_keys:
            keys_str = ", ".join(epic_keys)
            jql = f"issueKey in ({keys_str})"
        elif project_key:
            jql = (
                f'project = {project_key} AND issuetype = "{epic_issue_type}" '
                f"ORDER BY created DESC"
            )
        else:
            return {
                "status": "error",
                "error_message": (
                    "Provide jira_epic_keys in the request or set the "
                    "JIRA_PROJECT_KEY environment variable."
                ),
            }

        epic_issues = _paginated_jira_search(
            search_url=search_url,
            auth=auth,
            headers=headers,
            jql=jql,
            fields="summary,description,issuetype",
        )
        logger.info("Fetched %d epics from Jira", len(epic_issues))

        epics = []
        for issue in epic_issues:
            epic_key = issue["key"]
            epic_summary = issue["fields"].get("summary", "")
            epic_description = _extract_description_text(
                issue["fields"].get("description")
            )

            stories = _fetch_stories_for_epic(
                base_url=base_url,
                auth=auth,
                headers=headers,
                epic_key=epic_key,
                epic_link_field=epic_link_field,
            )

            epics.append(
                {
                    "issue_key": epic_key,
                    "epic_title": epic_summary,
                    "epic_description": epic_description,
                    "user_stories": stories,
                }
            )

        return {"status": "success", "epics": epics}

    except RuntimeError as exc:
        logger.error("Jira search error in fetch_jira_epics_and_stories: %s", exc)
        return {"status": "error", "error_message": str(exc)}
    except Exception as exc:
        logger.exception("Error fetching Jira epics and stories: %s", exc)
        return {"status": "error", "error_message": str(exc)}


def _fetch_stories_for_epic(
    base_url: str,
    auth: tuple,
    headers: dict,
    epic_key: str,
    epic_link_field: Optional[str],
) -> list[dict]:
    """Fetch all Story-type issues that belong to the given Epic."""
    # Use the new Enhanced JQL search endpoint (legacy /rest/api/3/search
    # was removed for cloud tenants on 2025-04-30).
    search_url = base_url.rstrip("/") + "/rest/api/3/search/jql"
    story_issue_type = os.getenv("JIRA_STORY_ISSUE_TYPE", "Story")

    # Build JQL: try 'parent' (team-managed) or epic link field (classic)
    if epic_link_field and epic_link_field != "parent":
        jql = (
            f'(parent = {epic_key} OR "{epic_link_field}" = {epic_key}) '
            f'AND issuetype = "{story_issue_type}"'
        )
    else:
        jql = f'parent = {epic_key} AND issuetype = "{story_issue_type}"'

    try:
        issues = _paginated_jira_search(
            search_url=search_url,
            auth=auth,
            headers=headers,
            jql=jql,
            fields="summary,description",
        )
        logger.info("Fetched %d stories for epic %s", len(issues), epic_key)

        return [
            {
                "issue_key": issue["key"],
                "title": issue["fields"].get("summary", ""),
                "description": _extract_description_text(
                    issue["fields"].get("description")
                ),
            }
            for issue in issues
        ]

    except Exception as exc:
        logger.warning("Error fetching stories for epic %s: %s", epic_key, exc)
        return []


# ---------------------------------------------------------------------------
# ADF → plain text helpers
# ---------------------------------------------------------------------------

def _extract_description_text(description_field) -> str:
    """Extract readable plain text from a Jira ADF description field."""
    if not description_field:
        return ""
    if isinstance(description_field, str):
        return description_field
    if isinstance(description_field, dict) and description_field.get("type") == "doc":
        return _adf_to_text(description_field).strip()
    return str(description_field)


def _adf_to_text(node: dict) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    if not node:
        return ""

    node_type = node.get("type", "")

    if node_type == "text":
        return node.get("text", "")

    content = node.get("content") or []
    parts = [_adf_to_text(child) for child in content]

    if node_type in ("paragraph", "heading"):
        return " ".join(p for p in parts if p).strip() + "\n"
    elif node_type == "listItem":
        return "- " + " ".join(p for p in parts if p).strip() + "\n"
    elif node_type in ("bulletList", "orderedList"):
        return "".join(parts)
    else:
        return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Lightweight epic picker (for UI)
# ---------------------------------------------------------------------------

def get_project_epics(project_key: Optional[str] = None) -> dict:
    """Fetch all epics in a project for the UI picker.

    Returns a lightweight list: issue_key + epic_title only.
    Results are paginated internally so all epics are returned regardless of
    project size.

    Args:
        project_key: Jira project key. Falls back to JIRA_PROJECT_KEY env var.

    Returns:
        {"status": "success", "epics": [{"issue_key": ..., "epic_title": ...}, ...]}
        or {"status": "error", "error_message": "..."}
    """
    try:
        search_context = _get_jira_search_context(project_key)
    except JiraConfigError as exc:
        return jira_config_error_result(exc)

    resolved_project = search_context["resolved_project"]

    if not resolved_project:
        return {
            "status": "error",
            "error_message": (
                "No project key provided. Pass project_key in the request or set "
                "JIRA_PROJECT_KEY environment variable."
            ),
        }

    auth = search_context["auth"]
    headers = search_context["headers"]
    search_url = search_context["search_url"]
    epic_issue_type = search_context["epic_issue_type"]
    jql = (
        f'project = {resolved_project} AND issuetype = "{epic_issue_type}" '
        f"ORDER BY created DESC"
    )

    try:
        issues = _paginated_jira_search(
            search_url=search_url,
            auth=auth,
            headers=headers,
            jql=jql,
            fields="summary",
        )
        logger.info(
            "Fetched %d epics for project %s", len(issues), resolved_project
        )
        epics = [
            {"issue_key": issue["key"], "epic_title": issue["fields"].get("summary", "")}
            for issue in issues
        ]
        return {"status": "success", "epics": epics}

    except RuntimeError as exc:
        logger.error("Jira search error in get_project_epics: %s", exc)
        return {"status": "error", "error_message": str(exc)}
    except Exception as exc:
        logger.exception("Error fetching project epics: %s", exc)
        return {"status": "error", "error_message": str(exc)}
