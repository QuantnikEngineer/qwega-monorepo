from fastapi import APIRouter, HTTPException

from app.schemas.context import ContextEnrichRequest, ContextEnrichResponse, ChunkItem
from app.indexing.embedder import Embedder
from app.retrieval.qdrant_store import QdrantStore
from app.api.deps import get_qdrant_store, get_embedder

router = APIRouter()


@router.post(
    "/context/enrich",
    response_model=ContextEnrichResponse,
    summary="Fetch enrichment context for agent pre-generation",
    description=(
        "Returns ranked knowledge chunks for a given artifact type and SDLC phase. "
        "Feedback chunks (corrections + domain preferences) are always surfaced first, "
        "followed by other relevant knowledge. "
        "Agents call this endpoint before generation and inject the returned chunks "
        "into their system prompt."
    ),
)
async def enrich_context(request: ContextEnrichRequest) -> ContextEnrichResponse:
    try:
        embedder = get_embedder()
        store    = get_qdrant_store()
        phase    = request.sdlc_phase.value if request.sdlc_phase else None

        # Build a query that targets domain rules and preferences for this artifact
        query = f"{request.artifact_type} domain guidelines rules preferences format requirements"
        if phase:
            query = f"{phase} {query}"

        query_vector = await embedder.embed_query(query)

        # Pass 1: feedback-only search — these are always surfaced first
        feedback_chunks = await store.search(
            query_vector    = query_vector,
            top_k           = request.top_k,
            sdlc_phase      = phase,
            source_type     = "feedback",
            score_threshold = None,   # return even low-scoring feedback; it's explicit domain knowledge
            query_text      = query,
            project_name    = request.project_name,
        )

        # Pass 2: general knowledge search (all source types)
        general_chunks = await store.search(
            query_vector    = query_vector,
            top_k           = request.top_k,
            sdlc_phase      = phase,
            score_threshold = None,
            query_text      = query,
            project_name    = request.project_name,
        )

        # Merge: feedback first, then general — deduplicate by chunk_id
        seen: set[str] = set()
        merged = []
        for r in feedback_chunks + general_chunks:
            if r.chunk_id not in seen:
                seen.add(r.chunk_id)
                merged.append(r)

        chunks = [
            ChunkItem(
                content     = r.content,
                source      = r.filename,
                score       = round(r.score, 4),
                source_type = r.source_type or None,
            )
            for r in merged[: request.top_k]
        ]

        return ContextEnrichResponse(
            artifact_type = request.artifact_type,
            sdlc_phase    = phase,
            chunks        = chunks,
            total         = len(chunks),
        )

    except Exception:
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again later.")
