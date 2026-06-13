from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import GuardrailViolationError
from app.guardrails.input_guard import validate as input_validate
from app.guardrails.output_guard import validate as output_validate
from app.models.query_log import QueryLog
from app.retrieval.retriever import Retriever
from app.schemas.query import QueryRequest, QueryResponse, SourceItem

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(
    request:          QueryRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
):
    try:
        # Input guardrail
        clean_query = input_validate(request.query)

        # Retrieve + Generate
        retriever = Retriever()
        result    = await retriever.retrieve(
            query                = clean_query,
            top_k                = request.top_k,
            sdlc_phase           = request.sdlc_phase.value if request.sdlc_phase else None,
            criticality          = request.criticality,
            document_name        = request.document_name,
            document_version     = request.document_version,
            conversation_history = [t.model_dump() for t in request.conversation_history],
        )

        # Output guardrail (skip on clarification — no LLM answer to validate)
        if result.clarification_needed:
            guard = {"answer": result.answer, "passed": True}
        else:
            guard = output_validate(result.answer, result.sources)

        sources = []
        if request.include_sources:
            sources = [
                SourceItem(
                    chunk_id    = r.chunk_id,
                    filename    = r.filename,
                    sdlc_phase  = r.sdlc_phase,
                    score       = round(r.score, 4),
                    content     = r.content,
                    criticality = r.criticality,
                    version     = r.version,
                    ingested_at = r.ingested_at,
                )
                for r in result.sources
            ]

        response = QueryResponse(
            query                = clean_query,
            answer               = guard["answer"],
            sources              = sources,
            guardrail_passed     = guard["passed"],
            retrieval_count      = result.retrieval_count,
            sdlc_phase           = result.sdlc_phase,
            clarification_needed = result.clarification_needed,
            available_versions   = result.available_versions,
        )

        # Fire-and-forget query log (non-blocking)
        background_tasks.add_task(
            _log_query,
            db                   = db,
            query_text           = clean_query,
            answer               = guard["answer"],
            sdlc_phase           = result.sdlc_phase,
            retrieval_count      = result.retrieval_count,
            guardrail_passed     = guard["passed"],
            conversation_id      = request.conversation_id,
            sources              = [
                {"filename": s.filename, "chunk_id": s.chunk_id,
                 "score": s.score, "version": s.version}
                for s in sources
            ],
            clarification_needed = result.clarification_needed,
        )

        return response

    except GuardrailViolationError as e:
        raise HTTPException(422, detail=e.message)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


async def _log_query(
    db:                   AsyncSession,
    query_text:           str,
    answer:               str,
    sdlc_phase:           str | None,
    retrieval_count:      int,
    guardrail_passed:     bool,
    conversation_id:      str | None,
    sources:              list[dict],
    clarification_needed: bool,
) -> None:
    try:
        db.add(QueryLog(
            query_text           = query_text,
            answer               = answer,
            sdlc_phase           = sdlc_phase,
            retrieval_count      = retrieval_count,
            guardrail_passed     = guardrail_passed,
            conversation_id      = conversation_id,
            sources              = sources,
            clarification_needed = clarification_needed,
        ))
        await db.commit()
    except Exception:
        # Logging must never break the main request path
        await db.rollback()
