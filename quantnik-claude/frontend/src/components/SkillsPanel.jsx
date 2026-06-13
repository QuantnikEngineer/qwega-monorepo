import React, { useEffect, useState } from 'react';
import { api } from '../lib/api.js';

const TEMPLATE = `---
name: my-skill
description: One-line description shown when Claude decides whether to use this skill
---

# my-skill

Steps for Claude to follow when invoking this skill.
`;

export function SkillsPanel({ project }) {
  const [skills, setSkills] = useState([]);
  const [inherited, setInherited] = useState({ user: [], plugins: [] });
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState('');
  const [newName, setNewName] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null);

  const flash = (kind, text) => {
    setStatus({ kind, text });
    setTimeout(() => setStatus((s) => (s && s.text === text ? null : s)), 3000);
  };

  const load = async () => {
    try {
      const list = await api.listSkills(project.id);
      setSkills(list);
    } catch (e) { flash('error', `Load failed: ${e.message}`); }
    try { setInherited(await api.inheritedSkills()); } catch { /* ignore */ }
  };

  useEffect(() => { load(); setSelected(null); setContent(''); setStatus(null); }, [project.id]);

  const open = async (name) => {
    try {
      setSelected(name);
      const s = await api.getSkill(project.id, name);
      setContent(s.content);
    } catch (e) { flash('error', `Open failed: ${e.message}`); }
  };

  const save = async () => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await api.saveSkill(project.id, selected, content);
      flash('ok', `Saved "${selected}"`);
      await load();
    } catch (e) { flash('error', `Save failed: ${e.message}`); }
    setBusy(false);
  };

  const create = async () => {
    if (busy) return;
    const name = newName.trim();
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
      flash('error', 'Name must match [a-zA-Z0-9_-]+');
      return;
    }
    setBusy(true);
    try {
      await api.saveSkill(project.id, name, TEMPLATE.replaceAll('my-skill', name));
      setNewName('');
      await load();
      await open(name);
      flash('ok', `Created "${name}"`);
    } catch (e) { flash('error', `Create failed: ${e.message}`); }
    setBusy(false);
  };

  const remove = async (name) => {
    if (!confirm(`Delete skill "${name}"?`)) return;
    try {
      await api.deleteSkill(project.id, name);
      if (selected === name) { setSelected(null); setContent(''); }
      await load();
      flash('ok', `Deleted "${name}"`);
    } catch (e) { flash('error', `Delete failed: ${e.message}`); }
  };

  return (
    <div className="panel-body">
      <h3>Skills</h3>
      <p style={{ color: 'var(--muted)' }}>
        Skills live in <code>{project.path}/.claude/skills/&lt;name&gt;/SKILL.md</code> and are picked
        up by Claude Code automatically when you chat in this project.
      </p>

      <div className="row">
        <input
          placeholder="new-skill-name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); create(); } }}
        />
        <button className="primary" onClick={create} disabled={busy}>
          {busy ? 'Creating…' : 'Create'}
        </button>
      </div>

      {status && (
        <div style={{
          marginTop: 10,
          padding: '6px 10px',
          borderRadius: 6,
          fontSize: 13,
          background: status.kind === 'ok' ? 'rgba(127,214,163,0.15)' : 'rgba(240,128,128,0.15)',
          color: status.kind === 'ok' ? '#7fd6a3' : '#ff8080',
          border: `1px solid ${status.kind === 'ok' ? '#7fd6a3' : '#ff8080'}`,
        }}>
          {status.text}
        </div>
      )}

      <label>Existing skills</label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {skills.length === 0 && <span style={{ color: 'var(--muted)' }}>None</span>}
        {skills.map((s) => (
          <span key={s.name} style={{ display: 'inline-flex', gap: 4 }}>
            <button
              onClick={() => open(s.name)}
              style={{ background: selected === s.name ? 'var(--accent)' : undefined, color: selected === s.name ? '#1a0f2e' : undefined }}
            >
              {s.name}
            </button>
            <button onClick={() => remove(s.name)}>×</button>
          </span>
        ))}
      </div>

      {selected && (
        <>
          <label>SKILL.md for "{selected}"</label>
          <textarea value={content} onChange={(e) => setContent(e.target.value)} />
          <div className="row" style={{ marginTop: 8 }}>
            <button className="primary" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : 'Save'}
            </button>
          </div>
        </>
      )}

      <h3 style={{ marginTop: 32 }}>Inherited from ~/.claude</h3>
      <p style={{ color: 'var(--muted)', fontSize: 12 }}>
        Read-only. Claude can invoke these in any project because the backend passes
        <code> settingSources: ['user', 'project', 'local']</code> to the Agent SDK.
        Edit them via your normal Claude Code config; they'll update here on refresh.
      </p>

      <label>User skills ({inherited.user?.length || 0})</label>
      {(inherited.user || []).map((s) => (
        <div key={s.name} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
          <div><strong>{s.name}</strong></div>
          {s.description && <small style={{ color: 'var(--muted)' }}>{s.description}</small>}
        </div>
      ))}

      <label style={{ marginTop: 16 }}>Plugin skills ({inherited.plugins?.length || 0})</label>
      {(inherited.plugins || []).map((s) => (
        <div key={`${s.plugin}/${s.name}`} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
          <div><strong>{s.name}</strong> <small style={{ color: 'var(--muted)' }}>· {s.plugin}</small></div>
          {s.description && <small style={{ color: 'var(--muted)' }}>{s.description}</small>}
        </div>
      ))}
    </div>
  );
}
