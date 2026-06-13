from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal, AsyncSessionLocalNonCritical


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yields a session bound to the critical DB (sdlc_kb)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db_non_critical() -> AsyncGenerator[AsyncSession, None]:
    """Yields a session bound to the non-critical DB (sdlc_kb_non_critical)."""
    async with AsyncSessionLocalNonCritical() as session:
        try:
            yield session
        finally:
            await session.close()