from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from models.schemas import AgentOutput, GenerateUserStoriesRequest
from tools.brd_parser import parse_brd_from_confluence, validate_confluence_url
from tools.exporter import export_to_jira
from userstory.agent import root_agent

from .support import (
    AGENT_TIMEOUT_SECONDS,
    brd_error_to_http_status,
    logger,
    parse_agent_json,
    raise_internal_error,
    run_agent_or_timeout_http,
)


router = APIRouter()


@router.post(
    "/generate-user-stories",
    tags=["User Stories"],
    summary="Generate user stories from BRD",
    description="Provide a BRD as a Confluence page link and generate epics and user stories using the AI agent",
    response_description="Generated epics and user stories"
)
async def generate_user_stories(request: GenerateUserStoriesRequest):
    brd_confluence_link = request.brd_confluence_link
    logger.info("Starting user story generation")

    if not brd_confluence_link or not brd_confluence_link.strip():
        logger.error("No BRD Confluence link provided")
        raise HTTPException(400, "Provide a BRD Confluence link")

    is_valid, reason = validate_confluence_url(brd_confluence_link)
    if not is_valid:
        logger.error("Invalid Confluence URL rejected: %s — %s", brd_confluence_link, reason)
        raise HTTPException(422, reason)

    logger.info("Using Confluence link as BRD source: %s", brd_confluence_link)
    brd_result = parse_brd_from_confluence(brd_confluence_link.strip())

    try:
        if brd_result["status"] == "error":
            category = brd_result.get("error_category")
            status_code = brd_error_to_http_status(category)
            logger.error(
                "BRD parsing failed (category=%s): %s",
                category, brd_result["error_message"],
            )
            raise HTTPException(status_code, brd_result["error_message"])

        brd_text = brd_result["content"]
        brd_title = brd_result.get("title") or ""
        logger.info(
            "BRD parsed successfully, title=%r, content length: %d characters",
            brd_title, len(brd_text),
        )

        logger.info("Running agent to generate user stories")
        final_text = await run_agent_or_timeout_http(
            agent=root_agent,
            app_name="user_story_agent",
            user_text=f"Here is the BRD content:\n\n{brd_text}",
            timeout_log_label="User story agent",
            timeout_detail=(
                f"Agent timed out after {AGENT_TIMEOUT_SECONDS:.0f}s. "
                "BRD may be too large or model is unresponsive; please retry."
            ),
        )

        if not final_text:
            logger.error("Agent failed to generate output")
            raise HTTPException(502, "Agent failed to generate output")

        final_json = parse_agent_json(final_text)
        if not isinstance(final_json, dict):
            logger.error("Agent returned non-JSON output: %s", final_text[:500])
            raise HTTPException(
                502,
                "Agent returned an unreadable response (expected JSON object).",
            )

        summary_text = (
            final_json.get("summary_text")
            or final_json.get("summary")
            or final_text
        )
        epics_payload = final_json.get("epics")

        if not isinstance(epics_payload, list) or not epics_payload:
            logger.error(
                "Agent JSON has missing/empty 'epics' field: %s", str(final_json)[:500]
            )
            raise HTTPException(
                502,
                "Agent response did not include any epics. The BRD may be too "
                "thin to derive epics, or the model output was malformed.",
            )

        try:
            validated = AgentOutput.model_validate({"epics": epics_payload})
        except ValidationError as exc:
            logger.error("Agent JSON failed schema validation: %s", exc)
            raise HTTPException(
                502,
                "Agent response did not match the expected schema. "
                f"Validation errors: {exc.errors()[:5]}",
            )

        epics_json = [epic.model_dump() for epic in validated.epics]
        stories_json: list[dict] = [
            story
            for epic in epics_json
            for story in (epic.get("user_stories") or [])
        ]

        logger.info(
            "User story generation completed successfully. Generated %d epics and %d total stories",
            len(epics_json), len(stories_json),
        )
        return {
            "status": "success",
            "summary": summary_text,
            "brd_confluence_link": brd_confluence_link,
            "brd_title": brd_title,
            "epics": epics_json,
            "stories": stories_json,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_internal_error(
            "Internal error during user story generation",
            "Internal error",
            e,
        )


@router.post(
    "/export-to-jira",
    tags=["Jira Integration"],
    summary="Export epics and stories to Jira",
    description="Export the provided epics and user stories to Jira project",
    response_description="Jira export result with created issue keys"
)
async def export_to_jira_endpoint(payload: AgentOutput):
    """Export the provided epics and stories to Jira on demand."""
    logger.info("Jira export requested for %d epics", len(payload.epics))

    try:
        epics = [epic.model_dump() for epic in payload.epics]
        result = export_to_jira(
            epics,
            brd_url=payload.brd_confluence_link,
            brd_title=payload.brd_title,
        )
        logger.info("Jira export completed with status: %s", result.get("status"))
        return {
            "status": result.get("status"),
            "jira_export_result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise_internal_error("Failed to export to Jira", "Failed to export to Jira", e)