from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

import vertexai
from vertexai.generative_models import GenerativeModel

from app.core.config import settings
from app.core.logging import logger
from app.indexing.embedder import Embedder
from app.retrieval.qdrant_store import QdrantStore, SearchResult


_SYSTEM_PROMPT = """
You are an SDLC knowledge assistant. Your answers must be:
1. Grounded strictly in the provided context — do not fabricate.
2. Focused on SDLC — requirements, design, development, testing, deployment, security.
3. Concise and structured. Use bullet points for lists, prose for explanations.
4. Cite the source filename when referencing specific information.
5. If context is insufficient, say: "The knowledge base does not contain enough information to answer this."

Context:
{context}
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


class Retriever:

    def __init__(self):
        self._store   = QdrantStore()
        self._embedder = Embedder()
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
        top_k:                int                = settings.TOP_K,
        sdlc_phase:           Optional[str]      = None,
        criticality:          Optional[str]      = None,
        document_name:        Optional[str]      = None,
        document_version:     Optional[int]      = None,
        conversation_history: list[dict]         = None,
    ) -> RetrievalResult:

        # 1. Embed query
        query_vector = await self._embedder.embed_query(query)

        inferred_phase = None if sdlc_phase else self._infer_phase(query)
        phase_filter   = sdlc_phase or inferred_phase

        # 2. Search Qdrant (with optional document_name / document_version filters)
        results = self._store.search(
            query_vector=query_vector,
            top_k=top_k,
            sdlc_phase=phase_filter,
            criticality=criticality,
            filename=document_name,
            version=document_version,
        )

        if phase_filter and not results:
            logger.info("retrieval_phase_fallback", requested_phase=phase_filter)
            results = self._store.search(
                query_vector=query_vector,
                top_k=top_k,
                sdlc_phase=None,
                criticality=criticality,
                filename=document_name,
                version=document_version,
            )

        if not results:
            logger.info("retrieval_threshold_fallback")
            results = self._store.search(
                query_vector=query_vector,
                top_k=top_k,
                sdlc_phase=None,
                score_threshold=None,
                criticality=criticality,
                filename=document_name,
                version=document_version,
            )

        resolved_phase = phase_filter if phase_filter and results else self._dominant_phase(results)

        if not results:
            return RetrievalResult(
                answer          = "No relevant information found in the knowledge base.",
                sources         = [],
                retrieval_count = 0,
                sdlc_phase      = resolved_phase,
            )

        # 3. Rerank — boost keyword overlap
        results = self._rerank(query, results)

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
            if turns:
                history_text = "Previous conversation:\n" + "\n".join(turns) + "\n\n"

        # 7. Generate
        prompt   = _SYSTEM_PROMPT.format(context=context) + f"\n\n{history_text}Question: {query}"
        response = self._llm.generate_content(prompt)
        answer   = response.text.strip()

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
        """Lightweight keyword-overlap reranker. Upgradeable to cross-encoder."""
        keywords = set(query.lower().split())
        for r in results:
            overlap     = len(keywords & set(r.content.lower().split()))
            r.score     = r.score * 0.7 + (overlap / max(len(keywords), 1)) * 0.3
        return sorted(results, key=lambda x: x.score, reverse=True)

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