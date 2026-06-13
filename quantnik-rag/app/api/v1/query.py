from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_retriever
from app.core.exceptions import GuardrailViolationError
from app.core.logging import logger
from app.core.resilience import CircuitOpenError
from app.guardrails.input_guard import validate as input_validate
from app.guardrails.output_guard import validate as output_validate
from app.memory.conversation import ConversationManager
from app.memory.knowledge_graph import KnowledgeGraphQuerier
from app.models.query_log import QueryLog
from app.retrieval.retriever import Retriever
from app.schemas.query import QueryRequest, QueryResponse, SourceItem

router = APIRouter()

_conv_manager = ConversationManager()
_kg_querier = KnowledgeGraphQuerier()


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(
    request:          QueryRequest,
    background_tasks: BackgroundTasks,
    db:               AsyncSession = Depends(get_db),
):
    try:
        # Input guardrail
        clean_query = input_validate(request.query)

        # Server-side conversation memory: load or create
        conv_id, conv = await _conv_manager.get_or_create(
            db, request.conversation_id, request.project_name,
        )

        # Load server-side history (summary + recent turns)
        server_history = await _conv_manager.load_history(db, conv_id)

        # Merge: server-side history takes precedence, client history as fallback
        conversation_history = (
            server_history
            if server_history
            else [t.model_dump() for t in request.conversation_history]
        )

        # Knowledge graph enrichment
        kg_context = ""
        try:
            kg_result = await _kg_querier.find_related_context(
                db, clean_query, request.project_name, top_k=5,
            )
            kg_context = kg_result.get("context", "")
        except Exception:
            pass  # KG enrichment is best-effort

        # Retrieve + Generate
        retriever = get_retriever()
        result    = await retriever.retrieve(
            query                = clean_query,
            project_name         = request.project_name,
            top_k                = request.top_k,
            sdlc_phase           = request.sdlc_phase.value if request.sdlc_phase else None,
            include_non_critical = request.include_non_critical,
            document_name        = request.document_name,
            document_version     = request.document_version,
            conversation_history = conversation_history,
            db                   = db,
            kg_context           = kg_context,
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
            project_name         = request.project_name,
            query                = clean_query,
            answer               = guard["answer"],
            sources              = sources,
            guardrail_passed     = guard["passed"],
            retrieval_count      = result.retrieval_count,
            sdlc_phase           = result.sdlc_phase,
            clarification_needed = result.clarification_needed,
            available_versions   = result.available_versions,
            conversation_id      = conv_id,
        )

        # Save turns to server-side conversation memory (non-blocking)
        background_tasks.add_task(
            _save_conversation_turns,
            conversation_id = conv_id,
            query           = clean_query,
            answer          = guard["answer"],
        )

        # Fire-and-forget: summarise if conversation is long
        background_tasks.add_task(
            _maybe_summarise_conversation,
            conversation_id = conv_id,
        )

        # Fire-and-forget query log (non-blocking)
        background_tasks.add_task(
            _log_query,
            db                   = db,
            project_name         = request.project_name,
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
    except CircuitOpenError:
        raise HTTPException(503, detail="Service temporarily unavailable. Please retry shortly.")
    except Exception:
        logger.exception("query_endpoint_error")
        raise HTTPException(500, detail="An internal error occurred. Please try again later.")


async def _save_conversation_turns(
    conversation_id: str,
    query: str,
    answer: str,
) -> None:
    """Save user query and assistant answer to server-side conversation store."""
    from app.db.session import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            await _conv_manager.add_turn(db, conversation_id, "user", query)
            await _conv_manager.add_turn(db, conversation_id, "assistant", answer)
    except Exception:
        pass  # Memory save must never break the response


async def _maybe_summarise_conversation(conversation_id: str) -> None:
    """Summarise old turns if the conversation is long."""
    from app.db.session import AsyncSessionLocal
    from app.api.deps import get_retriever
    try:
        retriever = get_retriever()
        async with AsyncSessionLocal() as db:
            await _conv_manager.maybe_summarise(
                db, conversation_id, retriever.summarise_conversation,
            )
    except Exception:
        pass  # Summarisation is best-effort


async def _log_query(
    db:                   AsyncSession,
    project_name:         str,
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
            project_name         = project_name,
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
