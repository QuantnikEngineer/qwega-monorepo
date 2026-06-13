from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings


@dataclass
class ChunkResult:
    chunk_id:     str
    doc_id:       str
    content:      str
    chunk_index:  int
    token_count:  int
    sdlc_phase:   str
    filename:     str
    project_name: str
    metadata:     dict[str, Any]


def chunk_document(
    text:          str,
    doc_id:        str,
    filename:      str,
    sdlc_phase:    str,
    project_name:  str,
    extra_meta:    dict[str, Any] = None,
) -> list[ChunkResult]:
    """
    Splits normalized text into overlapping chunks.
    Attaches metadata to each chunk for Qdrant payload.
    Only called for CRITICAL documents.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    raw_chunks = splitter.split_text(text)

    results = []
    for i, content in enumerate(raw_chunks):
        results.append(
            ChunkResult(
                chunk_id     = f"{doc_id}_{i}",
                doc_id       = doc_id,
                content      = content,
                chunk_index  = i,
                token_count  = len(content.split()),
                sdlc_phase   = sdlc_phase,
                filename     = filename,
                project_name = project_name,
                metadata     = extra_meta or {},
            )
        )

    return results