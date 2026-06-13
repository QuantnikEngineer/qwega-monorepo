import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(ms) {
  return new Date(ms).toLocaleString();
}

function originalName(stored) {
  return stored.replace(/^\d+-/, '');
}

export function FilesPanel({ project, onSendToSkill }) {
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const load = async () => {
    try { setFiles(await api.listUploads(project.id)); }
    catch (e) { setError(e.message); }
  };

  useEffect(() => { setError(''); load(); /* eslint-disable-next-line */ }, [project.id]);

  const onPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true);
    try {
      await api.uploadFile(project.id, file);
      await load();
    } catch (e) { alert(`Upload failed: ${e.message}`); }
    setBusy(false);
  };

  const remove = async (f) => {
    if (!confirm(`Delete ${originalName(f.name)} from disk?`)) return;
    await api.deleteUpload(project.id, f.name);
    await load();
  };

  const sendToSkill = (skill, f) => {
    const msg = `Use the ${skill} skill on the uploaded file at \`${f.relativePath}\` (original name: ${originalName(f.name)}, size: ${f.size} bytes). Read it first, then proceed.`;
    onSendToSkill?.(msg);
  };

  return (
    <div className="panel-body">
      <h3 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Uploaded files</span>
        <div>
          <input ref={inputRef} type="file" style={{ display: 'none' }} onChange={onPick} />
          <button className="primary" onClick={() => inputRef.current?.click()} disabled={busy}>
            {busy ? 'Uploading…' : '+ Upload file'}
          </button>
        </div>
      </h3>
      <p style={{ color: 'var(--muted)', fontSize: 12 }}>
        Stored at <code>{project.path}/uploads/</code>. Claude reads them as relative paths
        like <code>uploads/&lt;name&gt;</code> from the project's <code>cwd</code>.
      </p>

      {error && <div className="msg error">{error}</div>}
      {files.length === 0 && <div className="empty">No files uploaded yet.</div>}

      {files.map((f) => (
        <div key={f.name} style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {originalName(f.name)}
              </div>
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>
                {formatSize(f.size)} · {formatDate(f.mtime)} ·{' '}
                <code>{f.relativePath}</code>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
              <button onClick={() => sendToSkill('sdlc-planning', f)}>→ sdlc-planning</button>
              <button onClick={() => sendToSkill('sdlc-orchestrator', f)}>→ sdlc-orchestrator</button>
              <a href={api.uploadDownloadUrl(project.id, f.name)} download>
                <button>Download</button>
              </a>
              <button onClick={() => remove(f)}>Delete</button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
