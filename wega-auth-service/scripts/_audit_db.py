"""Quick DB audit - check tables, users, migration state."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def audit():
    from app.core.config import settings
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.connect() as conn:
        # Check tables exist
        tables = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        print("TABLES:", [r[0] for r in tables.fetchall()])
        
        # Check users
        users = await conn.execute(text("SELECT normalized_email, status FROM users"))
        print("USERS:", [(r[0], r[1]) for r in users.fetchall()])
        
        # Check alembic version
        version = await conn.execute(text("SELECT version_num FROM alembic_version"))
        print("ALEMBIC VERSION:", version.scalar())
        
        # Check roles
        roles = await conn.execute(text("SELECT name FROM roles ORDER BY name"))
        print("ROLES:", [r[0] for r in roles.fetchall()])
        
        # Check if keys exist
        import os
        keys_dir = Path(__file__).parent.parent / "keys"
        print("JWT KEYS:", "OK" if (keys_dir / "private.pem").exists() else "MISSING")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(audit())
