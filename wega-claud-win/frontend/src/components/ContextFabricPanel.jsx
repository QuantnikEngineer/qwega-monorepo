import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api.js';
import { ScreenFrame, Pill, Btn, S, SectionLabel } from './ui.jsx';

// ─────────────────────────────────────────────────────────────────────────────
// Visual primitives
// ─────────────────────────────────────────────────────────────────────────────
const TYPE_META = {
  repo:         { glyph: '▣',  label: 'Code repo',         tone: 'phosphor', supported: true,  helper: 'Walks a git working tree; ingests text files (filters binaries / vendored / build outputs).' },
  document:     { glyph: '▤',  label: 'Document',          tone: 'cyan',     supported: true,  helper: 'A file in the project uploads/ folder. .pdf / .md / .txt supported out of the box.' },
  website:      { glyph: '◯',  label: 'Website',           tone: 'amber',    supported: true,  helper: 'Single URL — fetches, strips boilerplate, ingests the main content.' },
  confluence:   { glyph: '⧉',  label: 'Confluence',        tone: 'violet',   supported: false, helper: 'Coming soon. Atlassian MCP auth is wired; pages-by-space pull is the next step.' },
  sharepoint:   { glyph: '⊞',  label: 'SharePoint',        tone: 'magenta',  supported: false, helper: 'Coming soon. Needs a Microsoft Graph OAuth app per tenant.' },
  agent_output: { glyph: '>_', label: 'Agent output',      tone: 'phosphor', supported: true,  helper: 'Replays assistant messages from this project\'s chat history. Useful for retrieving past BRDs / reports / analysis.' },
};

const STATUS_TONE = {
  pending:    'amber',
  ingesting:  'cyan',
  ready:      'phosphor',
  failed:     'red',
  disabled:   undefined,
};

function fmtBytes(n) {
  if (!n) return '—';
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)}K`;
  return `${(n / 1024 / 1024).toFixed(1)}M`;
}
function fmt(n) { return n == null ? '—' : Number(n).toLocaleString(); }
function relTime(epoch) {
  if (!epoch) return '—';
  const s = Math.floor(Date.now() / 1000 - epoch);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Source row
// ─────────────────────────────────────────────────────────────────────────────
function SourceRow({ source, onIngest, onDelete, busy }) {
  const meta = TYPE_META[source.type] || { glyph: '?', label: source.type, tone: 'phosphor' };
  const cfg = source.config || {};
  const descPieces = [];
  if (cfg.path) descPieces.push(cfg.path);
  if (cfg.url) descPieces.push(cfg.url);
  if (cfg.repoId) descPieces.push(`repo #${cfg.repoId}`);
  if (cfg.spaceKey) descPieces.push(`space=${cfg.spaceKey}`);
  if (cfg.siteUrl) descPieces.push(cfg.siteUrl);

  // Rows shown inside the project panel that actually belong to the org
  // scope are inherited (read-only here — managed at /context).
  const readOnly = source._inherited;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '24px 1fr auto auto auto auto',
      gap: 10,
      alignItems: 'center',
      padding: '8px 10px',
      borderBottom: '1px dashed var(--w-line)',
      background: source.status === 'ingesting' ? 'var(--w-phosphor-veil)' : 'transparent',
      opacity: readOnly ? 0.85 : 1,
    }}>
      <span style={{ color: `var(--w-${meta.tone})`, font: '13px/1 var(--w-mono)', textAlign: 'center' }}>{meta.glyph}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ color: 'var(--w-text-0)', font: '500 12.5px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {source.label || meta.label}
          {readOnly && <span style={{ marginLeft: 6, color: 'var(--w-cyan)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.08em' }}>· INHERITED FROM ORG</span>}
        </div>
        <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={descPieces.join(' · ')}>
          {descPieces.join(' · ') || <span style={{ fontStyle: 'italic' }}>no config</span>}
        </div>
        {source.error && (
          <div style={{ color: 'var(--w-red)', font: '10.5px/1.4 var(--w-mono)', whiteSpace: 'pre-wrap' }} title={source.error}>
            error: {source.error}
          </div>
        )}
      </div>
      <Pill tone={STATUS_TONE[source.status]} dot={source.status !== 'disabled'}>{source.status}</Pill>
      <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', minWidth: 90, textAlign: 'right' }}>
        {fmt(source.chunkCount)} chunks
      </span>
      <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', minWidth: 80, textAlign: 'right' }}>
        {relTime(source.lastIngestedAt)}
      </span>
      <div style={{ display: 'flex', gap: 4 }}>
        {readOnly ? (
          <span style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', padding: '0 6px', fontStyle: 'italic' }}>read-only</span>
        ) : (
          <>
            <Btn tone="ghost" disabled={busy || source.status === 'ingesting'} onClick={() => onIngest(source)} style={{ padding: '3px 8px' }}>[ ↻ ]</Btn>
            <Btn tone="danger" disabled={busy} onClick={() => onDelete(source)} style={{ padding: '3px 8px' }}>[ × ]</Btn>
          </>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// "Add source" form — supports bulk-add for URL-shaped types (website /
// confluence / sharepoint) via a multi-line textarea. One entry per line.
// ─────────────────────────────────────────────────────────────────────────────
function AddSourceForm({ type, scope, projectId, availableRepos, onSubmit, onSubmitBulk, onCancel }) {
  const meta = TYPE_META[type];
  const [label, setLabel] = useState('');
  const [config, setConfig] = useState({});
  // Bulk-add multi-line textarea (for website / confluence / sharepoint).
  const [bulkText, setBulkText] = useState('');
  const supportsBulk = type === 'website' || type === 'confluence' || type === 'sharepoint';

  // Parse the bulk textarea into a list of source-config payloads.
  function bulkPayloads() {
    const lines = bulkText.split('\n').map((s) => s.trim()).filter(Boolean);
    return lines.map((line) => {
      if (type === 'website') {
        return { scope, projectId: scope === 'project' ? projectId : null, type, label: null, config: { url: line } };
      }
      if (type === 'confluence') {
        // Line can be "SPACEKEY" or "SPACEKEY,label=foo"
        const [spaceKey, ...rest] = line.split(',').map((s) => s.trim());
        const extras = Object.fromEntries(rest.map((kv) => kv.split('=').map((s) => s.trim())));
        return { scope, projectId: scope === 'project' ? projectId : null, type, label: null, config: { spaceKey, labelFilter: extras.label || null } };
      }
      if (type === 'sharepoint') {
        return { scope, projectId: scope === 'project' ? projectId : null, type, label: null, config: { siteUrl: line } };
      }
      return null;
    }).filter(Boolean);
  }

  const handleSubmit = (e) => {
    e?.preventDefault?.();
    const items = supportsBulk ? bulkPayloads() : [];
    if (items.length > 1 && onSubmitBulk) {
      onSubmitBulk(items);
    } else if (items.length === 1 && onSubmitBulk) {
      // Single-line bulk treated as a regular single add.
      onSubmit({ ...items[0], label: label || items[0].label || null });
    } else {
      onSubmit({ scope, projectId: scope === 'project' ? projectId : null, type, label: label || null, config });
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        marginTop: 10,
        padding: '12px 14px',
        border: `1px solid var(--w-${meta.tone})`,
        borderLeft: `3px solid var(--w-${meta.tone})`,
        background: 'var(--w-bg-1)',
        borderRadius: 3,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 8 }}>
        <span style={{ color: `var(--w-${meta.tone})`, font: '12px/1 var(--w-mono)' }}>{meta.glyph}</span>
        <span style={{ color: 'var(--w-text-0)', font: '600 12.5px/1 var(--w-mono)' }}>Add {meta.label}</span>
        <span style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>· {meta.helper}</span>
      </div>

      {!meta.supported && (
        <div style={{ marginBottom: 8, padding: '6px 10px', background: 'var(--w-bg-2)', borderLeft: '2px solid var(--w-amber)', color: 'var(--w-text-1)', font: '10.5px/1.5 var(--w-mono)' }}>
          This source type is registrable but ingest is not yet wired — the row will live at status=pending until the connector ships.
        </div>
      )}

      {supportsBulk ? (
        // ─── Bulk-add for URL-shaped sources ────────────────────────────
        <div>
          <label style={{ display: 'block', font: '10px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
            {type === 'website' && 'URLs — one per line'}
            {type === 'confluence' && 'Confluence space keys — one per line (optional ", label=<filter>")'}
            {type === 'sharepoint' && 'SharePoint site URLs — one per line'}
          </label>
          <textarea
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            rows={5}
            placeholder={
              type === 'website'    ? 'https://example.com/page\nhttps://docs.example.com/getting-started\nhttps://blog.example.com/announcement'
            : type === 'confluence' ? 'BL\nWSKB, label=wega-project-faber\nDOCS'
            :                          'https://contoso.sharepoint.com/sites/engineering\nhttps://contoso.sharepoint.com/sites/design'
            }
            style={{
              width: '100%',
              font: '11.5px/1.55 var(--w-mono)',
              padding: '8px 10px',
              background: 'var(--w-bg-2)',
              color: 'var(--w-text-0)',
              border: '1px solid var(--w-line)',
              borderRadius: 2,
              resize: 'vertical',
            }}
          />
          <div style={{ marginTop: 6, color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>
            {bulkPayloads().length === 0 && 'add one or more lines — each becomes a separate source.'}
            {bulkPayloads().length === 1 && 'will register 1 source.'}
            {bulkPayloads().length > 1 && `will register ${bulkPayloads().length} sources (ingest fires for each).`}
          </div>
        </div>
      ) : (
        // ─── Single-source form (repo / document / agent_output) ────────
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <FormField label="Label (optional)" value={label} onChange={setLabel} placeholder={meta.label} />

          {type === 'repo' && (
            <FormField
              label="Pick a registered repo"
              kind="select"
              value={config.repoId || ''}
              options={[
                { value: '', label: '— pick one —' },
                ...availableRepos.filter((r) => !r.registered).map((r) => ({ value: r.id, label: `#${r.id} ${r.name} — ${r.path}` })),
              ]}
              onChange={(v) => setConfig({ ...config, repoId: Number(v) })}
            />
          )}
          {type === 'repo' && (
            <FormField
              label="Or absolute path (overrides registered repo)"
              value={config.path || ''}
              placeholder="C:\path\to\repo"
              onChange={(v) => setConfig({ ...config, path: v })}
            />
          )}

          {type === 'document' && (
            <FormField
              label="Path (relative to project, or absolute)"
              value={config.path || ''}
              placeholder="uploads/1779…-mydoc.pdf"
              onChange={(v) => setConfig({ ...config, path: v })}
            />
          )}

          {type === 'agent_output' && (
            <FormField
              label="Since message id (optional, 0 = entire history)"
              value={config.sinceMessageId || ''}
              placeholder="0"
              onChange={(v) => setConfig({ ...config, sinceMessageId: v ? Number(v) : 0 })}
            />
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
        <Btn tone="ghost" onClick={onCancel} type="button">cancel</Btn>
        <Btn tone="primary" type="submit" disabled={supportsBulk && bulkPayloads().length === 0}>
          {supportsBulk && bulkPayloads().length > 1 ? `[ + ] add ${bulkPayloads().length}` : '[ + ] add source'}
        </Btn>
      </div>
    </form>
  );
}

function FormField({ label, value, onChange, placeholder, kind = 'input', options }) {
  return (
    <div>
      <label style={{ display: 'block', font: '10px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</label>
      {kind === 'select' ? (
        <select value={value} onChange={(e) => onChange(e.target.value)} style={{ width: '100%' }}>
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={{ width: '100%' }} />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Test-query block (retrieve top-K)
// ─────────────────────────────────────────────────────────────────────────────
function QueryProbe({ scope, projectId }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const run = async (e) => {
    e?.preventDefault?.();
    if (!q.trim()) return;
    setBusy(true); setError('');
    try {
      const r = await api.queryContext({ scope, projectId, query: q, topK: 8 });
      setResult(r);
    } catch (e) { setError(e.message); setResult(null); }
    setBusy(false);
  };

  return (
    <div style={{ marginTop: 18, border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '12px 14px' }}>
      <SectionLabel tone="phosphor">// test query — top-K retrieval from the ingested chunks</SectionLabel>
      <form onSubmit={run} style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="ask anything — e.g. 'what is the BRD shape?'"
          style={{ flex: 1 }}
        />
        <Btn tone="primary" type="submit" disabled={busy || !q.trim()}>{busy ? 'searching…' : '[ → ] retrieve'}</Btn>
      </form>
      {error && <div style={{ color: 'var(--w-red)', font: '11px/1.5 var(--w-mono)', marginTop: 8 }}>error: {error}</div>}
      {result && (
        <div style={{ marginTop: 10 }}>
          <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>
            scanned {fmt(result.candidateCount || 0)} chunks · returned {result.results.length} · query tokens: {fmt(result.queryTokens)}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
            {result.results.map((r, i) => (
              <div key={r.chunkId} style={{
                padding: '8px 10px',
                background: 'var(--w-bg-1)',
                borderLeft: `2px solid var(--w-${TYPE_META[r.source.type]?.tone || 'phosphor'})`,
                borderRadius: 2,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
                  <span style={{ color: 'var(--w-text-0)', font: '500 11.5px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.document.title || r.document.uri}>
                    [{i + 1}] {r.source.scope === 'org' ? '🌐 ' : ''}{TYPE_META[r.source.type]?.glyph} {r.document.title || r.document.externalId || r.document.uri}
                  </span>
                  <span style={{ color: 'var(--w-phosphor)', font: '10.5px/1 var(--w-mono)', flex: '0 0 auto' }}>score: {r.score.toFixed(3)}</span>
                </div>
                <pre style={{
                  margin: '6px 0 0',
                  color: 'var(--w-text-1)',
                  font: '10.5px/1.55 var(--w-mono)',
                  whiteSpace: 'pre-wrap',
                  maxHeight: 96,
                  overflow: 'hidden',
                  background: 'transparent',
                }}>
                  {r.content.slice(0, 380)}{r.content.length > 380 ? '…' : ''}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Top-level panel
//
// Renders in two modes:
//   mode="global"  → wega2-level Context Fabric (org scope only).
//                    Admin-managed. Visible at /context. Project sources
//                    aren't shown — those belong to per-project surfaces.
//   mode="project" → per-project Context Fabric. Default scope is the
//                    project; admins can toggle to view org sources too
//                    (read-only — they're managed at /context).
// ─────────────────────────────────────────────────────────────────────────────
export function ContextFabricPanel({ mode = 'project', project }) {
  const isGlobal = mode === 'global';

  const [sources, setSources] = useState([]);
  const [health, setHealth] = useState(null);
  const [repos, setRepos] = useState([]);
  const [isAdmin, setIsAdmin] = useState(false);
  // scope: 'project' (only visible in project mode) or 'org'.
  const [scope, setScope] = useState(isGlobal ? 'org' : 'project');
  const [adding, setAdding] = useState(null); // type being added, or null
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const projectId = project?.id;

  const reload = async () => {
    if (!isGlobal && !projectId && scope === 'project') return;
    setError('');
    try {
      const [s, h, r] = await Promise.all([
        api.listContextSources({
          scope,
          projectId: scope === 'project' ? projectId : undefined,
        }),
        api.contextHealth(),
        scope === 'project' && projectId
          ? api.reposAvailableForContext(projectId)
          : Promise.resolve({ repos: [] }),
      ]);
      // In project mode, the API also returns org sources (so users see what
      // they inherit). Tag them locally so the row can render them read-only.
      const allSources = (s.sources || []).map((row) =>
        (!isGlobal && row.scope === 'org')
          ? { ...row, _inherited: true }
          : row,
      );
      setSources(allSources);
      setHealth(h);
      setRepos(r.repos || []);
    } catch (e) { setError(e.message); }
  };

  useEffect(() => {
    api.me().then((m) => setIsAdmin(!!m?.user?.isAdmin)).catch(() => setIsAdmin(false));
  }, []);

  // Auto-init: when the panel mounts for a project, ask the backend to
  // idempotently register a context source for every project_repos row that
  // doesn't have one yet + the project's agent-output stream. The user
  // should never have to manually wire up "their own code" or "their own
  // chat history" — it should just be there. Org-scope auto-init is a
  // no-op (no project_repos analog).
  useEffect(() => {
    if (isGlobal || !projectId) return;
    api.autoInitContext(projectId)
      .then(() => reload())
      .catch(() => { /* surface via reload's error state if any */ });
    // eslint-disable-next-line
  }, [projectId, isGlobal]);

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [projectId, scope]);
  useEffect(() => {
    // Poll while any source is in-flight so the UI shows live status changes.
    const poll = setInterval(() => {
      if (sources.some((s) => s.status === 'ingesting')) reload();
    }, 3000);
    return () => clearInterval(poll);
    // eslint-disable-next-line
  }, [sources]);

  const handleAdd = async (data) => {
    setBusy(true); setError('');
    try {
      const s = await api.addContextSource(data);
      setAdding(null);
      // Auto-ingest the new source if its type supports it
      if (TYPE_META[data.type]?.supported) {
        await api.ingestContextSource(s.id);
      }
      await reload();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  // Bulk variant — registers many sources in one round-trip. The backend
  // fires ingest for each one in the background.
  const handleAddBulk = async (items) => {
    setBusy(true); setError('');
    try {
      const r = await api.bulkAddContextSources(items);
      if (r.errors?.length) {
        setError(`${r.errors.length} of ${items.length} failed — ${r.errors[0].error}`);
      }
      setAdding(null);
      await reload();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const handleIngest = async (s) => {
    setBusy(true); setError('');
    try { await api.ingestContextSource(s.id); await reload(); }
    catch (e) { setError(e.message); }
    setBusy(false);
  };

  const handleDelete = async (s) => {
    if (!confirm(`Remove "${s.label || TYPE_META[s.type]?.label}" from the Context Fabric? All chunks for this source will be deleted.`)) return;
    setBusy(true); setError('');
    try { await api.deleteContextSource(s.id); await reload(); }
    catch (e) { setError(e.message); }
    setBusy(false);
  };

  // Group sources by type for the UI section list
  const byType = useMemo(() => {
    const g = {};
    for (const t of Object.keys(TYPE_META)) g[t] = [];
    for (const s of sources) (g[s.type] = g[s.type] || []).push(s);
    return g;
  }, [sources]);

  const totalChunks = sources.reduce((a, s) => a + (s.chunkCount || 0), 0);
  const totalDocs   = sources.reduce((a, s) => a + (s.documentCount || 0), 0);
  const totalTokens = sources.reduce((a, s) => a + (s.totalTokens || 0), 0);

  // Adding sources:
  //   - in global mode, you must be admin (the panel hides the [+] buttons
  //     for non-admins) AND the API rejects writes without is_admin
  //   - in project mode, project sources are open; org sources can only be
  //     added from /context (and we don't show the [+] for them here)
  const canAddProject = !isGlobal;
  const canAddOrg     = isAdmin; // global mode shows admin-only; project mode does not surface org-add

  return (
    <ScreenFrame
      breadcrumb={
        isGlobal
          ? <><S c="var(--w-phosphor)">wega</S> ─ context-fabric · global</>
          : <><S c="var(--w-phosphor)">~/{project?.name || 'wega'}</S> ─ context-fabric</>
      }
      title={isGlobal ? 'Context Fabric — Global' : 'Context Fabric'}
      subtitle={
        isGlobal
          ? <>Wega2-level RAG knowledge layer. Sources registered here are visible to <S c="var(--w-phosphor)">every project's queries</S> — runbooks, brand guidelines, architecture decisions, policy docs. Admin-managed.</>
          : <>Project-scoped RAG knowledge — repos, documents, websites, agent output. Org-level sources from <a href="/context" style={{ color: 'var(--w-cyan)' }}>/context</a> are inherited automatically.</>
      }
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          {!isGlobal && (
            <div style={{ display: 'flex', border: '1px solid var(--w-line)', borderRadius: 3, overflow: 'hidden' }}>
              <button
                onClick={() => setScope('project')}
                style={{
                  padding: '6px 12px',
                  background: scope === 'project' ? 'var(--w-phosphor-veil)' : 'transparent',
                  color: scope === 'project' ? 'var(--w-phosphor)' : 'var(--w-text-2)',
                  border: 'none',
                  font: '12px/1 var(--w-mono)',
                  cursor: 'pointer',
                }}
              >project</button>
              <button
                onClick={() => setScope('org')}
                title={'org sources — read-only here; manage at /context'}
                style={{
                  padding: '6px 12px',
                  background: scope === 'org' ? 'var(--w-phosphor-veil)' : 'transparent',
                  color: scope === 'org' ? 'var(--w-phosphor)' : 'var(--w-text-2)',
                  border: 'none',
                  borderLeft: '1px solid var(--w-line)',
                  font: '12px/1 var(--w-mono)',
                  cursor: 'pointer',
                }}
              >org</button>
            </div>
          )}
          {!isGlobal && isAdmin && (
            <a href="/context" style={{ textDecoration: 'none' }}>
              <Btn tone="ghost">[ → ] manage global</Btn>
            </a>
          )}
          {isGlobal && (
            <a href="/" style={{ textDecoration: 'none' }}>
              <Btn tone="ghost">[ ⌂ ] home</Btn>
            </a>
          )}
          <Btn tone="ghost" onClick={reload}>[ ↻ ] refresh</Btn>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Top metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          <Metric label="sources" value={fmt(sources.length)} accent="phosphor" />
          <Metric label="documents" value={fmt(totalDocs)} accent="cyan" />
          <Metric label="chunks" value={fmt(totalChunks)} accent="amber" />
          <Metric label="tokens embedded" value={fmt(totalTokens)} accent="violet" />
        </div>

        {/* Embedding posture banner — local-only; surfaces whether the
            first-ingest model download has happened yet. */}
        {health && (
          <div style={{
            padding: '8px 14px',
            border: '1px solid var(--w-line)',
            borderLeft: `2px solid var(--w-${health.cached ? 'phosphor' : 'amber'})`,
            background: 'var(--w-bg-2)',
            borderRadius: 3,
            font: '11px/1.6 var(--w-mono)',
            color: 'var(--w-text-1)',
          }}>
            embedding: <S c="var(--w-phosphor)">{health.embeddingModel}</S> · {health.embeddingDim}-dim · <S c="var(--w-cyan)">{health.backend}</S>
            {!health.cached && (
              <span style={{ color: 'var(--w-amber)', marginLeft: 8 }}>
                ⚠ model not cached yet — first ingest will download to <code style={{ color: 'var(--w-cyan)' }}>{health.cacheDir}</code> (one-time, ~134MB).
              </span>
            )}
            {health.cached && health.ready && (
              <span style={{ color: 'var(--w-phosphor)', marginLeft: 8 }}>· loaded</span>
            )}
            {health.cached && !health.ready && (
              <span style={{ color: 'var(--w-text-3)', marginLeft: 8 }}>· cached on disk · loads on first embed call</span>
            )}
          </div>
        )}

        {error && (
          <div style={{ padding: '8px 14px', border: '1px solid var(--w-red)', color: 'var(--w-red)', font: '11px/1.5 var(--w-mono)', borderRadius: 3 }}>
            {error}
          </div>
        )}

        {/* One section per source type */}
        {Object.entries(TYPE_META).map(([type, meta]) => {
          const items = byType[type] || [];
          const showAddRepoTip = type === 'repo' && !isGlobal && scope === 'project' && repos.length > 0 && !items.length;

          // Can the current user add a source of this type, in the current scope?
          //  - global mode: admin-only (org scope)
          //  - project mode + scope=project: anyone with project access
          //  - project mode + scope=org: not allowed here — manage at /context
          const showAdd = isGlobal
            ? canAddOrg
            : (scope === 'project');

          return (
            <div key={type} style={{
              border: '1px solid var(--w-line)',
              background: 'var(--w-bg-2)',
              borderRadius: 3,
              padding: '12px 14px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <span style={{ color: `var(--w-${meta.tone})`, font: '14px/1 var(--w-mono)' }}>{meta.glyph}</span>
                  <span style={{ color: 'var(--w-text-0)', font: '600 13px/1 var(--w-mono)' }}>{meta.label}</span>
                  <Pill tone={meta.tone}>{items.length}</Pill>
                  {!meta.supported && <Pill tone="amber">stub</Pill>}
                </div>
                {showAdd ? (
                  <Btn tone="ghost" onClick={() => setAdding(adding === type ? null : type)}>
                    {adding === type ? 'cancel' : '[ + ] add'}
                  </Btn>
                ) : (
                  <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', fontStyle: 'italic' }}>
                    {scope === 'org' && !isGlobal ? 'read-only — manage at /context' : 'admin only'}
                  </span>
                )}
              </div>
              <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.5 var(--w-mono)', marginBottom: 8 }}>
                {meta.helper}
              </div>

              {showAddRepoTip && (
                <div style={{ padding: '6px 10px', marginBottom: 8, background: 'var(--w-bg-1)', borderLeft: '2px solid var(--w-cyan)', font: '10.5px/1.5 var(--w-mono)', color: 'var(--w-text-2)' }}>
                  {repos.length} repo{repos.length === 1 ? '' : 's'} registered in this project's Repos tab — click [ + ] add to ingest one.
                </div>
              )}

              {adding === type && (
                <AddSourceForm
                  type={type}
                  scope={scope}
                  projectId={projectId}
                  availableRepos={repos}
                  onSubmit={handleAdd}
                  onSubmitBulk={handleAddBulk}
                  onCancel={() => setAdding(null)}
                />
              )}

              {items.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  {items.map((s) => (
                    <SourceRow key={s.id} source={s} onIngest={handleIngest} onDelete={handleDelete} busy={busy} />
                  ))}
                </div>
              )}
              {!items.length && adding !== type && (
                <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.5 var(--w-mono)', padding: '8px 4px', fontStyle: 'italic' }}>
                  no {meta.label.toLowerCase()} sources yet.
                </div>
              )}
            </div>
          );
        })}

        {/* Test-query probe */}
        {(sources.some((s) => s.status === 'ready')) && (
          <QueryProbe scope={scope} projectId={projectId} />
        )}
      </div>
    </ScreenFrame>
  );
}

function Metric({ label, value, accent = 'phosphor' }) {
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid var(--w-${accent})`,
      background: 'var(--w-bg-2)',
      borderRadius: 3,
      padding: '10px 14px',
    }}>
      <div style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div style={{ color: `var(--w-${accent})`, font: '600 18px/1 var(--w-mono)' }}>{value}</div>
    </div>
  );
}
