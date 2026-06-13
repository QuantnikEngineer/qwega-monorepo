import os
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable

from .http_utils import (
    classify_http_error,
    http_request_with_retry,
)
from .jira_common import JiraConfigError, get_jira_config, jira_config_error_result

logger = logging.getLogger(__name__)

# Jira limits
MAX_SUMMARY_LENGTH = 255
MAX_STORIES_PER_EPIC_WARNING = 50
MAX_DESCRIPTION_CHARS = 32767  # Jira ADF limit

# Concurrency settings
MAX_CONCURRENT_JIRA_REQUESTS = int(os.getenv("MAX_CONCURRENT_JIRA_REQUESTS", "5"))

# URL pattern for detecting links in text
_URL_PATTERN = re.compile(r'(https?://[^\s<>"{}|\\^`\[\]]+)')


def _truncate_summary(summary: str) -> str:
    """Truncate summary to Jira's max length."""
    if len(summary) <= MAX_SUMMARY_LENGTH:
        return summary
    logger.warning("Truncating summary from %d to %d chars", len(summary), MAX_SUMMARY_LENGTH)
    return summary[:MAX_SUMMARY_LENGTH - 3] + "..."


def _format_jira_error_guidance(status_code: int, response_text: str) -> str:
    """Provide actionable guidance for common Jira errors."""
    if status_code == 401:
        return (
            "Jira authentication failed. Verify JIRA_EMAIL and JIRA_API_TOKEN "
            "are correct. API tokens can be generated at: "
            "https://id.atlassian.com/manage-profile/security/api-tokens"
        )
    if status_code == 403:
        return (
            "Jira permission denied. Ensure the API token owner has permission "
            "to create issues in the target project. Check project permissions "
            "and issue type schemes."
        )
    if status_code == 404:
        if "project" in response_text.lower():
            return (
                f"Jira project not found. Verify JIRA_PROJECT_KEY is correct "
                f"and the project exists."
            )
        return "Jira resource not found. Check issue keys and project configuration."
    if status_code == 400:
        if "issuetype" in response_text.lower():
            return (
                "Invalid issue type. Check JIRA_EPIC_ISSUE_TYPE, JIRA_STORY_ISSUE_TYPE, "
                "and JIRA_SUBTASK_ISSUE_TYPE match your Jira project's issue type scheme."
            )
        if "priority" in response_text.lower():
            return (
                "Invalid priority value. Ensure your Jira project has the standard "
                "priority scheme (Highest, High, Medium, Low, Lowest)."
            )
    if status_code == 429:
        return "Jira rate limit exceeded. Wait a few minutes and retry."
    if 500 <= status_code < 600:
        return "Jira server error. This is usually temporary; retry in a few minutes."
    return f"Jira request failed: HTTP {status_code}"


def _make_adf_text(text: str, marks: list[dict] | None = None) -> dict:
    """Create an ADF text node, optionally with marks (bold, italic, etc.)."""
    node: dict = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def _make_adf_link(url: str, display_text: str | None = None) -> dict:
    """Create an ADF text node with a link mark (clickable URL)."""
    return {
        "type": "text",
        "text": display_text or url,
        "marks": [{"type": "link", "attrs": {"href": url}}],
    }


def _parse_text_with_links(text: str) -> list[dict]:
    """Parse text and convert URLs to clickable ADF link nodes."""
    if not text:
        return [_make_adf_text("")]
    
    parts = _URL_PATTERN.split(text)
    nodes: list[dict] = []
    
    for part in parts:
        if not part:
            continue
        if _URL_PATTERN.match(part):
            nodes.append(_make_adf_link(part))
        else:
            nodes.append(_make_adf_text(part))
    
    return nodes if nodes else [_make_adf_text(text)]


def _make_adf_paragraph(content: list[dict]) -> dict:
    """Create an ADF paragraph node."""
    return {"type": "paragraph", "content": content}


def _make_adf_heading(text: str, level: int = 3) -> dict:
    """Create an ADF heading node."""
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [_make_adf_text(text)],
    }


def _make_adf_bullet_list(items: list[str]) -> dict:
    """Create an ADF bulletList node from a list of strings."""
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [_make_adf_paragraph(_parse_text_with_links(item))],
            }
            for item in items
        ],
    }


def _parse_text_to_rich_adf(text: str) -> dict:
    """Parse a multi-line description text into a rich ADF document.

    Recognises patterns like:
    - Lines ending with ':' → treated as headings
    - Lines starting with '- ' or '* ' → collected into bullet lists
    - Other lines → paragraphs

    Returns a full ADF doc structure.
    """

    if not text:
        return {
            "type": "doc",
            "version": 1,
            "content": [_make_adf_paragraph([_make_adf_text("")])],
        }

    lines = text.split("\n")
    content: list[dict] = []
    bullet_buffer: list[str] = []

    def flush_bullets():
        nonlocal bullet_buffer
        if bullet_buffer:
            content.append(_make_adf_bullet_list(bullet_buffer))
            bullet_buffer = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            flush_bullets()
            continue

        # Detect bullet points
        if stripped.startswith("- ") or stripped.startswith("* "):
            bullet_buffer.append(stripped[2:])
            continue

        # Flush any pending bullets before a non-bullet line
        flush_bullets()

        # Detect section headings (lines ending with ':' that are short labels)
        if stripped.endswith(":") and len(stripped) < 80 and not stripped.startswith("As a"):
            content.append(_make_adf_heading(stripped, level=3))
            continue

        # Regular paragraph - parse for URLs to make them clickable
        content.append(_make_adf_paragraph(_parse_text_with_links(stripped)))

    flush_bullets()

    if not content:
        content.append(_make_adf_paragraph([_make_adf_text(text)]))

    return {"type": "doc", "version": 1, "content": content}


def _build_rich_adf_story_description(story: dict) -> dict | None:
    """Build a rich ADF description for a user story with structured sections."""

    story_description = story.get("description") or ""
    ac_list = story.get("acceptance_criteria") or []

    if not story_description and not ac_list:
        return None

    content: list[dict] = []

    # Story description as paragraph(s)
    if story_description:
        for para in story_description.split("\n"):
            para = para.strip()
            if para:
                content.append(_make_adf_paragraph([_make_adf_text(para)]))

    # Acceptance Criteria section
    if ac_list:
        content.append(_make_adf_heading("Acceptance Criteria", level=3))
        criteria_items: list[str] = []
        for ac in ac_list:
            if isinstance(ac, dict):
                criterion = ac.get("criterion", "")
            else:
                criterion = str(ac)
            if criterion:
                criteria_items.append(criterion)
        if criteria_items:
            content.append(_make_adf_bullet_list(criteria_items))

    if not content:
        return None

    return {"type": "doc", "version": 1, "content": content}


def _create_subtasks_for_story(
    base_url: str,
    auth: tuple,
    headers: dict,
    project_key: str,
    parent_story_key: str,
    sub_tasks: list[dict],
    subtask_issue_type: str,
) -> tuple[list[dict], bool]:
    """Create sub-tasks under a parent story."""
    api_url = base_url + "/rest/api/3/issue"
    created_subtasks: list[dict] = []
    all_success = True

    for subtask in sub_tasks:
        subtask_title = subtask.get("title")
        if not subtask_title:
            logger.warning("Skipping sub-task with empty title for story %s", parent_story_key)
            all_success = False
            continue

        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": subtask_title,
            "issuetype": {"name": subtask_issue_type},
            "parent": {"key": parent_story_key},
        }

        subtask_description = subtask.get("description")
        if subtask_description:
            adf_desc = _build_adf_description(subtask_description)
            if adf_desc:
                fields["description"] = adf_desc

        response = http_request_with_retry(
            "POST", api_url, json={"fields": fields}, auth=auth, headers=headers,
        )

        if response.status_code >= 300:
            logger.error(
                "Failed to create sub-task '%s' under %s: %s - %s",
                subtask_title, parent_story_key, response.status_code, response.text,
            )
            all_success = False
            continue

        subtask_data = response.json()
        subtask_key = subtask_data.get("key")
        browse_url = _build_issue_url(base_url, subtask_key)
        if browse_url:
            subtask_data["browse_url"] = browse_url
        logger.info("Created sub-task %s under story %s", subtask_key, parent_story_key)
        created_subtasks.append(subtask_data)

    return created_subtasks, all_success


def _create_single_story(
    base_url: str,
    auth: tuple,
    headers: dict,
    api_url: str,
    project_key: str,
    story: dict,
    epic_key: str | None,
    epic_link_field: str | None,
    story_issue_type: str,
    subtask_issue_type: str,
) -> dict:
    """Create a single story with its sub-tasks. Used for parallel execution."""
    story_title = _truncate_summary(story.get("title") or "Generated Story")
    
    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "summary": story_title,
        "issuetype": {"name": story_issue_type},
    }

    story_adf_description = _build_rich_adf_story_description(story)
    if story_adf_description is not None:
        fields["description"] = story_adf_description

    story_priority = story.get("priority")
    if story_priority:
        fields["priority"] = {"name": story_priority}

    if epic_link_field and epic_key:
        if epic_link_field == "parent":
            fields["parent"] = {"key": epic_key}
        else:
            fields[epic_link_field] = epic_key

    story_payload = {"fields": fields}

    story_response = http_request_with_retry(
        "POST", api_url, json=story_payload, auth=auth, headers=headers,
    )
    
    if story_response.status_code >= 300:
        return {
            "status": "error",
            "story_title": story_title,
            "status_code": story_response.status_code,
            "response_text": story_response.text,
        }

    story_data = story_response.json()
    story_key = story_data.get("key")
    result = {
        "status": "success",
        "story": _annotate_created_issue(story_data, base_url, "Story"),
        "subtasks": [],
    }

    # Create sub-tasks if provided
    sub_tasks = story.get("sub_tasks") or []
    if sub_tasks and story_key:
        subtasks_created, _ = _create_subtasks_for_story(
            base_url, auth, headers, project_key,
            story_key, sub_tasks, subtask_issue_type,
        )
        result["subtasks"] = subtasks_created

    logger.debug("Created story %s with %d sub-tasks", story_key, len(result["subtasks"]))
    return result


_REFERENCE_LINE_PATTERN = re.compile(
    r"^\s*\**\s*Reference\s*[:\-].*$", re.IGNORECASE,
)


def _strip_reference_lines(epic_description: str) -> str:
    """Remove any agent-generated 'Reference: ...' lines from the description.

    The exporter takes ownership of rendering the Reference link so the
    Confluence BRD page title becomes the clickable label.  Removing the
    agent's plain-text version avoids duplicate / inconsistent references.
    """
    if not epic_description:
        return epic_description

    cleaned: list[str] = []
    for line in epic_description.split("\n"):
        if _REFERENCE_LINE_PATTERN.match(line):
            continue
        cleaned.append(line)

    # Collapse trailing blank lines introduced by the removal.
    while cleaned and not cleaned[-1].strip():
        cleaned.pop()

    return "\n".join(cleaned)


def _build_reference_adf_paragraph(brd_title: str | None, brd_url: str) -> dict:
    """Build an ADF paragraph: 'Reference: <clickable title>'.

    The link's display text is the Confluence page title (when available),
    falling back to the URL itself.  The href always points at the BRD URL
    so clicking it navigates to the source Confluence page.
    """
    display_text = (brd_title or "").strip() or brd_url
    return _make_adf_paragraph([
        _make_adf_text("Reference: "),
        _make_adf_link(brd_url, display_text=display_text),
    ])


def _build_adf_description(text: str | None) -> dict | None:
    """Build a minimal Atlassian Document Format (ADF) description.

    Some Jira Cloud projects require description to be in ADF instead of a
    plain string. This helper wraps a simple text block into the structure
    Jira expects. If text is empty, returns None so the field can be omitted.
    """

    if not text:
        return None

    return _parse_text_to_rich_adf(text)


def _build_issue_url(base_url: str, issue_key: str | None) -> str | None:
    """Return a clickable Jira browse URL for the given issue key."""

    if not base_url or not issue_key:
        return None

    return base_url.rstrip("/") + f"/browse/{issue_key}"


def _annotate_created_issue(issue_data: dict[str, Any], base_url: str, issue_label: str) -> dict[str, Any]:
    """Add browse URL plus consistent logging/console output for created issues."""
    issue_key = issue_data.get("key")
    issue_url = _build_issue_url(base_url, issue_key)
    if issue_url:
        issue_data["browse_url"] = issue_url
        logger.info("Created %s %s: %s", issue_label, issue_key, issue_url)
        print(f"[Jira Export] Created {issue_label} {issue_key}: {issue_url}")
    return issue_data


def _rollback_created_issues(
    base_url: str,
    auth: tuple,
    headers: dict,
    issue_keys: list[str],
    delete_subtasks: bool = True,
) -> list[str]:
    """Best-effort rollback: delete every issue key in the list.

    Returns the list of issue keys that could NOT be deleted so the caller
    can include them in the error response (operators must clean these up
    manually).  Failures are logged at error level so they surface in alerts.
    """
    if not issue_keys:
        return []

    delete_url_tpl = base_url.rstrip("/") + "/rest/api/3/issue/{key}"
    params = {"deleteSubtasks": "true" if delete_subtasks else "false"}
    failed: list[str] = []

    for key in issue_keys:
        try:
            resp = http_request_with_retry(
                "DELETE",
                delete_url_tpl.format(key=key),
                auth=auth,
                headers=headers,
                params=params,
            )
            if resp.status_code < 300 or resp.status_code == 404:
                logger.info("[Rollback] Deleted %s", key)
            else:
                failed.append(key)
                logger.error(
                    "[Rollback] Could not delete %s: HTTP %s — %s",
                    key, resp.status_code, resp.text,
                )
        except Exception as exc:
            failed.append(key)
            logger.error("[Rollback] Exception deleting %s: %s", key, exc)

    if failed:
        logger.error(
            "[Rollback] %d issue(s) could not be cleaned up and remain orphaned in Jira: %s",
            len(failed), failed,
        )
    return failed


def export_additional_stories(stories: Iterable[dict]) -> dict:
    """Creates additional Jira Stories under existing Epics.

    Each story dict must contain at least:

    - epic_issue_key (str): Jira key of the target Epic (e.g. "PROJ-1").
    - title (str): Story title.
    - description (str): Main description text.
    - acceptance_criteria (list[dict | str]): Acceptance criteria; see
      ``_build_story_description`` for supported formats.

    On any unrecoverable error after stories have already been created, those
    stories are deleted (rolled back) before returning an error response.

    Returns a dict similar to ``export_to_jira`` with overall status and the
    list of created stories.
    """

    base_url: str | None = None
    auth: tuple | None = None
    rollback_story_keys: list[str] = []

    try:
        stories_list = list(stories or [])
        logger.info(
            "Starting Jira export for %d additional stories (existing epics)",
            len(stories_list),
        )

        try:
            base_url, auth, project_key = get_jira_config()
        except JiraConfigError as exc:
            logger.error("%s", exc)
            return jira_config_error_result(exc)

        story_issue_type = os.getenv("JIRA_STORY_ISSUE_TYPE", "Story")
        subtask_issue_type = os.getenv("JIRA_SUBTASK_ISSUE_TYPE", "Sub-task")
        epic_link_field = os.getenv("JIRA_EPIC_LINK_FIELD")

        api_url = base_url + "/rest/api/3/issue"
        headers = {"Content-Type": "application/json"}

        created_stories: list[dict] = []
        created_subtasks: list[dict] = []
        all_success = True

        # Filter out stories without epic_issue_key
        valid_stories = []
        for story in stories_list:
            epic_issue_key = story.get("epic_issue_key")
            if not epic_issue_key:
                logger.error("Skipping story without epic_issue_key: %s", story)
                all_success = False
            else:
                valid_stories.append(story)

        # Create stories in parallel
        if valid_stories:
            logger.info(f"Creating {len(valid_stories)} additional stories in parallel (max {MAX_CONCURRENT_JIRA_REQUESTS} concurrent)")
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JIRA_REQUESTS) as executor:
                future_to_story = {
                    executor.submit(
                        _create_single_story,
                        base_url, auth, headers, api_url, project_key,
                        story, story.get("epic_issue_key"), epic_link_field,
                        story_issue_type, subtask_issue_type,
                    ): story
                    for story in valid_stories
                }
                
                for future in as_completed(future_to_story):
                    result = future.result()
                    if result["status"] == "error":
                        logger.error(
                            "Failed to create additional story '%s' in Jira: %s - %s",
                            result["story_title"], result["status_code"], result["response_text"],
                        )
                        all_success = False
                        continue
                    
                    story_data = result["story"]
                    story_key = story_data.get("key")
                    if story_key:
                        rollback_story_keys.append(story_key)
                    created_stories.append(story_data)
                    created_subtasks.extend(result["subtasks"])

        overall_status = "success" if all_success else "partial_error"

        logger.info(
            "Jira export for additional stories completed with status '%s' and %d stories, %d sub-tasks",
            overall_status,
            len(created_stories),
            len(created_subtasks),
        )

        return {
            "status": overall_status,
            "created": {
                "stories": created_stories,
                "subtasks": created_subtasks,
            },
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("Error while exporting additional stories to Jira: %s", str(exc))
        if rollback_story_keys and base_url and auth:
            logger.error(
                "Exception during additional-story export, rolling back %d story/stories: %s",
                len(rollback_story_keys),
                rollback_story_keys,
            )
            _rollback_created_issues(base_url, auth, {"Content-Type": "application/json"}, rollback_story_keys, delete_subtasks=False)
        return {"status": "error", "error_message": str(exc)}


def export_to_jira(
    epics: list[dict],
    brd_url: str | None = None,
    brd_title: str | None = None,
) -> dict:
    """Creates Jira issues (Epics and Stories) for generated user stories.

    Configuration is read from environment variables:

    - JIRA_BASE_URL (required), e.g. "https://your-domain.atlassian.net"
    - JIRA_EMAIL (required)
    - JIRA_API_TOKEN (required)
    - JIRA_PROJECT_KEY (required)
    - JIRA_EPIC_ISSUE_TYPE (optional, default: "Epic")
    - JIRA_STORY_ISSUE_TYPE (optional, default: "Story")
    - JIRA_EPIC_LINK_FIELD (optional, e.g. "customfield_10014" for Epic Link)

    Args:
        epics: List of epic dictionaries in the same structure used by export_to_docx.
        brd_url: Source BRD Confluence URL. When provided, every epic description
            gets a single 'Reference: <title>' clickable link pointing at this URL,
            and brownfield analysis can later auto-discover related epics by
            searching Jira for the URL.
        brd_title: Confluence page title used as the clickable display text for
            the Reference link.  Falls back to the URL itself when missing.

    Returns:
        dict: {"status": "success", "created": {...}} on success,
              or {"status": "error", "error_message": "..."} on failure.
    """

    base_url: str | None = None
    auth: tuple | None = None
    rollback_epic_keys: list[str] = []

    try:
        logger.info(f"Starting Jira export for {len(epics or [])} epics")
        try:
            base_url, auth, project_key = get_jira_config()
        except JiraConfigError as exc:
            logger.error("%s", exc)
            return jira_config_error_result(exc)

        epic_issue_type = os.getenv("JIRA_EPIC_ISSUE_TYPE", "Epic")
        story_issue_type = os.getenv("JIRA_STORY_ISSUE_TYPE", "Story")
        subtask_issue_type = os.getenv("JIRA_SUBTASK_ISSUE_TYPE", "Sub-task")
        epic_link_field = os.getenv("JIRA_EPIC_LINK_FIELD")

        api_url = base_url + "/rest/api/3/issue"
        headers = {"Content-Type": "application/json"}

        created_epics: dict[str, dict] = {}
        created_stories: list[dict] = []
        created_subtasks: list[dict] = []

        for epic in epics or []:
            epic_title = _truncate_summary(epic.get("epic_title") or "Generated Epic")
            epic_description = epic.get("epic_description") or ""
            logger.info(f"Creating Jira epic: {epic_title}")

            # Warn if epic has many stories
            user_stories = epic.get("user_stories") or []
            if len(user_stories) > MAX_STORIES_PER_EPIC_WARNING:
                logger.warning(
                    "Epic '%s' has %d stories (> %d). Consider splitting into multiple epics.",
                    epic_title, len(user_stories), MAX_STORIES_PER_EPIC_WARNING,
                )

            # Strip any plain-text 'Reference:' line the agent emitted; the
            # exporter owns rendering the BRD reference as a single clickable
            # link with the Confluence page title as display text.
            if brd_url:
                epic_description = _strip_reference_lines(epic_description)

            epic_payload = {
                "fields": {
                    "project": {"key": project_key},
                    "summary": epic_title,
                    "issuetype": {"name": epic_issue_type},
                }
            }

            epic_adf_description = _build_adf_description(epic_description)

            # Append the canonical Reference paragraph as a proper ADF link so
            # clicking the BRD title navigates to the source Confluence page.
            # Brownfield analysis can still auto-discover the epic by searching
            # for the URL: the link's href is exactly the BRD URL.
            if brd_url:
                if epic_adf_description is None:
                    epic_adf_description = {
                        "type": "doc",
                        "version": 1,
                        "content": [],
                    }
                epic_adf_description["content"].append(
                    _build_reference_adf_paragraph(brd_title, brd_url)
                )

            if epic_adf_description is not None:
                epic_payload["fields"]["description"] = epic_adf_description

            epic_response = http_request_with_retry(
                "POST", api_url, json=epic_payload, auth=auth, headers=headers,
            )
            if epic_response.status_code >= 300:
                logger.error(f"Failed to create epic in Jira: {epic_response.status_code} - {epic_response.text}")
                rollback_failed = _rollback_created_issues(base_url, auth, {"Content-Type": "application/json"}, rollback_epic_keys)
                guidance = _format_jira_error_guidance(epic_response.status_code, epic_response.text)
                return {
                    "status": "error",
                    "error_message": f"Failed to create Epic in Jira: {guidance}",
                    "rolled_back_keys": rollback_epic_keys,
                    "rollback_failed_keys": rollback_failed,
                }

            epic_data = epic_response.json()
            epic_key = epic_data.get("key")
            if epic_key:
                rollback_epic_keys.append(epic_key)
            created_epics[epic_key or epic_title] = _annotate_created_issue(
                epic_data,
                base_url,
                "Epic",
            )

            # Create stories in parallel for better performance
            if user_stories:
                logger.info(f"Creating {len(user_stories)} stories in parallel (max {MAX_CONCURRENT_JIRA_REQUESTS} concurrent)")
                with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JIRA_REQUESTS) as executor:
                    future_to_story = {
                        executor.submit(
                            _create_single_story,
                            base_url, auth, headers, api_url, project_key,
                            story, epic_key, epic_link_field,
                            story_issue_type, subtask_issue_type,
                        ): story
                        for story in user_stories
                    }
                    
                    for future in as_completed(future_to_story):
                        result = future.result()
                        if result["status"] == "error":
                            logger.error(
                                "Failed to create story '%s' in Jira: %s - %s",
                                result["story_title"], result["status_code"], result["response_text"],
                            )
                            rollback_failed = _rollback_created_issues(
                                base_url, auth, {"Content-Type": "application/json"}, rollback_epic_keys
                            )
                            guidance = _format_jira_error_guidance(result["status_code"], result["response_text"])
                            return {
                                "status": "error",
                                "error_message": f"Failed to create Story in Jira: {guidance}",
                                "rolled_back_keys": rollback_epic_keys,
                                "rollback_failed_keys": rollback_failed,
                            }
                        created_stories.append(result["story"])
                        created_subtasks.extend(result["subtasks"])

        logger.info(
            f"Jira export completed successfully. Created {len(created_epics)} epics, "
            f"{len(created_stories)} stories, {len(created_subtasks)} sub-tasks"
        )
        return {
            "status": "success",
            "created": {
                "epics": created_epics,
                "stories": created_stories,
                "subtasks": created_subtasks,
            },
        }

    except Exception as e:
        # Attempt to clean up any epics already created before the exception
        if rollback_epic_keys:
            logger.error(
                "Exception during export, attempting rollback of %d epic(s): %s",
                len(rollback_epic_keys),
                rollback_epic_keys,
            )
            try:
                _rollback_created_issues(
                    base_url, auth, {"Content-Type": "application/json"}, rollback_epic_keys
                )
            except Exception:
                pass
        return {"status": "error", "error_message": str(e)}


def update_jira_issue(
    issue_key: str,
    summary: str | None = None,
    description: str | None = None,
    expected_summary: str | None = None,
    expected_description: str | None = None,
) -> dict:
    """Updates an existing Jira issue's summary and/or description.

    Optionally performs a read-before-write conflict check: if
    ``expected_summary`` and/or ``expected_description`` are supplied, the
    current Jira values are fetched first and the update is refused with
    ``status="conflict"`` if either differs.  This lets callers implement
    optimistic concurrency control.

    Returns ``status`` of one of: success / error / not_found / conflict.
    """

    try:
        logger.info(f"Updating Jira issue: {issue_key}")
        try:
            base_url, auth, _ = get_jira_config(require_project=False)
        except JiraConfigError as exc:
            logger.error("%s", exc)
            return jira_config_error_result(exc)

        if not issue_key:
            return {
                "status": "error",
                "error_message": "Jira issue key is required to perform an update.",
            }

        fields: dict[str, Any] = {}

        if summary is not None:
            fields["summary"] = summary

        if description is not None:
            adf_description = _build_adf_description(description)
            if adf_description is not None:
                fields["description"] = adf_description

        if not fields:
            return {
                "status": "error",
                "error_message": "No fields provided to update.",
            }

        api_url = base_url + f"/rest/api/3/issue/{issue_key}"
        headers = {"Content-Type": "application/json"}

        if expected_summary is not None or expected_description is not None:
            try:
                current = _get_jira_issue_text(base_url, auth, issue_key)
            except _JiraNotFound:
                return {
                    "status": "not_found",
                    "issue_key": issue_key,
                    "error_message": f"Jira issue {issue_key} does not exist.",
                }
            mismatches: list[str] = []
            if expected_summary is not None and current["summary"] != expected_summary:
                mismatches.append("summary")
            if expected_description is not None and current["description"] != expected_description:
                mismatches.append("description")
            if mismatches:
                logger.warning(
                    "Conflict on update of %s: fields differ from expected: %s",
                    issue_key, mismatches,
                )
                return {
                    "status": "conflict",
                    "issue_key": issue_key,
                    "conflicting_fields": mismatches,
                    "current_summary": current["summary"],
                    "current_description": current["description"],
                    "error_message": (
                        f"Jira issue {issue_key} was modified since you last fetched it. "
                        f"Conflicting fields: {', '.join(mismatches)}. Re-fetch and retry."
                    ),
                }

        response = http_request_with_retry(
            "PUT", api_url, json={"fields": fields}, auth=auth, headers=headers,
        )

        if response.status_code == 404:
            logger.warning("Update target %s not found in Jira", issue_key)
            return {
                "status": "not_found",
                "issue_key": issue_key,
                "error_message": f"Jira issue {issue_key} does not exist.",
            }

        if response.status_code >= 300:
            logger.error(
                "Failed to update Jira issue %s: %s - %s",
                issue_key, response.status_code, response.text,
            )
            return {
                "status": "error",
                "error_category": classify_http_error(response.status_code),
                "error_message": (
                    f"Failed to update Jira issue {issue_key}: "
                    f"HTTP {response.status_code} {response.text}"
                ),
            }

        browse_url = _build_issue_url(base_url, issue_key)

        logger.info(f"Successfully updated Jira issue: {issue_key}")
        return {
            "status": "success",
            "issue_key": issue_key,
            "browse_url": browse_url,
        }

    except Exception as e:
        logger.exception("Unexpected error updating %s: %s", issue_key, e)
        return {"status": "error", "error_message": str(e)}


class _JiraNotFound(Exception):
    """Raised by _get_jira_issue_text when the issue does not exist."""


def _get_jira_issue_text(base_url: str, auth: tuple, issue_key: str) -> dict:
    """Fetch the current summary + flattened description of a Jira issue.

    Returns ``{"summary": str, "description": str}``.  Raises ``_JiraNotFound``
    on HTTP 404 and ``RuntimeError`` on any other non-2xx response.
    """
    # Local import to avoid a circular dependency between exporter and fetcher.
    from .jira_fetcher import _extract_description_text

    api_url = base_url.rstrip("/") + f"/rest/api/3/issue/{issue_key}"
    response = http_request_with_retry(
        "GET", api_url, auth=auth, headers={"Accept": "application/json"},
        params={"fields": "summary,description"},
    )
    if response.status_code == 404:
        raise _JiraNotFound(issue_key)
    if response.status_code >= 300:
        raise RuntimeError(
            f"Jira GET {issue_key} failed: HTTP {response.status_code} {response.text}"
        )
    data = response.json().get("fields", {})
    return {
        "summary": data.get("summary") or "",
        "description": _extract_description_text(data.get("description")).strip(),
    }


def delete_jira_issue(issue_key: str, delete_subtasks: bool = False) -> dict:
    """Deletes an existing Jira issue.

    Returns ``status`` of one of: success / not_found / error.
    """

    try:
        logger.info(f"Deleting Jira issue: {issue_key} (delete_subtasks={delete_subtasks})")
        try:
            base_url, auth, _ = get_jira_config(require_project=False)
        except JiraConfigError as exc:
            logger.error("%s", exc)
            return jira_config_error_result(exc)

        if not issue_key:
            return {
                "status": "error",
                "error_message": "Jira issue key is required to perform a delete.",
            }

        api_url = base_url + f"/rest/api/3/issue/{issue_key}"
        headers = {"Content-Type": "application/json"}
        params = {"deleteSubtasks": "true" if delete_subtasks else "false"}

        response = http_request_with_retry(
            "DELETE", api_url, auth=auth, headers=headers, params=params,
        )

        if response.status_code == 404:
            logger.warning("Delete target %s not found in Jira", issue_key)
            return {
                "status": "not_found",
                "issue_key": issue_key,
                "error_message": f"Jira issue {issue_key} does not exist.",
            }

        if response.status_code >= 300:
            logger.error(
                "Failed to delete Jira issue %s: %s - %s",
                issue_key, response.status_code, response.text,
            )
            return {
                "status": "error",
                "error_category": classify_http_error(response.status_code),
                "error_message": (
                    f"Failed to delete Jira issue {issue_key}: "
                    f"HTTP {response.status_code} {response.text}"
                ),
            }

        browse_url = _build_issue_url(base_url, issue_key)

        logger.info(f"Successfully deleted Jira issue: {issue_key}")
        return {
            "status": "success",
            "issue_key": issue_key,
            "browse_url": browse_url,
        }

    except Exception as e:
        logger.exception("Unexpected error deleting %s: %s", issue_key, e)
        return {"status": "error", "error_message": str(e)}