// Document source — reads a file from the project's uploads/ folder (or an
// absolute path) and yields { title, content } for the ingestor to chunk.
// Supports .txt / .md / .json / .csv natively; .pdf via pdf-parse; everything
// else as best-effort utf-8 read.

import fs from 'node:fs';
import path from 'node:path';
import { resolveProjectPath } from '../../config.js';

export async function fetchDocuments(source, project) {
  const cfg = JSON.parse(source.config || '{}');
  const rel = cfg.path; // relative-to-project or absolute
  if (!rel) throw new Error('document source missing config.path');

  let absPath = rel;
  if (!path.isAbsolute(rel) && project) {
    absPath = path.join(resolveProjectPath(project), rel);
  }
  if (!fs.existsSync(absPath)) {
    throw new Error(`document not found: ${absPath}`);
  }

  const ext = path.extname(absPath).toLowerCase();
  let content = '';

  if (ext === '.pdf') {
    const { PDFParse } = await import('pdf-parse');
    const buf = fs.readFileSync(absPath);
    const r = await new PDFParse({ data: buf }).getText();
    content = r.text || '';
  } else {
    content = fs.readFileSync(absPath, 'utf8');
  }

  return [{
    title:       cfg.title || path.basename(absPath).replace(/^\d+-/, ''),
    uri:         absPath,
    external_id: rel,
    content,
  }];
}
