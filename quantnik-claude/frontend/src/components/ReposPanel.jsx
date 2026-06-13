import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';

function statusLabel(repo) {
  if (!repo.exists) return { text: 'path missing', color: '#f08080' };
  if (!repo.isGit) return { text: 'directory (not a git repo)', color: '#f0c060' };
  return { text: 'git repo', color: '#7fd6a3' };
}

export function ReposPanel({ project }) {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: '', path: '', remoteUrl: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef(null);

  const load = async () => {
    try { setList(await api.listRepos(project.id)); }
    catch (e) { setError(e.message); }
  };

  useEffect(() => { setError(''); load(); /* eslint-disable-next-line */ }, [project.id]);

  const openAdd = () => {
    setForm({ name: '', path: '', remoteUrl: '' });
    setError('');
    dialogRef.current?.showModal();
  };

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await api.addRepo(project.id, {
        name: form.name.trim(),
        path: form.path.trim(),
        remoteUrl: form.remoteUrl.trim() || undefined,
      });
      dialogRef.current?.close();
      await load();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const remove = async (repo) => {
    if (!confirm(`Remove "${repo.name}" from this project? Files on disk are NOT deleted.`)) return;
    await api.deleteRepo(project.id, repo.id);
    await load();
  };

  const clone = async (repo) => {
    if (!confirm(`Clone ${repo.remote_url} into ${repo.path}?`)) return;
    setBusy(true);
    try {
      await api.cloneRepo(project.id, repo.id);
      await load();
    } catch (e) { alert(`Clone failed: ${e.message}`); }
    setBusy(false);
  };

  return (
    <div className="panel-body">
      <h3 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Repositories</span>
        <button className="primary" onClick={openAdd}>+ Add repo</button>
      </h3>
      <p style={{ color: 'var(--muted)', fontSize: 12 }}>
        Each configured repo path is passed to the Claude Agent SDK as an
        <code> additionalDirectories</code> entry, so Claude can read and edit across all of
        them in a single conversation. The project's own workspace
        (<code>{project.path}</code>) is always Claude's <code>cwd</code>.
      </p>

      {list.length === 0 && <div className="empty">No repos configured for this project.</div>}

      {list.map((repo) => {
        const s = statusLabel(repo);
        return (
          <div key={repo.id} style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong>{repo.name}</strong>{' '}
                <small style={{ color: s.color }}>· {s.text}</small>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {repo.remote_url && !repo.exists && (
                  <button onClick={() => clone(repo)} disabled={busy}>Clone</button>
                )}
                <button onClick={() => remove(repo)}>Remove</button>
              </div>
            </div>
            <div style={{ color: 'var(--muted)', fontSize: 12, marginTop: 4 }}>
              <div>path: <code>{repo.path}</code></div>
              {repo.remote_url && <div>remote: <code>{repo.remote_url}</code></div>}
            </div>
          </div>
        );
      })}

      <dialog ref={dialogRef}>
        <form onSubmit={submit} style={{ minWidth: 480 }}>
          <h3 style={{ marginTop: 0 }}>Add repository</h3>

          <label>Display name</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="my-service"
            required
          />

          <label>Absolute local path</label>
          <input
            value={form.path}
            onChange={(e) => setForm({ ...form, path: e.target.value })}
            placeholder="/Users/you/code/my-service"
            required
          />

          <label>Remote URL (optional — enables Clone button if path doesn't exist yet)</label>
          <input
            value={form.remoteUrl}
            onChange={(e) => setForm({ ...form, remoteUrl: e.target.value })}
            placeholder="git@github.com:org/my-service.git"
          />

          {error && <p style={{ color: '#ff8080' }}>{error}</p>}

          <div className="row" style={{ marginTop: 16 }}>
            <button type="button" onClick={() => dialogRef.current?.close()}>Cancel</button>
            <button type="submit" className="primary" disabled={busy}>
              {busy ? 'Adding…' : 'Add'}
            </button>
          </div>
        </form>
      </dialog>
    </div>
  );
}
