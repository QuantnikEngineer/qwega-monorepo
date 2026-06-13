import React, { useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { Logo } from './Logo.jsx';

export function Sidebar({ projects, activeId, onSelect, onChanged }) {
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
    <aside className="sidebar">
      <header>
        <Logo />
        <button onClick={openNew}>+ New</button>
      </header>
      <div className="projects">
        {projects.length === 0 && <div className="empty">No projects yet.</div>}
        {projects.map((p) => (
          <div
            key={p.id}
            className={`project ${activeId === p.id ? 'active' : ''}`}
            onClick={() => onSelect(p.id)}
          >
            <div>
              <div>{p.name}</div>
              <small>{p.path}</small>
            </div>
            <button onClick={(e) => del(p.id, e)} title="Delete">×</button>
          </div>
        ))}
      </div>

      <dialog ref={dialogRef}>
        <form onSubmit={submit}>
          <h3 style={{ marginTop: 0 }}>New project</h3>
          <label>Name (a-z, 0-9, _ -)</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
          <label>Path (optional — defaults to backend/data/projects/&lt;name&gt;)</label>
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/absolute/path" />
          {error && <p style={{ color: '#ff8080' }}>{error}</p>}
          <div className="row" style={{ marginTop: 16 }}>
            <button type="button" onClick={() => dialogRef.current?.close()}>Cancel</button>
            <button type="submit" className="primary">Create</button>
          </div>
        </form>
      </dialog>
    </aside>
  );
}
