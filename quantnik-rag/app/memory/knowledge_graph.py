"""
Knowledge graph extraction and querying using Postgres + Qdrant.

Entities and relationships are extracted from document chunks during ingestion
via LLM, stored in Postgres, and entity embeddings are stored in a dedicated
Qdrant collection for similarity-based graph traversal.

No Neo4j/external graph DB required.
"""
import json
import uuid
from typing import Optional

import vertexai
from vertexai.generative_models import GenerativeModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.knowledge_graph import Entity, Relationship
from app.indexing.embedder import Embedder
from app.retrieval.qdrant_store import QdrantStore


_EXTRACTION_PROMPT = """
Extract entities and relationships from this SDLC document chunk.

ENTITY TYPES: SYSTEM, API, SERVICE, DATABASE, TECHNOLOGY, PERSON, TEAM, PROCESS, REQUIREMENT, STANDARD, TOOL, ENVIRONMENT, MODULE

RELATIONSHIP TYPES: DEPENDS_ON, IMPLEMENTS, TESTS, SECURES, DEPLOYS_TO, INTEGRATES_WITH, OWNED_BY, PART_OF, REQUIRES, PRODUCES, CONSUMES

Return ONLY valid JSON:
{
  "entities": [
    {"name": "exact name", "type": "ENTITY_TYPE", "description": "one line"}
  ],
  "relationships": [
    {"source": "entity name", "target": "entity name", "type": "RELATIONSHIP_TYPE", "description": "one line"}
  ]
}

If no entities found, return {"entities": [], "relationships": []}.

Chunk:
---
{chunk_text}
---
"""

# Qdrant collection for entity embeddings
ENTITY_COLLECTION = "sdlc_kb_entities"


class KnowledgeGraphExtractor:

    def __init__(self):
        vertexai.init(
            project=settings.VERTEX_PROJECT_ID,
            location=settings.VERTEX_LOCATION,
        )
        self._llm = GenerativeModel(model_name=settings.VERTEX_LLM_MODEL)
        self._embedder = Embedder()

    async def extract_and_store(
        self,
        db: AsyncSession,
        chunk_text: str,
        doc_id: str,
        project_name: str,
        sdlc_phase: str | None = None,
    ) -> dict:
        """
        Extract entities + relationships from a chunk, store in Postgres,
        and embed entities into Qdrant.
        """
        extracted = await self._extract(chunk_text)
        if not extracted["entities"]:
            return {"entities": 0, "relationships": 0}

        entity_name_to_id: dict[str, uuid.UUID] = {}

        for ent in extracted["entities"]:
            entity_id = await self._upsert_entity(
                db,
                project_name=project_name,
                name=ent["name"],
                entity_type=ent.get("type", "SYSTEM"),
                description=ent.get("description"),
                doc_id=doc_id,
                sdlc_phase=sdlc_phase,
            )
            entity_name_to_id[ent["name"]] = entity_id

        rel_count = 0
        for rel in extracted.get("relationships", []):
            src_id = entity_name_to_id.get(rel["source"])
            tgt_id = entity_name_to_id.get(rel["target"])
            if src_id and tgt_id:
                db.add(Relationship(
                    project_name=project_name,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type=rel.get("type", "RELATED_TO"),
                    description=rel.get("description"),
                    doc_id=uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id,
                ))
                rel_count += 1

        await db.commit()

        # Embed entities into Qdrant for similarity-based graph traversal
        await self._embed_entities(
            project_name=project_name,
            entities=extracted["entities"],
            entity_name_to_id=entity_name_to_id,
        )

        logger.info(
            "kg_extraction_done",
            doc_id=doc_id,
            entities=len(extracted["entities"]),
            relationships=rel_count,
        )
        return {"entities": len(extracted["entities"]), "relationships": rel_count}

    async def _extract(self, chunk_text: str) -> dict:
        """Use LLM to extract entities and relationships from text."""
        prompt = _EXTRACTION_PROMPT.format(chunk_text=chunk_text[:3000])
        try:
            from app.core.resilience import run_in_thread
            response = await run_in_thread(self._llm.generate_content, prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            return result
        except Exception as e:
            logger.warning("kg_extraction_failed", error=str(e))
            return {"entities": [], "relationships": []}

    async def _upsert_entity(
        self,
        db: AsyncSession,
        project_name: str,
        name: str,
        entity_type: str,
        description: str | None,
        doc_id: str,
        sdlc_phase: str | None,
    ) -> uuid.UUID:
        """Insert or update entity — increment mention_count if exists."""
        result = await db.execute(
            select(Entity).where(
                and_(
                    Entity.project_name == project_name,
                    func.lower(Entity.name) == name.lower(),
                    Entity.entity_type == entity_type,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.mention_count = (existing.mention_count or 1) + 1
            if description and not existing.description:
                existing.description = description
            await db.flush()
            return existing.id

        entity = Entity(
            project_name=project_name,
            name=name,
            entity_type=entity_type,
            description=description,
            doc_id=uuid.UUID(doc_id) if isinstance(doc_id, str) else doc_id,
            sdlc_phase=sdlc_phase,
        )
        db.add(entity)
        await db.flush()
        return entity.id

    async def _embed_entities(
        self,
        project_name: str,
        entities: list[dict],
        entity_name_to_id: dict[str, uuid.UUID],
    ) -> None:
        """Embed entity descriptions into Qdrant for graph-like similarity search."""
        store = QdrantStore()
        from qdrant_client.models import (
            PointStruct, VectorParams, Distance,
            HnswConfigDiff,
        )

        # Ensure entity collection exists
        try:
            existing = [c.name for c in (await store._client.get_collections()).collections]
            if ENTITY_COLLECTION not in existing:
                await store._client.create_collection(
                    collection_name=ENTITY_COLLECTION,
                    vectors_config=VectorParams(
                        size=settings.QDRANT_VECTOR_SIZE,
                        distance=Distance.COSINE,
                    ),
                    hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
                )
        except Exception as e:
            logger.warning("kg_collection_create_failed", error=str(e))
            return

        texts = [
            f"{ent['name']}: {ent.get('type', '')} - {ent.get('description', ent['name'])}"
            for ent in entities
        ]
        try:
            from app.core.resilience import run_in_thread
            embeddings = await run_in_thread(self._embedder._model.get_embeddings, texts)
            points = [
                PointStruct(
                    id=str(entity_name_to_id[ent["name"]]),
                    vector=emb.values,
                    payload={
                        "name": ent["name"],
                        "entity_type": ent.get("type", ""),
                        "description": ent.get("description", ""),
                        "project_name": project_name,
                    },
                )
                for ent, emb in zip(entities, embeddings)
                if ent["name"] in entity_name_to_id
            ]
            if points:
                await store._client.upsert(collection_name=ENTITY_COLLECTION, points=points)
        except Exception as e:
            logger.warning("kg_entity_embed_failed", error=str(e))


class KnowledgeGraphQuerier:
    """
    Query the knowledge graph to enrich RAG retrieval.
    Finds related entities and their relationships to provide
    graph-aware context alongside vector search results.
    """

    def __init__(self):
        self._embedder = Embedder()
        self._store = QdrantStore()

    async def find_related_context(
        self,
        db: AsyncSession,
        query: str,
        project_name: str,
        top_k: int = 5,
    ) -> dict:
        """
        Find entities related to the query and their relationships.
        Returns structured context to inject into the RAG prompt.
        """
        # 1. Embed query and search entity collection
        try:
            query_vector = await self._embedder.embed_query(query)
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results = await self._store._client.query_points(
                collection_name=ENTITY_COLLECTION,
                query=query_vector,
                limit=top_k,
                query_filter=Filter(must=[
                    FieldCondition(key="project_name", match=MatchValue(value=project_name))
                ]),
                with_payload=True,
            )
        except Exception:
            return {"entities": [], "relationships": [], "context": ""}

        if not results.points:
            return {"entities": [], "relationships": [], "context": ""}

        entity_ids = [uuid.UUID(str(p.id)) for p in results.points]
        entity_names = [p.payload.get("name", "") for p in results.points]

        # 2. Fetch relationships for these entities from Postgres
        from sqlalchemy import or_
        rel_result = await db.execute(
            select(Relationship).where(
                Relationship.project_name == project_name,
                or_(
                    Relationship.source_entity_id.in_(entity_ids),
                    Relationship.target_entity_id.in_(entity_ids),
                )
            ).limit(20)
        )
        relationships = rel_result.scalars().all()

        # 3. Fetch the entity names for relationship endpoints
        all_entity_ids = set(entity_ids)
        for rel in relationships:
            all_entity_ids.add(rel.source_entity_id)
            all_entity_ids.add(rel.target_entity_id)

        ent_result = await db.execute(
            select(Entity).where(Entity.id.in_(list(all_entity_ids)))
        )
        id_to_entity = {e.id: e for e in ent_result.scalars().all()}

        # 4. Build context string
        lines = ["Knowledge Graph Context:"]
        for ent_id in entity_ids:
            ent = id_to_entity.get(ent_id)
            if ent:
                lines.append(f"- Entity: {ent.name} ({ent.entity_type}): {ent.description or ''}")

        for rel in relationships:
            src = id_to_entity.get(rel.source_entity_id)
            tgt = id_to_entity.get(rel.target_entity_id)
            if src and tgt:
                lines.append(f"- {src.name} --[{rel.relation_type}]--> {tgt.name}")

        context = "\n".join(lines) if len(lines) > 1 else ""

        return {
            "entities": entity_names,
            "relationships": [
                {
                    "source": id_to_entity[r.source_entity_id].name if r.source_entity_id in id_to_entity else "",
                    "target": id_to_entity[r.target_entity_id].name if r.target_entity_id in id_to_entity else "",
                    "type": r.relation_type,
                }
                for r in relationships
            ],
            "context": context,
        }
