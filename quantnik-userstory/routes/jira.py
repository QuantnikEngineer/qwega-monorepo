from fastapi import APIRouter, HTTPException

from models.schemas import AdditionalUserStory, JiraIssueDelete, JiraIssueUpdate
from tools.exporter import delete_jira_issue, export_additional_stories, update_jira_issue

from .support import (
    batch_operation_status,
    find_duplicate_strings,
    logger,
    raise_internal_error,
)


router = APIRouter()


@router.put(
    "/jira-issue",
    tags=["Jira Integration"],
    summary="Update existing Jira issues",
    description="Update one or more Jira issues' title (summary) and/or description",
    response_description="Jira update result"
)
async def update_jira_issue_endpoint(payload: list[JiraIssueUpdate]):
    """Update one or more existing Jira issues' title and/or description."""
    logger.info("Jira issue update requested for %d issues", len(payload))

    keys = [item.issue_key for item in payload]
    duplicates = find_duplicate_strings(keys)
    if duplicates:
        raise HTTPException(
            422,
            f"Duplicate issue_keys in batch: {', '.join(duplicates)}. "
            "Each issue_key may appear at most once per request.",
        )

    try:
        results = []
        for item in payload:
            logger.info("Updating Jira issue: %s", item.issue_key)
            result = update_jira_issue(
                issue_key=item.issue_key,
                summary=item.summary,
                description=item.description,
                expected_summary=item.expected_summary,
                expected_description=item.expected_description,
            )
            results.append(result)

        return {
            "status": batch_operation_status(results),
            "jira_update_results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_internal_error(
            "Failed to update Jira issues",
            "Failed to update Jira issues",
            e,
        )


@router.post(
    "/create-additional-stories",
    tags=["Jira Integration"],
    summary="Create additional user stories under existing Jira epics",
    description=(
        "Create new Jira Story issues for existing Jira Epics. This is "
        "intended for user stories suggested by a separate validator agent "
        "that analyzes existing Jira issues. Each payload item must include "
        "the target epic's Jira issue key."
    ),
    response_description="Jira creation result for additional stories",
)
async def create_additional_stories_endpoint(payload: list[AdditionalUserStory]):
    """Create additional Jira Stories linked to existing Epics."""
    logger.info("Jira creation requested for %d additional stories", len(payload))

    try:
        stories = [story.model_dump() for story in payload]
        result = export_additional_stories(stories)
        logger.info(
            "Additional Jira story creation completed with status: %s",
            result.get("status"),
        )
        return {
            "status": result.get("status"),
            "jira_export_result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_error(
            "Failed to create additional Jira stories",
            "Failed to create additional Jira stories",
            e,
        )


@router.delete(
    "/delete-jira-issues",
    tags=["Jira Integration"],
    summary="Delete one or more Jira issues",
    description=(
        "Delete multiple Jira issues in Jira by their keys. Each item in the "
        "payload can optionally specify whether subtasks should also be deleted "
        "(delete_subtasks flag). By default, subtasks are not deleted."
    ),
    response_description="Jira delete results",
)
async def delete_jira_issues_endpoint(payload: list[JiraIssueDelete]):
    """Delete one or more Jira issues identified by their keys."""
    logger.info("Jira issues delete requested for %d issues", len(payload))

    try:
        results = []
        for item in payload:
            logger.info(
                "Deleting Jira issue %s (delete_subtasks=%s)",
                item.issue_key,
                item.delete_subtasks,
            )
            result = delete_jira_issue(
                issue_key=item.issue_key,
                delete_subtasks=bool(item.delete_subtasks),
            )
            results.append(result)

        return {
            "status": batch_operation_status(results),
            "jira_delete_results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_internal_error(
            "Failed to delete Jira issues",
            "Failed to delete Jira issues",
            e,
        )