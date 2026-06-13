import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from models.schemas import ApplyBrdUpdatesRequest, BrownfieldAnalysisRequest, BrownfieldAnalysisResult
from tools.brd_parser import parse_brd_from_confluence, validate_confluence_url
from tools.exporter import export_additional_stories, export_to_jira, update_jira_issue
from tools.jira_fetcher import fetch_jira_epics_and_stories, get_project_epics
from userstory.brownfield_agent import brownfield_agent

from .support import (
    AGENT_TIMEOUT_SECONDS,
    brd_error_to_http_status,
    build_story_update_description,
    logger,
    parse_agent_json,
    raise_internal_error,
    run_agent_or_timeout_http,
)


router = APIRouter()


@router.post(
    "/analyze-brd-updates",
    tags=["Brownfield"],
    summary="Compare updated BRD against existing Jira user stories",
    description=(
        "Fetches the latest BRD from the provided Confluence URL and compares it "
        "against existing Jira epics and stories. Returns a structured diff: which "
        "stories need updating, and which new stories should be created. "
        "No changes are written to Jira — apply them via the existing /jira-issue "
        "(PUT) and /create-additional-stories (POST) endpoints."
    ),
    response_description="Change-impact analysis result",
)
async def analyze_brd_updates(request: BrownfieldAnalysisRequest):
    """Compare an updated BRD against the existing Jira user stories."""
    logger.info("BRD update analysis requested")

    is_valid, reason = validate_confluence_url(request.brd_confluence_link)
    if not is_valid:
        logger.error(
            "Invalid Confluence URL rejected: %s — %s",
            request.brd_confluence_link, reason,
        )
        raise HTTPException(422, reason)

    logger.info("Fetching updated BRD from Confluence: %s", request.brd_confluence_link)
    brd_result = parse_brd_from_confluence(request.brd_confluence_link.strip())
    if brd_result["status"] == "error":
        category = brd_result.get("error_category")
        raise HTTPException(
            brd_error_to_http_status(category), brd_result["error_message"]
        )
    brd_text = brd_result["content"]
    logger.info("BRD fetched successfully (%d characters)", len(brd_text))

    logger.info(
        "Fetching existing Jira stories for epic_keys=%s", request.jira_epic_keys
    )
    jira_result = fetch_jira_epics_and_stories(request.jira_epic_keys)
    if jira_result["status"] == "error":
        raise HTTPException(502, jira_result["error_message"])

    existing_epics = jira_result["epics"]
    total_stories = sum(len(e.get("user_stories", [])) for e in existing_epics)
    logger.info(
        "Fetched %d epics with %d stories total", len(existing_epics), total_stories
    )

    if not existing_epics:
        raise HTTPException(
            404,
            "No epics found in Jira for the provided keys. "
            "Please check the epic keys and try again.",
        )

    try:
        delim = "===QUANTNIK-BROWNFIELD-SECTION-DELIMITER==="
        agent_input = (
            f"## NEW BRD CONTENT\n{delim}\n"
            f"{brd_text}\n{delim}\n\n"
            f"## EXISTING USER STORIES (JSON)\n{delim}\n"
            f"{json.dumps(existing_epics, indent=2)}\n{delim}"
        )

        logger.info("Running brownfield agent")
        final_text = await run_agent_or_timeout_http(
            agent=brownfield_agent,
            app_name="brownfield_story_agent",
            user_text=agent_input,
            timeout_log_label="Brownfield agent",
            timeout_detail=(
                f"Brownfield agent timed out after {AGENT_TIMEOUT_SECONDS:.0f}s. "
                "Try again with a smaller BRD or fewer epics."
            ),
        )

        if not final_text:
            raise HTTPException(502, "Brownfield agent failed to generate output")

        analysis_json = parse_agent_json(final_text)
        if not isinstance(analysis_json, dict):
            logger.error("Brownfield agent returned non-JSON output: %s", final_text[:500])
            raise HTTPException(502, "Brownfield agent returned an unreadable response")

        raw_no_changes = analysis_json.get("no_changes", False)
        if isinstance(raw_no_changes, str):
            analysis_json["no_changes"] = raw_no_changes.strip().lower() == "true"

        try:
            validated = BrownfieldAnalysisResult.model_validate(analysis_json)
        except ValidationError as exc:
            logger.error("Brownfield agent JSON failed schema validation: %s", exc)
            raise HTTPException(
                502,
                "Brownfield agent response did not match the expected schema. "
                f"Validation errors: {exc.errors()[:5]}",
            )

        known_epic_keys = {e["issue_key"] for e in existing_epics}
        unknown_refs = sorted(
            {ns.epic_issue_key for ns in validated.new_stories}
            - known_epic_keys
        )
        if unknown_refs:
            logger.error(
                "Brownfield agent referenced unknown epic keys in new_stories: %s",
                unknown_refs,
            )
            raise HTTPException(
                502,
                "Brownfield agent proposed new stories under epic keys that "
                f"were not part of the input: {', '.join(unknown_refs)}.",
            )

        logger.info(
            "Brownfield analysis complete: no_changes=%s, epic_updates=%d, story_updates=%d, new_stories=%d, new_epics=%d, deletion_reviews=%d",
            validated.no_changes,
            len(validated.epics_to_update),
            len(validated.stories_to_update),
            len(validated.new_stories),
            len(validated.epics_to_create),
            len(validated.stories_to_review_for_deletion),
        )

        empty_changes = {
            "epics_to_update": [],
            "stories_to_update": [],
            "new_stories": [],
            "epics_to_create": [],
            "stories_to_review_for_deletion": [],
        }

        if validated.no_changes:
            return {
                "status": "no_changes",
                "message": validated.summary
                or "No changes detected between the BRD and existing user stories.",
                "changes": empty_changes,
            }

        return {
            "status": "success",
            "message": validated.summary,
            "changes": {
                "epics_to_update": [m.model_dump() for m in validated.epics_to_update],
                "stories_to_update": [m.model_dump() for m in validated.stories_to_update],
                "new_stories": [m.model_dump() for m in validated.new_stories],
                "epics_to_create": [m.model_dump() for m in validated.epics_to_create],
                "stories_to_review_for_deletion": [
                    m.model_dump() for m in validated.stories_to_review_for_deletion
                ],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_internal_error(
            "Internal error during BRD update analysis",
            "Internal error",
            e,
        )


@router.post(
    "/apply-brd-updates",
    tags=["Brownfield"],
    summary="Apply the proposed BRD change diff to Jira",
    description=(
        "Applies the structured diff returned by /analyze-brd-updates. "
        "Updates existing epic descriptions, updates existing stories, creates new "
        "stories under existing epics, and creates brand-new epics with their stories. "
        "stories_to_review_for_deletion from the diff is informational — "
        "it is not applied automatically."
    ),
    response_description="Summary of applied changes",
)
async def apply_brd_updates(request: ApplyBrdUpdatesRequest):
    """One-shot endpoint to apply all approved changes from /analyze-brd-updates."""
    logger.info(
        "Applying BRD updates: %d epic updates, %d story updates, %d new stories, %d new epics",
        len(request.epics_to_update),
        len(request.stories_to_update),
        len(request.new_stories),
        len(request.epics_to_create),
    )

    applied: dict = {
        "updated_epics": [],
        "updated_stories": [],
        "created_stories": [],
        "created_epics": [],
        "errors": [],
    }
    all_success = True

    def _record_error(phase: str, issue_key: str | None, error: Any) -> None:
        nonlocal all_success
        all_success = False
        applied["errors"].append({
            "phase": phase,
            "issue_key": issue_key,
            "error": error,
        })

    try:
        for epic in request.epics_to_update:
            result = update_jira_issue(
                issue_key=epic.issue_key,
                description=epic.new_epic_description,
            )
            if result.get("status") != "success":
                _record_error("update_epic", epic.issue_key, result.get("error_message"))
                logger.error(
                    "Failed to update epic %s: %s",
                    epic.issue_key, result.get("error_message"),
                )
            else:
                applied["updated_epics"].append(result)
                logger.info("Updated epic %s", epic.issue_key)

        for story in request.stories_to_update:
            full_description = build_story_update_description(
                story.new_description,
                [ac.model_dump() for ac in story.new_acceptance_criteria],
            )
            result = update_jira_issue(
                issue_key=story.issue_key,
                summary=story.new_title,
                description=full_description,
            )
            if result.get("status") != "success":
                _record_error("update_story", story.issue_key, result.get("error_message"))
                logger.error(
                    "Failed to update story %s: %s",
                    story.issue_key, result.get("error_message"),
                )
            else:
                applied["updated_stories"].append(result)
                logger.info("Updated story %s", story.issue_key)

        if request.new_stories:
            new_story_dicts = [s.model_dump() for s in request.new_stories]
            create_result = export_additional_stories(new_story_dicts)
            created = create_result.get("created", {}).get("stories", [])
            applied["created_stories"].extend(created)
            status = create_result.get("status")
            if status not in ("success", "partial_error"):
                _record_error(
                    "create_new_stories", None, create_result.get("error_message"),
                )
            elif status == "partial_error":
                _record_error(
                    "create_new_stories",
                    None,
                    "One or more new stories failed to create; see Jira for details.",
                )
            logger.info("Created %d new stories", len(created))

        if request.epics_to_create:
            epic_dicts = [
                {
                    "epic_title": e.epic_title,
                    "epic_description": e.epic_description,
                    "user_stories": [s.model_dump() for s in e.user_stories],
                }
                for e in request.epics_to_create
            ]
            epic_result = export_to_jira(epic_dicts, brd_url=request.brd_confluence_link)
            status = epic_result.get("status")
            if status in ("success", "partial_error"):
                applied["created_epics"] = list(
                    epic_result.get("created", {}).get("epics", {}).values()
                )
            if status not in ("success", "partial_error"):
                _record_error(
                    "create_new_epics", None, epic_result.get("error_message"),
                )
                if epic_result.get("rollback_failed_keys"):
                    applied["rollback_failed_keys"] = epic_result["rollback_failed_keys"]
            elif status == "partial_error":
                _record_error(
                    "create_new_epics",
                    None,
                    "One or more new epics failed to create; see Jira for details.",
                )
            logger.info("Created %d new epics", len(applied["created_epics"]))

        overall = "success" if all_success else "partial_error"
        logger.info("apply-brd-updates completed with status: %s", overall)
        return {"status": overall, "applied": applied}

    except HTTPException:
        raise
    except Exception as e:
        raise_internal_error(
            "Internal error during apply-brd-updates",
            "Internal error",
            e,
        )


@router.get(
    "/jira-epics",
    tags=["Brownfield"],
    summary="List Jira epics for the UI picker",
    description=(
        "Returns all epics in the configured Jira project (or a specified project key) "
        "as a lightweight list for the UI to render the epic selector. "
        "All results are paginated internally — the full list is always returned."
    ),
    response_description="List of epics with issue_key and title",
)
async def list_jira_epics(
    project_key: Optional[str] = Query(
        default=None,
        description="Jira project key (e.g. QUANTNIKAIDEMO). Defaults to JIRA_PROJECT_KEY env var.",
    ),
):
    """Fetch all epics in a project for the brownfield epic picker."""
    logger.info("Jira epic list requested for project_key=%s", project_key)
    result = get_project_epics(project_key)
    if result["status"] == "error":
        raise HTTPException(400, result["error_message"])
    return {
        "status": "success",
        "total": len(result["epics"]),
        "epics": result["epics"],
    }