import { Router } from 'express';
import { db } from '../db.js';

export const phases = Router();

const VALID_STATUSES = new Set(['pending', 'running', 'done', 'skipped', 'failed']);

const CANONICAL_NAMES = {
  1: 'BRD', 2: 'User Stories', 3: 'Feature Dev', 4: 'Vulnerability',
  5: 'Tech Debt', 6: 'Test Cases', 7: 'Test Scripts', 8: 'Boot',
  9: 'Test Execution', 10: 'Deployment', 11: 'Sanity Checks',
};

function projectOr404(id, res) {
  const p = db.prepare('SELECT * FROM projects WHERE id = ?').get(id);
  if (!p) { res.status(404).json({ error: 'project not found' }); return null; }
  return p;
}

// GET — read the full phase map for a project. Returns 11 rows, filling in
// any missing phases as 'pending' with their canonical name. Always-present
// shape makes the frontend renderer trivial.
phases.get('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const rows = db.prepare(
    `SELECT phase_number, name, status, note, started_at, updated_at
     FROM project_phases WHERE project_id = ? ORDER BY phase_number ASC`
  ).all(project.id);
  const byNumber = new Map(rows.map((r) => [r.phase_number, r]));
  const phasesOut = [];
  for (let n = 1; n <= 11; n++) {
    const row = byNumber.get(n);
    phasesOut.push({
      number: n,
      name: (row && row.name) || CANONICAL_NAMES[n],
      status: (row && row.status) || 'pending',
      note: row?.note || null,
      started_at: row?.started_at || null,
      updated_at: row?.updated_at || null,
    });
  }
  res.json({ phases: phasesOut, anyTracked: rows.length > 0 });
});

// POST — upsert a single phase transition. Body: { phase, status, name?, note? }.
// Called by the orchestrator skill at every transition (start = running,
// end = done|skipped|failed). Sequential-ordering rule applies on the
// server side too: if Phase N goes to running/done, any earlier phase
// still pending/running is promoted to done (mirrors the client inference
// but is now persisted, so re-renders are consistent).
phases.post('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const { phase, status, name, note } = req.body || {};
  const phaseNum = Number(phase);
  if (!Number.isInteger(phaseNum) || phaseNum < 1 || phaseNum > 11) {
    return res.status(400).json({ error: 'phase must be an integer 1-11' });
  }
  if (!VALID_STATUSES.has(status)) {
    return res.status(400).json({ error: `status must be one of: ${[...VALID_STATUSES].join(', ')}` });
  }
  const now = Math.floor(Date.now() / 1000);
  const startedAt = (status === 'running') ? now : null;
  const canonicalName = name || CANONICAL_NAMES[phaseNum];

  db.prepare(
    `INSERT INTO project_phases (project_id, phase_number, name, status, note, started_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(project_id, phase_number) DO UPDATE SET
       name = excluded.name,
       status = excluded.status,
       note = COALESCE(excluded.note, project_phases.note),
       started_at = COALESCE(excluded.started_at, project_phases.started_at),
       updated_at = excluded.updated_at`
  ).run(project.id, phaseNum, canonicalName, status, note || null, startedAt, now);

  // Sequential-ordering inference, persisted. If we just set phase N to
  // running/done, every earlier phase must be done (they ran in order).
  // Insert a 'done' row for each missing earlier phase (so the promotion
  // is visible on read), and promote any existing pending/running row.
  // Doesn't overwrite skipped/failed — those are explicit user/agent calls.
  if (status === 'running' || status === 'done') {
    const upsertEarlier = db.prepare(
      `INSERT INTO project_phases (project_id, phase_number, name, status, started_at, updated_at)
       VALUES (?, ?, ?, 'done', NULL, ?)
       ON CONFLICT(project_id, phase_number) DO UPDATE SET
         status = CASE
           WHEN project_phases.status IN ('skipped', 'failed') THEN project_phases.status
           ELSE 'done'
         END,
         updated_at = excluded.updated_at`
    );
    for (let m = 1; m < phaseNum; m++) {
      upsertEarlier.run(project.id, m, CANONICAL_NAMES[m], now);
    }
  }

  // Return the full updated map so the caller can render the new state.
  const rows = db.prepare(
    `SELECT phase_number, name, status, note, started_at, updated_at
     FROM project_phases WHERE project_id = ? ORDER BY phase_number ASC`
  ).all(project.id);
  res.json({ ok: true, phases: rows });
});

// DELETE — wipe the phase map for a project. Called at the start of a new
// orchestrator run so the panel reflects the new pipeline, not the prior one.
phases.delete('/:projectId', (req, res) => {
  const project = projectOr404(req.params.projectId, res);
  if (!project) return;
  const result = db.prepare(`DELETE FROM project_phases WHERE project_id = ?`).run(project.id);
  res.json({ ok: true, cleared: result.changes });
});
