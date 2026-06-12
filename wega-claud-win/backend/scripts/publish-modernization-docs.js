// One-shot Confluence publish of the eShopLegacy modernization docs that
// landed on disk during the code-modernizer run. Recreates the same tree
// structure (Plan + Slices + Phase-1 Understanding + ADRs + Safety net +
// per-slice docs + Capstone) inside Confluence space `wegaclaude`,
// applying label `wega-project-modernization` to every page so the wega2
// dashboard's Atlassian-artifacts panel picks them up.
//
// Run with:
//   cd backend
//   node --env-file=.env scripts/publish-modernization-docs.js
//
// Idempotent-ish: if a page with the same title already exists under the
// same parent it gets UPDATED (version bumped) rather than creating a
// duplicate. Run again to refresh after edits.

import fs from 'node:fs/promises';
import path from 'node:path';
import { marked } from 'marked';

const SITE  = process.env.MCP_ATLASSIAN_SITE_NAME;
const EMAIL = process.env.MCP_ATLASSIAN_EMAIL;
const TOKEN = process.env.MCP_ATLASSIAN_TOKEN;
if (!SITE || !EMAIL || !TOKEN) {
  console.error('Missing MCP_ATLASSIAN_{SITE_NAME,EMAIL,TOKEN} in env');
  process.exit(1);
}
const HOST  = `${SITE}.atlassian.net`;
const AUTH  = 'Basic ' + Buffer.from(`${EMAIL}:${TOKEN}`).toString('base64');

const SPACE_ID   = '127270916';        // wegaclaude (from /api/atlassian/15/artifacts)
const SPACE_KEY  = 'wegaclaude';
const LABEL      = 'wega-project-modernization';
const REPO_ROOT  = 'C:/wega-claude/backend/data/projects/modernization/repos/legacy-app/modernization';

// ---- helpers --------------------------------------------------------------

async function atlFetch(path, opts = {}) {
  const res = await fetch(`https://${HOST}${path}`, {
    ...opts,
    headers: {
      Authorization: AUTH,
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
  const txt = await res.text();
  if (!res.ok) {
    throw new Error(`${opts.method || 'GET'} ${path} -> ${res.status} ${res.statusText}: ${txt.slice(0, 400)}`);
  }
  return txt ? JSON.parse(txt) : null;
}

async function readMd(rel) {
  return fs.readFile(path.join(REPO_ROOT, rel), 'utf8');
}

// Convert markdown to Confluence storage HTML. marked's default output is
// almost-valid storage; the only known incompatibility is bare `<br>` /
// `<hr>` (must be self-closing). We post-process for that.
function mdToStorage(md) {
  let html = marked.parse(md, { mangle: false, headerIds: false });
  html = html.replace(/<br>/g, '<br/>').replace(/<hr>/g, '<hr/>');
  return html;
}

// Look up an existing page by EXACT title across the whole space. Confluence
// enforces title uniqueness per space (not per parent), so this is the only
// reliable way to know if a re-run should UPDATE vs error on POST.
async function findExistingByTitle(title) {
  const path = `/wiki/rest/api/content?spaceKey=${encodeURIComponent(SPACE_KEY)}&title=${encodeURIComponent(title)}&type=page&limit=2&expand=version`;
  const data = await atlFetch(path);
  return (data.results && data.results[0]) || null;
}

async function createOrUpdatePage({ title, parentId, body }) {
  const existing = await findExistingByTitle(title);
  if (existing) {
    // Need the current version to PUT an update.
    const cur = await atlFetch(`/wiki/api/v2/pages/${existing.id}?body-format=storage`);
    const updated = await atlFetch(`/wiki/api/v2/pages/${existing.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        id: existing.id,
        status: 'current',
        title,
        parentId,
        spaceId: SPACE_ID,
        body: { representation: 'storage', value: body },
        version: { number: (cur.version?.number || 1) + 1 },
      }),
    });
    return { id: updated.id, action: 'updated', webui: updated._links?.webui };
  }
  const created = await atlFetch('/wiki/api/v2/pages', {
    method: 'POST',
    body: JSON.stringify({
      spaceId: SPACE_ID,
      status: 'current',
      title,
      parentId: parentId || undefined,
      body: { representation: 'storage', value: body },
    }),
  });
  return { id: created.id, action: 'created', webui: created._links?.webui };
}

async function ensureLabel(pageId) {
  // v1 endpoint — v2 hasn't shipped labels in writable form yet.
  try {
    await atlFetch(`/wiki/rest/api/content/${pageId}/label`, {
      method: 'POST',
      body: JSON.stringify([{ prefix: 'global', name: LABEL }]),
    });
  } catch (e) {
    if (!e.message.includes('400')) console.warn(`  label warn (${pageId}): ${e.message.slice(0, 120)}`);
  }
}

// ---- page tree ------------------------------------------------------------

// Source-of-truth tree. Each entry creates one page. Children inherit
// parentId. file=null means a section parent with no source markdown —
// uses the inline `body` instead.
const TREE = {
  title: 'eShopLegacy — Modernization',
  body: `<p>End-to-end modernization run of the eShopLegacy fixture from .NET Framework 4.7.2 MVC to .NET 8. This space holds every artifact the modernization produced: the plan, the slice backlog, per-phase docs, per-slice diff reports + tech/business docs, ADRs, and the capstone architecture. All pages carry label <strong>${LABEL}</strong> so the wega2 dashboard for project 15 surfaces them automatically.</p><p>Sections below — start with <strong>Plan</strong> and <strong>Capstone architecture</strong> for the executive picture.</p>`,
  children: [
    { title: 'Plan',                  file: 'plan.md' },
    { title: 'Slice backlog',         file: 'SLICES.md' },
    { title: 'Capstone architecture', file: 'capstone-architecture.md' },
    {
      title: 'Phase 1 — Understanding',
      body: '<p>Output of Phase 1 (Discovery & Understanding). 15 docs covering the legacy eShopLegacyMVC subsystems, plus a dependency map and seams analysis. Child pages are listed below in the canonical order.</p>',
      children: [
        { title: 'Index',                                  file: 'understanding/README.md' },
        { title: 'Dependency map',                         file: 'understanding/dependency-map.md' },
        { title: 'Seams',                                  file: 'understanding/seams.md' },
        { title: '00 — System overview',                   file: 'understanding/00-system-overview.md' },
        { title: '01 — Web MVC: Catalog',                  file: 'understanding/01-web-mvc-catalog.md' },
        { title: '02 — Pic Controller',                    file: 'understanding/02-pic-controller.md' },
        { title: '03 — Web API controllers',               file: 'understanding/03-web-api-controllers.md' },
        { title: '04 — Domain model',                      file: 'understanding/04-domain-model.md' },
        { title: '05 — Persistence (EF6)',                 file: 'understanding/05-persistence-ef6.md' },
        { title: '06 — DI and bootstrap',                  file: 'understanding/06-di-and-bootstrap.md' },
        { title: '07 — Shared kernel (net8)',              file: 'understanding/07-shared-kernel-net8.md' },
        { title: '08 — Utilities (Serializing)',           file: 'understanding/08-utilities-serializing.md' },
        { title: '09 — eShopPorted status',                file: 'understanding/09-eshop-ported-status.md' },
        { title: '10 — Logging + telemetry',               file: 'understanding/10-logging-telemetry.md' },
        { title: '11 — Views and static assets',           file: 'understanding/11-views-and-static-assets.md' },
      ],
    },
    {
      title: 'Decisions (ADRs)',
      body: '<p>Captured architecture decisions for the modernization run.</p>',
      children: [
        { title: 'ADR-0001 — Characterization tooling',    file: 'decisions/0001-characterization-tooling.md' },
        { title: 'ADR-0002 — Routing facade (YARP)',       file: 'decisions/0002-routing-facade-yarp.md' },
      ],
    },
    {
      title: 'Phase 3 — Safety net',
      body: '<p>Characterization test scaffolding + operator runbook for the safety net.</p>',
      children: [
        { title: 'Operator runbook',                       file: 'tests/README.md' },
        { title: 'Test plan',                              file: 'tests/test-plan.md' },
      ],
    },
    {
      title: 'Slice S1 — static-assets (live)',
      body: '<p>Pilot slice. Strangler facade stand-up + 82 static files migrated to a modern .NET 8 endpoint. Diff report + 7 technical docs + 3 business docs.</p>',
      children: [
        { title: 'Diff report',                            file: 'slices/S1-static-assets/diff-report.md' },
        { title: 'Architecture',                           file: 'slices/S1-static-assets/docs/technical/architecture.md' },
        { title: 'API contracts',                          file: 'slices/S1-static-assets/docs/technical/api-contracts.md' },
        { title: 'Configuration',                          file: 'slices/S1-static-assets/docs/technical/configuration.md' },
        { title: 'Data model',                             file: 'slices/S1-static-assets/docs/technical/data-model.md' },
        { title: 'Integrations',                           file: 'slices/S1-static-assets/docs/technical/integrations.md' },
        { title: 'Runbook',                                file: 'slices/S1-static-assets/docs/technical/runbook.md' },
        { title: 'Test inventory',                         file: 'slices/S1-static-assets/docs/technical/test-inventory.md' },
        { title: 'Release notes',                          file: 'slices/S1-static-assets/docs/business/release-notes.md' },
        { title: 'Support guide',                          file: 'slices/S1-static-assets/docs/business/support-guide.md' },
        { title: 'Stakeholder summary',                    file: 'slices/S1-static-assets/docs/business/stakeholder-summary.md' },
      ],
    },
    {
      title: 'Slice S2 — pic-serving (live)',
      body: '<p>Picture-serving endpoint with path-traversal guard (intentional-divergence). 13 files migrated. Same shape as S1. Titles prefixed with <code>S2 · </code> because Confluence enforces globally-unique page titles per space and S1 already owns the un-prefixed forms.</p>',
      children: [
        { title: 'S2 · Diff report',                       file: 'slices/S2-pic-serving/diff-report.md' },
        { title: 'S2 · Architecture',                      file: 'slices/S2-pic-serving/docs/technical/architecture.md' },
        { title: 'S2 · API contracts',                     file: 'slices/S2-pic-serving/docs/technical/api-contracts.md' },
        { title: 'S2 · Configuration',                     file: 'slices/S2-pic-serving/docs/technical/configuration.md' },
        { title: 'S2 · Data model',                        file: 'slices/S2-pic-serving/docs/technical/data-model.md' },
        { title: 'S2 · Integrations',                      file: 'slices/S2-pic-serving/docs/technical/integrations.md' },
        { title: 'S2 · Runbook',                           file: 'slices/S2-pic-serving/docs/technical/runbook.md' },
        { title: 'S2 · Test inventory',                    file: 'slices/S2-pic-serving/docs/technical/test-inventory.md' },
        { title: 'S2 · Release notes',                     file: 'slices/S2-pic-serving/docs/business/release-notes.md' },
        { title: 'S2 · Support guide',                     file: 'slices/S2-pic-serving/docs/business/support-guide.md' },
        { title: 'S2 · Stakeholder summary',               file: 'slices/S2-pic-serving/docs/business/stakeholder-summary.md' },
      ],
    },
    {
      title: 'Slice S3+S10 — Web API brands + Hello World stub (live)',
      body: '<p>Read-only Web API surface + the tiny <code>/api</code> stub. Compact-doc format (1 technical + 1 business overview).</p>',
      children: [
        { title: 'S3 · Diff report',                       file: 'slices/S3-api-brands/diff-report.md' },
        { title: 'Technical overview',                     file: 'slices/S3-api-brands/docs/technical/overview.md' },
        { title: 'Business overview',                      file: 'slices/S3-api-brands/docs/business/overview.md' },
      ],
    },
    { title: 'Pending operator runbook',                   file: 'slices/PENDING-OPERATOR-RUNBOOK.md' },
  ],
};

// ---- walker ---------------------------------------------------------------

const summary = { created: 0, updated: 0, failed: 0, urls: [] };

async function publishNode(node, parentId) {
  let body;
  if (node.file) {
    try { body = mdToStorage(await readMd(node.file)); }
    catch (e) {
      console.error(`  READ FAILED for ${node.file}: ${e.message}`);
      summary.failed++;
      return null;
    }
  } else {
    body = node.body || '';
  }

  let result;
  try {
    result = await createOrUpdatePage({ title: node.title, parentId, body });
  } catch (e) {
    console.error(`  PUBLISH FAILED for "${node.title}": ${e.message}`);
    summary.failed++;
    return null;
  }
  await ensureLabel(result.id);
  summary[result.action]++;
  const url = result.webui ? `https://${HOST}/wiki${result.webui}` : `https://${HOST}/wiki/pages/${result.id}`;
  summary.urls.push({ title: node.title, url, action: result.action });
  console.log(`  ${result.action.padEnd(7)} ${node.title}`);

  for (const child of (node.children || [])) {
    await publishNode(child, result.id);
  }
  return result.id;
}

console.log(`Publishing modernization docs to ${HOST}/wiki space=${SPACE_KEY}, label=${LABEL}`);
console.log(`Source: ${REPO_ROOT}\n`);

await publishNode(TREE, null);

console.log(`\nResult — created: ${summary.created}  updated: ${summary.updated}  failed: ${summary.failed}`);
if (summary.urls.length) {
  console.log('\nFirst 5 URLs:');
  for (const u of summary.urls.slice(0, 5)) console.log(`  ${u.url}`);
}
