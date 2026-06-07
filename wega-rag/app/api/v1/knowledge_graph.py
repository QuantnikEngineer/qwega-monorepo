"""
Knowledge graph query endpoint.

Returns entities and relationships relevant to a query,
enabling graph-aware context enrichment for RAG.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.memory.knowledge_graph import KnowledgeGraphQuerier

router = APIRouter()

_kg_querier = KnowledgeGraphQuerier()


class KGQueryRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=255)
    query:        str = Field(..., min_length=1, max_length=1000)
    top_k:        int = Field(5, ge=1, le=20)


class KGRelationship(BaseModel):
    source: str
    target: str
    type:   str


class KGQueryResponse(BaseModel):
    entities:      list[str]
    relationships: list[KGRelationship]
    context:       str


@router.post(
    "/knowledge-graph/query",
    response_model=KGQueryResponse,
    summary="Query the knowledge graph",
    description=(
        "Returns entities and their relationships relevant to the query. "
        "Used for graph-aware context enrichment in RAG retrieval."
    ),
)
async def query_knowledge_graph(
    request: KGQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> KGQueryResponse:
    try:
        result = await _kg_querier.find_related_context(
            db=db,
            query=request.query,
            project_name=request.project_name,
            top_k=request.top_k,
        )
        return KGQueryResponse(
            entities=result.get("entities", []),
            relationships=[
                KGRelationship(**r) for r in result.get("relationships", [])
            ],
            context=result.get("context", ""),
        )
    except Exception:
        raise HTTPException(500, detail="An internal error occurred.")
