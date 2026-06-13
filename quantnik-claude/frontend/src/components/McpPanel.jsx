import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';

const EMPTY_FORM = {
  name: '',
  transport: 'stdio',
  command: '',
  args: '',
  envText: '',
  url: '',
  headersText: '',
};

function statusColor(s) {
  if (s === 'connected') return '#7fd6a3';
  if (s === 'needs-auth') return '#f0c060';
  if (s === 'failed') return '#f08080';
  return 'var(--muted)';
}

export function McpPanel({ project }) {
  const [data, setData] = useState({ local: {}, runtime: [] });
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const dialogRef = useRef(null);

  const load = async () => {
    try { setData(await api.listMcp(project.id)); }
    catch (e) { setError(e.message); }
  };

  useEffect(() => { setError(''); load(); /* eslint-disable-next-line */ }, [project.id]);

  const openAdd = () => {
    setForm(EMPTY_FORM);
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
    if (!confirm(`Delete MCP server "${name}"? You may need to start a fresh chat for changes to take effect.`)) return;
    await api.deleteMcp(project.id, name);
    await load();
  };

  const localEntries = Object.entries(data.local || {});

  return (
    <div className="panel-body">
      <h3 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>MCP servers</span>
        <button className="primary" onClick={openAdd}>+ Add server</button>
      </h3>

      <h4 style={{ marginTop: 16, marginBottom: 4 }}>Live connections (last session)</h4>
      <p style={{ color: 'var(--muted)', fontSize: 12, marginTop: 0 }}>
        Reported by the Claude Agent SDK at the start of the most recent chat turn — includes
        your Claude.ai-hosted MCPs (Atlassian, Linear, Notion, etc.). To re-authenticate one,
        use <code>claude</code> in a terminal.
      </p>
      {data.runtime.length === 0 && (
        <div style={{ color: 'var(--muted)' }}>No session yet. Send a message in the chat tab.</div>
      )}
      {data.runtime.map((s) => (
        <div key={s.name} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between' }}>
          <strong>{s.name}</strong>
          <span style={{ color: statusColor(s.status) }}>{s.status}</span>
        </div>
      ))}

      <h4 style={{ marginTop: 24, marginBottom: 4 }}>Local servers (this project)</h4>
      <p style={{ color: 'var(--muted)', fontSize: 12, marginTop: 0 }}>
        Stored in <code>{project.path}/.claude/settings.json</code> under <code>mcpServers</code>.
        Added entries become active on the next chat turn.
      </p>
      {localEntries.length === 0 && (
        <div style={{ color: 'var(--muted)' }}>No local servers defined for this project.</div>
      )}
      {localEntries.map(([name, cfg]) => (
        <div key={name} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>{name}</strong>
            <button onClick={() => remove(name)}>Delete</button>
          </div>
          <pre style={{ margin: '6px 0 0', color: 'var(--muted)', fontSize: 12, whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(cfg, null, 2)}
          </pre>
        </div>
      ))}

      <dialog ref={dialogRef}>
        <form onSubmit={submit} style={{ minWidth: 480 }}>
          <h3 style={{ marginTop: 0 }}>Add MCP server</h3>

          <label>Name (a-z, 0-9, _ -)</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />

          <label>Transport</label>
          <select value={form.transport} onChange={(e) => setForm({ ...form, transport: e.target.value })}>
            <option value="stdio">stdio (local command)</option>
            <option value="http">http</option>
            <option value="sse">sse</option>
          </select>

          {form.transport === 'stdio' ? (
            <>
              <label>Command</label>
              <input
                value={form.command}
                onChange={(e) => setForm({ ...form, command: e.target.value })}
                placeholder="npx"
                required
              />
              <label>Args (space-separated)</label>
              <input
                value={form.args}
                onChange={(e) => setForm({ ...form, args: e.target.value })}
                placeholder="-y @modelcontextprotocol/server-filesystem /tmp"
              />
              <label>Env (JSON, optional)</label>
              <textarea
                value={form.envText}
                onChange={(e) => setForm({ ...form, envText: e.target.value })}
                placeholder='{"API_KEY": "..."}'
                style={{ minHeight: 80 }}
              />
            </>
          ) : (
            <>
              <label>URL</label>
              <input
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://mcp.example.com/sse"
                required
              />
              <label>Headers (JSON, optional)</label>
              <textarea
                value={form.headersText}
                onChange={(e) => setForm({ ...form, headersText: e.target.value })}
                placeholder='{"Authorization": "Bearer ..."}'
                style={{ minHeight: 80 }}
              />
            </>
          )}

          {error && <p style={{ color: '#ff8080' }}>{error}</p>}

          <div className="row" style={{ marginTop: 16 }}>
            <button type="button" onClick={() => dialogRef.current?.close()}>Cancel</button>
            <button type="submit" className="primary">Add</button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
