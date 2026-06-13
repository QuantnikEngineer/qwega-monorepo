from app.db.base import Base
from app.models._enums import Classification, DocumentStatus, SDLCPhase, SourceType  # noqa: F401 — re-exported
from app.models._mixins import DocumentMixin


class Document(DocumentMixin, Base):
    __tablename__ = "documents"
