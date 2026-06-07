import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { ScreenFrame, Pill, Btn, KeyCap, S } from './ui.jsx';

const QUOTA_MB = 200;

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function timeAgo(ms) {
  const s = Math.floor((Date.now() - ms) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

// Absolute upload timestamp — local-time YYYY-MM-DD HH:MM. Pairs with
// timeAgo() in the file row so the user can read both "when exactly" and
// "how long ago" without parsing the 13-digit prefix off the stored name.
function formatUploadedAt(ms) {
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function originalName(stored) {
  return stored.replace(/^\d+-/, '');
}

const EXTENSIONS = ['pdf', 'png', 'jpg', 'md', 'csv', 'json', 'docx', 'pptx', 'log', 'zip'];

export function FilesPanel({ project, onSendToSkill }) {
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const load = async () => {
    try { setFiles(await api.listUploads(project.id)); }
    catch (e) { setError(e.message); }
  };

  useEffect(() => { setError(''); load(); /* eslint-disable-next-line */ }, [project.id]);

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try { await api.uploadFile(project.id, file); await load(); }
    catch (e) { alert(`upload failed: ${e.message}`); }
    setBusy(false);
  };

  const onPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    await upload(file);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) upload(file);
  };

  const remove = async (f) => {
    if (!confirm(`delete ${originalName(f.name)} from disk?`)) return;
    await api.deleteUpload(project.id, f.name);
    await load();
  };

  const totalBytes = files.reduce((s, f) => s + f.size, 0);
  const usedMB = totalBytes / 1024 / 1024;
  const pct = Math.min(100, (usedMB / QUOTA_MB) * 100);

  return (
    <ScreenFrame
      breadcrumb={<><S c="var(--w-phosphor)">~/{project.name}</S> ─ files</>}
      title="Uploaded files"
      subtitle={
        <>
          Stored at <S c="var(--w-cyan)">{project.path}\uploads\</S>. Claude reads them as relative paths like <S c="var(--w-amber)">uploads/&lt;name&gt;</S> from the project's cwd.
        </>
      }
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <input ref={inputRef} type="file" style={{ display: 'none' }} onChange={onPick} />
          <Btn tone="primary" onClick={() => inputRef.current?.click()} disabled={busy}>
            {busy ? 'uploading…' : '[ + ] upload file'}
          </Btn>
        </div>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, minHeight: 500 }}>
        {files.length === 0 ? (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            style={{
              border: `1px dashed ${dragOver ? 'var(--w-line-hot)' : 'var(--w-line-strong)'}`,
              borderRadius: 4,
              background: dragOver
                ? 'var(--w-phosphor-veil)'
                : 'repeating-linear-gradient(135deg, transparent 0 22px, var(--w-phosphor-veil) 22px 23px)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
          >
            <div style={{ textAlign: 'center', padding: 40 }}>
              <pre style={{ margin: 0, color: 'var(--w-phosphor)', font: '11px/1.05 var(--w-mono)', textShadow: '0 0 10px var(--w-phosphor-glow)', marginBottom: 18 }}>
{`  ┌─────────────────────┐
  │   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒   │
  │   ▒  drop  zone ▒   │
  │   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒   │
  └─────────────────────┘
            ↓`}
              </pre>
              <div style={{ color: 'var(--w-text-0)', font: '16px/1.3 var(--w-mono)', marginBottom: 8 }}>
                drop files anywhere<span className="w-caret" />
              </div>
              <div style={{ color: 'var(--w-text-2)', font: '12px/1.4 var(--w-mono)' }}>
                or click to pick · paste an image with <KeyCap>⌘V</KeyCap>
              </div>
              <div style={{ marginTop: 18, display: 'flex', justifyContent: 'center', gap: 6, flexWrap: 'wrap', maxWidth: 480, margin: '18px auto 0' }}>
                {EXTENSIONS.map((e) => <Pill key={e}>.{e}</Pill>)}
              </div>
            </div>
          </div>
        ) : (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            style={{
              border: dragOver ? '1px dashed var(--w-phosphor)' : '1px solid var(--w-line)',
              borderRadius: 3,
              background: 'var(--w-bg-2)',
              padding: '8px 0',
              display: 'flex', flexDirection: 'column',
            }}
          >
            {files.map((f, i) => (
              <div key={f.name} style={{
                padding: '12px 16px',
                borderTop: i ? '1px dashed var(--w-line)' : 'none',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flex: 1 }}>
                  <span style={{ color: 'var(--w-cyan)', font: '12px/1 var(--w-mono)' }}>▤</span>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ color: 'var(--w-text-0)', font: '500 12.5px/1.3 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{originalName(f.name)}</div>
                    <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>
                      {formatSize(f.size)} · <S c="var(--w-text-2)">{f.relativePath}</S>
                    </div>
                    <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>
                      uploaded <S c="var(--w-cyan)">{formatUploadedAt(f.mtime)}</S> · {timeAgo(f.mtime)} ago
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <Btn tone="ghost" style={{ padding: '4px 10px' }} onClick={() => onSendToSkill?.(`Use the sdlc-planning skill on the uploaded file at \`${f.relativePath}\` (original name: ${originalName(f.name)}). Read it first, then proceed.`)}>→ planning</Btn>
                  <Btn tone="ghost" style={{ padding: '4px 10px' }} onClick={() => onSendToSkill?.(`Use the sdlc-orchestrator skill on the uploaded file at \`${f.relativePath}\` (original name: ${originalName(f.name)}). Read it first, then proceed.`)}>→ orchestrator</Btn>
                  <Btn
                    tone="ghost"
                    style={{ padding: '4px 10px' }}
                    onClick={() => api.downloadUpload(project.id, f.name, originalName(f.name)).catch((e) => alert(`download failed: ${e.message}`))}
                  >[ ⤓ ]</Btn>
                  <Btn tone="danger" style={{ padding: '4px 10px' }} onClick={() => remove(f)}>[ del ]</Btn>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Side panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '14px 16px' }}>
            <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 10 }}>// quota</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
              <span style={{ color: 'var(--w-text-0)', font: '20px/1 var(--w-display)' }}>{usedMB.toFixed(1)}<span style={{ color: 'var(--w-text-3)', fontSize: 12 }}> / {QUOTA_MB} MB</span></span>
              <span style={{ color: 'var(--w-phosphor)' }}>{pct.toFixed(1)}%</span>
            </div>
            <div style={{ height: 4, background: 'var(--w-bg-1)', border: '1px solid var(--w-line)', borderRadius: 2 }}>
              <div style={{ width: `${pct}%`, height: '100%', background: 'var(--w-phosphor)' }} />
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: 'var(--w-text-2)', lineHeight: 1.6 }}>
              files persist per-project. delete from disk to remove from claude's view.
            </div>
          </div>

          <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '14px 16px' }}>
            <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 10 }}>// hint</div>
            <div style={{ color: 'var(--w-text-1)', font: '11.5px/1.6 var(--w-mono)' }}>
              <span style={{ color: 'var(--w-phosphor)' }}>$</span> reference an upload in chat like:
              <pre style={{ margin: '8px 0 0', padding: '8px 10px', background: 'var(--w-bg-1)', borderRadius: 3, color: 'var(--w-syn-str)', font: '11px/1.5 var(--w-mono)', border: '1px solid var(--w-line)' }}>
                <S c="var(--w-text-3)">@</S>uploads/<S c="var(--w-cyan)">filename.pdf</S>
              </pre>
            </div>
          </div>

          {error && <div style={{ color: 'var(--w-red)', font: '11.5px/1.4 var(--w-mono)', padding: '10px 14px', border: '1px solid rgba(255,71,87,0.3)', borderRadius: 3 }}>{error}</div>}
        </div>
      </div>
    </ScreenFrame>
  );
}
