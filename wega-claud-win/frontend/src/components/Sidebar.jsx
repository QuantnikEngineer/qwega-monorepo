import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api.js';
import { QuantnikLockup, Pill, KeyCap, Btn, formatModel } from './ui.jsx';

const THEMES = [
  { id: 'cyber-dark',   label: 'cyber',   polarity: 'dark',  swatch: '#00ff9c', bg: '#04070a' },
  { id: 'cyber-light',  label: 'cyber',   polarity: 'light', swatch: '#00875a', bg: '#eef2ec' },
  { id: 'sunset-dark',  label: 'sunset',  polarity: 'dark',  swatch: '#ff6a3d', bg: '#110620' },
  { id: 'sunset-light', label: 'sunset',  polarity: 'light', swatch: '#d94e2e', bg: '#fbf6ee' },
];

export function Sidebar({
  projects, activeId, onSelect, onChanged, theme, onChangeTheme,
  user = null,
}) {
  const isAdmin = !!user?.isAdmin;
  const navigate = useNavigate();
  const dialogRef = useRef(null);
  const [name, setName] = useState('');
  const [path, setPath] = useState('');
  const [error, setError] = useState('');

  const openNew = () => {
    setName(''); setPath(''); setError('');
    dialogRef.current?.showModal();
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.createProject({ name: name.trim(), path: path.trim() || undefined });
      dialogRef.current?.close();
      onChanged();
    } catch (e) { setError(e.message); }
  };

  const del = async (id, ev) => {
    ev.stopPropagation();
    if (!confirm('Delete this project? Files on disk are kept.')) return;
    await api.deleteProject(id);
    onChanged();
  };

  return (
    <aside style={{
      width: 266, flex: '0 0 266px',
      borderRight: '1px solid var(--w-line)',
      background: 'var(--w-bg-1)',
      display: 'flex', flexDirection: 'column',
      padding: '18px 0 0',
      overflow: 'hidden',
    }}>
      <div
        onClick={() => navigate('/')}
        title="back to home"
        style={{
          padding: '0 18px 16px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: 0,
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <QuantnikLockup mark={38} type={16.5} />
        <span style={{ color: '#aab2bf', font: '700 10.5px/1 var(--w-mono)', letterSpacing: '0.16em', textTransform: 'uppercase' }}>Workbench</span>
      </div>

      <div style={{ padding: '0 16px 16px' }}>
        <button onClick={openNew} style={{
          width: '100%',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '11px 13px',
          background: '#f5f8ff',
          border: '1px dashed #c7d3ec',
          color: 'var(--w-phosphor)',
          font: '600 13.5px/1 var(--w-mono)',
          cursor: 'pointer',
          borderRadius: 11,
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><span style={{ fontSize: 15, fontWeight: 700 }}>+</span> New project</span>
          <KeyCap>⌘N</KeyCap>
        </button>
      </div>

      <div style={{ padding: '0 18px 10px', color: '#9aa4b2', font: '700 11px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', display: 'flex', justifyContent: 'space-between' }}>
        <span>Projects</span>
        <span style={{ color: '#8a94a3', background: '#f1f3f7', borderRadius: 6, padding: '1px 7px' }}>{projects.length}</span>
      </div>

      {/* Admin visibility is enforced by the backend: admins always receive
          every project across the workbench. */}
      {isAdmin && (
        <div style={{
          padding: '0 18px 10px',
          display: 'flex', alignItems: 'center', gap: 6,
          font: '10px/1 var(--w-mono)',
          letterSpacing: '0.1em', textTransform: 'uppercase',
          color: '#9aa4b2',
        }}>
          <span style={{ color: '#f59e0b' }}>Admin:</span>
          <span style={scopePillStyle(true)}>all projects</span>
        </div>
      )}

      <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', flex: 1 }}>
        {projects.length === 0 && (
          <div style={{ padding: '20px 12px', color: 'var(--w-text-3)', font: '11.5px/1.4 var(--w-mono)', textAlign: 'center' }}>
            no projects yet.<br />click [+] above.
          </div>
        )}
        {projects.map((p) => {
          const isActive = p.id === activeId;
          return (
            <div
              key={p.id}
              onClick={() => onSelect(p.id)}
              style={{
                padding: '13px 14px',
                background: isActive ? 'linear-gradient(180deg,#f5f9ff,#eff5ff)' : '#fff',
                border: `1px solid ${isActive ? '#d3e0ff' : 'transparent'}`,
                borderLeft: `3px solid ${isActive ? 'var(--w-phosphor)' : 'transparent'}`,
                borderRadius: 13,
                boxShadow: isActive ? '0 1px 2px rgba(37,99,235,.06)' : 'none',
                cursor: 'pointer',
                position: 'relative',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                <span style={{ color: isActive ? '#1b2330' : 'var(--w-text-0)', font: '700 14.5px/1.2 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                  {isActive && <span style={{ marginRight: 4, color: 'var(--w-phosphor)' }}>▸</span>}
                  {p.name}
                </span>
                <span
                  onClick={(e) => del(p.id, e)}
                  title="Delete project"
                  style={{ color: 'var(--w-text-3)', cursor: 'pointer', padding: '0 4px', fontSize: 14, lineHeight: 1 }}
                >×</span>
              </div>
              <div style={{ font: '11.5px/1.3 var(--w-mono)', color: '#94a0b4', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 3 }} title={p.path}>
                {p.path}
              </div>
              {isActive && (
                <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <Pill tone="phosphor" dot>live</Pill>
                  <Pill>{formatModel(p.model || 'opus-4-7')}</Pill>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ padding: '14px 18px 16px', borderTop: '1px solid #eef1f6', display: 'flex', flexDirection: 'column', gap: 11 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--w-text-2)', font: '10.5px/1.4 var(--w-mono)' }}>
          <span>build</span>
          <span>v0.4.2-α</span>
        </div>
        <div style={{ display: 'none' }}>
          <span style={{ color: 'var(--w-text-2)', font: '10.5px/1 var(--w-mono)' }}>theme</span>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            {THEMES.map((t) => {
              const active = t.id === theme;
              return (
                <div
                  key={t.id}
                  onClick={() => onChangeTheme?.(t.id)}
                  title={`${t.label} · ${t.polarity}`}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '4px 6px',
                    border: active ? '1px solid var(--w-phosphor)' : '1px solid var(--w-line)',
                    background: active ? 'var(--w-phosphor-veil)' : 'transparent',
                    borderRadius: 3,
                    cursor: 'pointer',
                  }}
                >
                  <span style={{
                    width: 10, height: 10,
                    borderRadius: 2,
                    background: t.bg,
                    boxShadow: `inset 0 0 0 2px ${t.swatch}`,
                    flex: '0 0 auto',
                  }} />
                  <span style={{
                    font: '9.5px/1 var(--w-mono)',
                    color: active ? 'var(--w-phosphor)' : 'var(--w-text-2)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>
                    {t.label} <span style={{ color: 'var(--w-text-3)' }}>{t.polarity[0]}</span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--w-text-2)', font: '10.5px/1.4 var(--w-mono)' }}>
          <span><span style={{ color: 'var(--w-phosphor)' }}>●</span> agent online</span>
          <span>{user?.name || user?.email || 'Quantnik'}</span>
        </div>
      </div>

      <dialog ref={dialogRef}>
        <form onSubmit={submit}>
          <h3 style={{ marginTop: 0, color: 'var(--w-phosphor)', font: '600 14px/1 var(--w-mono)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>// new project</h3>
          <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>name (a-z, 0-9, _ -)</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required style={{ width: '100%' }} />
          <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>path (optional)</label>
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/absolute/path" style={{ width: '100%' }} />
          {error && <p style={{ color: 'var(--w-red)', font: '11.5px/1.4 var(--w-mono)' }}>{error}</p>}
          <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
            <Btn tone="ghost" onClick={() => dialogRef.current?.close()}>cancel</Btn>
            <Btn tone="primary" type="submit">create</Btn>
          </div>
        </form>
      </dialog>
    </aside>
  );
}

// Pill style for the admin scope toggle. Active pill is phosphor-highlighted.
function scopePillStyle(active) {
  return {
    background: active ? 'var(--w-phosphor-veil)' : 'transparent',
    border: `1px solid ${active ? 'var(--w-phosphor)' : 'var(--w-line)'}`,
    color: active ? 'var(--w-phosphor)' : 'var(--w-text-2)',
    font: '10px/1 var(--w-mono)',
    letterSpacing: '0.1em',
    padding: '3px 7px',
    borderRadius: 2,
    cursor: 'pointer',
    textTransform: 'uppercase',
  };
}
