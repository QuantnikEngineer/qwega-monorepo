import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams,
    PointStruct, Filter,
    FieldCondition, MatchValue,
    PayloadSchemaType,
    ScalarQuantization, ScalarQuantizationConfig, ScalarType,
    OptimizersConfigDiff, HnswConfigDiff,
    SparseVectorParams, SparseVector,
    Prefetch, FusionQuery, Fusion,
    SearchParams,
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


def _build_sparse_vector(text: str) -> dict[int, float]:
    """
    Build a simple term-frequency sparse vector for BM25-style hybrid search.
    Qdrant's built-in IDF modifier is applied server-side.
    """
    tokens: dict[int, float] = {}
    for word in text.lower().split():
        idx = hash(word) % (2**31)
        tokens[idx] = tokens.get(idx, 0.0) + 1.0
    return tokens


class QdrantStore:
    """
    Manages two Qdrant collections:
      - *critical*     → settings.QDRANT_COLLECTION              (sdlc_kb)
      - *non_critical* → settings.QDRANT_COLLECTION_NON_CRITICAL (sdlc_kb_non_critical)

    All public methods accept a ``criticality`` parameter to route to the
    correct collection.  ``search()`` with ``criticality=None`` queries both
    collections and returns a merged, score-sorted result.

    Uses AsyncQdrantClient to avoid blocking the event loop.
    Collections are created with INT8 scalar quantization and HNSW tuning
    for optimal performance at scale.
    """

    def __init__(self):
        self._client           = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY.get_secret_value(),
            https=settings.QDRANT_VERIFY_SSL,
            verify=settings.QDRANT_VERIFY_SSL,
        )
        self._col_critical     = settings.QDRANT_COLLECTION
        self._col_non_critical = settings.QDRANT_COLLECTION_NON_CRITICAL

    # ── Collection management ─────────────────────────────────────────────────

    async def _create_if_missing(self, name: str):
        await self._client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=settings.QDRANT_VECTOR_SIZE,
                distance=Distance.COSINE,
                on_disk=True,
            ),
            sparse_vectors_config={
                "bm25": SparseVectorParams(
                    modifier="idf",
                ),
            },
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                ),
            ),
            optimizers_config=OptimizersConfigDiff(
                memmap_threshold=20000,
            ),
            hnsw_config=HnswConfigDiff(
                m=16,
                ef_construct=100,
                on_disk=False,
            ),
        )
        for field_name in ("project_name", "sdlc_phase", "source_type", "filename"):
            await self._client.create_payload_index(
                collection_name=name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        await self._client.create_payload_index(
            collection_name=name,
            field_name="version",
            field_schema=PayloadSchemaType.INTEGER,
        )
        logger.info("qdrant_collection_created", collection=name)

    async def _ensure_payload_indexes(self, name: str):
        """Creates payload indexes on an existing collection if missing."""
        info = await self._client.get_collection(name)
        existing = set(info.payload_schema.keys()) if info.payload_schema else set()
        for field_name in ("project_name", "sdlc_phase", "source_type", "filename"):
            if field_name not in existing:
                await self._client.create_payload_index(
                    collection_name=name,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
        if "version" not in existing:
            await self._client.create_payload_index(
                collection_name=name,
                field_name="version",
                field_schema=PayloadSchemaType.INTEGER,
            )

    async def _ensure_sparse_vectors(self, name: str):
        """Adds the bm25 sparse vector config to an existing collection if missing.

        If ``update_collection`` is rejected by the server (older Qdrant
        versions cannot add new sparse vectors to an existing collection),
        the collection is deleted and recreated from scratch – safe only
        when the collection is empty.
        """
        info = await self._client.get_collection(name)
        sparse_cfg = (
            info.config.params.sparse_vectors
            if info.config and info.config.params
            else None
        )
        if sparse_cfg and "bm25" in sparse_cfg:
            return
        try:
            await self._client.update_collection(
                collection_name=name,
                sparse_vectors_config={
                    "bm25": SparseVectorParams(modifier="idf"),
                },
            )
            logger.info("qdrant_bm25_sparse_vector_added", collection=name)
        except Exception:
            # Server does not support adding sparse vectors via update;
            # recreate the collection with the full config.
            logger.warning(
                "qdrant_recreating_collection_for_sparse_vectors",
                collection=name,
            )
            await self._client.delete_collection(name)
            await self._create_if_missing(name)
            logger.info("qdrant_collection_recreated_with_bm25", collection=name)

    async def ensure_collection(self):
        """Creates both collections if they do not exist. Called on app startup."""
        existing = {c.name for c in (await self._client.get_collections()).collections}
        for name in (self._col_critical, self._col_non_critical):
            if name not in existing:
                await self._create_if_missing(name)
            else:
                # Collection already exists — patch up missing config
                await self._ensure_payload_indexes(name)
                await self._ensure_sparse_vectors(name)

    async def ensure_entity_collection(self):
        """Creates the knowledge graph entity collection if missing."""
        from app.memory.knowledge_graph import ENTITY_COLLECTION
        existing = {c.name for c in (await self._client.get_collections()).collections}
        if ENTITY_COLLECTION not in existing:
            await self._client.create_collection(
                collection_name=ENTITY_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.QDRANT_VECTOR_SIZE,
                    distance=Distance.COSINE,
                ),
                hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
            )
            logger.info("kg_collection_created", collection=ENTITY_COLLECTION)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_collection(self, criticality: str) -> str:
        if criticality == "non_critical":
            return self._col_non_critical
        return self._col_critical

    def make_point_id(self, doc_id: str, chunk_index: int) -> str:
        """Deterministic UUID point id required by Qdrant."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{chunk_index}"))

    def _build_filter(
        self,
        sdlc_phase:    Optional[str],
        source_type:   Optional[str],
        filename:      Optional[str] = None,
        version:       Optional[int] = None,
        project_name:  Optional[str] = None,
    ) -> Optional[Filter]:
        must_conditions = []
        if project_name:
            must_conditions.append(
                FieldCondition(key="project_name", match=MatchValue(value=project_name))
            )
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

    async def upsert(
        self,
        embedded_chunks: list[EmbeddedChunk],
        criticality: str = "critical",
    ) -> int:
        """
        Upserts embedded chunks into the appropriate Qdrant collection.

        ``criticality`` must be ``"critical"`` or ``"non_critical"``.
        The value is also stored in every chunk's payload for transparency.
        Includes sparse BM25 vectors alongside dense vectors for hybrid search.
        """
        collection = self._resolve_collection(criticality)
        try:
            points = [
                PointStruct(
                    id      = self.make_point_id(chunk.doc_id, chunk.chunk_index),
                    vector  = {
                        "": chunk.vector,
                        "bm25": SparseVector(
                            indices=list(sparse.keys()),
                            values=list(sparse.values()),
                        ),
                    },
                    payload = {
                        "chunk_id":      chunk.chunk_id,
                        "doc_id":        chunk.doc_id,
                        "content":       chunk.content,
                        "filename":      chunk.filename,
                        "sdlc_phase":    chunk.sdlc_phase,
                        "chunk_index":   chunk.chunk_index,
                        "project_name":  chunk.project_name,
                        "criticality":   criticality,
                        **chunk.metadata,
                    },
                )
                for chunk in embedded_chunks
                for sparse in [_build_sparse_vector(chunk.content)]
            ]
            await self._client.upsert(collection_name=collection, points=points)
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

    async def search(
        self,
        query_vector:    list[float],
        top_k:           int             = settings.TOP_K,
        sdlc_phase:      Optional[str]   = None,
        source_type:     Optional[str]   = None,
        score_threshold: Optional[float] = settings.SIMILARITY_THRESHOLD,
        criticality:     Optional[str]   = None,
        filename:        Optional[str]   = None,
        version:         Optional[int]   = None,
        query_text:      Optional[str]   = None,
        project_name:    Optional[str]   = None,
    ) -> list[SearchResult]:
        """
        Hybrid semantic + BM25 search against Qdrant with RRF fusion.

        When ``query_text`` is provided, a sparse BM25 vector is computed and
        both dense and sparse prefetches are fused via Reciprocal Rank Fusion.
        Falls back to dense-only search when ``query_text`` is not supplied.

        ``project_name`` filters results to a single project namespace.

        ``criticality`` controls which collection is queried:
          - ``"critical"``     → critical collection only
          - ``"non_critical"`` → non-critical collection only
          - ``\"both\"``         → both collections; results merged and
                                 sorted by score descending, top_k returned
          - ``None`` (default) → critical collection only (non-critical is
                                 storage-only unless the user explicitly
                                 toggles on non-critical search)

        ``hnsw_ef`` is configured via settings.QDRANT_HNSW_EF for
        accuracy/speed trade-off at query time.
        """
        query_filter = self._build_filter(sdlc_phase, source_type, filename, version, project_name)

        search_params = SearchParams(
            hnsw_ef=settings.QDRANT_HNSW_EF,
            exact=False,
        )

        async def _query_one(col: str, crit_label: str) -> list[SearchResult]:
            try:
                if query_text:
                    sparse = _build_sparse_vector(query_text)
                    sparse_vec = SparseVector(
                        indices=list(sparse.keys()),
                        values=list(sparse.values()),
                    )
                    # Over-fetch for RRF fusion, then trim to top_k
                    prefetch_limit = min(top_k * 4, 40)
                    response = await self._client.query_points(
                        collection_name=col,
                        prefetch=[
                            Prefetch(
                                query=query_vector,
                                using="",
                                limit=prefetch_limit,
                                filter=query_filter,
                            ),
                            Prefetch(
                                query=sparse_vec,
                                using="bm25",
                                limit=prefetch_limit,
                                filter=query_filter,
                            ),
                        ],
                        query=FusionQuery(fusion=Fusion.RRF),
                        limit=top_k,
                        score_threshold=score_threshold,
                        with_payload=True,
                        search_params=search_params,
                    )
                else:
                    response = await self._client.query_points(
                        collection_name=col,
                        query          =query_vector,
                        limit          =top_k,
                        query_filter   =query_filter,
                        score_threshold=score_threshold,
                        with_payload   =True,
                        search_params  =search_params,
                    )
                return self._hits_to_results(response.points, crit_label)
            except Exception as e:
                raise VectorStoreError(str(e))

        if criticality == "non_critical":
            return await _query_one(self._col_non_critical, "non_critical")

        if criticality == "both":
            critical_results     = await _query_one(self._col_critical,     "critical")
            non_critical_results = await _query_one(self._col_non_critical, "non_critical")
            merged = sorted(
                critical_results + non_critical_results,
                key=lambda r: r.score,
                reverse=True,
            )
            return merged[:top_k]

        # Default: critical collection only
        return await _query_one(self._col_critical, "critical")

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_by_document(self, doc_id: str, criticality: Optional[str] = None):
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
                await self._client.delete(collection_name=col, points_selector=doc_filter)
                logger.info("qdrant_delete_done", collection=col, doc_id=doc_id)
            except Exception as e:
                raise VectorStoreError(str(e))

    async def retrieve_vectors(self, point_ids: list[str], criticality: str) -> dict[str, list[float]]:
        """
        Fetch stored vectors for the given point IDs without re-embedding.
        Returns ``{point_id: vector}``; missing IDs are simply absent.
        Used by the diff pipeline to reuse unchanged-chunk vectors.
        """
        if not point_ids:
            return {}
        collection = self._resolve_collection(criticality)
        try:
            records = await self._client.retrieve(
                collection_name=collection,
                ids=point_ids,
                with_vectors=True,
            )
            result: dict[str, list[float]] = {}
            for r in records:
                if r.vector is None:
                    continue
                # Named-vector collections return a dict; extract the unnamed dense vector.
                if isinstance(r.vector, dict):
                    dense = r.vector.get("")
                    if dense is not None:
                        result[str(r.id)] = dense
                else:
                    result[str(r.id)] = r.vector
            return result
        except Exception as e:
            raise VectorStoreError(str(e))