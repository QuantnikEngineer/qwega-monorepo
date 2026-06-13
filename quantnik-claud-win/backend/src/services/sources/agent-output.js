// Agent output source — pulls assistant messages from the project's chat
// history. Useful for letting the RAG agent reference prior runs, BRDs,
// reports, and any structured artifacts the agent has emitted in chat.
//
// Filters: only role='assistant', only payload types in TEXT_TYPES (skips
// tool_use / tool_result / ephemeral stream events which would balloon the
// chunk count). Optional `sinceMessageId` config so re-ingest is incremental.

import { db } from '../../db.js';

const TEXT_TYPES = new Set(['assistant_text', 'result']);

export async function fetchDocuments(source, project) {
  if (!project) throw new Error('agent_output source requires a project');
  const cfg = JSON.parse(source.config || '{}');
  const sinceId = cfg.sinceMessageId || 0;

  const rows = db.prepare(`
    SELECT id, payload, created_at
    FROM messages
    WHERE project_id = ? AND id > ? AND role = 'assistant'
    ORDER BY id ASC
  `).all(project.id, sinceId);

  // Concatenate consecutive assistant_text events into a single "turn" doc so
  // we don't fragment a long answer across hundreds of tiny chunks.
  const turns = [];
  let bucket = [];
  let bucketStart = null;

  function flushBucket() {
    if (!bucket.length) return;
    turns.push({
      title:       `Turn ${bucketStart} — ${bucket.length} fragments`,
      uri:         `quantnik://project/${project.id}/messages/${bucketStart}`,
      external_id: `msg-${bucketStart}`,
      content:     bucket.join('\n\n'),
    });
    bucket = [];
    bucketStart = null;
  }

  for (const r of rows) {
    let p;
    try { p = JSON.parse(r.payload); } catch { continue; }
    if (!TEXT_TYPES.has(p.type)) {
      flushBucket();
      continue;
    }
    if (p.type === 'assistant_text' && p.text) {
      if (!bucketStart) bucketStart = r.id;
      bucket.push(p.text);
    } else if (p.type === 'result') {
      flushBucket();
    }
  }
  flushBucket();
  return turns;
}
