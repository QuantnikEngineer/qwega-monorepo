import { Router } from 'express';
import { db } from '../db.js';

export const sessionInfo = Router();

sessionInfo.get('/:projectId/last-init', (req, res) => {
  const row = db
    .prepare(
      `SELECT payload FROM messages
       WHERE project_id = ? AND payload LIKE '%"type":"session"%'
       ORDER BY id DESC LIMIT 1`
    )
    .get(req.params.projectId);
  if (!row) return res.json(null);
  try { res.json(JSON.parse(row.payload)); }
  catch { res.json(null); }
});
