// One-shot Confluence publish for the sample-legacy-java modernization docs.
//
// Mirrors backend/scripts/publish-modernization-docs.js (the eShopLegacy one)
// but for project 16 (modernization-java). Every page title is prefixed with
// "Java —" so it doesn't collide with the eShopLegacy tree in the same
// wegaclaude space (Confluence enforces per-space title uniqueness; the
// prior run hit this for slice-level page names like "Diff report").
//
// The page tree lives under a single "Java fixture — sample-legacy-java"
// parent so it's clearly separable from the eShopLegacy tree in the
// space navigation.
//
// Label: wega-project-modernization-java (matches project 16's
// atlassian_labels — so /api/atlassian/16/artifacts picks them up).
//
// Run:
//   cd backend
//   node --env-file=.env scripts/publish-java-modernization-docs.js

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

const SPACE_ID   = '127270916';
const SPACE_KEY  = 'wegaclaude';
const LABEL      = 'wega-project-modernization-java';
const REPO_ROOT  = 'C:/tmp/sample-legacy-java/modernization';

// ---- helpers --------------------------------------------------------------

async function atlFetch(p, opts = {}) {
  const res = await fetch(`https://${HOST}${p}`, {
    ...opts,
    headers: {
      Authorization: AUTH,
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
  const txt = await res.text();
  if (!res.ok) throw new Error(`${opts.method || 'GET'} ${p} -> ${res.status} ${res.statusText}: ${txt.slice(0, 400)}`);
  return txt ? JSON.parse(txt) : null;
}

async function readMd(rel) {
  return fs.readFile(path.join(REPO_ROOT, rel), 'utf8');
}

function mdToStorage(md) {
  let html = marked.parse(md, { mangle: false, headerIds: false });
  html = html.replace(/<br>/g, '<br/>').replace(/<hr>/g, '<hr/>');
  return html;
}

async function findExistingByTitle(title) {
  const p = `/wiki/rest/api/content?spaceKey=${encodeURIComponent(SPACE_KEY)}&title=${encodeURIComponent(title)}&type=page&limit=2&expand=version`;
  const data = await atlFetch(p);
  return (data.results && data.results[0]) || null;
}

async function createOrUpdatePage({ title, parentId, body }) {
  const existing = await findExistingByTitle(title);
  if (existing) {
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
  try {
    await atlFetch(`/wiki/rest/api/content/${pageId}/label`, {
      method: 'POST',
      body: JSON.stringify([{ prefix: 'global', name: LABEL }]),
    });
  } catch (e) {
    if (!e.message.includes('400')) console.warn(`  label warn (${pageId}): ${e.message.slice(0, 120)}`);
  }
}

// ---- page tree (every title prefixed "Java —" to avoid eShopLegacy collisions) -----------

const TREE = {
  title: 'Java fixture — sample-legacy-java',
  body: `<p>End-to-end modernization run on the Java fixture at <code>C:\\tmp\\sample-legacy-java</code> — a 4-class Maven multi-module app on Java 1.8 with log4j 1.x / commons-lang 2 / gson 2.2.4, ported to Java 21 + SLF4J + Logback + commons-lang3 + gson 2.11. Status: <strong>all slices live · 0 unintentional diffs · 8/8 characterization tests green on both legacy and modern</strong>. Every page in this tree carries label <strong>${LABEL}</strong> so the wega2 dashboard for project 16 surfaces them automatically.</p>`,
  children: [
    { title: 'Java — Plan',                                       file: 'plan.md' },
    { title: 'Java — Slice backlog',                              file: 'SLICES.md' },
    { title: 'Java — Capstone architecture',                      file: 'capstone-architecture.md' },
    {
      title: 'Java — Phase 1: Understanding',
      body: '<p>Output of Phase 1 (Discovery & Understanding) for the Java fixture. 6 docs covering the three subsystems (greeter, person-repository, console-host) plus a dependency map and seams analysis.</p>',
      children: [
        { title: 'Java — Phase 1 Index',                          file: 'understanding/README.md' },
        { title: 'Java — Dependency map',                         file: 'understanding/dependency-map.md' },
        { title: 'Java — Seams',                                  file: 'understanding/seams.md' },
        { title: 'Java — Greeter',                                file: 'understanding/greeter.md' },
        { title: 'Java — PersonRepository',                       file: 'understanding/person-repository.md' },
        { title: 'Java — Console host',                           file: 'understanding/console-host.md' },
      ],
    },
    {
      title: 'Java — Decisions (ADRs)',
      body: '<p>Captured architecture decisions for the Java fixture modernization run.</p>',
      children: [
        { title: 'Java — ADR-0001: Characterization tooling',     file: 'decisions/0001-characterization-tooling-java.md' },
      ],
    },
    {
      title: 'Java — Phase 3: Safety net',
      body: '<p>JUnit 5 + AssertJ + ApprovalTests safety-net suite. 8 tests, green against both legacy and modern code.</p>',
      children: [
        { title: 'Java — Test plan',                              file: 'tests/test-plan.md' },
      ],
    },
    {
      title: 'Java — Slices S1+S2 (live)',
      body: '<p>Combined library-port + app-port slice. Both run as one cutover because the app-port had no behavioural change beyond the library\\u2019s record-Person constructor call.</p>',
      children: [
        { title: 'Java — S1+S2 Diff report',                      file: 'slices/S1-library-port/diff-report.md' },
      ],
    },
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
  for (const child of (node.children || [])) await publishNode(child, result.id);
  return result.id;
}

console.log(`Publishing Java modernization docs to ${HOST}/wiki space=${SPACE_KEY}, label=${LABEL}`);
console.log(`Source: ${REPO_ROOT}\n`);

await publishNode(TREE, null);

console.log(`\nResult — created: ${summary.created}  updated: ${summary.updated}  failed: ${summary.failed}`);
if (summary.urls.length) {
  console.log('\nRoot page URL:');
  console.log('  ' + summary.urls[0].url);
}
