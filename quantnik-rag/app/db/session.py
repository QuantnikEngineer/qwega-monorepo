import psycopg
from psycopg import sql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.core.logging import logger


async def ensure_databases() -> None:
    """Connect to the default 'postgres' DB and create sdlc_kb /
    sdlc_kb_non_critical if they do not already exist.
    Must be called before SQLAlchemy engines are first used.
    """
    async with await psycopg.AsyncConnection.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname="postgres",
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD.get_secret_value(),
        autocommit=True,
        sslmode=settings.POSTGRES_SSLMODE,
        connect_timeout=30,
    ) as conn:
        for db in (settings.POSTGRES_DB, settings.POSTGRES_DB_NON_CRITICAL):
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (db,)
                )
                if not await cur.fetchone():
                    await cur.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db))
                    )
                    logger.info("postgres_db_created", db=db)
                else:
                    logger.info("postgres_db_exists", db=db)

# ── Critical DB (sdlc_kb) ─────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── Non-Critical DB (sdlc_kb_non_critical) ────────────────────────────────────
# Completely isolated engine/session — drop or swap this block when migrating
# non-critical storage away from Postgres (e.g. back to text files).
engine_nc = create_async_engine(
    settings.DATABASE_URL_NON_CRITICAL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocalNonCritical = async_sessionmaker(
    bind=engine_nc,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)