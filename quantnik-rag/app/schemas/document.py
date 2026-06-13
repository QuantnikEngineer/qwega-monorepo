from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models._enums import DocumentStatus, Classification, SDLCPhase


class DocumentUploadResponse(BaseModel):
    id:             UUID
    filename:       str
    file_type:      str
    file_size_bytes:int
    status:         DocumentStatus
    message:        str


class DocumentBatchUploadResponse(BaseModel):
    documents: list[DocumentUploadResponse]
    skipped:   list[str] = []
    message:   str


class DocumentStatusResponse(BaseModel):
    id:              UUID
    project_name:    str
    filename:        str
    original_name:   str
    file_type:       str
    status:          DocumentStatus
    classification:  Optional[Classification]
    sdlc_phase:      Optional[SDLCPhase]
    confidence_score:Optional[float]
    triggered_areas: Optional[list]
    chunk_count:     int
    error_message:   Optional[str]
    created_at:      datetime
    processed_at:    Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    total:     int
    documents: list[DocumentStatusResponse]