// Ingest orchestrator — owns the source → documents → chunks → embeddings →
// DB-write pipeline. Each source-type module exports `fetchDocuments` which
// returns an array of { title, uri, external_id, content } strings; the
// orchestrator chunks each one, embeds the chunks (batched), and persists.
//
// Idempotent: on re-ingest of a source we drop all its previously-stored
// documents and re-create them. Diff-based incremental ingest is a follow-up
// once corpora actually get big.

import crypto from 'node:crypto';
import { db } from '../db.js';
import { chunk } from './chunker.js';
import { embedBatch, floatsToBlob, EMBEDDING_MODEL } from './embedding.js';

import * as documentSource    from './sources/document.js';
import * as websiteSource     from './sources/website.js';
import * as repoSource        from './sources/repo.js';
import * as agentOutputSource from './sources/agent-output.js';
import * as confluenceSource  from './sources/confluence.js';
import * as sharepointSource  from './sources/sharepoint.js';

const FETCHERS = {
  document:     documentSource.fetchDocuments,
  website:      websiteSource.fetchDocuments,
  repo:         repoSource.fetchDocuments,
  agent_output: agentOutputSource.fetchDocuments,
  confluence:   confluenceSource.fetchDocuments,
  sharepoint:   sharepointSource.fetchDocuments,
};

function hashContent(s) {
  return crypto.createHash('sha256').update(s).digest('hex').slice(0, 16);
}

function setSourceStatus(sourceId, patch) {
  const fields = Object.keys(patch);
  const sets   = fields.map((f) => `${f} = ?`).join(', ');
  const vals   = fields.map((f) => patch[f]);
  db.prepare(`UPDATE context_sources SET ${sets}, updated_at = strftime('%s','now') WHERE id = ?`)
    .run(...vals, sourceId);
}

/**
 * Run a full ingest cycle for a source. Marks the source row's status
 * through pending → ingesting → ready | failed. Wipes prior documents and
 * chunks for this source before re-ingest.
 *
 * Returns a summary: { documents, chunks, totalTokens, embedTokens, durationMs }.
 */
export async function ingestSource(sourceId) {
  const source = db.prepare('SELECT * FROM context_sources WHERE id = ?').get(sourceId);
  if (!source) throw new Error(`source ${sourceId} not found`);

  const project = source.project_id
    ? db.prepare('SELECT * FROM projects WHERE id = ?').get(source.project_id)
    : null;

  setSourceStatus(sourceId, { status: 'ingesting', error: null });

  const t0 = Date.now();
  let documentCount = 0;
  let chunkCount    = 0;
  let totalTokens   = 0;
  let embedTokens   = 0;

  try {
    const fetcher = FETCHERS[source.type];
    if (!fetcher) throw new Error(`unsupported source type: ${source.type}`);

    const docs = await fetcher(source, project);

    // Wipe prior content for this source — clean re-ingest.
    db.prepare(`DELETE FROM context_documents WHERE source_id = ?`).run(sourceId);

    // Persist each doc's chunks.
    const insertDoc = db.prepare(`
      INSERT INTO context_documents
        (source_id, external_id, title, uri, content_hash, char_count, token_count)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);
    const insertChunk = db.prepare(`
      INSERT INTO context_chunks
        (document_id, chunk_index, content, token_count, start_char, end_char, embedding)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    for (const d of docs) {
      const text = (d.content || '').trim();
      if (!text) continue;
      const chunks = chunk(text);
      if (!chunks.length) continue;

      // Embed all chunks for this doc in a bounded-concurrency batch
      const { results: embeddings, totalTokens: embTok } =
        await embedBatch(chunks.map((c) => c.content));
      embedTokens += embTok;

      const docTokens = chunks.reduce((s, c) => s + c.tokens, 0);
      const r = insertDoc.run(
        sourceId,
        d.external_id || d.uri || d.title || null,
        d.title || null,
        d.uri || null,
        hashContent(text),
        text.length,
        docTokens,
      );
      const documentId = r.lastInsertRowid;
      documentCount++;
      totalTokens += docTokens;

      const tx = db.transaction(() => {
        for (let i = 0; i < chunks.length; i++) {
          const c   = chunks[i];
          const emb = embeddings[i].embedding;
          insertChunk.run(
            documentId, i, c.content, c.tokens, c.start, c.end,
            floatsToBlob(emb),
          );
          chunkCount++;
        }
      });
      tx();
    }

    setSourceStatus(sourceId, {
      status:           'ready',
      error:            null,
      last_ingested_at: Math.floor(Date.now() / 1000),
      document_count:   documentCount,
      chunk_count:      chunkCount,
      total_tokens:     totalTokens,
    });

    return {
      documents:   documentCount,
      chunks:      chunkCount,
      totalTokens,
      embedTokens,
      durationMs:  Date.now() - t0,
      model:       EMBEDDING_MODEL,
    };
  } catch (err) {
    setSourceStatus(sourceId, {
      status: 'failed',
      error:  String(err?.message || err).slice(0, 1000),
    });
    throw err;
  }
}
