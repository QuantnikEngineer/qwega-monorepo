import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { ScreenFrame, Pill, Btn, S, SectionLabel } from './ui.jsx';

const EMPTY_FORM = {
  name: '',
  transport: 'stdio',
  command: '',
  args: '',
  envText: '',
  url: '',
  headersText: '',
};

const SUGGESTED = [
  { n: 'linear',    d: 'issues, projects, comments', t: 'http' },
  { n: 'notion',    d: 'pages, databases, search',   t: 'http' },
  { n: 'slack',     d: 'messages, threads, files',   t: 'http' },
  { n: 'github',    d: 'repos, issues, pulls',       t: 'http' },
  { n: 'puppeteer', d: 'browser automation',         t: 'stdio' },
];

function McpRow({ name, status, transport, url, json, onAuth, onRemove }) {
  const [expanded, setExpanded] = useState(false);
  const accent = status === 'connected' ? 'phosphor' : status === 'needs-auth' ? 'amber' : status === 'pending' ? 'cyan' : 'red';
  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid var(--w-${accent})`,
      borderRadius: 3,
      background: 'var(--w-bg-2)',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, borderBottom: expanded ? '1px solid var(--w-line)' : 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
          <span className="w-dot" style={{ background: `var(--w-${accent})`, color: `var(--w-${accent})` }} />
          <span style={{ color: 'var(--w-text-0)', font: '600 13px/1 var(--w-mono)' }}>{name}</span>
          <Pill tone={accent}>{status}</Pill>
          {transport && <Pill>{transport}</Pill>}
          {url && <span style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{url}</span>}
        </div>
        <div style={{ display: 'flex', gap: 6, flex: '0 0 auto' }}>
          {onAuth && status === 'needs-auth' && <Btn tone="line" style={{ padding: '4px 10px' }} onClick={onAuth}>[ auth ↗ ]</Btn>}
          {json && <Btn tone="ghost" style={{ padding: '4px 10px' }} onClick={() => setExpanded((x) => !x)}>{expanded ? '[ − ]' : '[ + ]'}</Btn>}
          {onRemove && <Btn tone="danger" style={{ padding: '4px 10px' }} onClick={onRemove}>[ del ]</Btn>}
        </div>
      </div>
      {expanded && json && (
        <pre style={{
          margin: 0,
          padding: '12px 14px',
          background: 'var(--w-bg-1)',
          color: 'var(--w-text-1)',
          font: '11.5px/1.5 var(--w-mono)',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}>{json}</pre>
      )}
    </div>
  );
}

export function McpPanel({ project, sessionInfo }) {
  const [data, setData] = useState({ local: {}, env: {}, runtime: [] });
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const dialogRef = useRef(null);

  const load = async () => {
    try { setData(await api.listMcp(project.id)); }
    catch (e) { setError(e.message); }
  };

  useEffect(() => { setError(''); load(); /* eslint-disable-next-line */ }, [project.id]);

  const openAdd = (prefill) => {
    setForm({ ...EMPTY_FORM, ...(prefill || {}) });
    setError('');
    dialogRef.current?.showModal();
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    let config;
    try {
      if (form.transport === 'stdio') {
        config = {
          type: 'stdio',
          command: form.command.trim(),
          args: form.args.trim() ? form.args.split(/\s+/) : [],
          env: form.envText.trim() ? JSON.parse(form.envText) : undefined,
        };
      } else {
        config = {
          type: form.transport,
          url: form.url.trim(),
          headers: form.headersText.trim() ? JSON.parse(form.headersText) : undefined,
        };
      }
      Object.keys(config).forEach((k) => config[k] === undefined && delete config[k]);
      await api.addMcp(project.id, form.name.trim(), config);
      dialogRef.current?.close();
      await load();
    } catch (e) { setError(e.message); }
  };

  const remove = async (name) => {
    if (!confirm(`delete MCP server "${name}"? changes take effect next chat turn.`)) return;
    await api.deleteMcp(project.id, name);
    await load();
  };

  const localEntries = Object.entries(data.local || {});
  const envEntries = Object.entries(data.env || {});
  const sessionRuntime = Array.isArray(sessionInfo?.mcpServers) ? sessionInfo.mcpServers : [];
  const backendRuntime = Array.isArray(data.runtime) ? data.runtime : [];
  const runtime = sessionRuntime.length > 0 ? sessionRuntime : backendRuntime;
  const activeCount = runtime.filter((s) => s.status === 'connected').length;

  return (
    <ScreenFrame
      breadcrumb={<><S c="var(--w-phosphor)">~/{project.name}</S> ─ mcp</>}
      title="MCP servers"
      subtitle={
        <>Model Context Protocol servers extend Claude with external tools. Live connections are reported by the Agent SDK at the start of each chat turn. Local entries are added to <S c="var(--w-cyan)">.claude/settings.json</S> under <S c="var(--w-amber)">mcpServers</S>.</>
      }
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn tone="ghost" onClick={load}>[ ↻ ] refresh</Btn>
          <Btn tone="primary" onClick={() => openAdd()}>[ + ] add server</Btn>
        </div>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Live */}
          <div>
            <SectionLabel tone="phosphor" right={<Pill tone="cyan">{activeCount} active / {runtime.length}</Pill>}>
              // live · last session
            </SectionLabel>
            {runtime.length === 0 ? (
              <div style={{ color: 'var(--w-text-3)', font: '11.5px/1.4 var(--w-mono)', padding: '10px 14px', border: '1px dashed var(--w-line)', borderRadius: 3 }}>
                no session yet. send a chat message to populate.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {runtime.map((s) => (
                  <McpRow key={s.name} name={s.name} status={s.status} />
                ))}
              </div>
            )}
          </div>

          {/* Backend env */}
          <div>
            <SectionLabel tone="amber" right={<Pill>service-wide</Pill>}>
              // backend env · configured
            </SectionLabel>
            {envEntries.length === 0 ? (
              <div style={{ color: 'var(--w-text-3)', font: '11.5px/1.4 var(--w-mono)', padding: '10px 14px', border: '1px dashed var(--w-line)', borderRadius: 3 }}>
                no backend environment MCP servers configured.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {envEntries.map(([name, cfg]) => (
                  <McpRow
                    key={name}
                    name={name}
                    status={runtime.find((s) => s.name === name)?.status || 'pending'}
                    transport={cfg.type || (cfg.command ? 'stdio' : 'http')}
                    url={cfg.url || cfg.command}
                    json={JSON.stringify(cfg, null, 2)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Local */}
          <div>
            <SectionLabel tone="cyan" right={<Pill>active on next turn</Pill>}>
              // local · {project.name}
            </SectionLabel>
            {localEntries.length === 0 ? (
              <div style={{ color: 'var(--w-text-3)', font: '11.5px/1.4 var(--w-mono)', padding: '10px 14px', border: '1px dashed var(--w-line)', borderRadius: 3 }}>
                no local servers defined for this project.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {localEntries.map(([name, cfg]) => (
                  <McpRow
                    key={name}
                    name={name}
                    status={runtime.find((s) => s.name === name)?.status || 'pending'}
                    transport={cfg.type || (cfg.command ? 'stdio' : 'http')}
                    url={cfg.url || cfg.command}
                    json={JSON.stringify(cfg, null, 2)}
                    onRemove={() => remove(name)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Side: registry */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '14px 16px' }}>
            <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 10 }}>// registry · suggested</div>
            {SUGGESTED.map((s, i) => (
              <div key={s.n} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderTop: i ? '1px dashed var(--w-line)' : 'none' }}>
                <div>
                  <div style={{ color: 'var(--w-text-0)', font: '12px/1.3 var(--w-mono)' }}>{s.n}</div>
                  <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>{s.d}</div>
                </div>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <Pill>{s.t}</Pill>
                  <span onClick={() => openAdd({ name: s.n, transport: s.t })} style={{ color: 'var(--w-phosphor)', font: '10.5px/1 var(--w-mono)', cursor: 'pointer' }}>[ + ]</span>
                </div>
              </div>
            ))}
          </div>

          <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '14px 16px' }}>
            <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 10 }}>// summary</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, font: '11px/1.4 var(--w-mono)' }}>
              <div>
                <div style={{ color: 'var(--w-text-3)', fontSize: 10 }}>LIVE</div>
                <div style={{ color: 'var(--w-phosphor)', fontSize: 18 }}>{activeCount}</div>
              </div>
              <div>
                <div style={{ color: 'var(--w-text-3)', fontSize: 10 }}>LOCAL</div>
                <div style={{ color: 'var(--w-text-0)', fontSize: 18 }}>{localEntries.length}</div>
              </div>
              <div>
                <div style={{ color: 'var(--w-text-3)', fontSize: 10 }}>ENV</div>
                <div style={{ color: 'var(--w-amber)', fontSize: 18 }}>{envEntries.length}</div>
              </div>
              <div>
                <div style={{ color: 'var(--w-text-3)', fontSize: 10 }}>TOOLS</div>
                <div style={{ color: 'var(--w-text-0)', fontSize: 18 }}>{(sessionInfo?.tools || []).filter((t) => t.startsWith('mcp__')).length}</div>
              </div>
              <div>
                <div style={{ color: 'var(--w-text-3)', fontSize: 10 }}>AUTH</div>
                <div style={{ color: 'var(--w-amber)', fontSize: 18 }}>{runtime.filter((s) => s.status === 'needs-auth').length}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <dialog ref={dialogRef}>
        <form onSubmit={submit} style={{ minWidth: 480 }}>
          <h3 style={{ marginTop: 0, color: 'var(--w-phosphor)', font: '600 14px/1 var(--w-mono)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>// add MCP server</h3>

          <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>name</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required style={{ width: '100%' }} />

          <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>transport</label>
          <select value={form.transport} onChange={(e) => setForm({ ...form, transport: e.target.value })} style={{ width: '100%' }}>
            <option value="stdio">stdio (local command)</option>
            <option value="http">http</option>
            <option value="sse">sse</option>
          </select>

          {form.transport === 'stdio' ? (
            <>
              <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>command</label>
              <input value={form.command} onChange={(e) => setForm({ ...form, command: e.target.value })} placeholder="npx" required style={{ width: '100%' }} />
              <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>args (space-separated)</label>
              <input value={form.args} onChange={(e) => setForm({ ...form, args: e.target.value })} placeholder="-y @modelcontextprotocol/server-filesystem /tmp" style={{ width: '100%' }} />
              <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>env (JSON, optional)</label>
              <textarea value={form.envText} onChange={(e) => setForm({ ...form, envText: e.target.value })} placeholder='{"API_KEY": "..."}' style={{ width: '100%', minHeight: 80 }} />
            </>
          ) : (
            <>
              <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>url</label>
              <input value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://mcp.example.com/sse" required style={{ width: '100%' }} />
              <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>headers (JSON, optional)</label>
              <textarea value={form.headersText} onChange={(e) => setForm({ ...form, headersText: e.target.value })} placeholder='{"Authorization": "Bearer ..."}' style={{ width: '100%', minHeight: 80 }} />
            </>
          )}

          {error && <p style={{ color: 'var(--w-red)', font: '11.5px/1.4 var(--w-mono)' }}>{error}</p>}

          <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
            <Btn tone="ghost" onClick={() => dialogRef.current?.close()}>cancel</Btn>
            <Btn tone="primary" type="submit">[ + ] add</Btn>
          </div>
        </form>
      </dialog>
    </ScreenFrame>
  );
}
