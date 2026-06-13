// Retrieval — embed a query, fetch all chunks in the requested scope, score
// in-memory by cosine similarity, return top-K with their source metadata.
//
// In-memory cosine is good up to ~50K chunks (under 200 ms at 10K, ~1 s at
// 50K on a modern laptop). When corpora grow past that, swap this single
// function for an sqlite-vec MATCH or an Aurora pgvector `<=>` lookup — the
// rest of the pipeline stays identical.

import { db } from '../db.js';
import { embedText, blobToFloats, cosineSim } from './embedding.js';

/**
 * Find the K chunks most relevant to `query` within `scope`.
 *
 * scope:
 *   { kind: 'org' }                     → only org-scoped sources
 *   { kind: 'project', projectId: 14 }  → org sources + this project's sources
 *
 * Returns: [{
 *   chunkId, content, score,
 *   document: { id, title, uri, externalId },
 *   source:   { id, type, label, scope, projectId },
 * }]
 */
export async function retrieve(query, scope, { topK = 10 } = {}) {
  if (!query || !query.trim()) return { results: [], queryTokens: 0 };

  const { embedding: q, tokens: queryTokens } = await embedText(query);

  // Pull every (chunk, document, source) in scope. Filter to ready sources.
  let rows;
  if (scope.kind === 'org') {
    rows = db.prepare(`
      SELECT
        ch.id            AS chunk_id,
        ch.content       AS chunk_content,
        ch.embedding     AS chunk_embedding,
        d.id             AS document_id,
        d.title          AS document_title,
        d.uri            AS document_uri,
        d.external_id    AS document_external_id,
        s.id             AS source_id,
        s.type           AS source_type,
        s.label          AS source_label,
        s.scope          AS source_scope,
        s.project_id     AS source_project_id
      FROM context_chunks ch
      JOIN context_documents d ON d.id = ch.document_id
      JOIN context_sources s   ON s.id = d.source_id
      WHERE s.status = 'ready' AND s.scope = 'org'
    `).all();
  } else if (scope.kind === 'project') {
    rows = db.prepare(`
      SELECT
        ch.id            AS chunk_id,
        ch.content       AS chunk_content,
        ch.embedding     AS chunk_embedding,
        d.id             AS document_id,
        d.title          AS document_title,
        d.uri            AS document_uri,
        d.external_id    AS document_external_id,
        s.id             AS source_id,
        s.type           AS source_type,
        s.label          AS source_label,
        s.scope          AS source_scope,
        s.project_id     AS source_project_id
      FROM context_chunks ch
      JOIN context_documents d ON d.id = ch.document_id
      JOIN context_sources s   ON s.id = d.source_id
      WHERE s.status = 'ready'
        AND (s.scope = 'org' OR (s.scope = 'project' AND s.project_id = ?))
    `).all(scope.projectId);
  } else {
    throw new Error(`unknown scope.kind: ${scope.kind}`);
  }

  if (!rows.length) return { results: [], queryTokens };

  const scored = rows.map((r) => {
    const emb = blobToFloats(r.chunk_embedding);
    return {
      chunkId:  r.chunk_id,
      content:  r.chunk_content,
      score:    cosineSim(q, emb),
      document: {
        id:         r.document_id,
        title:      r.document_title,
        uri:        r.document_uri,
        externalId: r.document_external_id,
      },
      source:   {
        id:        r.source_id,
        type:      r.source_type,
        label:     r.source_label,
        scope:     r.source_scope,
        projectId: r.source_project_id,
      },
    };
  });

  scored.sort((a, b) => b.score - a.score);
  return { results: scored.slice(0, topK), queryTokens, candidateCount: rows.length };
}
