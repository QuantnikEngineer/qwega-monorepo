import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams,
    PointStruct, Filter,
    FieldCondition, MatchValue,
    PayloadSchemaType,
)

from app.core.config import settings
from app.core.exceptions import VectorStoreError
from app.core.logging import logger
from app.indexing.embedder import EmbeddedChunk


@dataclass
class SearchResult:
    chunk_id:     str
    doc_id:       str
    content:      str
    filename:     str
    sdlc_phase:   str
    score:        float
    source_type:  str  = ""
    criticality:  str  = "critical"   # "critical" | "non_critical"
    version:      int  = 1
    ingested_at:  str  = ""


class QdrantStore:
    """
    Manages two Qdrant collections:
      - *critical*     → settings.QDRANT_COLLECTION              (sdlc_kb)
      - *non_critical* → settings.QDRANT_COLLECTION_NON_CRITICAL (sdlc_kb_non_critical)

    All public methods accept a ``criticality`` parameter to route to the
    correct collection.  ``search()`` with ``criticality=None`` queries both
    collections and returns a merged, score-sorted result.
    """

    def __init__(self):
        self._client           = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
            https=settings.QDRANT_VERIFY_SSL,
            verify=settings.QDRANT_VERIFY_SSL,
        )
        self._col_critical     = settings.QDRANT_COLLECTION
        self._col_non_critical = settings.QDRANT_COLLECTION_NON_CRITICAL

    # ── Collection management ─────────────────────────────────────────────────

    def _create_if_missing(self, name: str):
        existing = [c.name for c in self._client.get_collections().collections]
        if name not in existing:
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=settings.QDRANT_VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
            )
            for field_name in ("sdlc_phase", "source_type", "filename"):
                self._client.create_payload_index(
                    collection_name=name,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            self._client.create_payload_index(
                collection_name=name,
                field_name="version",
                field_schema=PayloadSchemaType.INTEGER,
            )
            logger.info("qdrant_collection_created", collection=name)

    def _ensure_payload_indexes(self, name: str):
        """Creates payload indexes on an existing collection if missing."""
        info = self._client.get_collection(name)
        existing = set(info.payload_schema.keys()) if info.payload_schema else set()
        for field_name in ("sdlc_phase", "source_type", "filename"):
            if field_name not in existing:
                self._client.create_payload_index(
                    collection_name=name,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
        if "version" not in existing:
            self._client.create_payload_index(
                collection_name=name,
                field_name="version",
                field_schema=PayloadSchemaType.INTEGER,
            )

    def ensure_collection(self):
        """Creates both collections if they do not exist. Called on app startup."""
        self._create_if_missing(self._col_critical)
        self._create_if_missing(self._col_non_critical)
        self._ensure_payload_indexes(self._col_critical)
        self._ensure_payload_indexes(self._col_non_critical)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_collection(self, criticality: str) -> str:
        if criticality == "non_critical":
            return self._col_non_critical
        return self._col_critical

    def _make_point_id(self, doc_id: str, chunk_index: int) -> str:
        """Deterministic UUID point ids required by local Qdrant."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk_index}"))

    def make_point_id(self, doc_id: str, chunk_index: int) -> str:
        """Public wrapper for deterministic point ID generation."""
        return self._make_point_id(doc_id, chunk_index)

    def _build_filter(
        self,
        sdlc_phase:  Optional[str],
        source_type: Optional[str],
        filename:    Optional[str] = None,
        version:     Optional[int] = None,
    ) -> Optional[Filter]:
        must_conditions = []
        if sdlc_phase:
            must_conditions.append(
                FieldCondition(key="sdlc_phase", match=MatchValue(value=sdlc_phase))
            )
        if source_type:
            must_conditions.append(
                FieldCondition(key="source_type", match=MatchValue(value=source_type))
            )
        if filename:
            must_conditions.append(
                FieldCondition(key="filename", match=MatchValue(value=filename))
            )
        if version is not None:
            must_conditions.append(
                FieldCondition(key="version", match=MatchValue(value=version))
            )
        return Filter(must=must_conditions) if must_conditions else None

    def _hits_to_results(
        self, hits, criticality: str
    ) -> list[SearchResult]:
        return [
            SearchResult(
                chunk_id    = h.payload.get("chunk_id", str(h.id)),
                doc_id      = h.payload.get("doc_id", ""),
                content     = h.payload.get("content", ""),
                filename    = h.payload.get("filename", ""),
                sdlc_phase  = h.payload.get("sdlc_phase", ""),
                score       = h.score,
                source_type = h.payload.get("source_type", ""),
                criticality = criticality,
                version     = h.payload.get("version", 1),
                ingested_at = h.payload.get("ingested_at", ""),
            )
            for h in hits
        ]

    # ── Write ─────────────────────────────────────────────────────────────────

    def upsert(
        self,
        embedded_chunks: list[EmbeddedChunk],
        criticality: str = "critical",
    ) -> int:
        """
        Upserts embedded chunks into the appropriate Qdrant collection.

        ``criticality`` must be ``"critical"`` or ``"non_critical"``.
        The value is also stored in every chunk's payload for transparency.
        """
        collection = self._resolve_collection(criticality)
        try:
            points = [
                PointStruct(
                    id      = self._make_point_id(chunk.doc_id, chunk.chunk_index),
                    vector  = chunk.vector,
                    payload = {
                        "chunk_id":    chunk.chunk_id,
                        "doc_id":      chunk.doc_id,
                        "content":     chunk.content,
                        "filename":    chunk.filename,
                        "sdlc_phase":  chunk.sdlc_phase,
                        "chunk_index": chunk.chunk_index,
                        "criticality": criticality,
                        **chunk.metadata,
                    },
                )
                for chunk in embedded_chunks
            ]
            self._client.upsert(collection_name=collection, points=points)
            logger.info(
                "qdrant_upsert_done",
                collection=collection,
                criticality=criticality,
                count=len(points),
            )
            return len(points)
        except Exception as e:
            raise VectorStoreError(str(e))

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(
        self,
        query_vector:    list[float],
        top_k:           int             = settings.TOP_K,
        sdlc_phase:      Optional[str]   = None,
        source_type:     Optional[str]   = None,
        score_threshold: Optional[float] = settings.SIMILARITY_THRESHOLD,
        criticality:     Optional[str]   = None,
        filename:        Optional[str]   = None,
        version:         Optional[int]   = None,
    ) -> list[SearchResult]:
        """
        Semantic search against Qdrant.

        ``criticality`` controls which collection(s) are queried:
          - ``"critical"``     → critical collection only
          - ``"non_critical"`` → non-critical collection only
          - ``None`` (default) → both collections; results merged and
                                 sorted by score descending, top_k returned
        """
        query_filter = self._build_filter(sdlc_phase, source_type, filename, version)

        def _query_one(col: str, crit_label: str) -> list[SearchResult]:
            try:
                response = self._client.query_points(
                    collection_name=col,
                    query          =query_vector,
                    limit          =top_k,
                    query_filter   =query_filter,
                    score_threshold=score_threshold,
                    with_payload   =True,
                )
                return self._hits_to_results(response.points, crit_label)
            except Exception as e:
                raise VectorStoreError(str(e))

        if criticality == "critical":
            return _query_one(self._col_critical, "critical")

        if criticality == "non_critical":
            return _query_one(self._col_non_critical, "non_critical")

        # Both collections — merge and re-rank by score
        critical_results     = _query_one(self._col_critical,     "critical")
        non_critical_results = _query_one(self._col_non_critical, "non_critical")
        merged = sorted(
            critical_results + non_critical_results,
            key=lambda r: r.score,
            reverse=True,
        )
        return merged[:top_k]

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_by_document(self, doc_id: str, criticality: Optional[str] = None):
        """
        Removes all vectors for ``doc_id``.

        If ``criticality`` is provided only that collection is targeted;
        otherwise both collections are scanned (safe for all cases).
        """
        doc_filter = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
        collections = (
            [self._resolve_collection(criticality)]
            if criticality
            else [self._col_critical, self._col_non_critical]
        )
        for col in collections:
            try:
                self._client.delete(collection_name=col, points_selector=doc_filter)
                logger.info("qdrant_delete_done", collection=col, doc_id=doc_id)
            except Exception as e:
                raise VectorStoreError(str(e))

    def retrieve_vectors(self, point_ids: list[str], criticality: str) -> dict[str, list[float]]:
        """
        Fetch stored vectors for the given point IDs without re-embedding.
        Returns ``{point_id: vector}``; missing IDs are simply absent.
        Used by the diff pipeline to reuse unchanged-chunk vectors.
        """
        if not point_ids:
            return {}
        collection = self._resolve_collection(criticality)
        try:
            records = self._client.retrieve(
                collection_name=collection,
                ids=point_ids,
                with_vectors=True,
            )
            return {str(r.id): r.vector for r in records if r.vector is not None}
        except Exception as e:
            raise VectorStoreError(str(e))