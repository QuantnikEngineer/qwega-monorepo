import asyncio
from dataclasses import dataclass
from typing import Any

import vertexai
from vertexai.language_models import TextEmbeddingModel

from app.core.config import settings
from app.core.exceptions import EmbeddingError
from app.core.logging import logger
from app.indexing.chunker import ChunkResult


BATCH_SIZE = 20       
RETRY_LIMIT = 3
BACKOFF_BASE = 2      # seconds


@dataclass
class EmbeddedChunk:
    chunk_id:    str
    doc_id:      str
    content:     str
    chunk_index: int
    token_count: int
    sdlc_phase:  str
    filename:    str
    metadata:    dict[str, Any]
    vector:      list[float]


class Embedder:

    def __init__(self):
        vertexai.init(
            project=settings.VERTEX_PROJECT_ID,
            location=settings.VERTEX_LOCATION,
        )
        self._model = TextEmbeddingModel.from_pretrained(settings.VERTEX_EMBEDDING_MODEL)

    async def embed_chunks(self, chunks: list[ChunkResult]) -> list[EmbeddedChunk]:
        """Embeds all chunks in batches. Returns EmbeddedChunk list."""
        batches = [
            chunks[i: i + BATCH_SIZE]
            for i in range(0, len(chunks), BATCH_SIZE)
        ]

        embedded = []
        for batch_idx, batch in enumerate(batches):
            vectors = await self._embed_batch_with_retry(batch, batch_idx)
            for chunk, vector in zip(batch, vectors):
                embedded.append(
                    EmbeddedChunk(**chunk.__dict__, vector=vector)
                )

        logger.info("embedding_complete", total_chunks=len(embedded))
        return embedded

    async def embed_query(self, query: str) -> list[float]:
        """Embeds a single query string for retrieval."""
        try:
            result = self._model.get_embeddings([query])
            return result[0].values
        except Exception as e:
            raise EmbeddingError(str(e))

    async def _embed_batch_with_retry(
        self,
        batch: list[ChunkResult],
        batch_idx: int,
    ) -> list[list[float]]:
        texts = [c.content for c in batch]

        for attempt in range(RETRY_LIMIT):
            try:
                results = self._model.get_embeddings(texts)
                logger.info("batch_embedded", batch=batch_idx + 1, size=len(batch))
                return [r.values for r in results]
            except Exception as e:
                if attempt == RETRY_LIMIT - 1:
                    raise EmbeddingError(f"Batch {batch_idx} failed after {RETRY_LIMIT} retries: {e}")
                wait = BACKOFF_BASE ** attempt
                logger.warning("batch_retry", batch=batch_idx, attempt=attempt + 1, wait=wait)
                await asyncio.sleep(wait)