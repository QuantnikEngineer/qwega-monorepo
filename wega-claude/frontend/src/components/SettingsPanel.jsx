import React, { useEffect, useState } from 'react';
import { api } from '../lib/api.js';

const MODELS = [
  'claude-opus-4-7',
  'claude-sonnet-4-6',
  'claude-haiku-4-5-20251001',
];

const PERMISSION_MODES = ['default', 'acceptEdits', 'plan', 'bypassPermissions'];

export function SettingsPanel({ project, onChanged }) {
  const [model, setModel] = useState(project.model || 'claude-opus-4-7');
  const [permMode, setPermMode] = useState(project.permission_mode || 'acceptEdits');
  const [settingsJson, setSettingsJson] = useState('');
  const [hooksJson, setHooksJson] = useState('');
  const [lastInit, setLastInit] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    setModel(project.model || 'claude-opus-4-7');
    setPermMode(project.permission_mode || 'acceptEdits');
    setError('');
    api.getSettings(project.id).then((s) => {
      setSettingsJson(JSON.stringify(s, null, 2));
      setHooksJson(JSON.stringify(s.hooks || {}, null, 2));
    });
    api.lastSessionInit(project.id).then(setLastInit).catch(() => {});
  }, [project.id]);

  const saveProject = async () => {
    await api.updateProject(project.id, { model, permission_mode: permMode });
    onChanged?.();
  };

  const saveSettings = async () => {
    setError('');
    try {
      const data = JSON.parse(settingsJson);
      await api.saveSettings(project.id, data);
      setHooksJson(JSON.stringify(data.hooks || {}, null, 2));
    } catch (e) { setError(`settings.json: ${e.message}`); }
  };

  const saveHooks = async () => {
    setError('');
    try {
      const hooks = JSON.parse(hooksJson);
      await api.saveHooks(project.id, hooks);
      const s = await api.getSettings(project.id);
      setSettingsJson(JSON.stringify(s, null, 2));
    } catch (e) { setError(`hooks: ${e.message}`); }
  };

  return (
    <div className="panel-body">
      <h3>Project settings</h3>
      <label>Model</label>
      <select value={model} onChange={(e) => setModel(e.target.value)}>
        {MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      <label>Permission mode</label>
      <select value={permMode} onChange={(e) => setPermMode(e.target.value)}>
        {PERMISSION_MODES.map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      <div className="row" style={{ marginTop: 12 }}>
        <button className="primary" onClick={saveProject}>Save project</button>
      </div>

      <h3 style={{ marginTop: 24 }}>Hooks (.claude/settings.json → hooks)</h3>
      <p style={{ color: 'var(--muted)', fontSize: 12 }}>
        See Claude Code docs for hook event schema (PreToolUse, PostToolUse, UserPromptSubmit, etc.).
      </p>
      <textarea value={hooksJson} onChange={(e) => setHooksJson(e.target.value)} />
      <div className="row" style={{ marginTop: 8 }}>
        <button className="primary" onClick={saveHooks}>Save hooks</button>
      </div>

      <h3 style={{ marginTop: 24 }}>Raw settings.json</h3>
      <textarea value={settingsJson} onChange={(e) => setSettingsJson(e.target.value)} />
      <div className="row" style={{ marginTop: 8 }}>
        <button className="primary" onClick={saveSettings}>Save settings.json</button>
      </div>

      <h3 style={{ marginTop: 24 }}>Loaded in last session</h3>
      <p style={{ color: 'var(--muted)', fontSize: 12 }}>
        Ground truth reported by the Agent SDK at the start of the most recent chat turn.
        Send a message first; this populates after the first turn. MCP servers live in the
        dedicated <strong>MCP</strong> tab.
      </p>
      {!lastInit && <div style={{ color: 'var(--muted)' }}>No session yet. Send a message in the chat tab.</div>}
      {lastInit && (
        <>
          <label>Agents ({lastInit.agents?.length || 0})</label>
          <div style={{ color: 'var(--muted)', fontSize: 12 }}>
            {(lastInit.agents || []).join(', ') || 'none'}
          </div>

          <label style={{ marginTop: 16 }}>Tools ({lastInit.tools?.length || 0})</label>
          <div style={{ color: 'var(--muted)', fontSize: 12, wordBreak: 'break-all' }}>
            {(lastInit.tools || []).join(', ') || 'none'}
          </div>
        </>
      )}

      {error && <p style={{ color: '#ff8080' }}>{error}</p>}
    </div>
  );
}
