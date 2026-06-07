import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sa_delete

from app.core.logging import logger
from app.models.document import Document, DocumentStatus, Classification, SDLCPhase, SourceType
from app.models.document_nc import DocumentNonCritical
from app.models.chunk import Chunk
from app.models.chunk_nc import ChunkNonCritical
from app.ingestion.deduplication import build_source_identity_filters
from app.ingestion.doc_ingestion import ingest
from app.classification.rule_engine import classify as rule_classify
from app.classification.llm_classifier import LLMClassifier
from app.indexing.chunker import chunk_document
from app.indexing.embedder import Embedder, EmbeddedChunk
from app.retrieval.qdrant_store import QdrantStore


# Weights for final decision
_RULE_WEIGHT = 0.4
_LLM_WEIGHT  = 0.6


class IngestionPipeline:
    """
    Dual-database ingestion pipeline.

    ``db``    â†’ critical Postgres DB (sdlc_kb)
    ``db_nc`` â†’ non-critical Postgres DB (sdlc_kb_non_critical)

    Documents are initially created in the critical DB by the upload API.
    After classification, non-critical documents are migrated to the NC DB with
    their chunks, and the critical DB record is removed.

    To swap the NC Postgres store for a text-file fallback in the future:
      1. Remove ``db_nc`` parameter and all ``_nc`` model writes in this file.
      2. Re-add ``_archive_non_critical_text`` helper.
    """

    def __init__(self, db: AsyncSession, db_nc: AsyncSession | None = None):
        self.db       = db
        self.db_nc    = db_nc   # None for paths that are always critical (e.g. feedback)
        self.llm_clf  = LLMClassifier()
        self.embedder = Embedder()
        self.store    = QdrantStore()

    # â”€â”€ Public entry points â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def run(self, doc_id: str, file_path: Path):
        doc = await self._get_doc(doc_id)

        try:
            await self._set_status(doc, DocumentStatus.PROCESSING)

            logger.info("pipeline_ingest", doc_id=doc_id)
            normalized          = ingest(file_path)
            doc.normalized_text = normalized["text"]

            prev_doc, prev_criticality = await self._find_previous_version(doc)
            if prev_doc is not None:
                doc.version = (getattr(prev_doc, "version", 1) or 1) + 1
                logger.info(
                    "pipeline_diff_detected",
                    doc_id=doc_id,
                    prev_doc_id=str(prev_doc.id),
                    new_version=doc.version,
                )
                await self._classify_and_index_diff(
                    doc, normalized, prev_doc, prev_criticality, cleanup_path=file_path
                )
            else:
                doc.version = 1
                await self._classify_and_index(doc, normalized, cleanup_path=file_path)
        except Exception as e:
            doc.status        = DocumentStatus.FAILED
            doc.error_message = str(e)
            await self.db.commit()
            logger.error("pipeline_failed", doc_id=doc_id, error=str(e))
            raise

    async def run_from_text(self, doc_id: str, normalized: dict):
        """Entry point for websites, repositories, etc. â€” skips file parsing."""
        doc = await self._get_doc(doc_id)

        try:
            await self._set_status(doc, DocumentStatus.PROCESSING)
            doc.normalized_text = normalized["text"]
            doc.content_hash = doc.content_hash or hashlib.sha256(
                normalized["text"].encode("utf-8")
            ).hexdigest()

            prev_doc, prev_criticality = await self._find_previous_version(doc)
            if prev_doc is not None:
                doc.version = (getattr(prev_doc, "version", 1) or 1) + 1
                logger.info(
                    "pipeline_diff_detected",
                    doc_id=doc_id,
                    prev_doc_id=str(prev_doc.id),
                    new_version=doc.version,
                )
                await self._classify_and_index_diff(
                    doc, normalized, prev_doc, prev_criticality, cleanup_path=None
                )
                return

            doc.version = 1
            await self._classify_and_index(doc, normalized, cleanup_path=None)

        except Exception as e:
            doc.status        = DocumentStatus.FAILED
            doc.error_message = str(e)
            await self.db.commit()
            logger.error("pipeline_failed", doc_id=doc_id, error=str(e))
            raise

    async def run_agent_output(self, doc_id: str, normalized: dict, sdlc_phase: str):
        """Agent outputs bypass classification â€” always critical."""
        doc = await self._get_doc(doc_id)

        try:
            await self._set_status(doc, DocumentStatus.PROCESSING)
            doc.normalized_text  = normalized["text"]
            doc.content_hash     = doc.content_hash or hashlib.sha256(
                normalized["text"].encode("utf-8")
            ).hexdigest()
            doc.classification   = Classification.CRITICAL
            doc.confidence_score = 1.0
            doc.sdlc_phase       = (
                SDLCPhase(sdlc_phase)
                if sdlc_phase in SDLCPhase._value2member_map_
                else SDLCPhase.GENERAL
            )
            doc.triggered_areas = ["agent_output"]

            prev_doc, prev_criticality = await self._find_previous_version(doc)

            logger.info("pipeline_agent_indexing", doc_id=doc_id, sdlc_phase=sdlc_phase)
            count = await self._index_agent_output(doc, normalized, sdlc_phase, prev_doc, prev_criticality)
            logger.info("pipeline_agent_done", doc_id=doc_id, sdlc_phase=sdlc_phase, chunks=count)

        except Exception as e:
            doc.status        = DocumentStatus.FAILED
            doc.error_message = str(e)
            await self.db.commit()
            logger.error("pipeline_agent_failed", doc_id=doc_id, error=str(e))
            raise

    async def _index_agent_output(
        self,
        doc,
        normalized: dict,
        sdlc_phase: str,
        prev_doc=None,
        prev_criticality: str | None = None,
    ) -> int:
        doc_id = str(doc.id)
        prev_doc_id = str(prev_doc.id) if prev_doc is not None else None

        new_chunks = chunk_document(
            text       = normalized["text"],
            doc_id     = doc_id,
            filename   = doc.original_name,
            sdlc_phase = sdlc_phase,
            extra_meta = {
                "ingested_at": datetime.utcnow().isoformat(),
                "version":     getattr(doc, "version", 1),
            },
        )

        all_embedded: list[EmbeddedChunk]
        if prev_doc is None or prev_criticality is None:
            all_embedded = await self.embedder.embed_chunks(new_chunks)
        else:
            new_hash_per_index = {
                c.chunk_index: hashlib.sha256(c.content.encode()).hexdigest()
                for c in new_chunks
            }
            old_chunks = await self._fetch_old_chunks(prev_doc_id, prev_criticality)
            old_hash_to_chunk = {
                c.content_hash: c
                for c in old_chunks
                if c.content_hash
            }
            unchanged_hashes = set(new_hash_per_index.values()) & set(old_hash_to_chunk.keys())
            unchanged_old_point_ids = [
                self.store.make_point_id(prev_doc_id, old_hash_to_chunk[h].chunk_index)
                for h in unchanged_hashes
            ]
            old_vectors = self.store.retrieve_vectors(unchanged_old_point_ids, prev_criticality)

            old_hash_to_vector: dict[str, list[float]] = {}
            for content_hash in unchanged_hashes:
                old_chunk = old_hash_to_chunk[content_hash]
                point_id = self.store.make_point_id(prev_doc_id, old_chunk.chunk_index)
                if point_id in old_vectors:
                    old_hash_to_vector[content_hash] = old_vectors[point_id]

            chunks_to_embed = []
            chunks_reuse_vector = []
            for new_chunk in new_chunks:
                content_hash = new_hash_per_index[new_chunk.chunk_index]
                if content_hash in old_hash_to_vector:
                    chunks_reuse_vector.append((new_chunk, old_hash_to_vector[content_hash]))
                else:
                    chunks_to_embed.append(new_chunk)

            newly_embedded = (
                await self.embedder.embed_chunks(chunks_to_embed) if chunks_to_embed else []
            )
            all_embedded = list(newly_embedded)
            for new_chunk, vector in chunks_reuse_vector:
                all_embedded.append(
                    EmbeddedChunk(
                        chunk_id    = new_chunk.chunk_id,
                        doc_id      = new_chunk.doc_id,
                        content     = new_chunk.content,
                        chunk_index = new_chunk.chunk_index,
                        token_count = new_chunk.token_count,
                        sdlc_phase  = new_chunk.sdlc_phase,
                        filename    = new_chunk.filename,
                        metadata    = new_chunk.metadata,
                        vector      = vector,
                    )
                )

        count = self.store.upsert(all_embedded, criticality="critical")

        if prev_doc is not None and prev_criticality is not None:
            self.store.delete_by_document(prev_doc_id, prev_criticality)
            await self._delete_previous_version(prev_doc, prev_criticality)

        for item in all_embedded:
            self.db.add(Chunk(
                document_id  = doc_id,
                qdrant_id    = item.chunk_id,
                content      = item.content,
                chunk_index  = item.chunk_index,
                token_count  = item.token_count,
                sdlc_phase   = item.sdlc_phase,
                criticality  = "critical",
                content_hash = hashlib.sha256(item.content.encode()).hexdigest(),
            ))

        doc.chunk_count  = count
        doc.status       = DocumentStatus.COMPLETED
        doc.processed_at = datetime.utcnow()
        await self.db.commit()
        return count

    async def run_feedback(self, doc_id: str, content: str, sdlc_phase: str, artifact_type: str):
        """Feedback is always critical."""
        doc = await self._get_doc(doc_id)

        try:
            await self._set_status(doc, DocumentStatus.PROCESSING)
            doc.normalized_text  = content
            doc.classification   = Classification.CRITICAL
            doc.confidence_score = 1.0
            doc.sdlc_phase       = (
                SDLCPhase(sdlc_phase)
                if sdlc_phase in SDLCPhase._value2member_map_
                else SDLCPhase.GENERAL
            )
            doc.triggered_areas = ["feedback"]

            logger.info("pipeline_feedback_indexing", doc_id=doc_id, sdlc_phase=sdlc_phase)

            chunks   = chunk_document(
                text       = content,
                doc_id     = doc_id,
                filename   = doc.original_name,
                sdlc_phase = sdlc_phase,
                extra_meta = {
                    "source_type":   "feedback",
                    "artifact_type": artifact_type,
                    "ingested_at":   datetime.utcnow().isoformat(),
                },
            )
            embedded = await self.embedder.embed_chunks(chunks)
            count    = self.store.upsert(embedded, criticality="critical")

            for item in embedded:
                self.db.add(Chunk(
                    document_id = doc_id,
                    qdrant_id   = item.chunk_id,
                    content     = item.content,
                    chunk_index = item.chunk_index,
                    token_count = item.token_count,
                    sdlc_phase  = item.sdlc_phase,
                    criticality = "critical",
                ))

            doc.chunk_count  = count
            doc.status       = DocumentStatus.COMPLETED
            doc.processed_at = datetime.utcnow()
            await self.db.commit()
            logger.info("pipeline_feedback_done", doc_id=doc_id, chunks=count)

        except Exception as e:
            doc.status        = DocumentStatus.FAILED
            doc.error_message = str(e)
            await self.db.commit()
            logger.error("pipeline_feedback_failed", doc_id=doc_id, error=str(e))
            raise

    # â”€â”€ Classification + indexing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _classify_and_index(self, doc, normalized: dict, cleanup_path: Path | None):
        doc_id = str(doc.id)

        logger.info("pipeline_classify_both", doc_id=doc_id)
        rule_result, llm_result = await self._run_both(normalized["text"])

        final = self._combine(rule_result, llm_result)

        logger.info(
            "pipeline_classification_final",
            doc_id     = doc_id,
            rule       = rule_result.classification,
            rule_conf  = round(rule_result.confidence, 3),
            llm        = llm_result["classification"],
            llm_conf   = round(llm_result["confidence"], 3),
            final      = final["classification"],
            final_conf = round(final["confidence"], 3),
            agreement  = rule_result.classification == llm_result["classification"],
        )

        doc.classification   = Classification(final["classification"])
        doc.confidence_score = final["confidence"]
        doc.sdlc_phase       = (
            SDLCPhase(final["sdlc_phase"])
            if final["sdlc_phase"] in SDLCPhase._value2member_map_
            else SDLCPhase.GENERAL
        )
        doc.triggered_areas  = final["triggered_areas"]

        criticality = final["classification"]   # "critical" | "non_critical"
        logger.info("pipeline_indexing", doc_id=doc_id, criticality=criticality)

        chunks   = chunk_document(
            text       = normalized["text"],
            doc_id     = doc_id,
            filename   = doc.original_name,
            sdlc_phase = final["sdlc_phase"],            extra_meta = {
                "ingested_at": datetime.utcnow().isoformat(),
                "version":     getattr(doc, "version", 1),
            },        )
        embedded = await self.embedder.embed_chunks(chunks)
        count    = self.store.upsert(embedded, criticality=criticality)

        if criticality == "non_critical":
            await self._write_non_critical(doc, embedded, count)
            # Remove from critical DB â€” it was staged there by the upload API
            await self.db.delete(doc)
            await self.db.commit()
            if cleanup_path:
                self._cleanup_upload(cleanup_path)
            logger.info("pipeline_done", doc_id=doc_id, classification="non_critical", db="sdlc_kb_non_critical")
        else:
            for item in embedded:
                self.db.add(Chunk(
                    document_id  = doc_id,
                    qdrant_id    = item.chunk_id,
                    content      = item.content,
                    chunk_index  = item.chunk_index,
                    token_count  = item.token_count,
                    sdlc_phase   = item.sdlc_phase,
                    criticality  = "critical",
                    content_hash = hashlib.sha256(item.content.encode()).hexdigest(),
                ))
            doc.chunk_count  = count
            doc.status       = DocumentStatus.COMPLETED
            doc.processed_at = datetime.utcnow()
            await self.db.commit()
            logger.info("pipeline_done", doc_id=doc_id, classification="critical", db="sdlc_kb")

    async def _write_non_critical(self, doc, embedded, count: int):
        """Persists a non-critical document + its chunks into the NC Postgres DB."""
        if self.db_nc is None:
            raise RuntimeError(
                "IngestionPipeline.db_nc is not set. "
                "Pass a non-critical DB session to IngestionPipeline(db, db_nc)."
            )
        doc_nc = DocumentNonCritical(
            id               = doc.id,
            filename         = doc.filename,
            original_name    = doc.original_name,
            file_type        = doc.file_type,
            file_size_bytes  = doc.file_size_bytes,
            status           = DocumentStatus.COMPLETED,
            classification   = Classification.NON_CRITICAL,
            sdlc_phase       = doc.sdlc_phase,
            confidence_score = doc.confidence_score,
            triggered_areas  = doc.triggered_areas,
            chunk_count      = count,
            normalized_text  = doc.normalized_text,
            source_type      = doc.source_type,
            source_url       = doc.source_url,
            source_metadata  = doc.source_metadata,
            content_hash     = getattr(doc, "content_hash", None),
            version          = getattr(doc, "version", 1),
            processed_at     = datetime.utcnow(),
        )
        self.db_nc.add(doc_nc)
        # Flush doc_nc first so the FK from chunks → documents is satisfied
        # immediately. With autoflush=False and raw UUID values (no ORM
        # relationship), SQLAlchemy cannot infer the parent-before-child
        # ordering, causing a PostgreSQL ForeignKeyViolation on commit.
        await self.db_nc.flush()

        for item in embedded:
            self.db_nc.add(ChunkNonCritical(
                document_id  = doc.id,
                qdrant_id    = item.chunk_id,
                content      = item.content,
                chunk_index  = item.chunk_index,
                token_count  = item.token_count,
                sdlc_phase   = item.sdlc_phase,
                criticality  = "non_critical",
                content_hash = hashlib.sha256(item.content.encode()).hexdigest(),
            ))

        await self.db_nc.commit()

    # ── Diff-based re-upload handling ─────────────────────────────────────────

    async def _find_previous_version(self, doc: Document):
        """
        Return (previous_doc, criticality) if a completed document with the
        same source identity already exists; otherwise (None, None).
        """
        filters = build_source_identity_filters(
            Document,
            source_type=doc.source_type,
            original_name=doc.original_name,
            source_url=doc.source_url,
            source_metadata=doc.source_metadata,
            exclude_doc_id=doc.id,
        )
        result = await self.db.execute(
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc())
            .limit(1)
        )
        prev = result.scalar_one_or_none()
        if prev:
            return prev, "critical"

        if self.db_nc:
            filters_nc = build_source_identity_filters(
                DocumentNonCritical,
                source_type=doc.source_type,
                original_name=doc.original_name,
                source_url=doc.source_url,
                source_metadata=doc.source_metadata,
            )
            result_nc = await self.db_nc.execute(
                select(DocumentNonCritical)
                .where(*filters_nc)
                .order_by(DocumentNonCritical.created_at.desc())
                .limit(1)
            )
            prev_nc = result_nc.scalar_one_or_none()
            if prev_nc:
                return prev_nc, "non_critical"

        return None, None

    async def _fetch_old_chunks(self, doc_id: str, criticality: str):
        """Fetch all DB Chunk records for a prior document version."""
        if criticality == "non_critical" and self.db_nc:
            result = await self.db_nc.execute(
                select(ChunkNonCritical).where(ChunkNonCritical.document_id == doc_id)
            )
            return result.scalars().all()
        result = await self.db.execute(
            select(Chunk).where(Chunk.document_id == doc_id)
        )
        return result.scalars().all()

    async def _delete_previous_version(self, prev_doc, prev_criticality: str):
        """Remove old document + its chunks from the appropriate DB."""
        prev_id = prev_doc.id
        if prev_criticality == "non_critical" and self.db_nc:
            await self.db_nc.execute(
                sa_delete(ChunkNonCritical).where(ChunkNonCritical.document_id == prev_id)
            )
            await self.db_nc.delete(prev_doc)
            await self.db_nc.commit()
        else:
            await self.db.execute(
                sa_delete(Chunk).where(Chunk.document_id == prev_id)
            )
            await self.db.delete(prev_doc)
            await self.db.commit()

    async def _classify_and_index_diff(
        self,
        doc,
        normalized: dict,
        prev_doc,
        prev_criticality: str,
        cleanup_path: "Path | None",
    ):
        """
        Diff-aware ingestion for a re-uploaded document.

        * Chunks whose content is identical to the previous version are NOT
          re-embedded — their existing Qdrant vectors are reused directly.
        * Only new or changed chunks go through the embedding model.
        * Old Qdrant vectors are deleted after the new set is safely upserted.
        * The previous DB document + chunk records are removed.
        """
        doc_id      = str(doc.id)
        prev_doc_id = str(prev_doc.id)

        # 1. Classify the new content (full text, same as normal path)
        logger.info("pipeline_diff_classify", doc_id=doc_id)
        rule_result, llm_result = await self._run_both(normalized["text"])
        final = self._combine(rule_result, llm_result)

        doc.classification   = Classification(final["classification"])
        doc.confidence_score = final["confidence"]
        doc.sdlc_phase       = (
            SDLCPhase(final["sdlc_phase"])
            if final["sdlc_phase"] in SDLCPhase._value2member_map_
            else SDLCPhase.GENERAL
        )
        doc.triggered_areas = final["triggered_areas"]
        new_criticality = final["classification"]

        # 2. Chunk the new content and hash each chunk
        ingested_at = datetime.utcnow().isoformat()
        new_chunks = chunk_document(
            text       = normalized["text"],
            doc_id     = doc_id,
            filename   = doc.original_name,
            sdlc_phase = final["sdlc_phase"],
            extra_meta = {
                "ingested_at": ingested_at,
                "version":     getattr(doc, "version", 1),
            },
        )
        new_hash_per_index = {
            c.chunk_index: hashlib.sha256(c.content.encode()).hexdigest()
            for c in new_chunks
        }
        new_content_hashes = set(new_hash_per_index.values())

        # 3. Load old chunks and build a content-hash -> chunk map
        old_chunks = await self._fetch_old_chunks(prev_doc_id, prev_criticality)
        old_hash_to_chunk = {
            c.content_hash: c
            for c in old_chunks
            if c.content_hash
        }
        unchanged_hashes = new_content_hashes & set(old_hash_to_chunk.keys())

        # 4. Retrieve stored vectors for unchanged chunks (skip re-embedding)
        unchanged_old_point_ids = [
            self.store.make_point_id(prev_doc_id, old_hash_to_chunk[h].chunk_index)
            for h in unchanged_hashes
        ]
        old_vectors = self.store.retrieve_vectors(unchanged_old_point_ids, prev_criticality)

        # Map content_hash -> vector
        old_hash_to_vector: dict = {}
        for h in unchanged_hashes:
            old_c = old_hash_to_chunk[h]
            pid   = self.store.make_point_id(prev_doc_id, old_c.chunk_index)
            if pid in old_vectors:
                old_hash_to_vector[h] = old_vectors[pid]

        # 5. Partition new chunks: re-embed vs reuse-vector
        chunks_to_embed:     list = []
        chunks_reuse_vector: list = []   # list of (ChunkResult, vector)

        for nc in new_chunks:
            h = new_hash_per_index[nc.chunk_index]
            if h in old_hash_to_vector:
                chunks_reuse_vector.append((nc, old_hash_to_vector[h]))
            else:
                chunks_to_embed.append(nc)

        logger.info(
            "pipeline_diff_stats",
            doc_id    = doc_id,
            total     = len(new_chunks),
            changed   = len(chunks_to_embed),
            unchanged = len(chunks_reuse_vector),
        )

        # 6. Embed only the changed / new chunks
        newly_embedded: list = (
            await self.embedder.embed_chunks(chunks_to_embed) if chunks_to_embed else []
        )

        # 7. Build complete embedded list (changed + reused vectors)
        all_embedded: list = list(newly_embedded)
        for nc, vec in chunks_reuse_vector:
            all_embedded.append(
                EmbeddedChunk(
                    chunk_id    = nc.chunk_id,
                    doc_id      = nc.doc_id,
                    content     = nc.content,
                    chunk_index = nc.chunk_index,
                    token_count = nc.token_count,
                    sdlc_phase  = nc.sdlc_phase,
                    filename    = nc.filename,
                    metadata    = nc.metadata,
                    vector      = vec,
                )
            )

        # 8. Upsert all chunks to the target collection (new doc_id-based point IDs)
        count = self.store.upsert(all_embedded, criticality=new_criticality)

        # Note: previous version vectors and DB records are intentionally retained.
        # Both versions remain queryable so the chatbot can ask users to clarify
        # which version they want when a query returns chunks from multiple versions.

        # 9. Persist new document + chunks to DB
        if new_criticality == "non_critical":
            await self._write_non_critical(doc, all_embedded, count)
            await self.db.delete(doc)
            await self.db.commit()
            if cleanup_path:
                self._cleanup_upload(cleanup_path)
            logger.info(
                "pipeline_diff_done",
                doc_id         = doc_id,
                classification = "non_critical",
                changed        = len(chunks_to_embed),
                unchanged      = len(chunks_reuse_vector),
            )
        else:
            for item in all_embedded:
                self.db.add(Chunk(
                    document_id  = doc_id,
                    qdrant_id    = item.chunk_id,
                    content      = item.content,
                    chunk_index  = item.chunk_index,
                    token_count  = item.token_count,
                    sdlc_phase   = item.sdlc_phase,
                    criticality  = "critical",
                    content_hash = hashlib.sha256(item.content.encode()).hexdigest(),
                ))
            doc.chunk_count  = count
            doc.status       = DocumentStatus.COMPLETED
            doc.processed_at = datetime.utcnow()
            await self.db.commit()
            if cleanup_path:
                self._cleanup_upload(cleanup_path)
            logger.info(
                "pipeline_diff_done",
                doc_id         = doc_id,
                classification = "critical",
                changed        = len(chunks_to_embed),
                unchanged      = len(chunks_reuse_vector),
            )

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def _run_both(self, text: str) -> tuple:
        import asyncio
        return await asyncio.gather(
            self._run_rule_engine(text),
            self.llm_clf.classify(text),
        )

    async def _run_rule_engine(self, text: str):
        return rule_classify(text)

    def _combine(self, rule_result, llm_result: dict) -> dict:
        final_clf = (
            "critical"
            if rule_result.classification == "critical" or llm_result["classification"] == "critical"
            else "non_critical"
        )

        blended_confidence = (
            (rule_result.confidence * _RULE_WEIGHT) +
            (llm_result["confidence"] * _LLM_WEIGHT)
        )
        final_confidence = max(blended_confidence, rule_result.confidence, llm_result["confidence"])

        final_phase = (
            llm_result["sdlc_phase"]
            if llm_result["sdlc_phase"] != "general"
            else rule_result.sdlc_phase
        )

        triggered_areas = list(set(
            rule_result.triggered_rules +
            llm_result.get("triggered_areas", [])
        ))

        return {
            "classification":  final_clf,
            "confidence":      round(final_confidence, 4),
            "sdlc_phase":      final_phase,
            "triggered_areas": triggered_areas,
        }

    async def _get_doc(self, doc_id: str) -> Document:
        result = await self.db.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one()

    async def _set_status(self, doc: Document, status: DocumentStatus):
        doc.status = status
        await self.db.commit()

    def _cleanup_upload(self, file_path: Path):
        try:
            file_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("pipeline_upload_cleanup_failed", path=str(file_path), error=str(exc))

