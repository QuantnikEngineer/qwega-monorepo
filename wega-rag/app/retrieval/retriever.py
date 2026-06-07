import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

import vertexai
from vertexai.generative_models import GenerativeModel
from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.core.logging import logger
from app.core.resilience import (
    vertex_breaker, run_in_thread, retry_async, with_llm_semaphore,
)
from app.indexing.embedder import Embedder
from app.retrieval.qdrant_store import QdrantStore, SearchResult


_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


_SYSTEM_PROMPT = """
You are an SDLC knowledge assistant. Your answers must be:
1. Grounded strictly in the provided context — do not fabricate.
2. Focused on SDLC — requirements, design, development, testing, deployment, security.
3. Concise and structured. Use bullet points for lists, prose for explanations.
4. Cite the source filename when referencing specific information.
5. If context is insufficient, say: "The knowledge base does not contain enough information to answer this."

{kg_context}
Context:
{context}
"""

_SUMMARISE_PROMPT = """
Summarise this conversation in 3-5 sentences, preserving key questions asked,
answers given, and any decisions or preferences expressed by the user.

Conversation:
{text}
"""

_PHASE_HINTS = {
    "requirements": {
        "requirement", "requirements", "brd", "prd", "scope", "stakeholder",
        "acceptance criteria", "user story", "user stories", "business requirement",
    },
    "design": {
        "design", "architecture", "component", "sequence", "uml", "flow", "wireframe",
        "diagram", "high level design", "low level design",
    },
    "development": {
        "development", "code", "implementation", "module", "service", "api", "endpoint",
        "repository", "branch", "commit", "build",
    },
    "testing": {
        "test", "testing", "qa", "uat", "defect", "bug", "test case", "test scenario",
        "action item", "action items", "issue", "retest",
    },
    "deployment": {
        "deploy", "deployment", "release", "rollout", "production", "environment", "infra",
        "infrastructure", "devops", "ci/cd", "pipeline",
    },
    "security": {
        "security", "vulnerability", "threat", "risk", "auth", "authentication",
        "authorization", "compliance", "audit", "encryption",
    },
}


@dataclass
class RetrievalResult:
    answer:               str
    sources:              list[SearchResult]
    retrieval_count:      int
    sdlc_phase:           Optional[str]
    clarification_needed: bool = False
    available_versions:   dict = field(default_factory=dict)  # filename -> [v1, v2, ...]
    conversation_id:      Optional[str] = None


class Retriever:

    def __init__(self, store: QdrantStore | None = None, embedder: Embedder | None = None):
        self._store    = store or QdrantStore()
        self._embedder = embedder or Embedder()
        self._reranker = CrossEncoder(_CROSS_ENCODER_MODEL)
        vertexai.init(
            project=settings.VERTEX_PROJECT_ID,
            location=settings.VERTEX_LOCATION,
        )
        self._llm = GenerativeModel(
            model_name=settings.VERTEX_LLM_MODEL,
        )

    async def retrieve(
        self,
        query:                str,
        project_name:         str,
        top_k:                int                = settings.TOP_K,
        sdlc_phase:           Optional[str]      = None,
        include_non_critical: bool               = False,
        document_name:        Optional[str]      = None,
        document_version:     Optional[int]      = None,
        conversation_history: list[dict]         = None,
        db:                   "AsyncSession | None" = None,
        kg_context:           str                = "",
    ) -> RetrievalResult:

        # 1. Embed query
        query_vector = await self._embedder.embed_query(query)

        inferred_phase = None if sdlc_phase else self._infer_phase(query)
        phase_filter   = sdlc_phase or inferred_phase

        # Over-fetch for cross-encoder reranking, then trim to top_k
        fetch_k = min(top_k * 4, 40)

        # Default searches critical only; toggle searches both
        criticality = "both" if include_non_critical else None

        # 2. Search Qdrant — hybrid dense + BM25 with RRF fusion, scoped to project
        results = await self._store.search(
            query_vector=query_vector,
            top_k=fetch_k,
            sdlc_phase=phase_filter,
            criticality=criticality,
            filename=document_name,
            version=document_version,
            query_text=query,
            project_name=project_name,
        )

        if phase_filter and not results:
            logger.info("retrieval_phase_fallback", requested_phase=phase_filter)
            results = await self._store.search(
                query_vector=query_vector,
                top_k=fetch_k,
                sdlc_phase=None,
                criticality=criticality,
                filename=document_name,
                version=document_version,
                query_text=query,
                project_name=project_name,
            )

        if not results:
            logger.info("retrieval_threshold_fallback")
            results = await self._store.search(
                query_vector=query_vector,
                top_k=fetch_k,
                sdlc_phase=None,
                score_threshold=None,
                criticality=criticality,
                filename=document_name,
                version=document_version,
                query_text=query,
                project_name=project_name,
            )

        resolved_phase = phase_filter if phase_filter and results else self._dominant_phase(results)

        if not results:
            return RetrievalResult(
                answer          = "No relevant information found in the knowledge base.",
                sources         = [],
                retrieval_count = 0,
                sdlc_phase      = resolved_phase,
            )

        # 3. Rerank — cross-encoder reranking (CPU-bound, run in thread pool)
        results = await self._rerank_async(query, results)
        results = results[:top_k]

        # 4. Multi-version detection — if the same filename appears with multiple
        #    version numbers the user must clarify which version they mean.
        #    Skip this check when the caller already specified a document_version.
        if document_version is None:
            version_map: dict[str, set[int]] = defaultdict(set)
            for r in results:
                if r.version and r.filename:
                    version_map[r.filename].add(r.version)
            multi_version_docs = {
                fname: sorted(versions)
                for fname, versions in version_map.items()
                if len(versions) > 1
            }
            if multi_version_docs:
                options_lines = "\n".join(
                    f"- **{fname}**: versions {', '.join(str(v) for v in versions)}"
                    for fname, versions in multi_version_docs.items()
                )
                logger.info(
                    "retrieval_clarification_needed",
                    query=query,
                    multi_version_docs=list(multi_version_docs.keys()),
                )
                return RetrievalResult(
                    answer=(
                        "Multiple versions of the following document(s) were found. "
                        "Please specify which version you are referring to:\n\n"
                        + options_lines
                    ),
                    sources              = results,
                    retrieval_count      = len(results),
                    sdlc_phase           = resolved_phase,
                    clarification_needed = True,
                    available_versions   = multi_version_docs,
                )

        # 5. Build context
        context = "\n\n---\n\n".join(
            f"[Source: {r.filename} (v{r.version}) | Phase: {r.sdlc_phase} | {r.criticality}]\n{r.content}"
            for r in results
        )

        # 6. Build conversation history prefix (last 4 turns max)
        history_text = ""
        if conversation_history:
            turns = []
            for turn in (conversation_history or [])[-4:]:
                role    = turn.get("role", "")
                content = turn.get("content", "")
                if role == "user":
                    turns.append(f"User: {content}")
                elif role == "assistant":
                    turns.append(f"Assistant: {content}")
                elif role == "system":
                    turns.append(content)   # summary injection
            if turns:
                history_text = "Previous conversation:\n" + "\n".join(turns) + "\n\n"

        # 7. Generate (with circuit breaker + retry + semaphore)
        prompt = _SYSTEM_PROMPT.format(
            context=context,
            kg_context=kg_context,
        ) + f"\n\n{history_text}Question: {query}"

        async def _generate():
            return await run_in_thread(self._llm.generate_content, prompt)

        try:
            response = await vertex_breaker.call(
                retry_async, _generate, max_retries=3, backoff_base=2.0,
            )
            answer = response.text.strip()
        except Exception as e:
            logger.error("llm_generation_failed", error=str(e))
            answer = (
                "I was unable to generate a response at this time. "
                "Here are the most relevant sources found:\n\n"
                + "\n".join(f"- {r.filename} (v{r.version}): {r.content[:200]}..." for r in results[:3])
            )

        logger.info("retrieval_done", query=query, results=len(results))

        return RetrievalResult(
            answer          = answer,
            sources         = results,
            retrieval_count = len(results),
            sdlc_phase      = resolved_phase,
        )

    def _rerank(
        self,
        query:   str,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Cross-encoder reranker for precise query-chunk relevance scoring."""
        if not results:
            return results
        pairs = [(query, r.content) for r in results]
        scores = self._reranker.predict(pairs)
        for r, s in zip(results, scores):
            r.score = float(s)
        return sorted(results, key=lambda x: x.score, reverse=True)

    async def _rerank_async(
        self,
        query:   str,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Cross-encoder reranking in thread pool to avoid blocking event loop."""
        if not results:
            return results
        return await run_in_thread(self._rerank, query, results)

    async def summarise_conversation(self, text: str) -> str:
        """Summarise conversation text for memory compression."""
        prompt = _SUMMARISE_PROMPT.format(text=text[:4000])
        response = await run_in_thread(self._llm.generate_content, prompt)
        return response.text.strip()

    def _infer_phase(self, query: str) -> Optional[str]:
        query_lower = query.lower()
        scores: dict[str, int] = {}

        for phase, hints in _PHASE_HINTS.items():
            score = sum(1 for hint in hints if hint in query_lower)
            if score:
                scores[phase] = score

        if not scores:
            return None

        return max(scores, key=scores.get)

    def _dominant_phase(self, results: list[SearchResult]) -> Optional[str]:
        phases = [result.sdlc_phase for result in results if result.sdlc_phase]
        if not phases:
            return None
        return Counter(phases).most_common(1)[0][0]