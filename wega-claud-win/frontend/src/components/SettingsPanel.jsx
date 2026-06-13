import React, { useEffect, useState } from 'react';
import { api } from '../lib/api.js';
import { ScreenFrame, Pill, Btn, S, formatModel } from './ui.jsx';

// ---- Admin overview helpers ----------------------------------------------
const nf = new Intl.NumberFormat('en-US');
const fmtTokens = (n) => nf.format(Number(n) || 0);
const fmtCost = (n) => `$${(Number(n) || 0).toFixed(2)}`;
const fmtDate = (epoch) => epoch ? new Date(epoch * 1000).toISOString().slice(0, 10) : '—';
const fmtDateTime = (epoch) => epoch ? new Date(epoch * 1000).toLocaleString() : '—';

const ADMIN_COLLAPSED_KEY = 'quantnik.admin.collapsed';

function AdminOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [opsMessage, setOpsMessage] = useState('');
  const [opsBusy, setOpsBusy] = useState('');
  // User-deletion modal: holds the user being deleted (or null for closed).
  const [deletingUser, setDeletingUser] = useState(null);
  const [me, setMe] = useState(null);
  useEffect(() => { api.me().then((r) => setMe(r?.user || null)); }, []);
  // Default = collapsed on first load; persist the user's choice so the
  // section stays in whichever state they left it across reloads. Absence
  // of the localStorage key (first visit, or never toggled) reads as
  // collapsed; explicit '0' keeps it expanded after an explicit expand.
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const v = localStorage.getItem(ADMIN_COLLAPSED_KEY);
      return v !== '0';
    } catch { return true; }
  });
  useEffect(() => {
    try { localStorage.setItem(ADMIN_COLLAPSED_KEY, collapsed ? '1' : '0'); } catch {}
  }, [collapsed]);

  const load = () => {
    setLoading(true); setError('');
    api.adminOverview()
      .then((d) => { setData(d); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  };
  useEffect(() => { load(); }, []);

  const restartService = async (target) => {
    const label = target === 'backend' ? 'backend' : 'frontend';
    if (!confirm(`Restart ${label}?`)) return;
    setOpsBusy(target);
    setOpsMessage('');
    setError('');
    try {
      const result = target === 'backend'
        ? await api.adminRestartBackend()
        : await api.adminRestartFrontend();
      setOpsMessage(result.message || `${label} restart requested`);
    } catch (e) {
      setError(e.message || `${label} restart failed`);
    } finally {
      setOpsBusy('');
    }
  };

  if (loading) {
    return (
      <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '16px 18px', color: 'var(--w-text-3)', font: '12px/1.4 var(--w-mono)' }}>
        loading admin overview…
      </div>
    );
  }
  if (error) {
    return (
      <div style={{ border: '1px solid var(--w-red)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '16px 18px', color: 'var(--w-red)', font: '12px/1.4 var(--w-mono)' }}>
        admin overview failed: {error}
      </div>
    );
  }
  if (!data) return null;

  const { summary, users, projects } = data;

  const th = { textAlign: 'left', color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', padding: '6px 8px', borderBottom: '1px solid var(--w-line)', whiteSpace: 'nowrap' };
  const td = { color: 'var(--w-text-1)', font: '11.5px/1.4 var(--w-mono)', padding: '6px 8px', borderBottom: '1px solid var(--w-line)', whiteSpace: 'nowrap' };
  const tdNum = { ...td, textAlign: 'right' };

  return (
    <div style={{ border: '1px solid var(--w-phosphor)', background: 'var(--w-bg-2)', borderRadius: 3, padding: collapsed ? '10px 18px' : '16px 18px', marginBottom: 16 }}>
      <div
        onClick={() => setCollapsed((c) => !c)}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: collapsed ? 0 : 10, cursor: 'pointer', userSelect: 'none' }}
        title={collapsed ? 'click to expand' : 'click to collapse'}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--w-phosphor)', font: '12px/1 var(--w-mono)', width: 14, display: 'inline-block' }}>
            {collapsed ? '▸' : '▾'}
          </span>
          <div>
            <div style={{ color: 'var(--w-phosphor)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: collapsed ? 0 : 4 }}>// admin overview</div>
            {!collapsed && <div style={{ color: 'var(--w-text-0)', font: '13px/1.4 var(--w-mono)' }}>visible only to administrators</div>}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {collapsed && data && (
            <span style={{ color: 'var(--w-text-2)', font: '11px/1 var(--w-mono)' }}>
              {data.summary.total_users} users · {data.summary.total_projects} projects · {fmtCost(data.summary.total_cost_usd)}
            </span>
          )}
          {!collapsed && (
            <Btn tone="ghost" onClick={(e) => { e.stopPropagation(); load(); }}>[ ↻ ] refresh</Btn>
          )}
        </div>
      </div>

      {collapsed ? null : (<>
      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 14 }}>
        {[
          { label: 'users',          value: summary.total_users },
          { label: 'projects',       value: summary.total_projects },
          { label: 'agent turns',    value: fmtTokens(summary.total_turns) },
          { label: 'total spend',    value: fmtCost(summary.total_cost_usd) },
          { label: 'tracked since',  value: fmtDate(summary.data_tracked_since) },
        ].map((c) => (
          <div key={c.label} style={{
            padding: '10px 12px',
            border: '1px solid var(--w-line)',
            background: 'var(--w-bg-1)',
            borderRadius: 3,
          }}>
            <div style={{ color: 'var(--w-text-3)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>{c.label}</div>
            <div style={{ color: 'var(--w-phosphor)', font: '600 15px/1 var(--w-mono)' }}>{c.value}</div>
          </div>
        ))}
      </div>

      <div style={{ padding: '8px 12px', background: 'var(--w-bg-1)', borderLeft: '2px solid var(--w-amber)', borderRadius: 3, font: '11px/1.5 var(--w-mono)', color: 'var(--w-text-1)', marginBottom: 14 }}>
        Token usage and cost are recorded per-turn from this rollout forward.
        Activity before tracking started doesn't appear in these rollups.
      </div>

      <div style={{ padding: '10px 12px', background: 'var(--w-bg-1)', border: '1px solid var(--w-line)', borderRadius: 3, marginBottom: 14 }}>
        <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
          // service controls
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Btn tone="amber" disabled={!!opsBusy} onClick={() => restartService('backend')}>
            {opsBusy === 'backend' ? 'restarting…' : 'restart backend'}
          </Btn>
          <Btn tone="line" disabled={!!opsBusy} onClick={() => restartService('frontend')}>
            {opsBusy === 'frontend' ? 'restarting…' : 'restart frontend'}
          </Btn>
          {opsMessage && <span style={{ color: 'var(--w-text-2)', font: '11px/1.4 var(--w-mono)' }}>{opsMessage}</span>}
        </div>
      </div>

      {/* Users table */}
      <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
        // users <span style={{ color: 'var(--w-text-3)' }}>· {users.length}</span>
      </div>
      <div style={{ overflowX: 'auto', marginBottom: 14, border: '1px solid var(--w-line)', borderRadius: 3 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={th}>email</th>
              <th style={th}>registered</th>
              <th style={th}>last login</th>
              <th style={{ ...th, textAlign: 'right' }}>projects</th>
              <th style={{ ...th, textAlign: 'right' }}>turns</th>
              <th style={{ ...th, textAlign: 'right' }}>input tok</th>
              <th style={{ ...th, textAlign: 'right' }}>output tok</th>
              <th style={{ ...th, textAlign: 'right' }}>cache rd</th>
              <th style={{ ...th, textAlign: 'right' }}>cost</th>
              <th style={th}>role</th>
              <th style={th}></th>{/* delete column */}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              // Last-admin protection mirrors the backend rule.
              const adminCount = users.filter((x) => x.is_admin).length;
              const isLastAdmin = u.is_admin && adminCount === 1;
              const isSelf = me?.id === u.id;
              const deletable = !isSelf && !isLastAdmin;
              return (
                <tr key={u.id}>
                  <td style={td}>{u.email}</td>
                  <td style={td}>{fmtDate(u.created_at)}</td>
                  <td style={td}>{fmtDate(u.last_login_at)}</td>
                  <td style={tdNum}>{u.project_count}</td>
                  <td style={tdNum}>{fmtTokens(u.turn_count)}</td>
                  <td style={tdNum}>{fmtTokens(u.input_tokens)}</td>
                  <td style={tdNum}>{fmtTokens(u.output_tokens)}</td>
                  <td style={tdNum}>{fmtTokens(u.cache_read_input_tokens)}</td>
                  <td style={{ ...tdNum, color: 'var(--w-phosphor)' }}>{fmtCost(u.total_cost_usd)}</td>
                  <td style={td}>{u.is_admin ? <Pill tone="amber" dot>admin</Pill> : <span style={{ color: 'var(--w-text-3)' }}>—</span>}</td>
                  <td style={{ ...td, textAlign: 'right' }}>
                    {deletable ? (
                      <button
                        type="button"
                        onClick={() => setDeletingUser(u)}
                        title="delete this user"
                        style={{
                          background: 'transparent',
                          border: '1px solid var(--w-line)',
                          color: 'var(--w-red, var(--w-text-3))',
                          font: '10px/1 var(--w-mono)',
                          padding: '3px 7px',
                          borderRadius: 2,
                          cursor: 'pointer',
                          letterSpacing: '0.08em',
                          textTransform: 'uppercase',
                        }}
                      >× delete</button>
                    ) : (
                      <span title={isSelf ? 'you (sign out instead)' : 'last admin'} style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)' }}>
                        {isSelf ? 'you' : 'last admin'}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {deletingUser && (
        <DeleteUserModal
          target={deletingUser}
          users={users}
          onCancel={() => setDeletingUser(null)}
          onDone={() => { setDeletingUser(null); load(); }}
        />
      )}

      {/* Projects table */}
      <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
        // projects <span style={{ color: 'var(--w-text-3)' }}>· {projects.length}</span>
      </div>
      <div style={{ overflowX: 'auto', border: '1px solid var(--w-line)', borderRadius: 3 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={th}>name</th>
              <th style={th}>owner</th>
              <th style={th}>created</th>
              <th style={th}>model</th>
              <th style={th}>visibility</th>
              <th style={{ ...th, textAlign: 'right' }}>turns</th>
              <th style={{ ...th, textAlign: 'right' }}>input tok</th>
              <th style={{ ...th, textAlign: 'right' }}>output tok</th>
              <th style={{ ...th, textAlign: 'right' }}>cache rd</th>
              <th style={{ ...th, textAlign: 'right' }}>cost</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id}>
                <td style={td}>{p.name}</td>
                <td style={td}>{p.owner_email || <span style={{ color: 'var(--w-text-3)' }}>—</span>}</td>
                <td style={td}>{fmtDate(p.created_at)}</td>
                <td style={td}>{formatModel(p.model) || <span style={{ color: 'var(--w-text-3)' }}>—</span>}</td>
                <td style={td}>{p.is_public ? <Pill tone="phosphor" dot>shared</Pill> : <span style={{ color: 'var(--w-text-3)' }}>private</span>}</td>
                <td style={tdNum}>{fmtTokens(p.turn_count)}</td>
                <td style={tdNum}>{fmtTokens(p.input_tokens)}</td>
                <td style={tdNum}>{fmtTokens(p.output_tokens)}</td>
                <td style={tdNum}>{fmtTokens(p.cache_read_input_tokens)}</td>
                <td style={{ ...tdNum, color: 'var(--w-phosphor)' }}>{fmtCost(p.total_cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <AuditLogViewer />
      </>)}
    </div>
  );
}

function AuditLogViewer() {
  const [levels, setLevels] = useState(['info', 'warning', 'error']);
  const [search, setSearch] = useState('');
  const [limit, setLimit] = useState(500);
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(null);

  const load = () => {
    setBusy(true);
    setError('');
    api.adminAuditLogs({ levels, search, limit })
      .then((r) => { setData(r); setBusy(false); })
      .catch((e) => { setError(e.message || 'audit log load failed'); setBusy(false); });
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const toggleLevel = (level) => {
    setLevels((prev) => {
      const next = prev.includes(level) ? prev.filter((x) => x !== level) : [...prev, level];
      return next.length ? next : [level];
    });
  };

  const tone = (level) => level === 'error' ? 'red' : level === 'warning' ? 'amber' : 'phosphor';
  const rows = data?.rows || [];
  const summary = data?.summary || {};

  return (
    <div style={{ marginTop: 16, border: '1px solid var(--w-line)', background: 'var(--w-bg-1)', borderRadius: 3, padding: '12px 14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 10 }}>
        <div>
          <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>
            // audit logs
          </div>
          <div style={{ color: 'var(--w-text-0)', font: '13px/1.4 var(--w-mono)' }}>
            persisted backend information, warnings, and errors
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <Pill tone="phosphor">{summary.info || 0} info</Pill>
          <Pill tone="amber">{summary.warning || 0} warnings</Pill>
          <Pill tone="red">{summary.error || 0} errors</Pill>
          <Btn tone="ghost" disabled={busy} onClick={load}>{busy ? 'loading…' : '[ ↻ ] refresh'}</Btn>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
        {['info', 'warning', 'error'].map((level) => (
          <button
            key={level}
            type="button"
            onClick={() => toggleLevel(level)}
            style={{
              border: `1px solid var(--w-${levels.includes(level) ? tone(level) : 'line'})`,
              background: levels.includes(level) ? 'var(--w-phosphor-veil)' : 'transparent',
              color: levels.includes(level) ? `var(--w-${tone(level)})` : 'var(--w-text-3)',
              borderRadius: 999,
              padding: '6px 10px',
              font: '600 11px/1 var(--w-mono)',
              cursor: 'pointer',
              textTransform: 'uppercase',
            }}
          >
            {level}
          </button>
        ))}
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') load(); }}
          placeholder="search message, source, metadata"
          style={{ flex: '1 1 260px', minWidth: 220 }}
        />
        <select value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          {[100, 500, 1000, 5000].map((n) => <option key={n} value={n}>{n} rows</option>)}
        </select>
        <Btn tone="line" disabled={busy} onClick={load}>apply</Btn>
      </div>

      {error && <div style={{ color: 'var(--w-red)', font: '11.5px/1.4 var(--w-mono)', marginBottom: 8 }}>{error}</div>}

      <div style={{ maxHeight: 460, overflow: 'auto', border: '1px solid var(--w-line)', borderRadius: 3 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {['time', 'level', 'source', 'message', 'request'].map((h) => (
                <th key={h} style={{ textAlign: 'left', position: 'sticky', top: 0, background: 'var(--w-bg-2)', color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase', padding: '8px', borderBottom: '1px solid var(--w-line)', zIndex: 1 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} style={{ color: 'var(--w-text-3)', font: '11.5px/1.4 var(--w-mono)', padding: 12 }}>no audit logs match the current filters.</td>
              </tr>
            )}
            {rows.map((r) => (
              <React.Fragment key={r.id}>
                <tr onClick={() => setExpanded(expanded === r.id ? null : r.id)} style={{ cursor: 'pointer' }}>
                  <td style={logTd}>{fmtDateTime(r.created_at)}</td>
                  <td style={logTd}><Pill tone={tone(r.level)}>{r.level}</Pill></td>
                  <td style={logTd}>{r.source}</td>
                  <td style={{ ...logTd, whiteSpace: 'normal', minWidth: 360 }}>{r.message}</td>
                  <td style={logTd}>{r.request_id || '—'}</td>
                </tr>
                {expanded === r.id && (
                  <tr>
                    <td colSpan={5} style={{ padding: 0, borderBottom: '1px solid var(--w-line)' }}>
                      <pre style={{ margin: 0, padding: '10px 12px', background: 'var(--w-bg-2)', color: 'var(--w-text-1)', font: '11px/1.5 var(--w-mono)', whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(r.meta || {}, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, color: 'var(--w-text-3)', font: '10.5px/1.4 var(--w-mono)' }}>
        Captures console info/warn/error, HTTP status logs, route errors, process exceptions, rejections, and explicit admin actions from backend startup onward.
      </div>
    </div>
  );
}

const logTd = {
  color: 'var(--w-text-1)',
  font: '11px/1.35 var(--w-mono)',
  padding: '7px 8px',
  borderBottom: '1px solid var(--w-line)',
  whiteSpace: 'nowrap',
  verticalAlign: 'top',
};

// Modal that drives the admin user-deletion flow. If the target has zero
// projects, asks for a single confirm. If they own ≥1 project, the admin
// must pick a disposition (transfer to another user OR delete the projects).
function DeleteUserModal({ target, users, onCancel, onDone }) {
  const hasProjects = target.project_count > 0;
  // Default to 'transfer' when there are projects (less destructive). 'none'
  // when there are no projects — server doesn't need disposition then.
  const [disposition, setDisposition] = useState(hasProjects ? 'transfer' : 'none');
  // For transfer: default to the first non-target user. If only the target
  // exists (impossible in practice — last-admin protection blocks first),
  // the dropdown is empty and transfer is disabled.
  const transferCandidates = users.filter((u) => u.id !== target.id);
  const [transferTo, setTransferTo] = useState(transferCandidates[0]?.id ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const confirm = async () => {
    setBusy(true); setError('');
    try {
      const body = hasProjects
        ? (disposition === 'transfer'
            ? { disposition: 'transfer', transferToUserId: Number(transferTo) }
            : { disposition: 'delete' })
        : {};
      await api.adminDeleteUser(target.id, body);
      onDone();
    } catch (e) {
      setError(e.message || 'delete failed');
      setBusy(false);
    }
  };

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 16,
      }}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 480, maxWidth: '100%',
          background: 'var(--w-bg-1)',
          border: '1px solid var(--w-line)',
          borderLeft: '3px solid var(--w-red, #d04a4a)',
          borderRadius: 4,
          padding: '20px 22px 18px',
          font: '12px/1.4 var(--w-mono)',
          color: 'var(--w-text-1)',
        }}>
        <div style={{ font: '600 13px/1 var(--w-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--w-red, #d04a4a)', marginBottom: 10 }}>
          delete user
        </div>
        <div style={{ marginBottom: 12 }}>
          <span style={{ color: 'var(--w-text-3)' }}>account:</span>{' '}
          <span style={{ color: 'var(--w-text-0)' }}>{target.email}</span>
        </div>

        {!hasProjects && (
          <div style={{ marginBottom: 14, color: 'var(--w-text-2)' }}>
            This user owns no projects. The account row, their sessions, and
            their usage_event history (user_id only) will be removed.
            Historical project costs they accrued stay attributed to the
            project, just not back to the user.
          </div>
        )}

        {hasProjects && (
          <>
            <div style={{ marginBottom: 10, color: 'var(--w-text-2)' }}>
              This user owns <span style={{ color: 'var(--w-amber)' }}>{target.project_count}</span> project(s).
              Choose what to do with them:
            </div>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10, cursor: 'pointer' }}>
              <input
                type="radio"
                name="disposition"
                value="transfer"
                checked={disposition === 'transfer'}
                onChange={() => setDisposition('transfer')}
                style={{ marginTop: 2 }}
              />
              <div>
                <div style={{ color: 'var(--w-text-0)' }}>transfer to another user</div>
                <div style={{ color: 'var(--w-text-3)', fontSize: 11 }}>
                  Projects stay intact. owner_user_id changes. Sessions and
                  history are preserved.
                </div>
                {disposition === 'transfer' && (
                  <select
                    value={transferTo ?? ''}
                    onChange={(e) => setTransferTo(e.target.value)}
                    style={{
                      marginTop: 6,
                      width: '100%',
                      background: 'var(--w-bg-0)',
                      border: '1px solid var(--w-line)',
                      color: 'var(--w-text-0)',
                      font: '12px/1.3 var(--w-mono)',
                      padding: '6px 8px',
                      borderRadius: 2,
                    }}>
                    {transferCandidates.length === 0 && (
                      <option value="">(no other user available)</option>
                    )}
                    {transferCandidates.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.email}{u.is_admin ? ' · admin' : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </label>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 12, cursor: 'pointer' }}>
              <input
                type="radio"
                name="disposition"
                value="delete"
                checked={disposition === 'delete'}
                onChange={() => setDisposition('delete')}
                style={{ marginTop: 2 }}
              />
              <div>
                <div style={{ color: 'var(--w-text-0)' }}>delete the projects too</div>
                <div style={{ color: 'var(--w-text-3)', fontSize: 11 }}>
                  Project rows + their chat history, phases, repos, MCP
                  configs, and per-project context sources cascade-delete.
                  On-disk workspace folders are NOT removed — operator can
                  clean those separately.
                </div>
              </div>
            </label>
          </>
        )}

        {error && (
          <div style={{ color: 'var(--w-red, #d04a4a)', marginBottom: 10 }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 6 }}>
          <Btn tone="ghost" onClick={onCancel} disabled={busy}>cancel</Btn>
          <button
            type="button"
            onClick={confirm}
            disabled={busy || (hasProjects && disposition === 'transfer' && !transferTo)}
            style={{
              background: 'var(--w-red, #d04a4a)',
              color: 'var(--w-bg-0)',
              border: 0,
              padding: '7px 16px',
              font: '600 11px/1 var(--w-mono)',
              letterSpacing: '0.1em', textTransform: 'uppercase',
              borderRadius: 3,
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.6 : 1,
            }}>
            {busy ? '…' : 'delete user'}
          </button>
        </div>
      </div>
    </div>
  );
}

const MODELS = [
  { id: 'claude-opus-4-7',          tag: 'deep · slow · $$$' },
  { id: 'claude-sonnet-4-6',        tag: 'balanced · default' },
  { id: 'claude-haiku-4-5-20251001', tag: 'fast · cheap · $' },
];

// LLM providers — must match the backend PROVIDERS catalog in routes/llm.js.
// `wired: true` means the quantnik agent runtime can actually use this provider
// today (Claude Agent SDK supports Anthropic + Bedrock + Vertex + Foundry).
// `wired: false` providers store config but the runtime can't execute against
// them yet — switching to one of these will surface a clear error on the next
// chat turn instead of silently routing to Claude.
const LLM_PROVIDERS = [
  {
    id: 'anthropic',
    label: 'Anthropic (default)',
    wired: true,
    note: 'Direct Anthropic API. By default uses the service-wide CLAUDE_CODE_OAUTH_TOKEN / ANTHROPIC_API_KEY from the backend .env. Set your own key below to override per project.',
    fields: [
      { name: 'anthropicApiKey', label: 'Anthropic API key (optional, overrides .env)', placeholder: 'sk-ant-api03-…', secret: true },
    ],
    defaultModel: 'claude-opus-4-7',
    models: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
    tone: 'phosphor',
  },
  {
    id: 'bedrock',
    label: 'AWS Bedrock (Claude)',
    wired: true,
    note: 'Claude on AWS Bedrock. Region + access key + secret. Session token optional (STS).',
    fields: [
      { name: 'awsRegion',          label: 'AWS region',          placeholder: 'us-east-1' },
      { name: 'awsAccessKeyId',     label: 'AWS access key ID',   placeholder: 'AKIA...' },
      { name: 'awsSecretAccessKey', label: 'AWS secret key',      placeholder: '...', secret: true },
      { name: 'awsSessionToken',    label: 'AWS session token (optional)', placeholder: '', secret: true },
    ],
    defaultModel: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
    models: [
      'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
      'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
      'us.anthropic.claude-3-5-haiku-20241022-v1:0',
      'us.anthropic.claude-3-opus-20240229-v1:0',
    ],
    tone: 'amber',
  },
  {
    id: 'vertex',
    label: 'GCP Vertex AI (Claude)',
    wired: true,
    note: 'Claude on Google Vertex. Needs GCP project + region. Auth uses Application Default Credentials (gcloud login) or a service-account JSON path.',
    fields: [
      { name: 'gcpProjectId',                 label: 'GCP project ID',                  placeholder: 'my-project-123' },
      { name: 'gcpRegion',                    label: 'Region',                          placeholder: 'us-east5' },
      { name: 'googleApplicationCredentials', label: 'Service-account JSON path (opt.)', placeholder: '/path/to/key.json' },
    ],
    defaultModel: 'claude-3-7-sonnet@20250219',
    models: ['claude-3-7-sonnet@20250219', 'claude-3-5-sonnet-v2@20241022', 'claude-3-5-haiku@20241022', 'claude-3-opus@20240229'],
    tone: 'cyan',
  },
  {
    id: 'foundry',
    label: 'Azure AI Foundry (Claude)',
    wired: true,
    note: 'Claude via Azure AI Foundry. Endpoint URL + API key.',
    fields: [
      { name: 'azureEndpoint', label: 'Foundry endpoint URL', placeholder: 'https://<resource>.openai.azure.com' },
      { name: 'azureApiKey',   label: 'API key',              placeholder: '', secret: true },
    ],
    defaultModel: 'claude-opus-4-7',
    models: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5'],
    tone: 'violet',
  },
  {
    id: 'openai',
    label: 'OpenAI',
    wired: false,
    note: 'Stored only — quantnik uses the Claude Agent SDK which is Claude-only. Config persists so it can be wired into a separate OpenAI agent runtime later.',
    fields: [
      { name: 'openaiApiKey',  label: 'OpenAI API key',                    placeholder: 'sk-...', secret: true },
      { name: 'openaiBaseUrl', label: 'Base URL (optional, for proxies)',  placeholder: 'https://api.openai.com/v1' },
      { name: 'openaiOrgId',   label: 'Organization ID (optional)',        placeholder: 'org-...' },
    ],
    defaultModel: 'gpt-4o',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'o1', 'o1-mini', 'o3-mini'],
    tone: 'magenta',
  },
  {
    id: 'gemini',
    label: 'Google Gemini',
    wired: false,
    note: 'Stored only — same caveat as OpenAI. quantnik agent runtime is Claude-specific.',
    fields: [
      { name: 'geminiApiKey', label: 'Gemini API key',          placeholder: 'AIza...', secret: true },
      { name: 'geminiBaseUrl', label: 'Base URL (optional)',    placeholder: 'https://generativelanguage.googleapis.com/v1beta' },
    ],
    defaultModel: 'gemini-2.0-flash-exp',
    models: ['gemini-2.0-flash-exp', 'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.5-flash-8b'],
    tone: 'red',
  },
];

const PERMISSION_MODES = [
  { id: 'default',           desc: 'ask on writes, allow reads.',                            tone: 'cyan' },
  { id: 'acceptEdits',       desc: 'auto-accept file edits, prompt for shell.',              tone: 'cyan' },
  { id: 'plan',              desc: 'plan only — no execution, no edits.',                    tone: 'violet' },
  { id: 'bypassPermissions', desc: 'skip prompts entirely. only for trusted projects.',      tone: 'amber' },
];

function highlightJson(src) {
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  let html = escape(src);
  html = html.replace(/(&quot;[^&]*?&quot;)(\s*:)/g, '<span style="color:var(--w-syn-key)">$1</span>$2');
  html = html.replace(/:\s*(&quot;[^&]*?&quot;)/g, (m, g1) => m.replace(g1, `<span style="color:var(--w-syn-str)">${g1}</span>`));
  html = html.replace(/:\s*(-?\d+\.?\d*)([,\s\n}])/g, ': <span style="color:var(--w-syn-num)">$1</span>$2');
  html = html.replace(/:\s*(true|false|null)([,\s\n}])/g, ': <span style="color:var(--w-syn-num)">$1</span>$2');
  return html;
}

export function SettingsPanel({ project, onChanged }) {
  const hasProject = !!project?.id;
  const [permMode, setPermMode] = useState(project?.permission_mode || 'acceptEdits');
  const [settingsJson, setSettingsJson] = useState('');
  const [hooksJson, setHooksJson] = useState('');
  const [error, setError] = useState('');
  const [savedFlash, setSavedFlash] = useState('');
  const [llmProvider, setLlmProvider] = useState('anthropic');
  const [llmModel, setLlmModel] = useState('');
  const [llmConfig, setLlmConfig] = useState({});
  const [isAdmin, setIsAdmin] = useState(false);

  // Probe the current user once per panel mount to decide whether to render
  // the admin overview. Silent on failure — non-admins simply don't see it.
  useEffect(() => {
    api.me().then((m) => setIsAdmin(!!m?.user?.isAdmin)).catch(() => setIsAdmin(false));
  }, []);

  const loadAll = () => {
    if (!hasProject) {
      setSettingsJson('');
      setHooksJson('{}');
      return;
    }
    api.getSettings(project.id).then((s) => {
      setSettingsJson(JSON.stringify(s, null, 2));
      setHooksJson(JSON.stringify(s.hooks || {}, null, 2));
    });
    api.getLlmConfig(project.id).then((l) => {
      setLlmProvider(l.provider || 'anthropic');
      setLlmModel(l.model || '');
      setLlmConfig(l.config || {});
    }).catch(() => {});
  };

  useEffect(() => {
    setPermMode(project?.permission_mode || 'acceptEdits');
    setError('');
    loadAll();
  }, [project?.id]);

  const saveAll = async () => {
    if (!hasProject) return;
    setError(''); setSavedFlash('');
    try {
      await api.updateProject(project.id, { permission_mode: permMode });
      const hooks = JSON.parse(hooksJson || '{}');
      await api.saveHooks(project.id, hooks);
      await api.saveLlmConfig(project.id, {
        provider: llmProvider,
        model: llmModel,
        config: llmConfig,
      });
      onChanged?.();
      setSavedFlash('saved');
      setTimeout(() => setSavedFlash(''), 2200);
    } catch (e) {
      setError(e.message);
    }
  };

  const reset = () => {
    setPermMode(project?.permission_mode || 'acceptEdits');
    loadAll();
    setError('');
  };

  if (!hasProject) {
    return (
      <ScreenFrame
        breadcrumb={<><S c="var(--w-phosphor)">~/workbench</S> ─ settings</>}
        title="Admin settings"
        subtitle="Global service controls and audit logs are available without a project. Project-specific settings appear after you create or select a project."
      >
        {isAdmin && <AdminOverview />}
        {!isAdmin && (
          <div style={{ border: '1px dashed var(--w-line)', background: 'var(--w-bg-1)', borderRadius: 3, padding: '16px 20px', color: 'var(--w-text-2)', font: '12px/1.5 var(--w-mono)' }}>
            Sign in as an admin to view global service controls. Create or select a project to edit model, permission, and hook settings.
          </div>
        )}
      </ScreenFrame>
    );
  }

  const currentProvider = LLM_PROVIDERS.find((p) => p.id === llmProvider) || LLM_PROVIDERS[0];

  let hooksValid = true;
  try { JSON.parse(hooksJson || '{}'); } catch { hooksValid = false; }
  const hooksLines = hooksJson.split('\n').length;

  return (
    <ScreenFrame
      breadcrumb={<><S c="var(--w-phosphor)">~/{project.name}</S> ─ settings</>}
      title="Project settings"
      subtitle="Stored in .claude/settings.json. Hooks run on lifecycle events — pre/post tool, prompt submit, session start, etc."
      action={
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn tone="ghost" onClick={reset}>[ ↺ ] reset</Btn>
          <Btn tone="primary" onClick={saveAll}>[ ⤓ ] save</Btn>
          {savedFlash && <Pill tone="phosphor" dot>{savedFlash}</Pill>}
        </div>
      }
    >
      {isAdmin && <AdminOverview />}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, height: isAdmin ? 'auto' : '100%' }}>
        {/* Left: config */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>
          {/* Permission mode */}
          <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '16px 18px' }}>
            <div style={{ marginBottom: 10 }}>
              <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>// permission mode</div>
              <div style={{ color: 'var(--w-text-0)', font: '13px/1.4 var(--w-mono)' }}>how much should claude ask before acting?</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {PERMISSION_MODES.map((p) => {
                const active = p.id === permMode;
                return (
                  <div
                    key={p.id}
                    onClick={() => setPermMode(p.id)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '8px 12px',
                      border: active ? `1px solid var(--w-${p.tone})` : '1px solid var(--w-line)',
                      background: active ? `var(--w-phosphor-veil)` : 'transparent',
                      borderRadius: 3,
                      cursor: 'pointer',
                    }}
                  >
                    <span style={{ color: active ? `var(--w-${p.tone})` : 'var(--w-text-3)', font: '12px/1 var(--w-mono)' }}>
                      {active ? '[◉]' : '[ ]'}
                    </span>
                    <span style={{ color: active ? `var(--w-${p.tone})` : 'var(--w-text-1)', font: '12px/1 var(--w-mono)', width: 160 }}>{p.id}</span>
                    <span style={{ color: 'var(--w-text-2)', font: '11.5px/1.4 var(--w-mono)', flex: 1 }}>{p.desc}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* LLM provider */}
          <div style={{ border: '1px solid var(--w-line)', background: 'var(--w-bg-2)', borderRadius: 3, padding: '16px 18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div>
                <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>// llm provider</div>
                <div style={{ color: 'var(--w-text-0)', font: '13px/1.4 var(--w-mono)' }}>which inference backend should run agent turns?</div>
              </div>
              <Pill tone={currentProvider.wired ? 'phosphor' : 'red'} dot>
                {currentProvider.wired ? 'wired' : 'config only'}
              </Pill>
            </div>

            {/* Provider tile picker */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, marginTop: 10 }}>
              {LLM_PROVIDERS.map((p) => {
                const active = p.id === llmProvider;
                return (
                  <div
                    key={p.id}
                    onClick={() => {
                      setLlmProvider(p.id);
                      if (!p.models.includes(llmModel)) setLlmModel(p.defaultModel);
                    }}
                    style={{
                      padding: '10px 12px',
                      border: active ? `1px solid var(--w-${p.tone})` : '1px solid var(--w-line)',
                      background: active ? 'var(--w-phosphor-veil)' : 'var(--w-bg-3)',
                      borderRadius: 3,
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                      <div style={{ color: active ? `var(--w-${p.tone})` : 'var(--w-text-0)', font: '600 12px/1.3 var(--w-mono)' }}>
                        {active ? '[●] ' : '[ ] '}{p.label}
                      </div>
                      {!p.wired && <span style={{ color: 'var(--w-red)', font: '9.5px/1 var(--w-mono)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>n/w</span>}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--w-bg-1)', borderLeft: `2px solid var(--w-${currentProvider.tone})`, borderRadius: 3, font: '11px/1.5 var(--w-mono)', color: 'var(--w-text-1)' }}>
              {currentProvider.note}
            </div>

            {/* Model picker for the chosen provider */}
            <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.1em', textTransform: 'uppercase', margin: '14px 0 6px' }}>
              model
            </label>
            <div style={{ display: 'flex', gap: 6 }}>
              <select
                value={currentProvider.models.includes(llmModel) ? llmModel : '__custom'}
                onChange={(e) => {
                  if (e.target.value === '__custom') return;
                  setLlmModel(e.target.value);
                }}
                style={{ flex: '0 0 auto', minWidth: 240 }}
              >
                {currentProvider.models.map((m) => <option key={m} value={m}>{m}</option>)}
                {!currentProvider.models.includes(llmModel) && <option value="__custom">— custom (below) —</option>}
              </select>
              <input
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder={`or type any model id (default: ${currentProvider.defaultModel})`}
                style={{ flex: 1 }}
              />
            </div>

            {/* Per-provider field grid */}
            {currentProvider.fields.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
                  // credentials &amp; config
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  {currentProvider.fields.map((f) => (
                    <div key={f.name}>
                      <label style={{ display: 'block', font: '10.5px/1 var(--w-mono)', color: 'var(--w-text-2)', letterSpacing: '0.06em', marginBottom: 4 }}>
                        {f.label}
                      </label>
                      <input
                        type={f.secret ? 'password' : 'text'}
                        value={llmConfig[f.name] || ''}
                        onChange={(e) => setLlmConfig({ ...llmConfig, [f.name]: e.target.value })}
                        placeholder={f.placeholder}
                        autoComplete="off"
                        style={{ width: '100%' }}
                      />
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 8, color: 'var(--w-text-3)', font: '10.5px/1.5 var(--w-mono)' }}>
                  Secrets are masked on read (shown as <code>••••••••</code> + last 4 chars). Leave masked values alone to keep them; type a new value to replace.
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: hooks editor */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ color: 'var(--w-text-3)', font: '10px/1 var(--w-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>// hooks · .claude/settings.json → hooks</div>
              <div style={{ color: 'var(--w-text-0)', font: '13px/1.4 var(--w-mono)' }}>shell out on lifecycle events</div>
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <Pill tone="phosphor">PreToolUse</Pill>
              <Pill>PostToolUse</Pill>
              <Pill>UserPromptSubmit</Pill>
              <Pill>SessionStart</Pill>
            </div>
          </div>
          <div style={{
            flex: 1, minHeight: 320,
            border: '1px solid var(--w-line-strong)',
            background: 'var(--w-bg-1)',
            borderRadius: 3,
            overflow: 'hidden',
            display: 'flex', flexDirection: 'column',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '6px 12px', borderBottom: '1px solid var(--w-line)', background: 'var(--w-bg-3)', color: 'var(--w-text-3)', font: '10.5px/1 var(--w-mono)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              <span>hooks.json</span>
              <span style={{ flex: 1 }} />
              <Pill tone={hooksValid ? 'phosphor' : 'red'} dot>{hooksValid ? 'valid' : 'invalid'}</Pill>
              <span>json</span>
              <span>·</span>
              <span>{hooksLines} lines</span>
            </div>
            <textarea
              value={hooksJson}
              onChange={(e) => setHooksJson(e.target.value)}
              style={{
                flex: 1,
                margin: 0,
                padding: '12px 14px',
                color: 'var(--w-text-0)',
                font: '11.5px/1.55 var(--w-mono)',
                background: 'var(--w-bg-1)',
                border: 'none',
                outline: 'none',
                resize: 'none',
                whiteSpace: 'pre',
              }}
              spellCheck={false}
            />
          </div>
          {error && <div style={{ color: 'var(--w-red)', font: '11.5px/1.4 var(--w-mono)' }}>{error}</div>}
        </div>
      </div>
    </ScreenFrame>
  );
}
