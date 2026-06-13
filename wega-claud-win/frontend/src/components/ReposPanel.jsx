import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api.js';
import { ScreenFrame, Pill, Btn, S } from './ui.jsx';

function formatSize(bytes) {
  if (bytes == null) return null;
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}K`;
  return `${(bytes / 1024 / 1024).toFixed(1)}M`;
}

function FileTreeLine({ depth, name, kind, meta, last }) {
  const indent = '│  '.repeat(Math.max(0, depth));
  const tee = depth === 0 ? '' : (last ? '└─ ' : '├─ ');
  const color = kind === 'dir' ? 'var(--w-cyan)' : 'var(--w-text-1)';
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1px 0' }}>
      <div style={{ display: 'flex', gap: 0, font: '11.5px/1.55 var(--w-mono)' }}>
        <span style={{ color: 'var(--w-text-3)' }}>{indent}{tee}</span>
        <span style={{ color }}>{kind === 'dir' ? `${name}/` : name}</span>
      </div>
      {meta && <span style={{ color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)' }}>{meta}</span>}
    </div>
  );
}

function langGuess(name) {
  if (/web|frontend|react|vite|next/i.test(name)) return 'react · vite';
  if (/backend|api|server/i.test(name)) return 'node · express';
  if (/terraform|infra/i.test(name)) return 'hcl · iac';
  if (/design|figma/i.test(name)) return 'design';
  return 'repo';
}

function RepoCard({ repo, projectId, onClone, onRemove, busy }) {
  const [tree, setTree] = useState(null);
  useEffect(() => {
    if (!repo.exists) { setTree(null); return; }
    let cancelled = false;
    api.repoTree(projectId, repo.id).then((t) => { if (!cancelled) setTree(t); }).catch(() => {});
    return () => { cancelled = true; };
  }, [projectId, repo.id, repo.exists]);

  const status = !repo.exists ? 'missing' : repo.isGit ? 'git' : 'dir';
  const tone = status === 'missing' ? 'red' : status === 'git' ? 'phosphor' : 'amber';
  const border = status === 'missing' ? 'var(--w-red)' : status === 'git' ? 'var(--w-phosphor)' : 'var(--w-amber)';
  const branch = tree?.branch || 'main';

  return (
    <div style={{
      border: '1px solid var(--w-line)',
      borderLeft: `2px solid ${border}`,
      borderRadius: 3,
      background: 'var(--w-bg-2)',
      display: 'flex', flexDirection: 'column',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--w-line)', background: 'var(--w-bg-3)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ color: border, font: '13px/1 var(--w-mono)' }}>▸</span>
            <span style={{ color: 'var(--w-text-0)', font: '600 14px/1 var(--w-mono)' }}>{repo.name}</span>
            <Pill tone="cyan">{langGuess(repo.name)}</Pill>
          </div>
          <div style={{ color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={repo.path}>
            {repo.path}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          <Pill tone={tone} dot>{status === 'missing' ? 'missing' : branch}</Pill>
        </div>
      </div>

      <div style={{ padding: '10px 14px', borderBottom: '1px dashed var(--w-line)', background: 'var(--w-bg-1)', flex: 1, minHeight: 140 }}>
        {!repo.exists && (
          <div style={{ color: 'var(--w-text-3)', font: '11.5px/1.4 var(--w-mono)' }}>
            path doesn't exist on disk{repo.remote_url ? '. clone to populate.' : '.'}
          </div>
        )}
        {repo.exists && tree && tree.entries.length === 0 && (
          <div style={{ color: 'var(--w-text-3)', font: '11.5px/1.4 var(--w-mono)' }}>empty.</div>
        )}
        {repo.exists && tree && tree.entries.length > 0 && (
          <>
            <FileTreeLine depth={0} name={repo.name} kind="dir" meta={`${tree.stats.files} files · ${tree.stats.dirs} dirs`} />
            {tree.entries.map((e, i) => (
              <FileTreeLine key={i} depth={e.depth + 1} name={e.name} kind={e.kind} meta={e.size != null ? formatSize(e.size) : (e.kind === 'dir' ? '' : null)} last={i === tree.entries.length - 1} />
            ))}
          </>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 16px', font: '11px/1 var(--w-mono)', color: 'var(--w-text-2)' }}>
        {repo.exists && tree && (
          <>
            <span><S c="var(--w-text-3)">files</S> <S c="var(--w-text-0)">{tree.stats.files}</S></span>
            <span><S c="var(--w-text-3)">dirs</S> <S c="var(--w-text-0)">{tree.stats.dirs}</S></span>
          </>
        )}
        <span style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
          {repo.remote_url && !repo.exists && <Btn tone="line" style={{ padding: '2px 8px' }} onClick={() => onClone(repo)} disabled={busy}>clone</Btn>}
          <Btn tone="danger" style={{ padding: '2px 8px' }} onClick={() => onRemove(repo)}>[ del ]</Btn>
        </span>
      </div>
    </div>
  );
}

export function ReposPanel({ project }) {
  const [list, setList] = useState([]);
  const [form, setForm] = useState({ name: '', remoteUrl: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef(null);

  const load = async () => {
    try { setList(await api.listRepos(project.id)); }
    catch (e) { setError(e.message); }
  };

  useEffect(() => { setError(''); load(); /* eslint-disable-next-line */ }, [project.id]);

  const openAdd = () => {
    setForm({ name: '', remoteUrl: '' });
    setError('');
    dialogRef.current?.showModal();
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      await api.addRepo(project.id, {
        name: form.name.trim(),
        remoteUrl: form.remoteUrl.trim(),
      });
      dialogRef.current?.close();
      await load();
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const remove = async (repo) => {
    if (!confirm(`remove "${repo.name}" from this project? files on disk are NOT deleted.`)) return;
    await api.deleteRepo(project.id, repo.id);
    await load();
  };

  const clone = async (repo) => {
    if (!confirm(`clone ${repo.remote_url} into ${repo.path}?`)) return;
    setBusy(true);
    try {
      await api.cloneRepo(project.id, repo.id);
      await load();
    } catch (e) { alert(`clone failed: ${e.message}`); }
    setBusy(false);
  };

  return (
    <ScreenFrame
      breadcrumb={<><S c="var(--w-phosphor)">~/{project.name}</S> ─ repos</>}
      title="Repositories"
      subtitle={
        <>Each path is passed to the Claude Agent SDK as an <S c="var(--w-amber)">additionalDirectories</S> entry, so Claude can read and edit across all of them in a single conversation. The project's own workspace (<S c="var(--w-cyan)">{project.path}</S>) is always Claude's <S c="var(--w-phosphor)">cwd</S>.</>
      }
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn tone="primary" onClick={openAdd}>[ + ] add repo</Btn>
        </div>
      }
    >
      {list.length === 0 ? (
        <div style={{
          border: '1px dashed var(--w-line)',
          borderRadius: 3,
          padding: '40px 20px',
          color: 'var(--w-text-3)',
          textAlign: 'center',
          font: '12px/1.5 var(--w-mono)',
        }}>
          no repos configured. click <S c="var(--w-phosphor)">[+] add repo</S> to point Claude at additional directories.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {list.map((repo) => (
            <RepoCard key={repo.id} repo={repo} projectId={project.id} onClone={clone} onRemove={remove} busy={busy} />
          ))}
        </div>
      )}

      <dialog ref={dialogRef}>
        <form onSubmit={submit} style={{ minWidth: 540 }}>
          <h3 style={{ marginTop: 0, color: 'var(--w-phosphor)', font: '600 14px/1 var(--w-mono)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>// add repository</h3>

          <p style={{ font: '11px/1.5 var(--w-mono)', color: 'var(--w-text-3)', margin: '6px 0 14px' }}>
            Paste a remote URL — quantnik clones it under <S c="var(--w-cyan)">backend/data/repos/&lt;project&gt;/&lt;repo&gt;</S> and points the Claude agent at the working copy. No local-path field: the repo's identity is its remote, the working copy is quantnik-managed.
          </p>

          <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>display name</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="my-service" required style={{ width: '100%' }} />

          <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>remote url <S c="var(--w-amber)">(required)</S></label>
          <input value={form.remoteUrl} onChange={(e) => setForm({ ...form, remoteUrl: e.target.value })} placeholder="https://git.harness.io/your-account/.../your-repo.git" required style={{ width: '100%' }} />

          {error && <p style={{ color: 'var(--w-red)', font: '11.5px/1.4 var(--w-mono)' }}>{error}</p>}
          {busy && form.remoteUrl && <p style={{ color: 'var(--w-amber)', font: '11.5px/1.4 var(--w-mono)' }}>cloning {form.remoteUrl}… can take a minute on first run for large repos.</p>}

          <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
            <Btn tone="ghost" onClick={() => dialogRef.current?.close()}>cancel</Btn>
            <Btn tone="primary" type="submit" disabled={busy}>{busy ? 'cloning…' : '[ + ] add'}</Btn>
          </div>
        </form>
      </dialog>
    </ScreenFrame>
  );
}
