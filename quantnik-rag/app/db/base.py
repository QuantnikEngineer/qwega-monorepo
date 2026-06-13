from sqlalchemy.orm import DeclarativeBase


# ── Critical DB (sdlc_kb) ─────────────────────────────────────────────────────
# All critical models + feedback are registered here.
class Base(DeclarativeBase):
    pass


# ── Non-Critical DB (sdlc_kb_non_critical) ────────────────────────────────────
# Non-critical Document and Chunk rows live here.
# This base has its own isolated metadata so create_all targets only this DB.
# If the non-critical Postgres DB is removed in the future, only this base
# (and the nc_ models below) need to be swapped out.
class BaseNonCritical(DeclarativeBase):
    pass


# Register critical-DB models with Base
from app.models.document import Document          # noqa
from app.models.chunk import Chunk                # noqa
import app.models.feedback                        # noqa  — registers Feedback table
import app.models.query_log                       # noqa  — registers QueryLog table
import app.models.conversation                    # noqa  — registers Conversation table
import app.models.knowledge_graph                 # noqa  — registers Entity + Relationship tables

# Register non-critical-DB models with BaseNonCritical
from app.models.document_nc import DocumentNonCritical   # noqa
from app.models.chunk_nc import ChunkNonCritical         # noqa