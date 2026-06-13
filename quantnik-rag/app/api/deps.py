from functools import lru_cache
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal, AsyncSessionLocalNonCritical
from app.retrieval.qdrant_store import QdrantStore
from app.indexing.embedder import Embedder
from app.retrieval.retriever import Retriever


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields a session bound to the critical DB (sdlc_kb)."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_db_non_critical() -> AsyncGenerator[AsyncSession, None]:
    """Yields a session bound to the non-critical DB (sdlc_kb_non_critical)."""
    async with AsyncSessionLocalNonCritical() as session:
        yield session


@lru_cache()
def get_qdrant_store() -> QdrantStore:
    return QdrantStore()


@lru_cache()
def get_embedder() -> Embedder:
    return Embedder()


@lru_cache()
def get_retriever() -> Retriever:
    return Retriever(store=get_qdrant_store(), embedder=get_embedder())