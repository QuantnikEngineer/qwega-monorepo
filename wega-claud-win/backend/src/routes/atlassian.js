import { Router } from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { db } from '../db.js';
import { projectForRead, projectForWrite } from './projectAccess.js';

export const atlassian = Router();

// Persist the wega2 project's atlassian + LLM scope into <project>/.claude/wega.json
// so skills running inside the SDK (which can't read wega2.db) have a single
// well-known file to consult for defaults instead of guessing or asking.
export function writeWegaProjectFile(project) {
  try {
    const dir = path.join(project.path, '.claude');
    fs.mkdirSync(dir, { recursive: true });
    let labels = [];
    if (project.atlassian_labels) {
      try { labels = JSON.parse(project.atlassian_labels) || []; } catch {}
    }
    const body = {
      generatedBy: 'wega2',
      generatedAt: new Date().toISOString(),
      project: { id: project.id, name: project.name, path: project.path },
      atlassian: {
        siteName: process.env.MCP_ATLASSIAN_SITE_NAME || null,
        siteUrl: process.env.MCP_ATLASSIAN_SITE_NAME
          ? `https://${process.env.MCP_ATLASSIAN_SITE_NAME}.atlassian.net`
          : null,
        jiraProjectKey: project.jira_project_key || null,
        confluenceSpaceId: project.confluence_space_id || null,
        confluenceSpaceKey: project.confluence_space_key || null,
        labels,
      },
      llm: {
        provider: project.llm_provider || 'anthropic',
        model: project.llm_model || null,
      },
    };
    fs.writeFileSync(path.join(dir, 'wega.json'), JSON.stringify(body, null, 2));
  } catch (e) {
    // Non-fatal — wega2 still works without the sidecar file; skills just
    // fall back to asking the user.
    console.error('[wega.json] write failed for project', project?.id, e?.message);
  }
}

function atlassianCreds() {
  const site = process.env.MCP_ATLASSIAN_SITE_NAME;
  const email = process.env.MCP_ATLASSIAN_EMAIL;
  const token = process.env.MCP_ATLASSIAN_TOKEN;
  if (!site || !email || !token) return null;
  const auth = 'Basic ' + Buffer.from(`${email}:${token}`).toString('base64');
  return { site, email, token, auth };
}

async function atlGet(creds, host, path, timeoutMs = 15_000) {
  const url = `https://${host}${path}`;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      headers: { Authorization: creds.auth, Accept: 'application/json' },
      signal: ctrl.signal,
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`${res.status} ${res.statusText} on ${path}${text ? ': ' + text.slice(0, 200) : ''}`);
    }
    return await res.json();
  } catch (err) {
    if (err.name === 'AbortError') throw new Error(`atlassian fetch timed out after ${timeoutMs}ms on ${path}`);
    throw err;
  } finally {
    clearTimeout(t);
  }
}

// PUT /api/atlassian/:projectId/config — set the per-project Jira key + Confluence space.
atlassian.put('/:projectId/config', (req, res) => {
  const project = projectForWrite(req.params.projectId, req, res);
  if (!project) return;
  const {
    jiraProjectKey,
    confluenceSpaceId,
    confluenceSpaceKey,
    labels,
  } = req.body || {};

  const norm = (v) => (typeof v === 'string' && v.trim() ? v.trim() : null);

  db.prepare(`
    UPDATE projects SET
      jira_project_key = ?,
      confluence_space_id = ?,
      confluence_space_key = ?,
      atlassian_labels = ?
    WHERE id = ?
  `).run(
    norm(jiraProjectKey),
    norm(confluenceSpaceId),
    norm(confluenceSpaceKey),
    Array.isArray(labels) && labels.length ? JSON.stringify(labels) : null,
    project.id,
  );
  const updated = db.prepare('SELECT * FROM projects WHERE id = ?').get(project.id);
  writeWegaProjectFile(updated);
  res.json(updated);
});

// GET /api/atlassian/:projectId/config — read it back
atlassian.get('/:projectId/config', (req, res) => {
  const project = projectForRead(req.params.projectId, req, res);
  if (!project) return;
  let labels = [];
  if (project.atlassian_labels) {
    try { labels = JSON.parse(project.atlassian_labels) || []; } catch {}
  }
  res.json({
    jiraProjectKey: project.jira_project_key || '',
    confluenceSpaceId: project.confluence_space_id || '',
    confluenceSpaceKey: project.confluence_space_key || '',
    labels,
    credsConfigured: !!atlassianCreds(),
  });
});

// GET /api/atlassian/:projectId/artifacts — pull live data scoped to this project.
atlassian.get('/:projectId/artifacts', async (req, res) => {
  const project = projectForRead(req.params.projectId, req, res);
  if (!project) return;

  const creds = atlassianCreds();
  if (!creds) {
    return res.json({
      configured: false,
      reason: 'no-credentials',
      message: 'MCP_ATLASSIAN_SITE_NAME / MCP_ATLASSIAN_EMAIL / MCP_ATLASSIAN_TOKEN not set on the service',
    });
  }
  const host = `${creds.site}.atlassian.net`;
  const jiraKey = project.jira_project_key;
  const spaceId = project.confluence_space_id;
  const spaceKey = project.confluence_space_key;

  if (!jiraKey && !spaceId && !spaceKey) {
    return res.json({
      configured: false,
      reason: 'no-scope',
      message: 'Set jiraProjectKey and/or confluenceSpaceId for this project (see settings)',
    });
  }

  const labels = (() => {
    if (!project.atlassian_labels) return [];
    try { return JSON.parse(project.atlassian_labels) || []; } catch { return []; }
  })();

  const result = { configured: true, host, jira: { issues: [] }, confluence: { pages: [] }, errors: {} };

  // --- Jira ---
  if (jiraKey) {
    try {
      const jqlParts = [`project = "${jiraKey.replace(/"/g, '')}"`];
      if (labels.length) {
        const list = labels.map((l) => `"${l.replace(/"/g, '')}"`).join(', ');
        jqlParts.push(`labels in (${list})`);
      }
      const jql = jqlParts.join(' AND ') + ' ORDER BY created DESC';
      const path = `/rest/api/3/search/jql?jql=${encodeURIComponent(jql)}&fields=summary,issuetype,status,priority,created,parent,labels&maxResults=100`;
      const data = await atlGet(creds, host, path);
      const issues = (data.issues || []).map((iss) => ({
        key: iss.key,
        summary: iss.fields?.summary || '',
        type: iss.fields?.issuetype?.name || '',
        status: iss.fields?.status?.name || '',
        priority: iss.fields?.priority?.name || '',
        created: iss.fields?.created || null,
        parent: iss.fields?.parent?.key || null,
        labels: iss.fields?.labels || [],
        url: `https://${host}/browse/${iss.key}`,
      }));
      result.jira.project = jiraKey;
      result.jira.total = data.total || issues.length;
      result.jira.issues = issues;
    } catch (e) {
      // Fallback to the older /rest/api/3/search endpoint (some sites haven't moved to /search/jql)
      try {
        const jqlParts = [`project = "${jiraKey.replace(/"/g, '')}"`];
        if (labels.length) {
          const list = labels.map((l) => `"${l.replace(/"/g, '')}"`).join(', ');
          jqlParts.push(`labels in (${list})`);
        }
        const jql = jqlParts.join(' AND ') + ' ORDER BY created DESC';
        const path = `/rest/api/3/search?jql=${encodeURIComponent(jql)}&fields=summary,issuetype,status,priority,created,parent,labels&maxResults=100`;
        const data = await atlGet(creds, host, path);
        const issues = (data.issues || []).map((iss) => ({
          key: iss.key,
          summary: iss.fields?.summary || '',
          type: iss.fields?.issuetype?.name || '',
          status: iss.fields?.status?.name || '',
          priority: iss.fields?.priority?.name || '',
          created: iss.fields?.created || null,
          parent: iss.fields?.parent?.key || null,
          labels: iss.fields?.labels || [],
          url: `https://${host}/browse/${iss.key}`,
        }));
        result.jira.project = jiraKey;
        result.jira.total = data.total || issues.length;
        result.jira.issues = issues;
      } catch (e2) {
        result.errors.jira = e2.message || String(e2);
      }
    }
  }

  // --- Confluence ---
  if (spaceId || spaceKey) {
    try {
      let resolvedSpaceId = spaceId;
      let resolvedSpaceKey = spaceKey;
      let spaceName = null;

      if (!resolvedSpaceId && resolvedSpaceKey) {
        const sp = await atlGet(creds, host, `/wiki/api/v2/spaces?keys=${encodeURIComponent(resolvedSpaceKey)}`);
        const first = sp.results?.[0];
        if (first) { resolvedSpaceId = first.id; spaceName = first.name; }
      } else if (resolvedSpaceId) {
        try {
          const sp = await atlGet(creds, host, `/wiki/api/v2/spaces/${resolvedSpaceId}`);
          spaceName = sp.name;
          resolvedSpaceKey = sp.key || resolvedSpaceKey;
        } catch {}
      }

      if (resolvedSpaceId) {
        // If the project has labels, scope the Confluence pull via CQL so the
        // dashboard shows only pages tagged with this project's labels.
        // Without this, every project in the same space sees every page —
        // BRDs, reports, etc. cross-pollinate across projects.
        //
        // CQL has an indexing lag (seconds to ~an hour after a label change).
        // If CQL returns 0 hits, fall back to listing the space's recent
        // pages and filtering by their label metadata directly — that path
        // reads label assignments off each page instead of going through
        // the search index, so freshly-tagged pages appear immediately.
        let pages = [];
        if (labels.length) {
          const labelSet = new Set(labels);
          const labelClause = labels.map((l) => `"${l.replace(/"/g, '')}"`).join(', ');
          const cql = `space = "${(resolvedSpaceKey || '').replace(/"/g, '')}" AND label in (${labelClause}) AND type = page ORDER BY lastmodified DESC`;
          try {
            const data = await atlGet(creds, host, `/wiki/rest/api/content/search?cql=${encodeURIComponent(cql)}&limit=100&expand=version`);
            pages = (data.results || []).map((p) => ({
              id: p.id,
              title: p.title || '',
              status: p.status,
              createdAt: p.history?.createdDate || null,
              version: p.version?.number,
              webui: p._links?.webui,
              url: p._links?.webui ? `https://${host}/wiki${p._links.webui}` : `https://${host}/wiki/pages/viewpage.action?pageId=${p.id}`,
              isBrd: /BRD|Business Requirements/i.test(p.title || ''),
            }));
          } catch (cqlErr) {
            // CQL failed — keep going, the fallback below may still work.
            result.errors.confluence = `CQL label filter failed: ${cqlErr.message}`;
          }
          // Fallback when CQL returned no hits — read recent pages from the
          // space and filter by their label metadata. Catches the index-lag
          // window right after a page was tagged.
          if (pages.length === 0) {
            try {
              const data = await atlGet(creds, host, `/wiki/api/v2/spaces/${resolvedSpaceId}/pages?limit=100&sort=-modified-date`);
              for (const p of data.results || []) {
                let pageLabels = [];
                try {
                  const lb = await atlGet(creds, host, `/wiki/api/v2/pages/${p.id}/labels?limit=50`);
                  pageLabels = (lb.results || []).map((l) => l.name);
                } catch {}
                if (pageLabels.some((n) => labelSet.has(n))) {
                  pages.push({
                    id: p.id,
                    title: p.title || '',
                    status: p.status,
                    createdAt: p.createdAt || null,
                    version: p.version?.number,
                    webui: p._links?.webui,
                    url: p._links?.webui ? `https://${host}/wiki${p._links.webui}` : `https://${host}/wiki/pages/viewpage.action?pageId=${p.id}`,
                    isBrd: /BRD|Business Requirements/i.test(p.title || ''),
                  });
                }
              }
              if (pages.length > 0) delete result.errors.confluence;
            } catch (fbErr) {
              result.errors.confluence = `Label fallback failed: ${fbErr.message}`;
            }
          }
        } else {
          // No labels configured — fall back to the full space listing. This
          // is the legacy behaviour; new projects all get a label auto-set so
          // this branch only fires for projects without one.
          const data = await atlGet(creds, host, `/wiki/api/v2/spaces/${resolvedSpaceId}/pages?limit=100&sort=-modified-date`);
          pages = (data.results || []).map((p) => ({
            id: p.id,
            title: p.title || '',
            status: p.status,
            createdAt: p.createdAt || null,
            version: p.version?.number,
            webui: p._links?.webui,
            url: p._links?.webui ? `https://${host}/wiki${p._links.webui}` : `https://${host}/wiki/pages/viewpage.action?pageId=${p.id}`,
            isBrd: /BRD|Business Requirements/i.test(p.title || ''),
          }));
        }
        result.confluence.spaceId = resolvedSpaceId;
        result.confluence.spaceKey = resolvedSpaceKey || null;
        result.confluence.spaceName = spaceName;
        result.confluence.pages = pages;
        result.confluence.labels = labels;
      }
    } catch (e) {
      result.errors.confluence = e.message || String(e);
    }
  }

  res.json(result);
});
