import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.document import Document, SDLCPhase, SourceType
from app.models.feedback import Feedback, FeedbackType
from app.schemas.feedback import FeedbackRequest, FeedbackResponse
from app.ingestion.pipeline import IngestionPipeline


# Maps artifact_type → SDLCPhase when caller does not supply sdlc_phase
_ARTIFACT_PHASE_MAP: dict[str, SDLCPhase] = {
    "brd":          SDLCPhase.REQUIREMENTS,
    "prd":          SDLCPhase.REQUIREMENTS,
    "user_story":   SDLCPhase.REQUIREMENTS,
    "design":       SDLCPhase.DESIGN,
    "architecture": SDLCPhase.DESIGN,
    "code_review":  SDLCPhase.DEVELOPMENT,
    "test_case":    SDLCPhase.TESTING,
    "test_plan":    SDLCPhase.TESTING,
    "security":     SDLCPhase.SECURITY,
    "deployment":   SDLCPhase.DEPLOYMENT,
    "cicd":         SDLCPhase.DEPLOYMENT,
}


def _resolve_phase(artifact_type: str | None, sdlc_phase: str | None) -> SDLCPhase:
    if sdlc_phase and sdlc_phase in SDLCPhase._value2member_map_:
        return SDLCPhase(sdlc_phase)
    if artifact_type:
        return _ARTIFACT_PHASE_MAP.get(artifact_type.lower(), SDLCPhase.GENERAL)
    return SDLCPhase.GENERAL


async def collect(body: FeedbackRequest, db: AsyncSession) -> FeedbackResponse:
    """
    Main entry point for all feedback types.

    - rating            → saved to Postgres only; not indexed.
    - correction        → saved to Postgres + indexed to Qdrant as CRITICAL.
    - domain_preference → saved to Postgres + indexed to Qdrant as CRITICAL.
    """

    # 1. Persist raw feedback record regardless of type
    feedback = Feedback(
        feedback_type = body.feedback_type,
        rating        = body.rating,
        content       = body.content,
        artifact_type = body.artifact_type,
        sdlc_phase    = body.sdlc_phase,
        agent_name    = body.agent_name,
        session_id    = body.session_id,
        ref_doc_id    = body.ref_doc_id,
        indexed       = False,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    logger.info("feedback_saved", feedback_id=str(feedback.id), type=body.feedback_type)

    # 2. Ratings carry no reusable knowledge — stop here
    if body.feedback_type == FeedbackType.RATING:
        return FeedbackResponse(
            id            = feedback.id,
            feedback_type = feedback.feedback_type,
            indexed       = False,
            message       = "Rating recorded."
        )

    # 3. Corrections and domain preferences get indexed
    sdlc_phase    = _resolve_phase(body.artifact_type, body.sdlc_phase)
    artifact_type = (body.artifact_type or "general").lower().strip()
    doc_id        = uuid.uuid4()
    title         = f"feedback:{body.feedback_type}:{artifact_type}"

    doc = Document(
        id              = doc_id,
        filename        = f"{doc_id}.txt",
        original_name   = title,
        file_type       = "feedback",
        file_size_bytes = len(body.content.encode()),
        source_type     = SourceType.FEEDBACK.value,
        source_metadata = {
            "feedback_type": body.feedback_type,
            "artifact_type": artifact_type,
            "agent_name":    body.agent_name,
            "session_id":    body.session_id,
            "feedback_id":   str(feedback.id),
        },
    )
    db.add(doc)
    await db.commit()

    pipeline = IngestionPipeline(db)
    await pipeline.run_feedback(
        doc_id        = str(doc_id),
        content       = body.content,
        sdlc_phase    = sdlc_phase.value,
        artifact_type = artifact_type,
    )

    # 4. Update feedback record with the Qdrant doc reference
    feedback.indexed       = True
    feedback.qdrant_doc_id = doc_id
    await db.commit()

    logger.info("feedback_indexed", feedback_id=str(feedback.id), doc_id=str(doc_id))

    return FeedbackResponse(
        id            = feedback.id,
        feedback_type = feedback.feedback_type,
        indexed       = True,
        message       = "Feedback indexed into knowledge base."
    )
