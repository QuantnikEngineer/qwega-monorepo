"""
Non-critical Document model — stored in the separate sdlc_kb_non_critical database.

Mirrors app.models.document.Document but is bound to BaseNonCritical so that
SQLAlchemy routes create_all / session operations to the non-critical engine.

If the non-critical Postgres DB is ever removed, only this file (and chunk_nc.py)
need to be deleted and the pipeline NC path replaced with a text-file fallback.
"""
from app.db.base import BaseNonCritical
from app.models._mixins import DocumentMixin


class DocumentNonCritical(DocumentMixin, BaseNonCritical):
    __tablename__ = "documents"    # same table name — different DB
